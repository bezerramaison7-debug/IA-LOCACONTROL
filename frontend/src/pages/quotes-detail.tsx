import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import {
  Ban,
  CircleCheck,
  CircleX,
  Clock3,
  Copy,
  Download,
  FileText,
  PencilLine,
  Send,
} from 'lucide-react'
import { useAuth } from '../auth/context'
import { periods } from '../lib/masters'
import {
  brDate,
  brDateTime,
  brMoney,
  brQuantity,
  downloadQuotePdf,
  duplicateQuote,
  failureMessage,
  getQuote,
  isConflict,
  quoteActions,
  quoteStatuses,
  transitionQuote,
  type Quote,
  type QuoteAction,
  type QuoteStatus,
} from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, ErrorState, Field, PageHeader, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable } from './masters-shared'

const badges = {
  RASCUNHO: ['muted', PencilLine],
  ENVIADO: ['info', Send],
  APROVADO: ['success', CircleCheck],
  REJEITADO: ['danger', CircleX],
  EXPIRADO: ['warning', Clock3],
  CANCELADO: ['muted', Ban],
  CONVERTIDO: ['success', FileText],
} as const

/** Status is always icon + text + colour, never colour alone. */
export function QuoteBadge({ status }: { status: QuoteStatus }) {
  const [tone, Icon] = badges[status]
  return (
    <span className={`badge badge-${tone}`}>
      <Icon size={14} aria-hidden="true" />
      {quoteStatuses[status]}
    </span>
  )
}

const dialogs: Record<QuoteAction, { title: string; text: string; confirm: string }> = {
  send: {
    title: 'Enviar orçamento',
    text: 'O orçamento deixa de ser editável e passa a aguardar a resposta do cliente. Se precisar alterar, reabra-o depois.',
    confirm: 'Confirmar envio',
  },
  approve: {
    title: 'Aprovar orçamento',
    text: 'A aprovação registra o aceite da proposta. Orçamento aprovado não reserva estoque.',
    confirm: 'Confirmar aprovação',
  },
  reject: {
    title: 'Rejeitar orçamento',
    text: 'Registre o motivo da recusa. O orçamento rejeitado não pode ser reaberto, apenas duplicado.',
    confirm: 'Confirmar rejeição',
  },
  cancel: {
    title: 'Cancelar orçamento',
    text: 'O cancelamento é definitivo e fica no histórico. Depois dele o orçamento só pode ser duplicado.',
    confirm: 'Confirmar cancelamento',
  },
  reopen: {
    title: 'Reabrir orçamento',
    text: 'O orçamento volta a ser rascunho e pode ser editado, inclusive a validade.',
    confirm: 'Confirmar reabertura',
  },
}
const allowed: Record<QuoteStatus, QuoteAction[]> = {
  RASCUNHO: ['send', 'approve', 'cancel'],
  ENVIADO: ['approve', 'reject', 'reopen', 'cancel'],
  EXPIRADO: ['reopen', 'cancel'],
  APROVADO: ['cancel'],
  REJEITADO: [],
  CANCELADO: [],
  CONVERTIDO: [],
}

function TransitionForm({
  quote,
  action,
  done,
  close,
  reload,
}: {
  quote: Quote
  action: QuoteAction
  done: () => void
  close: () => void
  reload: () => void
}) {
  const { request } = useAuth()
  const [failure, setFailure] = useState<{ message: string; conflict: boolean } | null>(null)
  const needsReason = action === 'reject' || action === 'cancel'
  const form = useForm<{ reason: string }>({ defaultValues: { reason: '' } })
  return (
    <form
      className="form-stack"
      noValidate
      onSubmit={form.handleSubmit(async ({ reason }) => {
        setFailure(null)
        try {
          await transitionQuote(request, quote, action, reason)
          done()
        } catch (e) {
          setFailure({
            message: failureMessage(e, 'Não foi possível concluir a ação.'),
            conflict: isConflict(e),
          })
        }
      })}
    >
      <p>{dialogs[action].text}</p>
      <Field
        label={needsReason ? 'Motivo' : 'Observação (opcional)'}
        maxLength={500}
        autoComplete="off"
        hint={needsReason ? 'Obrigatório · pelo menos 5 caracteres.' : undefined}
        {...form.register('reason', {
          validate: (value) =>
            !needsReason ||
            value.trim().length >= 5 ||
            'Informe o motivo com pelo menos 5 caracteres.',
        })}
        error={form.formState.errors.reason?.message}
      />
      {failure && (
        <div className="quote-notice quote-notice-danger" role="alert">
          <p>{failure.message}</p>
          {failure.conflict && (
            <Button variant="secondary" onClick={reload}>
              Recarregar orçamento
            </Button>
          )}
        </div>
      )}
      <div className="modal-actions">
        <Button variant="secondary" onClick={close}>
          Voltar
        </Button>
        <Button
          type="submit"
          variant={action === 'cancel' || action === 'reject' ? 'danger' : 'primary'}
          disabled={form.formState.isSubmitting}
        >
          {form.formState.isSubmitting ? 'Enviando…' : dialogs[action].confirm}
        </Button>
      </div>
    </form>
  )
}

