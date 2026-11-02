import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  Ban,
  CircleCheck,
  CircleX,
  ClipboardCheck,
  Clock3,
  FileText,
  Package,
  Send,
  Wifi,
} from 'lucide-react'
import { ApiError } from '../auth/api'
import { useAuth } from '../auth/context'
import { contractOrigins, contractStatuses, eventKinds, unitStates } from '../lib/contracts'
import { periods } from '../lib/masters'
import {
  cancelMyRequest,
  downloadPortalDocument,
  downloadPortalQuote,
  getPortalContract,
  getPortalDashboard,
  getPortalEquipment,
  getPortalProfile,
  getPortalQuote,
  listMyRequests,
  listPortalContracts,
  listPortalDocuments,
  listPortalQuotes,
  requestRenewal,
  type PortalContract,
} from '../lib/portal'
import {
  brDate,
  brDateTime,
  brMoney,
  brQuantity,
  quoteStatuses,
  type QuoteStatus,
} from '../lib/quotes'
import { Button } from '../components/Button'
import { ConfirmDialog, Modal } from '../components/Modal'
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
import { ContractBadge, DocumentBadge } from './contracts-shared'
import { Failure, MasterTable } from './masters-shared'
import { PeriodText, RequestBadge } from './portal-shared'

export type PortalView =
  'inicio' | 'contratos' | 'equipamentos' | 'orcamentos' | 'renovacoes' | 'documentos' | 'cadastro'

const renewable = ['ATIVO', 'VENCENDO', 'VENCIDO']
const quoteBadges = {
  RASCUNHO: ['muted', FileText],
  ENVIADO: ['info', Send],
  APROVADO: ['success', CircleCheck],
  REJEITADO: ['danger', CircleX],
  EXPIRADO: ['warning', Clock3],
  CANCELADO: ['muted', Ban],
  CONVERTIDO: ['success', FileText],
} as const
function QuoteTag({ status }: { status: QuoteStatus }) {
  const [tone, icon] = quoteBadges[status]
  return (
    <Tag tone={tone} icon={icon}>
      {quoteStatuses[status]}
    </Tag>
  )
}

/**
 * Loading, error and data of a portal query. An account without a customer link (403) and a
 * record that is not the customer's own (404) are screen states, not failures to retry.
 */
