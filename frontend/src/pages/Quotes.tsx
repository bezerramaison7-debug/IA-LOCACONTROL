import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useAuth } from '../auth/context'
import { brDate, brMoney, getQuote, listQuotes, quoteStatuses, type Quote } from '../lib/quotes'
import { Button } from '../components/Button'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { MasterTable, Pager } from './masters-shared'
import { QuoteBadge, QuoteDetail } from './quotes-detail'
import { QuoteEditor } from './quotes-editor'

type Filters = { q: string; status: string; offset: number }

function QuoteList({
  filters,
  setFilters,
  canWrite,
  onOpen,
  onEdit,
  onNew,
}: {
  filters: Filters
  setFilters: (filters: Filters) => void
  canWrite: boolean
  onOpen: (id: number) => void
  onEdit: (id: number) => void
  onNew: () => void
}) {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['quotes', 'list', filters],
    queryFn: () => listQuotes(request, filters),
    retry: false,
  })
  const filtered = !!filters.q || !!filters.status
  return (
    <Card title="Lista de orçamentos">
      <div className="master-filters">
        <Field
          label="Buscar em orçamentos"
          value={filters.q}
          maxLength={160}
          placeholder="Cliente, documento ou número"
          onChange={(e) => setFilters({ ...filters, q: e.target.value, offset: 0 })}
        />
        <Select
          label="Filtrar situação"
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, offset: 0 })}
        >
          <option value="">Todas</option>
          {Object.entries(quoteStatuses).map(([key, text]) => (
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
        filtered ? (
          <EmptyState
            title="Nenhum orçamento encontrado"
            description="Experimente outro termo ou ajuste a situação."
            action={
              <Button
                variant="secondary"
                onClick={() => setFilters({ q: '', status: '', offset: 0 })}
              >
                Limpar filtros
              </Button>
            }
          />
        ) : (
          <EmptyState
            initial
            title="Nenhum orçamento ainda"
            description={
              canWrite
                ? 'Crie o primeiro orçamento com cliente, itens e preços de tabela.'
                : 'Quando houver orçamentos, eles aparecerão aqui.'
            }
            action={
              canWrite ? (
                <Button variant="secondary" onClick={onNew}>
                  Criar orçamento
                </Button>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <MasterTable
            label="Orçamentos"
            headers={['Número', 'Cliente', 'Início', 'Validade', 'Total', 'Situação', 'Ações']}
          >
            {query.data.items.map((row) => (
              <tr key={row.id}>
                <td className="code-cell">{row.number}</td>
                <td>
                  <span className="cell-title">{row.customer.legal_name}</span>
                  <span className="cell-description">
                    {row.customer.document} · {row.item_count}{' '}
                    {row.item_count === 1 ? 'item' : 'itens'}
                  </span>
                </td>
                <td className="date-cell">{brDate(row.start_date)}</td>
                <td className="date-cell">{brDate(row.valid_until)}</td>
                <td className="date-cell">{brMoney(row.total)}</td>
                <td>
                  <QuoteBadge status={row.status} />
                </td>
                <td>
                  <div className="row-actions">
                    <Button
                      variant="ghost"
                      aria-label={'Abrir ' + row.number}
                      onClick={() => onOpen(row.id)}
                    >
                      Abrir
                    </Button>
                    {canWrite && row.status === 'RASCUNHO' && (
                      <Button
                        variant="ghost"
                        aria-label={'Editar ' + row.number}
                        onClick={() => onEdit(row.id)}
                      >
                        Editar
                      </Button>
                    )}
                  </div>
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

function DraftEditor({
  id,
  onSaved,
  onBack,
}: {
  id: number
  onSaved: (quote: Quote) => void
  onBack: () => void
}) {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['quotes', 'detail', id],
    queryFn: () => getQuote(request, id),
    retry: false,
  })
  const back = (
    <Button variant="secondary" onClick={onBack}>
      Voltar ao orçamento
    </Button>
  )
  if (query.isPending)
    return (
      <>
        <PageHeader title="Editar orçamento" description="Carregando o rascunho." actions={back} />
        <Skeleton rows={4} />
      </>
    )
  if (query.isError)
    return (
      <>
        <PageHeader title="Editar orçamento" description="Não foi possível abrir." actions={back} />
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      </>
    )
  const quote = query.data
  return (
    <>
      <PageHeader
        title={'Editar orçamento ' + quote.number}
        description="Altere o rascunho. O salvamento é auditado e confere a versão atual."
        actions={back}
      />
      {quote.status !== 'RASCUNHO' ? (
        <ErrorState
          message={
            'Somente rascunhos podem ser editados. Este orçamento está ' +
            quoteStatuses[quote.status].toLocaleLowerCase('pt-BR') +
            ': reabra ou duplique para alterar.'
          }
        />
      ) : (
        <QuoteEditor
          key={quote.id + ':' + quote.version}
          quote={quote}
          onSaved={onSaved}
          onCancel={onBack}
          onReload={() => void query.refetch()}
        />
      )}
    </>
  )
}

export function Quotes() {
  const { user } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState<Filters>({ q: '', status: '', offset: 0 })
  const [duplicated, setDuplicated] = useState<{ id: number; warnings: string[] } | null>(null)
  const canRead = !!user?.permissions.includes('quotes.read')
  const canWrite = !!user?.permissions.includes('quotes.write')
  const id = /^[1-9]\d*$/.test(params.get('id') || '') ? Number(params.get('id')) : null
  const view = params.has('novo') ? 'new' : id ? (params.has('editar') ? 'edit' : 'detail') : 'list'
  const place = view + ':' + (id ?? '')
  const mounted = useRef(false)
  useEffect(() => {
    // Views change without a route change, so focus moves to the content like a page change.
    if (mounted.current) document.getElementById('main-content')?.focus()
    mounted.current = true
  }, [place])
  const openList = () => setParams({})
  const openDetail = (quoteId: number) => setParams({ id: String(quoteId) })
  const openEdit = (quoteId: number) => setParams({ id: String(quoteId), editar: '1' })
  const openNew = () => setParams({ novo: '1' })
  const saved = (quote: Quote) => {
    toast('Orçamento ' + quote.number + ' salvo como rascunho.')
    void cache.invalidateQueries({ queryKey: ['quotes'] })
    openDetail(quote.id)
  }
  if (!canRead)
    return (
      <>
        <PageHeader title="Orçamentos" description="Propostas de locação." />
        <ErrorState message="Seu perfil não tem permissão para consultar orçamentos." />
      </>
    )
  if ((view === 'new' || view === 'edit') && !canWrite)
    return (
      <>
        <PageHeader
          title="Orçamentos"
          description="Propostas de locação."
          actions={
            <Button variant="secondary" onClick={openList}>
              Voltar para a lista
            </Button>
          }
        />
        <ErrorState message="Seu perfil não tem permissão para criar ou editar orçamentos." />
      </>
    )
  if (view === 'new')
    return (
      <>
        <PageHeader
          title="Novo orçamento"
          description="Monte a proposta com preços de tabela. Orçamento não reserva estoque."
          actions={
            <Button variant="secondary" onClick={openList}>
              Voltar para a lista
            </Button>
          }
        />
        <QuoteEditor onSaved={saved} onCancel={openList} />
      </>
    )
  if (view === 'edit' && id)
    return <DraftEditor key={id} id={id} onSaved={saved} onBack={() => openDetail(id)} />
  if (view === 'detail' && id)
    return (
      <QuoteDetail
        key={id}
        id={id}
        warnings={duplicated?.id === id ? duplicated.warnings : null}
        onBack={openList}
        onEdit={() => openEdit(id)}
        onDuplicated={(quote, warnings) => {
          setDuplicated({ id: quote.id, warnings })
          openDetail(quote.id)
        }}
      />
    )
  return (
    <>
      <PageHeader
        title="Orçamentos"
        description="Propostas reais com preço de tabela, validade e histórico. Orçamento não reserva estoque."
        actions={
          canWrite && (
            <Button onClick={openNew}>
              <Plus size={18} aria-hidden="true" />
              Novo orçamento
            </Button>
          )
        }
      />
      <QuoteList
        filters={filters}
        setFilters={setFilters}
        canWrite={canWrite}
        onOpen={openDetail}
        onEdit={openEdit}
        onNew={openNew}
      />
    </>
  )
}
