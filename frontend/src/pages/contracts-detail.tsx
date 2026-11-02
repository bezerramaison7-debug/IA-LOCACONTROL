import { useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { Download, FilePlus2, PencilLine, RefreshCw, Truck, Undo2 } from 'lucide-react'
import { useAuth } from '../auth/context'
import { periods } from '../lib/masters'
import {
  actionError,
  conditions,
  contractActions,
  contractOrigins,
  contractStatuses,
  customerLine,
  destinations,
  downloadDocument,
  downloadPreview,
  eventKinds,
  expectedReturn,
  generateDocument,
  getContract,
  getTemplates,
  positive,
  priceOptions,
  signDocument,
  transitionContract,
  unitStates,
  useContractPermissions,
  type ActionError,
  type Contract,
  type ContractAction,
  type ContractDocument,
} from '../lib/contracts'
import { brDate, brDateTime, brMoney, brQuantity, failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable } from './masters-shared'
import { ActionFailure, ContractBadge, DocumentBadge } from './contracts-shared'

export type Operation = 'retirada' | 'devolucao' | 'renovar'

const dialogs: Record<ContractAction, { title: string; text: string; confirm: string }> = {
  confirm: {
    title: 'Confirmar contrato',
    text: 'O contrato deixa de ser editável e passa a aguardar a retirada. O estoque só é baixado quando a retirada for registrada.',
    confirm: 'Confirmar contrato',
  },
  cancel: {
    title: 'Cancelar contrato',
    text: 'O cancelamento é definitivo: o número não é reaproveitado e o contrato fica apenas para consulta. Contrato com retirada registrada não pode ser cancelado.',
    confirm: 'Confirmar cancelamento',
  },
  close: {
    title: 'Encerrar contrato',
    text: 'Use o encerramento manual quando o saldo restante nunca foi retirado. O contrato passa a Encerrado, não aceita novas retiradas e isso não pode ser desfeito.',
    confirm: 'Confirmar encerramento',
  },
}

function ReasonForm({
  text,
  label,
  required,
  confirm,
  danger = false,
  failure,
  onReload,
  onClose,
  onSubmit,
}: {
  text: ReactNode
  label: string
  required: boolean
  confirm: string
  danger?: boolean
  failure: ActionError | null
  onReload: () => void
  onClose: () => void
  onSubmit: (reason: string) => Promise<void>
}) {
  const form = useForm<{ reason: string }>({ defaultValues: { reason: '' } })
  return (
    <form
      className="form-stack"
      noValidate
      onSubmit={form.handleSubmit(({ reason }) => onSubmit(reason))}
    >
      <div className="form-stack">{text}</div>
      <Field
        label={label}
        maxLength={500}
        autoComplete="off"
        hint={required ? 'Obrigatório · pelo menos 5 caracteres.' : undefined}
        {...form.register('reason', {
          validate: (value) =>
            !required ||
            value.trim().length >= 5 ||
            'Informe o motivo com pelo menos 5 caracteres.',
        })}
        error={form.formState.errors.reason?.message}
      />
      <ActionFailure failure={failure} onReload={onReload} />
      <div className="modal-actions">
        <Button variant="secondary" onClick={onClose}>
          Voltar
        </Button>
        <Button
          type="submit"
          variant={danger ? 'danger' : 'primary'}
          disabled={form.formState.isSubmitting}
        >
          {form.formState.isSubmitting ? 'Enviando…' : confirm}
        </Button>
      </div>
    </form>
  )
}

type Dialog =
  | { kind: 'action'; action: ContractAction }
  | { kind: 'generate' }
  | { kind: 'sign'; document: ContractDocument }

function Documents({
  contract,
  canWrite,
  onDialog,
}: {
  contract: Contract
  canWrite: boolean
  onDialog: (dialog: Dialog) => void
}) {
  const { request } = useAuth()
  const toast = useToast()
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const templates = useQuery({
    queryKey: ['contracts', 'templates'],
    queryFn: () => getTemplates(request),
    retry: false,
  })
  const model = templates.data?.items.find((item) => item.is_active)
  const draft = contract.stored_status === 'RASCUNHO' || contract.stored_status === 'CANCELADO'
  async function run(name: string, task: () => Promise<void>, done: string) {
    setBusy(name)
    setError('')
    try {
      await task()
      toast(done)
    } catch (e) {
      setError(failureMessage(e, 'Não foi possível baixar o documento.'))
    } finally {
      setBusy('')
    }
  }
  return (
    <Card
      title="Documentos"
      description="Cada geração cria uma versão armazenada. Um documento assinado nunca é substituído."
    >
      <div className="padded form-stack">
        {model?.is_provisional && (
          <p className="quote-notice" role="note">
            <span>
              <strong>Modelo provisório.</strong> O modelo em uso ({model.name}, versão{' '}
              {model.version}) é um texto de exemplo e sai com esse aviso no PDF. Publique o
              contrato oficial da locadora em Configurações.
            </span>
          </p>
        )}
        {templates.isError && (
          <p className="field-hint">
            Não foi possível consultar o modelo em uso: {templates.error.message}
          </p>
        )}
        {draft && (
          <p className="field-hint">
            {contract.stored_status === 'RASCUNHO'
              ? 'No rascunho só existe a prévia, que não é armazenada. Confirme o contrato para gerar o documento.'
              : 'Contrato cancelado não gera novos documentos.'}
          </p>
        )}
        <Failure message={error} />
        <div className="row-actions" role="group" aria-label="Ações de documento">
          <Button
            variant="secondary"
            disabled={!!busy}
            onClick={() =>
              void run('preview', () => downloadPreview(contract), 'Prévia do contrato baixada.')
            }
          >
            <Download size={16} aria-hidden="true" />
            {busy === 'preview' ? 'Gerando prévia…' : 'Baixar prévia (PDF)'}
          </Button>
          {canWrite && !draft && (
            <Button disabled={!!busy} onClick={() => onDialog({ kind: 'generate' })}>
              <FilePlus2 size={16} aria-hidden="true" />
              Gerar documento
            </Button>
          )}
        </div>
      </div>
      {!contract.documents.length ? (
        <EmptyState
          initial
          title="Nenhum documento gerado"
          description="As versões geradas e a situação de assinatura aparecem aqui."
        />
      ) : (
        <MasterTable
          label={'Versões do documento do contrato ' + contract.number}
          headers={['Versão', 'Situação', 'Gerado em', 'Assinatura', 'Motivo', 'Ações']}
        >
          {contract.documents.map((doc) => (
            <tr key={doc.id}>
              <td className="code-cell">v{doc.version}</td>
              <td>
                <DocumentBadge status={doc.status} />
              </td>
              <td>{brDateTime(doc.created_at)}</td>
              <td>{doc.signed_at ? brDateTime(doc.signed_at) : 'Não assinado'}</td>
              <td>{doc.reason || '—'}</td>
              <td>
                <div className="row-actions">
                  <Button
                    variant="ghost"
                    disabled={!!busy}
                    aria-label={'Baixar versão ' + doc.version}
                    onClick={() =>
                      void run(
                        'doc' + doc.id,
                        () => downloadDocument(contract, doc),
                        'Versão ' + doc.version + ' baixada.',
                      )
                    }
                  >
                    {busy === 'doc' + doc.id ? 'Baixando…' : 'Baixar'}
                  </Button>
                  {canWrite && doc.status === 'GERADO' && (
                    <Button
                      variant="ghost"
                      aria-label={'Marcar versão ' + doc.version + ' como assinada'}
                      onClick={() => onDialog({ kind: 'sign', document: doc })}
                    >
                      Marcar como assinado
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </MasterTable>
      )}
    </Card>
  )
}

export function ContractDetail({
  id,
  onBack,
  onEdit,
  onOperation,
}: {
  id: number
  onBack: () => void
  onEdit: () => void
  onOperation: (operation: Operation) => void
}) {
  const { request } = useAuth()
  const can = useContractPermissions()
  const cache = useQueryClient()
  const toast = useToast()
  const [dialog, setDialog] = useState<Dialog | null>(null)
  const [failure, setFailure] = useState<ActionError | null>(null)
  const query = useQuery({
    queryKey: ['contracts', 'detail', id],
    queryFn: () => getContract(request, id),
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
        <PageHeader title="Contrato" description="Carregando os dados salvos." actions={back} />
        <Skeleton rows={4} />
      </>
    )
  if (query.isError)
    return (
      <>
        <PageHeader title="Contrato" description="Não foi possível abrir." actions={back} />
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      </>
    )
  const contract = query.data
  const customer = contract.customer
  const stored = contract.stored_status
  const difference = contract.negotiated_difference
  const toWithdraw = contract.items.some((item) => positive(item.to_withdraw))
  const withCustomer = contract.items.some((item) => positive(item.outstanding))
  const numbers = new Map(contract.chain.map((link) => [link.id, link.number]))
  const itemNames = new Map(contract.items.map((item) => [item.id, item]))
  const signed = contract.documents.find((doc) => doc.status === 'ASSINADO')
  const pending = contract.documents.find((doc) => doc.status === 'GERADO')
  const open = (next: Dialog) => {
    setFailure(null)
    setDialog(next)
  }
  const reload = () => {
    setDialog(null)
    void cache.invalidateQueries({ queryKey: ['contracts'] })
  }
  async function submit(task: () => Promise<unknown>, done: string) {
    setFailure(null)
    try {
      await task()
      toast(done)
      reload()
    } catch (e) {
      setFailure(actionError(e, 'Não foi possível concluir a ação.'))
    }
  }
  const movementLine = (line: { contract_item_id: number; quantity: string }) => {
    const item = itemNames.get(line.contract_item_id)
    return brQuantity(line.quantity) + ' ' + (item ? item.unit + ' · ' + item.product_name : '')
  }
  const unitCode = (line: { contract_item_id: number; equipment_id: number | null }) =>
    itemNames
      .get(line.contract_item_id)
      ?.units.find((unit) => unit.equipment_id === line.equipment_id)?.code
  return (
    <>
      <PageHeader
        title={'Contrato ' + contract.number}
        description={customerLine(contract)}
        actions={back}
      />
      <Card
        title="Resumo"
        description="Dados oficiais calculados pelo servidor."
        action={<ContractBadge status={contract.status} />}
      >
        <div className="padded form-stack">
          <dl className="master-details">
            <div>
              <dt>Número</dt>
              <dd>{contract.number}</dd>
            </div>
            <div>
              <dt>Origem</dt>
              <dd>
                {contractOrigins[contract.origin] || contract.origin}
                {contract.quote_id &&
                  contract.quote_number &&
                  (can.has('quotes.read') ? (
                    <>
                      {' · '}
                      <Link to={'/orcamentos?id=' + contract.quote_id}>
                        {contract.quote_number}
                      </Link>
                    </>
                  ) : (
                    ' · ' + contract.quote_number
                  ))}
              </dd>
            </div>
            {contract.price_option && (
              <div>
                <dt>Opção de preço da renovação</dt>
                <dd>{priceOptions[contract.price_option]}</dd>
              </div>
            )}
            {contract.status_reason && (
              <div>
                <dt>Motivo da última alteração</dt>
                <dd>{contract.status_reason}</dd>
              </div>
            )}
            <div>
              <dt>Observações</dt>
              <dd>{contract.notes || 'Não informado'}</dd>
            </div>
          </dl>
          {contract.status === 'VENCIDO' && (
            <p className="quote-notice quote-notice-danger">
              Devolução prevista vencida em {brDate(expectedReturn(contract))}. Registre a devolução
              ou renove os itens que continuam com o cliente.
            </p>
          )}
          {contract.status === 'VENCENDO' && (
            <p className="quote-notice">
              Devolução prevista para {brDate(expectedReturn(contract))}. Combine a devolução ou a
              renovação com o cliente.
            </p>
          )}
          {stored === 'ATIVO' && !withCustomer && (
            <p className="quote-notice">
              Nenhum item está com o cliente.{' '}
              {toWithdraw
                ? 'Registre a retirada do saldo restante ou encerre o contrato manualmente.'
                : 'O contrato pode ser encerrado.'}
            </p>
          )}
          <div className="row-actions" role="group" aria-label="Ações do contrato">
            {stored === 'RASCUNHO' && can.write && (
              <>
                <Button onClick={onEdit}>
                  <PencilLine size={16} aria-hidden="true" />
                  Editar
                </Button>
                <Button
                  variant="secondary"
                  onClick={() => open({ kind: 'action', action: 'confirm' })}
                >
                  {contractActions.confirm.label}
                </Button>
              </>
            )}
            {(stored === 'AGUARDANDO_RETIRADA' || stored === 'ATIVO') &&
              can.operate &&
              toWithdraw && (
                <Button
                  variant={stored === 'ATIVO' ? 'secondary' : 'primary'}
                  onClick={() => onOperation('retirada')}
                >
                  <Truck size={16} aria-hidden="true" />
                  Registrar retirada
                </Button>
              )}
            {stored === 'ATIVO' && can.operate && withCustomer && (
              <Button onClick={() => onOperation('devolucao')}>
                <Undo2 size={16} aria-hidden="true" />
                Registrar devolução
              </Button>
            )}
            {stored === 'ATIVO' && can.write && withCustomer && (
              <Button variant="secondary" onClick={() => onOperation('renovar')}>
                <RefreshCw size={16} aria-hidden="true" />
                Renovar
              </Button>
            )}
            {stored === 'ATIVO' && can.write && !withCustomer && (
              <Button variant="danger" onClick={() => open({ kind: 'action', action: 'close' })}>
                {contractActions.close.label}
              </Button>
            )}
            {(stored === 'RASCUNHO' || stored === 'AGUARDANDO_RETIRADA') && can.write && (
              <Button variant="danger" onClick={() => open({ kind: 'action', action: 'cancel' })}>
                {contractActions.cancel.label}
              </Button>
            )}
          </div>
        </div>
      </Card>
      <Card title="Cliente" description="Dados registrados no contrato ao salvar.">
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
        description="Saldos por item: contratado, retirado, com o cliente, devolvido, renovado e a retirar."
      >
        <MasterTable
          label={'Itens do contrato ' + contract.number}
          headers={[
            'Produto',
            'Contratado',
            'Retirado',
            'Com o cliente',
            'Devolvido',
            'Renovado',
            'A retirar',
            'Períodos',
            'Devolução prevista',
          ]}
        >
          {contract.items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.product_name}</strong>
                <span className="cell-description">
                  {item.product_code} · {item.individual_tracking ? 'unidade física' : 'quantidade'}
                </span>
                {item.units.length > 0 && (
                  <ul
                    className="contract-units"
                    aria-label={'Unidades físicas de ' + item.product_name}
                  >
                    {item.units.map((unit) => (
                      <li key={unit.equipment_id}>
                        <span className="code-cell">{unit.code}</span> · {unitStates[unit.state]}
                      </li>
                    ))}
                  </ul>
                )}
              </td>
              <td>
                {brQuantity(item.quantity)} {item.unit}
              </td>
              <td>{brQuantity(item.withdrawn)}</td>
              <td>
                <strong>{brQuantity(item.outstanding)}</strong>
              </td>
              <td>{brQuantity(item.returned)}</td>
              <td>{brQuantity(item.renewed)}</td>
              <td>{brQuantity(item.to_withdraw)}</td>
              <td>
                {item.period_count} × {periods[item.period]}
              </td>
              <td className="date-cell">{brDate(item.end_date)}</td>
            </tr>
          ))}
        </MasterTable>
      </Card>
      <Card title="Datas" description="Datas comerciais do contrato, em dias corridos.">
        <div className="padded">
          <dl className="master-details">
            <div>
              <dt>Início da locação</dt>
              <dd>{brDate(contract.start_date)}</dd>
            </div>
            <div>
              <dt>Fim do período contratado</dt>
              <dd>{brDate(contract.end_date)}</dd>
            </div>
            <div>
              <dt>Próxima devolução prevista</dt>
              <dd>{contract.due_date ? brDate(contract.due_date) : 'Sem itens com o cliente'}</dd>
            </div>
            <div>
              <dt>Criado em</dt>
              <dd>{brDateTime(contract.created_at)}</dd>
            </div>
            <div>
              <dt>Atualizado em</dt>
              <dd>{brDateTime(contract.updated_at)}</dd>
            </div>
          </dl>
        </div>
      </Card>
      <Card
        title="Valores"
        description="Valor do item = quantidade × preço do período × número de períodos."
      >
        <MasterTable
          label={'Valores do contrato ' + contract.number}
          headers={['Produto', 'Quantidade', 'Preço de tabela', 'Preço aplicado', 'Total']}
        >
          {contract.items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.product_name}</strong>
                <span className="cell-description">
                  {item.period_count} × {periods[item.period]}
                </span>
              </td>
              <td>
                {brQuantity(item.quantity)} {item.unit}
              </td>
              <td>{brMoney(item.table_price)}</td>
              <td>
                {brMoney(item.unit_price)}
                <span className="cell-description">{item.negotiated ? 'Negociado' : 'Tabela'}</span>
              </td>
              <td>
                <strong>{brMoney(item.total)}</strong>
              </td>
            </tr>
          ))}
        </MasterTable>
        <dl className="quote-totals">
          <div>
            <dt>Total pela tabela</dt>
            <dd>{brMoney(contract.table_total)}</dd>
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
            <dt>Total do contrato</dt>
            <dd>{brMoney(contract.total)}</dd>
          </div>
        </dl>
      </Card>
      <Documents contract={contract} canWrite={can.write} onDialog={open} />
      <Card
        title="Cadeia de renovações"
        description="Contrato original e suas renovações. Abra qualquer elo da cadeia."
      >
        <MasterTable
          label={'Cadeia do contrato ' + contract.base_number}
          headers={['Número', 'Início', 'Fim do período', 'Total', 'Situação']}
        >
          {contract.chain.map((link) => (
            <tr key={link.id}>
              <td className="code-cell">
                {link.id === contract.id ? (
                  <span aria-current="true">{link.number} (este contrato)</span>
                ) : (
                  <Link
                    to={{ search: '?id=' + link.id }}
                    aria-label={'Abrir contrato ' + link.number}
                  >
                    {link.number}
                  </Link>
                )}
              </td>
              <td className="date-cell">{brDate(link.start_date)}</td>
              <td className="date-cell">{brDate(link.end_date)}</td>
              <td className="date-cell">{brMoney(link.total)}</td>
              <td>
                <ContractBadge status={link.status} />
              </td>
            </tr>
          ))}
        </MasterTable>
      </Card>
      {(contract.withdrawals.length > 0 || contract.returns.length > 0) && (
        <Card
          title="Retiradas e devoluções"
          description="Movimentações deste contrato, com condição e destino de cada devolução."
        >
          <MasterTable
            label={'Movimentações do contrato ' + contract.number}
            headers={['Data', 'Operação', 'Itens', 'Observação']}
          >
            {contract.withdrawals.map((row) => (
              <tr key={'w' + row.id}>
                <td className="date-cell">{brDate(row.occurred_on)}</td>
                <td>Retirada</td>
                <td>
                  <ul className="contract-units">
                    {row.items.map((line, index) => (
                      <li key={index}>
                        {movementLine(line)}
                        {unitCode(line) && ' · ' + unitCode(line)}
                      </li>
                    ))}
                  </ul>
                </td>
                <td>{row.notes || '—'}</td>
              </tr>
            ))}
            {contract.returns.map((row) => (
              <tr key={'r' + row.id}>
                <td className="date-cell">{brDate(row.occurred_on)}</td>
                <td>Devolução</td>
                <td>
                  <ul className="contract-units">
                    {row.items.map((line, index) => (
                      <li key={index}>
                        {movementLine(line)}
                        {unitCode(line) && ' · ' + unitCode(line)}
                        {' · '}
                        {conditions[line.condition as keyof typeof conditions] || line.condition}
                        {' → '}
                        {destinations[line.destination as keyof typeof destinations] ||
                          line.destination}
                        {line.notes && ' · ' + line.notes}
                      </li>
                    ))}
                  </ul>
                </td>
                <td>{row.notes || '—'}</td>
              </tr>
            ))}
          </MasterTable>
        </Card>
      )}
      <Card
        title="Histórico"
        description="Linha do tempo de toda a cadeia: contrato original e renovações."
      >
        <ol
          className="contract-timeline"
          aria-label={'Linha do tempo da cadeia ' + contract.base_number}
        >
          {contract.events.map((event) => (
            <li key={event.id}>
              <span className="contract-timeline-when">{brDateTime(event.created_at)}</span>
              <span>
                <strong>{eventKinds[event.kind] || event.kind}</strong>
                {' · contrato '}
                {numbers.get(event.contract_id) || contract.number}
              </span>
              <span>{event.description}</span>
              <span className="cell-description">Usuário nº {event.created_by}</span>
            </li>
          ))}
        </ol>
      </Card>
      <Modal
        open={dialog !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setDialog(null)
        }}
        title={
          dialog?.kind === 'action'
            ? dialogs[dialog.action].title
            : dialog?.kind === 'sign'
              ? 'Marcar documento como assinado'
              : 'Gerar documento do contrato'
        }
        description={'Contrato ' + contract.number + ' · ' + customer.legal_name}
      >
        {dialog?.kind === 'action' && (
          <ReasonForm
            key={dialog.action + contract.version}
            text={<p>{dialogs[dialog.action].text}</p>}
            label={dialog.action === 'confirm' ? 'Observação (opcional)' : 'Motivo'}
            required={dialog.action !== 'confirm'}
            confirm={dialogs[dialog.action].confirm}
            danger={dialog.action !== 'confirm'}
            failure={failure}
            onReload={reload}
            onClose={() => setDialog(null)}
            onSubmit={(reason) =>
              submit(
                () => transitionContract(request, contract, dialog.action, reason),
                contractActions[dialog.action].done,
              )
            }
          />
        )}
        {dialog?.kind === 'generate' && (
          <ReasonForm
            key={'generate' + contract.documents.length}
            text={
              <>
                <p>
                  Será gerada e armazenada a versão{' '}
                  {Math.max(0, ...contract.documents.map((doc) => doc.version)) + 1} do documento,
                  com os dados atuais do contrato ({contractStatuses[contract.status]}).
                </p>
                {signed && (
                  <p className="quote-notice">
                    <span>
                      <strong>Já existe documento assinado (versão {signed.version}).</strong> Ele
                      será preservado e continua disponível para baixar. Informe o motivo da nova
                      versão.
                    </span>
                  </p>
                )}
                {pending && (
                  <p>
                    A versão {pending.version}, ainda não assinada, passa a constar como
                    substituída.
                  </p>
                )}
              </>
            }
            label={signed ? 'Motivo da nova versão' : 'Motivo (opcional)'}
            required={!!signed}
            confirm="Gerar documento"
            failure={failure}
            onReload={reload}
            onClose={() => setDialog(null)}
            onSubmit={(reason) =>
              submit(() => generateDocument(request, contract.id, reason), 'Documento gerado.')
            }
          />
        )}
        {dialog?.kind === 'sign' && (
          <ReasonForm
            key={'sign' + dialog.document.id}
            text={
              <p>
                Marque a versão {dialog.document.version} como assinada depois de conferir o
                documento assinado pelo cliente. A partir daí ela nunca é substituída: novas versões
                exigem motivo e o assinado é preservado. Isso não pode ser desfeito.
              </p>
            }
            label="Observação da assinatura (opcional)"
            required={false}
            confirm="Confirmar assinatura"
            failure={failure}
            onReload={reload}
            onClose={() => setDialog(null)}
            onSubmit={(notes) =>
              submit(
                () => signDocument(request, dialog.document.id, notes),
                'Versão ' + dialog.document.version + ' marcada como assinada.',
              )
            }
          />
        )}
      </Modal>
    </>
  )
}
