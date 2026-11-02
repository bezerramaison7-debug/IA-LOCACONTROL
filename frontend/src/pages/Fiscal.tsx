import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useSearchParams } from 'react-router-dom'
import { Ban, CircleCheck, Hourglass, PencilLine, Plus, TriangleAlert } from 'lucide-react'
import { canOpen, useAuth } from '../auth/context'
import { actionError, contractSummarySchema, type ActionError } from '../lib/contracts'
import {
  actOnFiscal,
  createFiscal,
  downloadFiscal,
  fiscalActions,
  fiscalEventActions,
  fiscalFormSchema,
  fiscalStatuses,
  getFiscal,
  getProvider,
  listFiscal,
  type FiscalAction,
  type FiscalDetail,
  type FiscalFilters,
  type FiscalForm,
  type FiscalProvider,
  type FiscalStatus,
} from '../lib/fiscal'
import { localDate, pageSchema } from '../lib/masters'
import { brDate, brDateTime, brMoney, failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import {
  Card,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  Select,
  Skeleton,
  Tag,
} from '../components/ui'
import { useToast } from '../components/toast-context'
import { ActionFailure } from './contracts-shared'
import { Failure, MasterTable, Pager } from './masters-shared'
import { RecordPicker } from './quotes-editor'

const badges = {
  PENDENTE: ['muted', PencilLine],
  PROCESSANDO: ['warning', Hourglass],
  EMITIDO: ['success', CircleCheck],
  ERRO: ['danger', TriangleAlert],
  CANCELADO: ['muted', Ban],
} as const
function FiscalBadge({ status }: { status: FiscalStatus }) {
  const [tone, icon] = badges[status]
  return (
    <Tag tone={tone} icon={icon}>
      {fiscalStatuses[status]}
    </Tag>
  )
}

/** Permanent while the provider is the simulation: nothing here has fiscal value. */
function ProviderNotice({ provider }: { provider: FiscalProvider }) {
  return (
    <>
      {provider.is_simulation && (
        <div
          className="quote-notice quote-notice-danger"
          role="note"
          aria-label="Aviso de simulação"
        >
          <strong>SIMULAÇÃO — sem valor fiscal.</strong>
          <span>
            Nenhum documento é transmitido a órgãos ou provedores fiscais. Números, PDFs e XMLs
            gerados aqui servem apenas para validar o fluxo. A integração real depende das regras
            definidas com a contabilidade, da escolha do provedor e de credenciais de teste.
          </span>
        </div>
      )}
      <p className="field-hint fiscal-provider">
        Provedor: {provider.is_simulation ? 'simulação interna' : provider.name} · ambiente:{' '}
        {provider.is_simulation ? 'simulação' : provider.environment} · tipo de documento:{' '}
        {provider.document_kind || 'ainda não definido com a contabilidade'}.
      </p>
    </>
  )
}

function NewDocument({ onCreated }: { onCreated: (id: number) => void }) {
  const { user, request } = useAuth()
  // Generated once per form: a repeated submit returns the same record instead of a duplicate.
  const [requestKey] = useState(() => crypto.randomUUID())
  const [customerLabel, setCustomerLabel] = useState('')
  const [failure, setFailure] = useState('')
  const form = useForm<FiscalForm>({
    resolver: zodResolver(fiscalFormSchema),
    defaultValues: {
      customer_id: '',
      contract_id: '',
      period_start: localDate(),
      period_end: localDate(),
      amount: '',
      description: '',
    },
  })
  const errors = form.formState.errors
  const customerId = useWatch({ control: form.control, name: 'customer_id' })
  const canContracts = canOpen(user, '/contratos')
  const contracts = useQuery({
    queryKey: ['fiscal', 'contracts', customerId],
    queryFn: async () =>
      pageSchema(contractSummarySchema)
        .parse(await request('/contracts?limit=100&offset=0&customer_id=' + customerId))
        .items.filter((row) => !['RASCUNHO', 'CANCELADO'].includes(row.stored_status)),
    enabled: canContracts && !!customerId,
    retry: false,
  })
  return (
    <form
      className="form-stack"
      noValidate
      onSubmit={form.handleSubmit(async (values) => {
        setFailure('')
        try {
          onCreated((await createFiscal(request, values, requestKey)).id)
        } catch (e) {
          setFailure(failureMessage(e, 'Não foi possível criar o documento.'))
        }
      })}
    >
      <RecordPicker
        kind="customers"
        searchLabel="Buscar cliente"
        label="Cliente"
        placeholder="Selecione um cliente"
        value={customerId}
        knownLabel={customerLabel}
        error={errors.customer_id?.message}
        onChange={(id, text) => {
          setCustomerLabel(text)
          form.setValue('customer_id', id, { shouldValidate: true })
          form.setValue('contract_id', '')
        }}
      />
      {canContracts && (
        <Select label="Contrato (opcional)" {...form.register('contract_id')}>
          <option value="">Sem contrato vinculado</option>
          {(contracts.data || []).map((row) => (
            <option key={row.id} value={row.id}>
              Contrato {row.number} · {brMoney(row.total)}
            </option>
          ))}
        </Select>
      )}
      <div className="master-form-grid">
        <Field
          label="Início do período"
          type="date"
          {...form.register('period_start')}
          error={errors.period_start?.message}
        />
        <Field
          label="Fim do período"
          type="date"
          {...form.register('period_end')}
          error={errors.period_end?.message}
        />
      </div>
      <Field
        label="Valor (R$)"
        inputMode="decimal"
        maxLength={12}
        autoComplete="off"
        placeholder="0,00"
        {...form.register('amount')}
        error={errors.amount?.message}
      />
      <Field
        label="Descrição do faturamento"
        maxLength={500}
        autoComplete="off"
        hint="Ex.: locação de equipamentos no período informado."
        {...form.register('description')}
        error={errors.description?.message}
      />
      <p className="field-hint">
        O documento é criado como pendente. Nada é enviado ao provedor até você escolher “Enviar ao
        provedor”.
      </p>
      <Failure message={failure} />
      <div className="modal-actions">
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Salvando…' : 'Criar documento'}
        </Button>
      </div>
    </form>
  )
}

function CancelDialog({
  document,
  onClose,
  onDone,
}: {
  document: FiscalDetail
  onClose: () => void
  onDone: (document: FiscalDetail) => void
}) {
  const { request } = useAuth()
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState('')
  const [failure, setFailure] = useState<ActionError | null>(null)
  const [busy, setBusy] = useState(false)
  return (
    <Modal
      open
      onOpenChange={(open) => !open && onClose()}
      title="Cancelar documento"
      description={
        document.status === 'EMITIDO'
          ? document.is_simulation
            ? 'O cancelamento é registrado na simulação e não pode ser desfeito. Nada é transmitido.'
            : 'O cancelamento é enviado ao provedor fiscal e não pode ser desfeito.'
          : 'O documento deixa de poder ser enviado ao provedor. Esta ação não pode ser desfeita.'
      }
    >
      <form
        className="form-stack"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          if (reason.trim().length < 5) {
            setReasonError('Informe o motivo com pelo menos 5 caracteres.')
            return
          }
          setReasonError('')
          setFailure(null)
          setBusy(true)
          void actOnFiscal(request, document, 'cancel', reason)
            .then(onDone)
            .catch((e) => setFailure(actionError(e, 'Não foi possível cancelar o documento.')))
            .finally(() => setBusy(false))
        }}
      >
        <Field
          label="Motivo do cancelamento"
          maxLength={500}
          autoComplete="off"
          value={reason}
          error={reasonError}
          onChange={(e) => setReason(e.target.value)}
        />
        <ActionFailure failure={failure} />
        <div className="modal-actions">
          <Button variant="secondary" onClick={onClose}>
            Voltar
          </Button>
          <Button type="submit" variant="danger" disabled={busy}>
            {busy ? 'Cancelando…' : 'Confirmar cancelamento'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function Detail({ id, canWrite }: { id: number; canWrite: boolean }) {
  const { user, request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [failure, setFailure] = useState<ActionError | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState(false)
  const query = useQuery({
    queryKey: ['fiscal', 'detail', id],
    queryFn: () => getFiscal(request, id),
    retry: false,
  })
  if (query.isPending) return <Skeleton rows={4} />
  if (query.isError)
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
  const document = query.data
  const reload = () => {
    setFailure(null)
    void cache.invalidateQueries({ queryKey: ['fiscal'] })
  }
  const applied = (next: FiscalDetail, message: string) => {
    cache.setQueryData(['fiscal', 'detail', id], next)
    void cache.invalidateQueries({ queryKey: ['fiscal', 'list'] })
    toast(message)
  }
  function act(action: Exclude<FiscalAction, 'cancel'>) {
    setFailure(null)
    setBusy(action)
    void actOnFiscal(request, document, action, '')
      .then((next) => applied(next, fiscalActions[action].done))
      .catch((e) => setFailure(actionError(e, 'Não foi possível concluir a ação.')))
      .finally(() => setBusy(null))
  }
  function download(kind: 'pdf' | 'xml') {
    setFailure(null)
    setBusy(kind)
    void downloadFiscal(document, kind)
      .catch((e) => setFailure(actionError(e, 'Não foi possível baixar o arquivo.')))
      .finally(() => setBusy(null))
  }
  return (
    <>
      <Card
        title={'Documento ' + (document.number || 'nº interno ' + document.id)}
        description={document.customer.legal_name + ' · ' + document.customer.document}
        action={<FiscalBadge status={document.status} />}
      >
        <div className="padded form-stack">
          <dl className="master-details">
            <div>
              <dt>Período faturado</dt>
              <dd>
                {brDate(document.period_start)} a {brDate(document.period_end)}
              </dd>
            </div>
            <div>
              <dt>Valor</dt>
              <dd>{brMoney(document.amount)}</dd>
            </div>
            <div>
              <dt>Descrição</dt>
              <dd>{document.description}</dd>
            </div>
            <div>
              <dt>Contrato</dt>
              <dd>
                {document.contract_id ? (
                  canOpen(user, '/contratos') ? (
                    <Link to={'/contratos?id=' + document.contract_id}>
                      Abrir contrato vinculado
                    </Link>
                  ) : (
                    'Vinculado a um contrato'
                  )
                ) : (
                  'Sem contrato vinculado'
                )}
              </dd>
            </div>
            <div>
              <dt>Número / série</dt>
              <dd>
                {document.number
                  ? document.number + ' / ' + (document.series || '—')
                  : 'Não emitido'}
              </dd>
            </div>
            <div>
              <dt>Referência no provedor</dt>
              <dd>{document.provider_ref || 'Ainda não enviado'}</dd>
            </div>
            {document.access_key && (
              <div>
                <dt>Chave de acesso</dt>
                <dd>{document.access_key}</dd>
              </div>
            )}
            {document.cancel_reason && (
              <div>
                <dt>Motivo do cancelamento</dt>
                <dd>{document.cancel_reason}</dd>
              </div>
            )}
          </dl>
          {document.is_simulation && (
            <p className="quote-notice quote-notice-danger" role="note">
              Documento de simulação: não tem valor fiscal e não foi transmitido.
            </p>
          )}
          {document.error_message && (
            <p className="quote-notice quote-notice-danger" role="alert">
              Retorno do provedor: {document.error_message}
            </p>
          )}
          <ActionFailure failure={failure} onReload={reload} reloadLabel="Recarregar documento" />
          <div className="row-actions" role="group" aria-label="Ações do documento">
            {canWrite && ['PENDENTE', 'ERRO'].includes(document.status) && (
              <Button disabled={busy !== null} onClick={() => act('emit')}>
                {busy === 'emit'
                  ? 'Enviando…'
                  : document.status === 'ERRO'
                    ? 'Enviar novamente ao provedor'
                    : fiscalActions.emit.label}
              </Button>
            )}
            {canWrite && document.status === 'PROCESSANDO' && (
              <Button disabled={busy !== null} onClick={() => act('refresh')}>
                {busy === 'refresh' ? 'Consultando…' : fiscalActions.refresh.label}
              </Button>
            )}
            {document.has_pdf && (
              <Button variant="secondary" disabled={busy !== null} onClick={() => download('pdf')}>
                {busy === 'pdf' ? 'Baixando…' : 'Baixar PDF'}
              </Button>
            )}
            {document.has_xml && (
              <Button variant="secondary" disabled={busy !== null} onClick={() => download('xml')}>
                {busy === 'xml' ? 'Baixando…' : 'Baixar XML'}
              </Button>
            )}
            {canWrite && ['PENDENTE', 'ERRO', 'EMITIDO'].includes(document.status) && (
              <Button variant="danger" disabled={busy !== null} onClick={() => setCancelling(true)}>
                {fiscalActions.cancel.label}
              </Button>
            )}
          </div>
        </div>
      </Card>
      <Card
        title="Acompanhamento e retornos"
        description="Cada chamada ao provedor e a resposta recebida, em ordem."
      >
        <MasterTable
          label="Retornos do provedor"
          headers={['Quando', 'Ação', 'Situação resultante', 'Retorno do provedor']}
        >
          {document.events.map((event, index) => (
            <tr key={index}>
              <td className="date-cell">{brDateTime(event.created_at)}</td>
              <td>{fiscalEventActions[event.action] || event.action}</td>
              <td>{fiscalStatuses[event.status as FiscalStatus] || event.status}</td>
              <td>
                {Object.keys(event.response).length ? (
                  <pre className="audit-details">{JSON.stringify(event.response, null, 1)}</pre>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          ))}
        </MasterTable>
      </Card>
      {cancelling && (
        <CancelDialog
          document={document}
          onClose={() => setCancelling(false)}
          onDone={(next) => {
            setCancelling(false)
            applied(
              next,
              next.status === 'CANCELADO'
                ? 'Documento cancelado.'
                : 'O provedor não confirmou o cancelamento. Veja o retorno.',
            )
          }}
        />
      )}
    </>
  )
}

function List({ onOpen }: { onOpen: (id: number) => void }) {
  const { request } = useAuth()
  const [filters, setFilters] = useState<FiscalFilters>({ status: '', customer_id: '', offset: 0 })
  const query = useQuery({
    queryKey: ['fiscal', 'list', filters],
    queryFn: () => listFiscal(request, filters),
    retry: false,
  })
  return (
    <Card
      title="Documentos de faturamento"
      description="Do mais recente ao mais antigo, com a situação no provedor."
    >
      <div className="master-filters">
        <Select
          label="Filtrar situação"
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, offset: 0 })}
        >
          <option value="">Todas</option>
          {Object.entries(fiscalStatuses).map(([key, text]) => (
            <option key={key} value={key}>
              {text}
            </option>
          ))}
        </Select>
      </div>
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data.items.length ? (
        <EmptyState
          initial={!filters.status}
          title={filters.status ? 'Nenhum documento nesta situação' : 'Nenhum documento ainda'}
          description={
            filters.status
              ? 'Escolha outra situação para ver os demais documentos.'
              : 'Crie o primeiro documento de faturamento para acompanhar aqui.'
          }
          action={
            filters.status ? (
              <Button
                variant="secondary"
                onClick={() => setFilters({ status: '', customer_id: '', offset: 0 })}
              >
                Limpar filtros
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <MasterTable
            label="Lista de documentos de faturamento"
            headers={['Documento', 'Cliente', 'Período', 'Valor', 'Situação', 'Ações']}
          >
            {query.data.items.map((row) => (
              <tr key={row.id}>
                <td className="code-cell">{row.number || 'nº interno ' + row.id}</td>
                <td>
                  <span className="cell-title">{row.customer.legal_name}</span>
                  <span className="cell-description">{row.description}</span>
                </td>
                <td className="date-cell">
                  {brDate(row.period_start)} a {brDate(row.period_end)}
                </td>
                <td className="date-cell">{brMoney(row.amount)}</td>
                <td>
                  <FiscalBadge status={row.status} />
                  {row.is_simulation && <span className="cell-description">Simulação</span>}
                </td>
                <td>
                  <Button
                    variant="ghost"
                    aria-label={'Abrir documento ' + (row.number || 'nº interno ' + row.id)}
                    onClick={() => onOpen(row.id)}
                  >
                    Abrir
                  </Button>
                </td>
              </tr>
            ))}
          </MasterTable>
          <Pager
            total={query.data.total}
            offset={filters.offset}
            onChange={(offset) => setFilters({ ...filters, offset })}
          />
        </>
      )}
    </Card>
  )
}

export function Fiscal() {
  const { user, request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [creating, setCreating] = useState(false)
  const id = /^[1-9]\d*$/.test(params.get('id') || '') ? Number(params.get('id')) : null
  const canWrite = !!user?.permissions.includes('fiscal.write')
  const provider = useQuery({
    queryKey: ['fiscal', 'provider'],
    queryFn: () => getProvider(request),
    retry: false,
  })
  const mounted = useRef(false)
  useEffect(() => {
    if (mounted.current) document.getElementById('main-content')?.focus()
    mounted.current = true
  }, [id])
  return (
    <>
      <PageHeader
        title="Faturamento e fiscal"
        description="Documentos de faturamento por cliente e período, com o acompanhamento do provedor."
        actions={
          id ? (
            <Button variant="secondary" onClick={() => setParams({})}>
              Voltar para a lista
            </Button>
          ) : (
            canWrite && (
              <Button onClick={() => setCreating(true)}>
                <Plus size={18} aria-hidden="true" />
                Novo documento
              </Button>
            )
          )
        }
      />
      {provider.isPending ? (
        <Skeleton rows={1} />
      ) : provider.isError ? (
        <ErrorState message={provider.error.message} onRetry={() => void provider.refetch()} />
      ) : (
        <ProviderNotice provider={provider.data} />
      )}
      {id ? (
        <Detail key={id} id={id} canWrite={canWrite} />
      ) : (
        <List onOpen={(next) => setParams({ id: String(next) })} />
      )}
      <Modal
        open={creating}
        onOpenChange={setCreating}
        title="Novo documento de faturamento"
        description="Registra o que será faturado. O envio ao provedor é um passo separado."
        className="master-modal"
      >
        {creating && (
          <NewDocument
            onCreated={(next) => {
              setCreating(false)
              toast('Documento criado como pendente.')
              void cache.invalidateQueries({ queryKey: ['fiscal', 'list'] })
              setParams({ id: String(next) })
            }}
          />
        )}
      </Modal>
    </>
  )
}