export function QuoteDetail({
  id,
  warnings,
  onBack,
  onEdit,
  onDuplicated,
}: {
  id: number
  warnings: string[] | null
  onBack: () => void
  onEdit: () => void
  onDuplicated: (quote: Quote, warnings: string[]) => void
}) {
  const { request, user } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [action, setAction] = useState<QuoteAction | null>(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const can = (code: string) => !!user?.permissions.includes('quotes.' + code)
  const query = useQuery({
    queryKey: ['quotes', 'detail', id],
    queryFn: () => getQuote(request, id),
    retry: false,
  })
  const back = (
    <Button variant="secondary" onClick={onBack}>
      Voltar para a lista
    </Button>
  )
  if (query.isPending)
    return (
      <>
        <PageHeader title="Orçamento" description="Carregando os dados salvos." actions={back} />
        <Skeleton rows={4} />
      </>
    )
  if (query.isError)
    return (
      <>
        <PageHeader title="Orçamento" description="Não foi possível abrir." actions={back} />
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      </>
    )
  const quote = query.data
  const customer = quote.customer
  const difference = quote.negotiated_difference
  const actions = allowed[quote.status].filter((item) =>
    item === 'approve' ? can('approve') : can('write'),
  )
  async function run(name: string, task: () => Promise<void>) {
    setBusy(name)
    setError('')
    try {
      await task()
    } catch (e) {
      setError(failureMessage(e, 'Não foi possível concluir a ação.'))
    } finally {
      setBusy('')
    }
  }
  const reload = () => {
    setAction(null)
    void cache.invalidateQueries({ queryKey: ['quotes'] })
  }
  return (
    <>
      <PageHeader
        title={'Orçamento ' + quote.number}
        description={customer.legal_name + ' · ' + customer.document}
        actions={back}
      />
      {warnings && (
        <div className="quote-notice" role="status">
          <p>
            <strong>Orçamento duplicado com os preços da tabela atual.</strong>
          </p>
          {warnings.length > 0 && (
            <ul>
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <Card
        title="Resumo"
        description="Dados oficiais calculados pelo servidor."
        action={<QuoteBadge status={quote.status} />}
      >
        <div className="padded form-stack">
          <dl className="master-details">
            <div>
              <dt>Início previsto</dt>
              <dd>{brDate(quote.start_date)}</dd>
            </div>
            <div>
              <dt>Validade</dt>
              <dd>{brDate(quote.valid_until)}</dd>
            </div>
            <div>
              <dt>Criado em</dt>
              <dd>{brDateTime(quote.created_at)}</dd>
            </div>
            <div>
              <dt>Atualizado em</dt>
              <dd>{brDateTime(quote.updated_at)}</dd>
            </div>
            {quote.status_reason && (
              <div>
                <dt>Motivo da última alteração</dt>
                <dd>{quote.status_reason}</dd>
              </div>
            )}
            <div>
              <dt>Observações</dt>
              <dd>{quote.notes || 'Não informado'}</dd>
            </div>
          </dl>
          {quote.status === 'EXPIRADO' && (
            <p className="quote-notice">
              Validade vencida. Reabra o orçamento para ajustar a validade, cancele ou duplique.
            </p>
          )}
          {quote.status === 'APROVADO' && (
            <p className="quote-notice">
              A conversão em contrato chega com o módulo de contratos. Até lá, o orçamento aprovado
              fica registrado e não reserva estoque.
            </p>
          )}
          <Failure message={error} />
          <div className="row-actions" role="group" aria-label="Ações do orçamento">
            {quote.status === 'RASCUNHO' && can('write') && (
              <Button onClick={onEdit}>
                <PencilLine size={16} aria-hidden="true" />
                Editar
              </Button>
            )}
            {actions.map((item) => (
              <Button
                key={item}
                variant={item === 'cancel' ? 'danger' : 'secondary'}
                disabled={!!busy}
                onClick={() => {
                  setError('')
                  setAction(item)
                }}
              >
                {quoteActions[item].label}
              </Button>
            ))}
            {can('write') && (
              <Button
                variant="secondary"
                disabled={!!busy}
                onClick={() =>
                  void run('duplicate', async () => {
                    const copy = await duplicateQuote(request, quote.id)
                    await cache.invalidateQueries({ queryKey: ['quotes'] })
                    toast('Novo rascunho ' + copy.number + ' criado.')
                    onDuplicated(copy, copy.warnings)
                  })
                }
              >
                <Copy size={16} aria-hidden="true" />
                {busy === 'duplicate' ? 'Duplicando…' : 'Duplicar'}
              </Button>
            )}
            <Button
              variant="secondary"
              disabled={!!busy}
              onClick={() =>
                void run('pdf', async () => {
                  await downloadQuotePdf(quote)
                  toast('PDF de ' + quote.number + ' gerado.')
                })
              }
            >
              <Download size={16} aria-hidden="true" />
              {busy === 'pdf' ? 'Gerando PDF…' : 'Baixar PDF'}
            </Button>
          </div>
        </div>
      </Card>
      <Card title="Cliente" description="Dados registrados no orçamento ao salvar.">
        <div className="padded">
          <dl className="master-details">
            <div>
              <dt>Nome / razão social</dt>
              <dd>{customer.legal_name}</dd>
            </div>
            <div>
              <dt>{customer.person_type === 'PJ' ? 'CNPJ' : 'CPF'}</dt>
              <dd>{customer.document}</dd>
            </div>
            <div>
              <dt>Contato</dt>
              <dd>
                {[customer.contact, customer.mobile || customer.phone, customer.email]
                  .filter(Boolean)
                  .join(' · ') || 'Não informado'}
              </dd>
            </div>
            <div>
              <dt>Endereço</dt>
              <dd>
                {customer.address
                  ? `${customer.address.street}, ${customer.address.city} / ${customer.address.state} · CEP ${customer.address.postal_code}`
                  : 'Não informado'}
              </dd>
            </div>
          </dl>
        </div>
      </Card>
      <Card
        title="Itens"
        description="Valor do item = quantidade × preço do período × número de períodos (dias corridos)."
      >
        <MasterTable
          label={'Itens do orçamento ' + quote.number}
          headers={[
            'Produto',
            'Quantidade',
            'Períodos',
            'Preço de tabela',
            'Preço aplicado',
            'Devolução prevista',
            'Total',
          ]}
        >
          {quote.items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.product_name}</strong>
                <span className="cell-description">{item.product_code}</span>
              </td>
              <td>
                {brQuantity(item.quantity)} {item.unit}
              </td>
              <td>
                {item.period_count} × {periods[item.period]}
              </td>
              <td>{brMoney(item.table_price)}</td>
              <td>
                {brMoney(item.unit_price)}
                <span className="cell-description">{item.negotiated ? 'Negociado' : 'Tabela'}</span>
              </td>
              <td>{brDate(item.end_date)}</td>
              <td>
                <strong>{brMoney(item.total)}</strong>
              </td>
            </tr>
          ))}
        </MasterTable>
        <dl className="quote-totals">
          <div>
            <dt>Total pela tabela</dt>
            <dd>{brMoney(quote.table_total)}</dd>
          </div>
          <div>
            <dt>
              {difference.startsWith('-')
                ? 'Acréscimo negociado'
                : /^0+\.0+$/.test(difference)
                  ? 'Diferença negociada'
                  : 'Desconto negociado'}
            </dt>
            <dd>{brMoney(difference.replace('-', ''))}</dd>
          </div>
          <div className="quote-total">
            <dt>Total do orçamento</dt>
            <dd>{brMoney(quote.total)}</dd>
          </div>
        </dl>
      </Card>
      <Card title="Histórico" description="Cada mudança de situação fica registrada.">
        <MasterTable
          label={'Histórico do orçamento ' + quote.number}
          headers={['Quando', 'Mudança', 'Motivo', 'Responsável']}
        >
          {quote.transitions.map((step, index) => (
            <tr key={index}>
              <td>{brDateTime(step.created_at)}</td>
              <td>
                {step.from_status
                  ? (quoteStatuses[step.from_status as QuoteStatus] || step.from_status) + ' → '
                  : 'Criação → '}
                {quoteStatuses[step.to_status as QuoteStatus] || step.to_status}
              </td>
              <td>{step.reason || '—'}</td>
              <td>Usuário nº {step.created_by}</td>
            </tr>
          ))}
        </MasterTable>
      </Card>
      <Modal
        open={action !== null}
        onOpenChange={(open) => {
          if (!open) setAction(null)
        }}
        title={action ? dialogs[action].title : ''}
        description={quote.number + ' · ' + customer.legal_name}
      >
        {action && (
          <TransitionForm
            key={action + quote.version}
            quote={quote}
            action={action}
            close={() => setAction(null)}
            reload={reload}
            done={() => {
              toast(quoteActions[action].done)
              reload()
            }}
          />
        )}
      </Modal>
    </>
  )
}