function Loaded<T>({
  query,
  children,
}: {
  query: UseQueryResult<T, Error>
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <Skeleton rows={4} />
  if (query.isError) {
    const error = query.error
    if (error instanceof ApiError && error.status === 403)
      return (
        <Card>
          <EmptyState
            initial
            title="Portal ainda não liberado para esta conta"
            description={error.message}
          />
        </Card>
      )
    if (error instanceof ApiError && error.status === 404)
      return (
        <Card>
          <EmptyState
            title="Registro não encontrado"
            description={error.message + ' Confira o endereço ou volte para a lista.'}
          />
        </Card>
      )
    return <ErrorState message={error.message} onRetry={() => void query.refetch()} />
  }
  return <>{children(query.data)}</>
}

function useDownload() {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState('')
  const run = (key: string, task: () => Promise<void>) => {
    setError('')
    setBusy(key)
    void task()
      .catch((e) => setError(e instanceof Error ? e.message : 'Não foi possível baixar o arquivo.'))
      .finally(() => setBusy(null))
  }
  return { busy, error, run }
}

function RenewalDialog({
  contracts,
  open,
  onOpenChange,
}: {
  contracts: Pick<PortalContract, 'id' | 'number'>[]
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const notesId = useId()
  const [contractId, setContractId] = useState(String(contracts[0]?.id ?? ''))
  const [period, setPeriod] = useState('MENSAL')
  const [count, setCount] = useState('1')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [sending, setSending] = useState(false)
  const chosen = contracts.find((row) => String(row.id) === contractId) || contracts[0]
  async function submit() {
    setError('')
    if (!/^[1-9]\d{0,2}$/.test(count.trim())) {
      setFieldError('Informe um número inteiro de 1 a 999.')
      return
    }
    setFieldError('')
    setSending(true)
    try {
      const created = await requestRenewal(request, {
        contract_id: chosen.id,
        period,
        period_count: Number(count.trim()),
        notes: notes.trim(),
      })
      toast(
        'Solicitação enviada para o contrato ' +
          created.contract_number +
          '. Aguarde a análise da locadora.',
      )
      void cache.invalidateQueries({ queryKey: ['portal'] })
      onOpenChange(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível enviar a solicitação.')
    } finally {
      setSending(false)
    }
  }
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Solicitar renovação"
      description="Envie um pedido de renovação para a locadora analisar."
    >
      <form
        className="form-stack"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          void submit()
        }}
      >
        <p className="quote-notice" role="note">
          Este é um pedido, não uma renovação. O contrato só é renovado depois que a locadora
          analisar e aprovar; preços e condições são confirmados por ela.
        </p>
        {contracts.length > 1 ? (
          <Select
            label="Contrato"
            value={String(chosen.id)}
            onChange={(e) => setContractId(e.target.value)}
          >
            {contracts.map((row) => (
              <option key={row.id} value={row.id}>
                Contrato {row.number}
              </option>
            ))}
          </Select>
        ) : (
          <p>
            Contrato <strong>{chosen.number}</strong>
          </p>
        )}
        <div className="master-form-grid">
          <Select
            label="Período desejado"
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
          >
            {Object.entries(periods).map(([key, text]) => (
              <option key={key} value={key}>
                {text}
              </option>
            ))}
          </Select>
          <Field
            label="Quantidade de períodos"
            inputMode="numeric"
            maxLength={3}
            value={count}
            error={fieldError}
            onChange={(e) => setCount(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor={notesId}>Observações para a locadora</label>
          <textarea
            id={notesId}
            rows={3}
            maxLength={500}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <p className="field-hint">Opcional · até 500 caracteres.</p>
        </div>
        <Failure message={error} />
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Voltar
          </Button>
          <Button type="submit" disabled={sending}>
            {sending ? 'Enviando…' : 'Enviar solicitação'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function ContractRows({ rows, label }: { rows: PortalContract[]; label: string }) {
  return (
    <MasterTable
      label={label}
      headers={['Contrato', 'Início', 'Devolução prevista', 'Total', 'Situação', 'Ações']}
    >
      {rows.map((row) => (
        <tr key={row.id}>
          <td className="code-cell">{row.number}</td>
          <td className="date-cell">{brDate(row.start_date)}</td>
          <td className="date-cell">{brDate(row.due_date || row.end_date)}</td>
          <td className="date-cell">{brMoney(row.total)}</td>
          <td>
            <ContractBadge status={row.status} />
          </td>
          <td>
            <Button asChild variant="ghost">
              <Link
                to={'/portal/contratos?id=' + row.id}
                aria-label={'Abrir contrato ' + row.number}
              >
                Abrir
              </Link>
            </Button>
          </td>
        </tr>
      ))}
    </MasterTable>
  )
}

function Home() {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['portal', 'dashboard'],
    queryFn: () => getPortalDashboard(request),
    retry: false,
  })
  return (
    <>
      <p className="quote-notice portal-note" role="note">
        <span>
          <Wifi size={16} aria-hidden="true" /> Este portal funciona na rede local da locadora. O
          acesso pela internet é uma etapa futura.
        </span>
      </p>
      <Loaded query={query}>
        {(data) => (
          <>
            <div className="metrics-grid" role="list" aria-label="Indicadores">
              {[
                {
                  label: 'Contratos ativos',
                  value: String(data.active_contracts),
                  detail: 'Locações em andamento',
                  icon: FileText,
                  tone: 'blue',
                },
                {
                  label: 'Itens locados',
                  value: brQuantity(data.rented_items),
                  detail: 'Com você neste momento',
                  icon: Package,
                  tone: 'violet',
                },
                {
                  label: 'Solicitações em análise',
                  value: String(data.pending_requests),
                  detail: 'Pedidos de renovação aguardando a locadora',
                  icon: ClipboardCheck,
                  tone: 'amber',
                },
              ].map((metric) => (
                <div role="listitem" className="card metric-card" key={metric.label}>
                  <div className="metric-top">
                    <span>{metric.label}</span>
                    <span className={`metric-icon tone-${metric.tone}`}>
                      <metric.icon size={20} aria-hidden="true" />
                    </span>
                  </div>
                  <strong className="metric-value">{metric.value}</strong>
                  <p>{metric.detail}</p>
                </div>
              ))}
            </div>
            <Card
              title="Próximas devoluções"
              description="Seus contratos ativos, pela data de devolução prevista."
              action={
                <Link className="text-link" to="/portal/contratos">
                  Ver meus contratos
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
              }
            >
              {data.next_due.length ? (
                <ContractRows rows={data.next_due} label="Lista das próximas devoluções" />
              ) : (
                <EmptyState
                  initial
                  title="Nenhuma devolução prevista"
                  description="Quando houver contrato ativo, a data de devolução aparece aqui."
                />
              )}
            </Card>
          </>
        )}
      </Loaded>
    </>
  )
}

function ContractDetail({ id }: { id: number }) {
  const { request } = useAuth()
  const download = useDownload()
  const [asking, setAsking] = useState(false)
  const query = useQuery({
    queryKey: ['portal', 'contract', id],
    queryFn: () => getPortalContract(request, id),
    retry: false,
  })
  return (
    <Loaded query={query}>
      {(contract) => (
        <>
          <Card
            title={'Contrato ' + contract.number}
            description="Dados registrados pela locadora."
            action={<ContractBadge status={contract.status} />}
          >
            <div className="padded form-stack">
              <dl className="master-details">
                <div>
                  <dt>Origem</dt>
                  <dd>{contractOrigins[contract.origin] || contract.origin}</dd>
                </div>
                <div>
                  <dt>Início</dt>
                  <dd>{brDate(contract.start_date)}</dd>
                </div>
                <div>
                  <dt>Devolução prevista</dt>
                  <dd>{brDate(contract.due_date || contract.end_date)}</dd>
                </div>
                <div>
                  <dt>Valor contratado</dt>
                  <dd>{brMoney(contract.total)}</dd>
                </div>
              </dl>
              {renewable.includes(contract.status) && (
                <div className="row-actions">
                  <Button onClick={() => setAsking(true)}>Solicitar renovação</Button>
                </div>
              )}
              <p className="field-hint">
                A solicitação de renovação é um pedido sujeito à aprovação da locadora.
              </p>
            </div>
          </Card>
          <Card title="Itens" description="Quantidades contratadas e o que está com você.">
            <MasterTable
              label={'Itens do contrato ' + contract.number}
              headers={['Produto', 'Contratado', 'Período', 'Preço', 'Total', 'Com você']}
            >
              {contract.items.map((item, index) => (
                <tr key={index}>
                  <td>
                    <span className="cell-title">{item.product_name}</span>
                    <span className="cell-description">{item.product_code}</span>
                    {!!item.units.length && (
                      <ul
                        className="contract-units"
                        aria-label={'Unidades de ' + item.product_name}
                      >
                        {item.units.map((unit) => (
                          <li key={unit.code}>
                            {unit.code} ·{' '}
                            {unitStates[unit.state as keyof typeof unitStates] || unit.state}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td className="date-cell">
                    {brQuantity(item.quantity)} {item.unit}
                  </td>
                  <td>
                    <PeriodText period={item.period} count={item.period_count} />
                    <span className="cell-description">
                      {brDate(item.start_date)} a {brDate(item.end_date)}
                    </span>
                  </td>
                  <td className="date-cell">{brMoney(item.unit_price)}</td>
                  <td className="date-cell">{brMoney(item.total)}</td>
                  <td className="date-cell">
                    {brQuantity(item.outstanding)} {item.unit}
                    <span className="cell-description">
                      Retirado {brQuantity(item.withdrawn)} · devolvido {brQuantity(item.returned)}
                    </span>
                  </td>
                </tr>
              ))}
            </MasterTable>
          </Card>
          <Card title="Documentos" description="PDFs gerados pela locadora para este contrato.">
            <div className="padded">
              <Failure message={download.error} />
            </div>
            {contract.documents.length ? (
              <MasterTable
                label={'Documentos do contrato ' + contract.number}
                headers={['Versão', 'Gerado em', 'Situação', 'Ações']}
              >
                {contract.documents.map((document) => (
                  <tr key={document.id}>
                    <td>v{document.version}</td>
                    <td className="date-cell">{brDateTime(document.created_at)}</td>
                    <td>
                      <DocumentBadge status={document.status} />
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        disabled={download.busy !== null}
                        aria-label={'Baixar versão ' + document.version}
                        onClick={() =>
                          download.run('d' + document.id, () =>
                            downloadPortalDocument({
                              ...document,
                              contract_number: contract.number,
                            }),
                          )
                        }
                      >
                        {download.busy === 'd' + document.id ? 'Baixando…' : 'Baixar PDF'}
                      </Button>
                    </td>
                  </tr>
                ))}
              </MasterTable>
            ) : (
              <EmptyState
                initial
                title="Nenhum documento disponível"
                description="Quando a locadora gerar o documento do contrato, ele aparece aqui."
              />
            )}
          </Card>
          {contract.chain.length > 1 && (
            <Card title="Renovações deste contrato" description="O contrato e suas renovações.">
              <MasterTable
                label={'Cadeia do contrato ' + contract.number}
                headers={['Contrato', 'Início', 'Devolução prevista', 'Total', 'Situação']}
              >
                {contract.chain.map((link) => (
                  <tr key={link.id}>
                    <td className="code-cell">
                      {link.id === contract.id ? (
                        link.number
                      ) : (
                        <Link
                          to={'/portal/contratos?id=' + link.id}
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
          )}
          <Card title="Histórico" description="Eventos registrados neste contrato.">
            {contract.events.length ? (
              <ol
                className="contract-timeline"
                aria-label={'Histórico do contrato ' + contract.number}
              >
                {contract.events.map((event, index) => (
                  <li key={index}>
                    <strong>{eventKinds[event.kind] || event.kind}</strong>
                    <span>{event.description}</span>
                    <span className="contract-timeline-when">{brDateTime(event.created_at)}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState initial title="Sem eventos" description="Nada registrado ainda." />
            )}
          </Card>
          {asking && (
            <RenewalDialog contracts={[contract]} open={asking} onOpenChange={setAsking} />
          )}
        </>
      )}
    </Loaded>
  )
}

function Contracts() {
  const { request } = useAuth()
  const [status, setStatus] = useState('')
  const query = useQuery({
    queryKey: ['portal', 'contracts', status],
    queryFn: () => listPortalContracts(request, status),
    retry: false,
  })
  return (
    <Card title="Contratos em seu nome" description="Contratos confirmados pela locadora.">
      <div className="master-filters">
        <Select label="Filtrar situação" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Todas</option>
          {Object.entries(contractStatuses)
            .filter(([key]) => key !== 'RASCUNHO')
            .map(([key, text]) => (
              <option key={key} value={key}>
                {text}
              </option>
            ))}
        </Select>
      </div>
      <Loaded query={query}>
        {(data) =>
          data.items.length ? (
            <ContractRows rows={data.items} label="Meus contratos" />
          ) : (
            <EmptyState
              initial={!status}
              title={status ? 'Nenhum contrato nesta situação' : 'Nenhum contrato ainda'}
              description={
                status
                  ? 'Escolha outra situação para ver os demais contratos.'
                  : 'Quando a locadora confirmar um contrato em seu nome, ele aparece aqui.'
              }
              action={
                status ? (
                  <Button variant="secondary" onClick={() => setStatus('')}>
                    Limpar filtro
                  </Button>
                ) : undefined
              }
            />
          )
        }
      </Loaded>
    </Card>
  )
}

function Equipment() {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['portal', 'equipment'],
    queryFn: () => getPortalEquipment(request),
    retry: false,
  })
  return (
    <Card title="Com você agora" description="Itens retirados e ainda não devolvidos.">
      <Loaded query={query}>
        {(data) =>
          data.items.length ? (
            <MasterTable
              label="Meus equipamentos"
              headers={['Produto', 'Quantidade', 'Unidades', 'Contrato', 'Devolução prevista']}
            >
              {data.items.map((item, index) => (
                <tr key={index}>
                  <td>
                    <span className="cell-title">{item.product_name}</span>
                    <span className="cell-description">{item.product_code}</span>
                  </td>
                  <td className="date-cell">
                    {brQuantity(item.quantity)} {item.unit}
                  </td>
                  <td>{item.units.length ? item.units.join(', ') : '—'}</td>
                  <td className="code-cell">
                    <Link
                      to={'/portal/contratos?id=' + item.contract_id}
                      aria-label={'Abrir contrato ' + item.contract_number}
                    >
                      {item.contract_number}
                    </Link>
                  </td>
                  <td className="date-cell">{brDate(item.due_date)}</td>
                </tr>
              ))}
            </MasterTable>
          ) : (
            <EmptyState
              initial
              title="Nenhum equipamento com você"
              description="Os itens aparecem aqui depois da retirada e saem após a devolução."
            />
          )
        }
      </Loaded>
    </Card>
  )
}

function QuoteDetail({ id }: { id: number }) {
  const { request } = useAuth()
  const download = useDownload()
  const query = useQuery({
    queryKey: ['portal', 'quote', id],
    queryFn: () => getPortalQuote(request, id),
    retry: false,
  })
  return (
    <Loaded query={query}>
      {(quote) => (
        <Card
          title={'Orçamento ' + quote.number}
          description={
            'Início previsto em ' +
            brDate(quote.start_date) +
            ' · válido até ' +
            brDate(quote.valid_until)
          }
          action={<QuoteTag status={quote.status} />}
        >
          <MasterTable
            label={'Itens do orçamento ' + quote.number}
            headers={['Produto', 'Quantidade', 'Período', 'Preço', 'Total']}
          >
            {quote.items.map((item, index) => (
              <tr key={index}>
                <td>
                  <span className="cell-title">{item.product_name}</span>
                  <span className="cell-description">{item.product_code}</span>
                </td>
                <td className="date-cell">
                  {brQuantity(item.quantity)} {item.unit}
                </td>
                <td>
                  <PeriodText period={item.period} count={item.period_count} />
                  <span className="cell-description">até {brDate(item.end_date)}</span>
                </td>
                <td className="date-cell">{brMoney(item.unit_price)}</td>
                <td className="date-cell">{brMoney(item.total)}</td>
              </tr>
            ))}
          </MasterTable>
          <div className="padded form-stack">
            <p>
              Total do orçamento: <strong>{brMoney(quote.total)}</strong>
            </p>
            <Failure message={download.error} />
            <div className="row-actions">
              <Button
                variant="secondary"
                disabled={download.busy !== null}
                onClick={() => download.run('q', () => downloadPortalQuote(quote))}
              >
                {download.busy ? 'Gerando PDF…' : 'Baixar PDF'}
              </Button>
            </div>
            <p className="field-hint">
              Para aprovar ou ajustar este orçamento, fale com a locadora.
            </p>
          </div>
        </Card>
      )}
    </Loaded>
  )
}

function Quotes() {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['portal', 'quotes'],
    queryFn: () => listPortalQuotes(request),
    retry: false,
  })
  return (
    <Card title="Orçamentos recebidos" description="Orçamentos enviados pela locadora para você.">
      <Loaded query={query}>
        {(data) =>
          data.items.length ? (
            <MasterTable
              label="Orçamentos"
              headers={['Número', 'Início previsto', 'Validade', 'Total', 'Situação', 'Ações']}
            >
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td className="code-cell">{row.number}</td>
                  <td className="date-cell">{brDate(row.start_date)}</td>
                  <td className="date-cell">{brDate(row.valid_until)}</td>
                  <td className="date-cell">{brMoney(row.total)}</td>
                  <td>
                    <QuoteTag status={row.status} />
                  </td>
                  <td>
                    <Button asChild variant="ghost">
                      <Link
                        to={'/portal/orcamentos?id=' + row.id}
                        aria-label={'Abrir orçamento ' + row.number}
                      >
                        Abrir
                      </Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </MasterTable>
          ) : (
            <EmptyState
              initial
              title="Nenhum orçamento enviado"
              description="Quando a locadora enviar um orçamento para você, ele aparece aqui."
            />
          )
        }
      </Loaded>
    </Card>
  )
}

function Renewals() {
  const { request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const requests = useQuery({
    queryKey: ['portal', 'requests'],
    queryFn: () => listMyRequests(request),
    retry: false,
  })
  const contracts = useQuery({
    queryKey: ['portal', 'contracts', ''],
    queryFn: () => listPortalContracts(request, ''),
    retry: false,
  })
  const pending = new Set(
    (requests.data?.items || [])
      .filter((row) => row.status === 'PENDENTE')
      .map((row) => row.contract_id),
  )
  const available = (contracts.data?.items || []).filter(
    (row) => renewable.includes(row.status) && !pending.has(row.id),
  )
  return (
    <>
      <p className="quote-notice" role="note">
        Solicitar renovação é fazer um pedido à locadora. O contrato só é renovado depois que ela
        analisar e aprovar; até lá, as datas e os valores do contrato continuam os mesmos.
      </p>
      <Card
        title="Minhas solicitações"
        description="Pedidos de renovação e a resposta da locadora."
        action={
          available.length ? (
            <Button onClick={() => setAsking(true)}>Solicitar renovação</Button>
          ) : undefined
        }
      >
        <div className="padded">
          <Failure message={error} />
          {contracts.isSuccess && !available.length && (
            <p className="field-hint">
              Não há contrato ativo sem solicitação em análise para pedir renovação agora.
            </p>
          )}
        </div>
        <Loaded query={requests}>
          {(data) =>
            data.items.length ? (
              <MasterTable
                label="Minhas solicitações de renovação"
                headers={['Contrato', 'Período pedido', 'Enviada em', 'Situação', 'Ações']}
              >
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="code-cell">
                      <Link
                        to={'/portal/contratos?id=' + row.contract_id}
                        aria-label={'Abrir contrato ' + row.contract_number}
                      >
                        {row.contract_number}
                      </Link>
                    </td>
                    <td>
                      <PeriodText period={row.period} count={row.period_count} />
                      {row.notes && <span className="cell-description">{row.notes}</span>}
                    </td>
                    <td className="date-cell">{brDateTime(row.created_at)}</td>
                    <td>
                      <RequestBadge status={row.status} />
                      {row.status === 'APROVADA' && (
                        <span className="cell-description">
                          Aprovada: a locadora fará a renovação do contrato.
                        </span>
                      )}
                      {row.decision_reason && (
                        <span className="cell-description">Motivo: {row.decision_reason}</span>
                      )}
                    </td>
                    <td>
                      {row.status === 'PENDENTE' ? (
                        <ConfirmDialog
                          title="Cancelar solicitação?"
                          description={
                            'O pedido de renovação do contrato ' +
                            row.contract_number +
                            ' deixa de ser analisado pela locadora. Você pode enviar outro depois.'
                          }
                          confirmLabel="Cancelar solicitação"
                          trigger={
                            <Button
                              variant="secondary"
                              disabled={busy}
                              aria-label={'Cancelar solicitação do contrato ' + row.contract_number}
                            >
                              Cancelar
                            </Button>
                          }
                          onConfirm={() => {
                            setError('')
                            setBusy(true)
                            void cancelMyRequest(request, row.id)
                              .then(() => {
                                toast('Solicitação cancelada.')
                                return cache.invalidateQueries({ queryKey: ['portal'] })
                              })
                              .catch((e) =>
                                setError(
                                  e instanceof Error ? e.message : 'Não foi possível cancelar.',
                                ),
                              )
                              .finally(() => setBusy(false))
                          }}
                        />
                      ) : (
                        <span className="cell-description">Sem ações</span>
                      )}
                    </td>
                  </tr>
                ))}
              </MasterTable>
            ) : (
              <EmptyState
                initial
                title="Nenhuma solicitação enviada"
                description="Peça a renovação de um contrato ativo e acompanhe a resposta aqui."
              />
            )
          }
        </Loaded>
      </Card>
      {asking && !!available.length && (
        <RenewalDialog contracts={available} open={asking} onOpenChange={setAsking} />
      )}
    </>
  )
}

function Documents() {
  const { request } = useAuth()
  const download = useDownload()
  const query = useQuery({
    queryKey: ['portal', 'documents'],
    queryFn: () => listPortalDocuments(request),
    retry: false,
  })
  return (
    <Card title="Documentos dos contratos" description="PDFs gerados pela locadora.">
      <div className="padded">
        <Failure message={download.error} />
      </div>
      <Loaded query={query}>
        {(data) =>
          data.items.length ? (
            <MasterTable
              label="Documentos"
              headers={['Contrato', 'Versão', 'Gerado em', 'Assinado em', 'Situação', 'Ações']}
            >
              {data.items.map((document) => (
                <tr key={document.id}>
                  <td className="code-cell">
                    <Link
                      to={'/portal/contratos?id=' + document.contract_id}
                      aria-label={'Abrir contrato ' + document.contract_number}
                    >
                      {document.contract_number}
                    </Link>
                  </td>
                  <td>v{document.version}</td>
                  <td className="date-cell">{brDateTime(document.created_at)}</td>
                  <td className="date-cell">
                    {document.signed_at ? brDateTime(document.signed_at) : '—'}
                  </td>
                  <td>
                    <DocumentBadge status={document.status} />
                  </td>
                  <td>
                    <Button
                      variant="ghost"
                      disabled={download.busy !== null}
                      aria-label={
                        'Baixar documento do contrato ' +
                        document.contract_number +
                        ', versão ' +
                        document.version
                      }
                      onClick={() =>
                        download.run('d' + document.id, () => downloadPortalDocument(document))
                      }
                    >
                      {download.busy === 'd' + document.id ? 'Baixando…' : 'Baixar PDF'}
                    </Button>
                  </td>
                </tr>
              ))}
            </MasterTable>
          ) : (
            <EmptyState
              initial
              title="Nenhum documento disponível"
              description="Os documentos dos seus contratos aparecem aqui quando forem gerados."
            />
          )
        }
      </Loaded>
    </Card>
  )
}

function Registration() {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['portal', 'profile'],
    queryFn: () => getPortalProfile(request),
    retry: false,
  })
  const text = (value: string) => value || 'Não informado'
  return (
    <Loaded query={query}>
      {(profile) => (
        <Card
          title="Dados do cadastro"
          description="Somente leitura. Para corrigir algum dado, fale com a locadora."
        >
          <div className="padded form-stack">
            <dl className="master-details">
              {(
                [
                  [
                    'Tipo de pessoa',
                    profile.person_type === 'PJ' ? 'Pessoa jurídica' : 'Pessoa física',
                  ],
                  ['Nome / razão social', profile.legal_name],
                  ['Nome fantasia', text(profile.trade_name)],
                  ['CPF / CNPJ', profile.document],
                  ['Inscrição estadual', text(profile.state_registration)],
                  ['Telefone', text(profile.phone)],
                  ['Celular', text(profile.mobile)],
                  ['E-mail', text(profile.email)],
                  ['Contato responsável', text(profile.contact)],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
            <section aria-label="Endereços" className="form-stack">
              <h3>Endereços</h3>
              {profile.addresses.length ? (
                <ul className="contract-review">
                  {profile.addresses.map((address, index) => (
                    <li key={index}>
                      <strong>{address.label}:</strong> {address.street}, {address.city} /{' '}
                      {address.state} · CEP {address.postal_code}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>Nenhum endereço cadastrado.</p>
              )}
            </section>
          </div>
        </Card>
      )}
    </Loaded>
  )
}

const views: Record<PortalView, { title: string; description: string }> = {
  inicio: {
    title: 'Portal do cliente',
    description: 'Seus contratos, equipamentos e documentos com a locadora.',
  },
  contratos: {
    title: 'Meus contratos',
    description: 'Consulte seus contratos, itens, documentos e histórico.',
  },
  equipamentos: {
    title: 'Meus equipamentos',
    description: 'O que está com você e quando deve ser devolvido.',
  },
  orcamentos: { title: 'Orçamentos', description: 'Orçamentos que a locadora enviou para você.' },
  renovacoes: {
    title: 'Renovações',
    description: 'Peça a renovação de um contrato e acompanhe a resposta.',
  },
  documentos: { title: 'Documentos', description: 'Baixe os PDFs dos seus contratos.' },
  cadastro: { title: 'Meu cadastro', description: 'Os dados que a locadora tem sobre você.' },
}

export function Portal({ view }: { view: PortalView }) {
  const [params, setParams] = useSearchParams()
  const id = /^[1-9]\d*$/.test(params.get('id') || '') ? Number(params.get('id')) : null
  const detail = id !== null && (view === 'contratos' || view === 'orcamentos')
  const place = view + ':' + (id ?? '')
  const mounted = useRef(false)
  useEffect(() => {
    // Detail and list share a route, so focus moves to the content like a page change.
    if (mounted.current) document.getElementById('main-content')?.focus()
    mounted.current = true
  }, [place])
  const { title, description } = views[view]
  return (
    <>
      <PageHeader
        title={title}
        description={description}
        actions={
          detail && (
            <Button variant="secondary" onClick={() => setParams({})}>
              Voltar para a lista
            </Button>
          )
        }
      />
      {view === 'inicio' && <Home />}
      {view === 'contratos' && (id ? <ContractDetail key={id} id={id} /> : <Contracts />)}
      {view === 'equipamentos' && <Equipment />}
      {view === 'orcamentos' && (id ? <QuoteDetail key={id} id={id} /> : <Quotes />)}
      {view === 'renovacoes' && <Renewals />}
      {view === 'documentos' && <Documents />}
      {view === 'cadastro' && <Registration />}
    </>
  )
}
