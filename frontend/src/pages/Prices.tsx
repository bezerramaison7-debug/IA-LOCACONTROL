import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useAuth } from '../auth/context'
import { decimalInput, localDate, money, pageSchema, periods, priceSchema } from '../lib/masters'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable, Pager, ProductPicker } from './masters-shared'
import type { z } from 'zod'
type Price = z.infer<typeof priceSchema>
function PriceEditor({ row, retire, done }: { row?: Price; retire?: boolean; done: () => void }) {
  const { request } = useAuth()
  const [productId, setProductId] = useState(row ? String(row.product_id) : '')
  const [error, setError] = useState('')
  const form = useForm<{ period: string; effective_date: string; amount: string; reason: string }>({
    defaultValues: {
      period: row?.period || 'DIARIA',
      effective_date: row?.effective_date || localDate(),
      amount: row?.amount || '',
      reason: '',
    },
  })
  return (
    <form
      className="form-stack"
      onSubmit={form.handleSubmit(async (values) => {
        setError('')
        if (!retire && !productId) {
          setError('Selecione um produto.')
          return
        }
        try {
          await request(
            '/prices' + (row ? '/' + row.id : ''),
            retire ? 'DELETE' : row ? 'PUT' : 'POST',
            retire
              ? { reason: values.reason }
              : {
                  ...values,
                  period: row?.period || values.period,
                  effective_date: row?.effective_date || values.effective_date,
                  product_id: Number(productId),
                  amount: decimalInput(values.amount),
                },
          )
          done()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Não foi possível publicar o preço.')
        }
      })}
    >
      {!retire && (
        <>
          <ProductPicker selected={productId} onChange={setProductId} locked={!!row} />
          <Select label="Período" disabled={!!row} {...form.register('period')}>
            {Object.entries(periods).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
          <Field
            label="Início da vigência"
            type="date"
            required
            readOnly={!!row}
            {...form.register('effective_date', { required: true })}
          />
          <Field
            label="Valor (R$)"
            inputMode="decimal"
            required
            maxLength={12}
            pattern="[0-9]+([.,][0-9]{1,2})?"
            hint="Até duas casas decimais."
            {...form.register('amount', { required: true })}
          />
        </>
      )}
      <Field
        label="Motivo"
        required
        minLength={5}
        maxLength={500}
        {...form.register('reason', { required: true, minLength: 5 })}
      />
      <p>
        {retire
          ? 'A desativação publica uma nova versão sem preço nessa vigência. Documentos anteriores e versões antigas serão preservados.'
          : 'O salvamento publica uma nova versão. Preços antigos e documentos que os utilizaram não serão sobrescritos.'}
      </p>
      <Failure message={error} />
      <Button
        type="submit"
        variant={retire ? 'danger' : 'primary'}
        disabled={form.formState.isSubmitting}
      >
        {retire ? 'Confirmar desativação' : 'Publicar preço'}
      </Button>
    </form>
  )
}
function EffectivePrice() {
  const { request } = useAuth()
  const [productId, setProductId] = useState('')
  const [period, setPeriod] = useState('DIARIA')
  const [at, setAt] = useState(localDate())
  const [lookup, setLookup] = useState<{ productId: string; period: string; at: string } | null>(
    null,
  )
  const query = useQuery({
    queryKey: ['masters', 'effective', lookup],
    queryFn: async () =>
      priceSchema.parse(
        await request(
          '/prices/effective?product_id=' +
            lookup!.productId +
            '&period=' +
            lookup!.period +
            '&at=' +
            lookup!.at,
        ),
      ),
    enabled: !!lookup,
    retry: false,
  })
  return (
    <Card title="Consultar preço vigente">
      <div className="padded form-stack">
        <form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault()
            setLookup({ productId, period, at })
          }}
        >
          <ProductPicker selected={productId} onChange={setProductId} />
          <div className="master-form-grid">
            <Select
              label="Período da consulta"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
            >
              {Object.entries(periods).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
            <Field
              label="Data da consulta"
              type="date"
              required
              value={at}
              onChange={(e) => setAt(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={!productId || !at}>
            Consultar preço
          </Button>
        </form>
        {lookup &&
          (query.isPending ? (
            <Skeleton rows={1} />
          ) : query.isError ? (
            <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
          ) : (
            <p role="status">
              <strong>{money(query.data.amount)}</strong> · {query.data.product_name} ·{' '}
              {periods[query.data.period]} · vigência {query.data.effective_date}
            </p>
          ))}
      </div>
    </Card>
  )
}
export function Prices() {
  const { request, user } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [productId, setProductId] = useState('')
  const [period, setPeriod] = useState('')
  const [offset, setOffset] = useState(0)
  const [editor, setEditor] = useState<Price | 'new' | null>(null)
  const [retire, setRetire] = useState<Price | null>(null)
  const canWrite = user?.permissions.includes('prices.write')
  const query = useQuery({
    queryKey: ['masters', 'prices', productId, period, offset],
    queryFn: async () =>
      pageSchema(priceSchema).parse(
        await request(
          '/prices?limit=20&offset=' +
            offset +
            (productId ? '&product_id=' + productId : '') +
            (period ? '&period=' + period : ''),
        ),
      ),
    retry: false,
  })
  function done() {
    setEditor(null)
    setRetire(null)
    toast('Nova versão de preço registrada.')
    void cache.invalidateQueries({ queryKey: ['masters'] })
  }
  return (
    <>
      <PageHeader
        title="Preços"
        description="Tabela por período e vigência, com histórico de versões preservado."
        actions={canWrite && <Button onClick={() => setEditor('new')}>Novo preço</Button>}
      />
      <EffectivePrice />
      <Card title="Histórico de preços">
        <div className="padded form-stack">
          <ProductPicker
            selected={productId}
            onChange={(v) => {
              setProductId(v)
              setOffset(0)
            }}
          />
          {productId && (
            <Button
              variant="ghost"
              onClick={() => {
                setProductId('')
                setOffset(0)
              }}
            >
              Todos os produtos
            </Button>
          )}
          <Select
            label="Filtrar período"
            value={period}
            onChange={(e) => {
              setPeriod(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">Todos</option>
            {Object.entries(periods).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
        </div>
        {query.isPending ? (
          <Skeleton />
        ) : query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : (
          <>
            {!query.data.items.length ? (
              <EmptyState
                title="Nenhum preço encontrado"
                description="Publique preços ou ajuste os filtros."
              />
            ) : (
              <MasterTable
                label="Histórico de preços"
                headers={['Produto', 'Período', 'Vigência', 'Valor', 'Histórico', 'Ações']}
              >
                {query.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{row.product_name}</strong>
                      <span className="cell-description">{row.product_code}</span>
                    </td>
                    <td>{periods[row.period]}</td>
                    <td>{row.effective_date}</td>
                    <td>{money(row.amount)}</td>
                    <td>
                      {row.supersedes_id ? 'Revisão' : 'Publicação inicial'}
                      <span className="cell-description">{row.reason}</span>
                    </td>
                    <td>
                      <div className="row-actions">
                        {canWrite && (
                          <>
                            <Button variant="ghost" onClick={() => setEditor(row)}>
                              Revisar
                            </Button>
                            {row.is_active && (
                              <Button variant="secondary" onClick={() => setRetire(row)}>
                                Desativar
                              </Button>
                            )}
                          </>
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
        open={editor !== null}
        onOpenChange={(open) => {
          if (!open) setEditor(null)
        }}
        title={editor === 'new' ? 'Novo preço' : 'Revisar preço'}
        description="Publicação de uma nova versão, sem apagar o histórico."
      >
        {editor && (
          <PriceEditor
            key={editor === 'new' ? 'new' : editor.id}
            row={editor === 'new' ? undefined : editor}
            done={done}
          />
        )}
      </Modal>
      <Modal
        open={!!retire}
        onOpenChange={(open) => {
          if (!open) setRetire(null)
        }}
        title="Desativar preço"
        description={retire?.product_name || ''}
      >
        {retire && <PriceEditor key={retire.id} row={retire} retire done={done} />}
      </Modal>
    </>
  )
}
