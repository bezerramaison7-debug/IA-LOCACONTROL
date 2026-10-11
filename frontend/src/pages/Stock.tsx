import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { decimalInput, movementSchema, pageSchema, states, stockSchema } from '../lib/masters'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable, Pager } from './masters-shared'
import type { z } from 'zod'
type StockRow = z.infer<typeof stockSchema>
function MovementEditor({ row, done }: { row: StockRow; done: () => void }) {
  const { request } = useAuth()
  const [error, setError] = useState('')
  const [key] = useState(() => crypto.randomUUID())
  const form = useForm<{
    quantity: string
    from_status: string
    to_status: string
    reason: string
  }>({
    defaultValues: { quantity: '1', from_status: '', to_status: 'DISPONIVEL', reason: '' },
  })
  return (
    <form
      className="form-stack"
      onSubmit={form.handleSubmit(async (values) => {
        setError('')
        try {
          await request('/stock/movements', 'POST', {
            ...values,
            product_id: row.id,
            quantity: decimalInput(values.quantity),
            from_status: values.from_status || null,
            request_key: key,
          })
          done()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Não foi possível movimentar.')
        }
      })}
    >
      <Select label="Origem" {...form.register('from_status')}>
        <option value="">Entrada de estoque</option>
        {Object.entries(states)
          .filter(([k]) => k !== 'BAIXADO')
          .map(([k, v]) => (
            <option key={k} value={k}>
              {v + ' · ' + row.balances[k as keyof typeof states]}
            </option>
          ))}
      </Select>
      <Select label="Destino" {...form.register('to_status')}>
        {Object.entries(states).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </Select>
      <Field
        label="Quantidade"
        inputMode="decimal"
        required
        pattern="[0-9]+([.,][0-9]{1,3})?"
        maxLength={13}
        hint={'Até três casas decimais · unidade ' + row.unit}
        {...form.register('quantity', { required: true })}
      />
      <Field
        label="Motivo"
        required
        minLength={5}
        maxLength={500}
        {...form.register('reason', { required: true, minLength: 5 })}
      />
      <p>
        Entradas vão para Disponível. Baixas preservam o histórico e são definitivas. O saldo será
        validado antes da confirmação.
      </p>
      <Failure message={error} />
      <Button type="submit" disabled={form.formState.isSubmitting}>
        Confirmar movimentação
      </Button>
    </form>
  )
}
export function Stock() {
  const { request, user } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [editor, setEditor] = useState<StockRow | null>(null)
  const [history, setHistory] = useState<StockRow | null>(null)
  const [historyOffset, setHistoryOffset] = useState(0)
  const query = useQuery({
    queryKey: ['masters', 'stock', q, offset],
    queryFn: async () =>
      pageSchema(stockSchema).parse(
        await request('/stock?limit=20&offset=' + offset + '&q=' + encodeURIComponent(q)),
      ),
    retry: false,
  })
  const movements = useQuery({
    queryKey: ['masters', 'movements', history?.id, historyOffset],
    queryFn: async () =>
      pageSchema(movementSchema).parse(
        await request(
          '/stock/movements?product_id=' + history!.id + '&limit=20&offset=' + historyOffset,
        ),
      ),
    enabled: !!history,
    retry: false,
  })
  return (
    <>
      <PageHeader
        title="Estoque"
        description="Saldos reais por produto e situação, com movimentos auditados."
      />
      <Card title="Posição do estoque">
        <div className="master-filters">
          <Field
            label="Buscar no estoque"
            value={q}
            maxLength={160}
            onChange={(e) => {
              setQ(e.target.value)
              setOffset(0)
            }}
          />
        </div>
        {query.isPending ? (
          <Skeleton />
        ) : query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : (
          <>
            {!query.data.items.length ? (
              <EmptyState
                title="Nenhum produto encontrado"
                description="Cadastre produtos antes de movimentar o estoque."
              />
            ) : (
              <MasterTable
                label="Saldos de estoque"
                headers={['Produto', ...Object.values(states), 'Ações']}
              >
                {query.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.name}</strong>
                      <span className="cell-description">
                        {row.code +
                          ' · ' +
                          row.unit +
                          ' · ' +
                          (row.individual_tracking ? 'Individual' : 'Quantidade') +
                          (row.is_active ? '' : ' · Inativo')}
                      </span>
                    </td>
                    {Object.keys(states).map((k) => (
                      <td key={k}>{row.balances[k as keyof typeof states]}</td>
                    ))}
                    <td>
                      <div className="row-actions">
                        <Button
                          variant="ghost"
                          onClick={() => {
                            setHistory(row)
                            setHistoryOffset(0)
                          }}
                        >
                          Histórico
                        </Button>
                        {row.individual_tracking
                          ? user?.permissions.includes('equipment.read') && (
                              <Button variant="secondary" asChild>
                                <Link to={'/equipamentos?product=' + row.id}>Ver unidades</Link>
                              </Button>
                            )
                          : row.is_active &&
                            user?.permissions.includes('stock.write') && (
                              <Button variant="secondary" onClick={() => setEditor(row)}>
                                Movimentar
                              </Button>
                            )}
                      </div>
                    </td>
                  </tr>
                ))}
              </MasterTable>
            )}
            <Pager total={query.data.total} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      <Modal
        open={!!editor}
        onOpenChange={(open) => {
          if (!open) setEditor(null)
        }}
        title="Movimentar estoque"
        description={editor?.name || ''}
      >
        {editor && (
          <MovementEditor
            key={editor.id}
            row={editor}
            done={() => {
              setEditor(null)
              toast('Estoque atualizado.')
              void cache.invalidateQueries({ queryKey: ['masters'] })
            }}
          />
        )}
      </Modal>
      <Modal
        open={!!history}
        onOpenChange={(open) => {
          if (!open) setHistory(null)
        }}
        title="Histórico de estoque"
        description={history?.name || ''}
        className="master-modal"
      >
        {movements.isPending ? (
          <Skeleton />
        ) : movements.isError ? (
          <ErrorState message={movements.error.message} onRetry={() => void movements.refetch()} />
        ) : (
          <>
            {!movements.data.items.length ? (
              <EmptyState title="Sem movimentos" />
            ) : (
              <MasterTable
                label="Movimentos de estoque"
                headers={['Quando', 'Origem → destino', 'Quantidade', 'Motivo']}
              >
                {movements.data.items.map((m) => (
                  <tr key={m.id}>
                    <td>{new Date(m.created_at * 1000).toLocaleString('pt-BR')}</td>
                    <td>
                      {m.from_status ? states[m.from_status as keyof typeof states] : 'Entrada'} →{' '}
                      {states[m.to_status as keyof typeof states]}
                      {m.equipment_id && (
                        <span className="cell-description">Unidade individual</span>
                      )}
                    </td>
                    <td>{m.quantity}</td>
                    <td>{m.reason}</td>
                  </tr>
                ))}
              </MasterTable>
            )}
            <Pager
              total={movements.data.total}
              offset={historyOffset}
              onChange={setHistoryOffset}
            />
          </>
        )}
      </Modal>
    </>
  )
}
