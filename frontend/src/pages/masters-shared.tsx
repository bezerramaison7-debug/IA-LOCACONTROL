import { useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/context'
import { pageSchema, productSchema } from '../lib/masters'
import { Button } from '../components/Button'
import { ErrorState, Field, Select, Skeleton } from '../components/ui'

export function ProductPicker({
  selected,
  onChange,
  individual = false,
  locked = false,
}: {
  selected: string
  onChange: (id: string) => void
  individual?: boolean
  locked?: boolean
}) {
  const { request } = useAuth()
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const query = useQuery({
    queryKey: ['masters', 'picker', q, offset],
    queryFn: async () =>
      pageSchema(productSchema).parse(
        await request(
          '/products?active=true&limit=20&offset=' + offset + '&q=' + encodeURIComponent(q),
        ),
      ),
    retry: false,
  })
  if (locked) return <p>Produto preservado nesta edição.</p>
  return (
    <div className="form-stack">
      <Field
        label="Buscar produto para selecionar"
        value={q}
        maxLength={160}
        onChange={(e) => {
          setQ(e.target.value)
          setOffset(0)
        }}
      />
      {query.isPending ? (
        <Skeleton rows={1} />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <Select
            label="Produto"
            value={selected}
            required
            onChange={(e) => onChange(e.target.value)}
          >
            <option value="">Selecione um produto</option>
            {selected && !query.data.items.some((p) => String(p.id) === selected) && (
              <option value={selected}>Produto selecionado (ajuste a busca para localizar)</option>
            )}
            {query.data.items
              .filter((p) => !individual || p.individual_tracking)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.code} · {p.name}
                  {p.individual_tracking ? ' · individual' : ''}
                </option>
              ))}
          </Select>
          <Pager total={query.data.total} offset={offset} onChange={setOffset} />
          {individual && (
            <p className="field-hint">
              Somente produtos com controle individual podem receber equipamentos.
            </p>
          )}
        </>
      )}
    </div>
  )
}

export function Pager({
  total,
  offset,
  onChange,
  size = 20,
}: {
  total: number
  offset: number
  onChange: (offset: number) => void
  size?: number
}) {
  return (
    <div className="table-footer">
      <span>
        {total} registros · página {Math.floor(offset / size) + 1}
      </span>
      <div className="pagination">
        <Button
          variant="secondary"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - size))}
        >
          Anterior
        </Button>
        <Button
          variant="secondary"
          disabled={offset + size >= total}
          onClick={() => onChange(offset + size)}
        >
          Próxima
        </Button>
      </div>
    </div>
  )
}

export function MasterTable({
  label,
  headers,
  children,
}: {
  label: string
  headers: string[]
  children: ReactNode
}) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={label}>
      <table className="data-table">
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
export function Failure({ message }: { message: string }) {
  return message ? (
    <p className="field-error" role="alert">
      {message}
    </p>
  ) : null
}
