import { useState } from 'react'
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Eye,
  Search,
} from 'lucide-react'
import { Badge, EmptyState, Skeleton, ErrorState } from './ui'
import { Button } from './Button'
import { Modal } from './Modal'
import { displayDate, type DemoRow } from '../demo/data'

type SortKey = 'id' | 'name' | 'date'
export function DataTable({
  rows,
  title,
  nameLabel = 'Cliente / equipamentos',
  detailLabel = 'Período',
  dateLabel = 'Vencimento',
  loading = false,
  error,
  onRetry,
}: {
  rows: DemoRow[]
  title: string
  nameLabel?: string
  detailLabel?: string
  dateLabel?: string
  loading?: boolean
  error?: string
  onRetry?: () => void
}) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('Todos')
  const [sort, setSort] = useState<{ key: SortKey; ascending: boolean }>({
    key: 'date',
    ascending: true,
  })
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(5)
  const filtered = rows
    .filter(
      (row) =>
        `${row.id} ${row.name} ${row.secondary}`
          .toLocaleLowerCase('pt-BR')
          .includes(search.toLocaleLowerCase('pt-BR')) &&
        (status === 'Todos' || status === row.status),
    )
    .sort(
      (a, b) =>
        a[sort.key].localeCompare(b[sort.key], 'pt-BR', { numeric: true }) *
        (sort.ascending ? 1 : -1),
    )
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize))
  const currentPage = Math.min(page, totalPages)
  const visible = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize)
  function resetFilters() {
    setSearch('')
    setStatus('Todos')
    setPage(1)
  }
  function sortBy(key: SortKey) {
    setSort({ key, ascending: sort.key === key ? !sort.ascending : true })
    setPage(1)
  }
  function sortable(key: SortKey, label: string) {
    const Icon = sort.key === key ? (sort.ascending ? ArrowUp : ArrowDown) : ArrowUpDown
    return (
      <th
        scope="col"
        aria-sort={sort.key === key ? (sort.ascending ? 'ascending' : 'descending') : 'none'}
      >
        <button className="sort-button" onClick={() => sortBy(key)}>
          {label}
          <Icon size={14} aria-hidden="true" />
        </button>
      </th>
    )
  }

  return (
    <div className="data-table">
      <div className="table-toolbar">
        <label className="search-field">
          <Search size={18} aria-hidden="true" />
          <span className="sr-only">Buscar em {title}</span>
          <input
            value={search}
            onChange={(e) => {
              setSearch(e.target.value)
              setPage(1)
            }}
            placeholder="Buscar por nome ou código…"
          />
        </label>
        <label className="filter-select">
          <span>Status</span>
          <select
            aria-label={`Filtrar status em ${title}`}
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <option>Todos</option>
            {[...new Set(rows.map((row) => row.status))].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        {(search || status !== 'Todos') && (
          <Button variant="ghost" onClick={resetFilters}>
            Limpar filtros
          </Button>
        )}
      </div>
      {loading ? (
        <Skeleton rows={4} />
      ) : error ? (
        <ErrorState message={error} onRetry={onRetry} />
      ) : !filtered.length ? (
        <EmptyState
          action={
            <Button variant="secondary" onClick={resetFilters}>
              Limpar filtros
            </Button>
          }
        />
      ) : (
        <>
          <div className="table-scroll" tabIndex={0} role="region" aria-label={`Tabela ${title}`}>
            <table>
              <caption className="sr-only">{title} — dados fictícios de demonstração</caption>
              <thead>
                <tr>
                  {sortable('id', 'Código')}
                  {sortable('name', nameLabel)}
                  <th scope="col">{detailLabel}</th>
                  {sortable('date', dateLabel)}
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="sr-only">Ações</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id}>
                    <td className="code-cell">{row.id}</td>
                    <td>
                      <span className="cell-title">{row.name}</span>
                      <span className="cell-description">{row.secondary}</span>
                    </td>
                    <td>{row.detail}</td>
                    <td className="date-cell">{displayDate(row.date)}</td>
                    <td>
                      <Badge status={row.status} />
                    </td>
                    <td>
                      <Modal
                        title={`Detalhes de ${row.id}`}
                        description="Registro fictício da demonstração visual. Nenhum dado comercial foi consultado."
                        trigger={
                          <Button variant="ghost" iconOnly aria-label={`Ver detalhes de ${row.id}`}>
                            <Eye size={18} aria-hidden="true" />
                          </Button>
                        }
                      >
                        <dl className="detail-list">
                          <div>
                            <dt>Nome</dt>
                            <dd>{row.name}</dd>
                          </div>
                          <div>
                            <dt>Descrição</dt>
                            <dd>{row.secondary}</dd>
                          </div>
                          <div>
                            <dt>{detailLabel}</dt>
                            <dd>{row.detail}</dd>
                          </div>
                          <div>
                            <dt>{dateLabel}</dt>
                            <dd>{displayDate(row.date)}</dd>
                          </div>
                          <div>
                            <dt>Status</dt>
                            <dd>
                              <Badge status={row.status} />
                            </dd>
                          </div>
                        </dl>
                      </Modal>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-footer">
            <p aria-live="polite">
              {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filtered.length)}{' '}
              de {filtered.length} registros
            </p>
            <div className="pagination">
              <label>
                Por página{' '}
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value))
                    setPage(1)
                  }}
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                </select>
              </label>
              <Button
                variant="secondary"
                iconOnly
                aria-label="Página anterior"
                disabled={currentPage === 1}
                onClick={() => setPage(currentPage - 1)}
              >
                <ChevronLeft size={16} aria-hidden="true" />
              </Button>
              <span>
                {currentPage} / {totalPages}
              </span>
              <Button
                variant="secondary"
                iconOnly
                aria-label="Próxima página"
                disabled={currentPage === totalPages}
                onClick={() => setPage(currentPage + 1)}
              >
                <ChevronRight size={16} aria-hidden="true" />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
