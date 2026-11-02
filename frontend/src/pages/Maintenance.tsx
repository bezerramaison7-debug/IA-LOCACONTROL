import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import type { z } from 'zod'
import { useAuth } from '../auth/context'
import { decimalInput, equipmentSchema, pageSchema, stockSchema } from '../lib/masters'
import { actionError, positive, quantityInput, type ActionError } from '../lib/contracts'
import { brQuantity, scaled } from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { MasterTable, Pager } from './masters-shared'
import { ActionFailure } from './contracts-shared'

type Unit = z.infer<typeof equipmentSchema>
type Balance = z.infer<typeof stockSchema>
type Target = { unit: Unit } | { product: Balance }

function ReleaseForm({
  target,
  done,
  close,
  reload,
}: {
  target: Target
  done: () => void
  close: () => void
  reload: () => void
}) {
  const { request } = useAuth()
  const [key] = useState(() => crypto.randomUUID())
  const [failure, setFailure] = useState<ActionError | null>(null)
  const balance = 'product' in target ? target.product.balances.MANUTENCAO : '1.000'
  const form = useForm<{ quantity: string; reason: string }>({
    defaultValues: { quantity: quantityInput(balance), reason: '' },
  })
  return (
    <form
      className="form-stack"
      noValidate
      onSubmit={form.handleSubmit(async (values) => {
        setFailure(null)
        try {
          if ('unit' in target)
            await request('/equipment/' + target.unit.id + '/status', 'POST', {
              version: target.unit.version,
              status: 'DISPONIVEL',
              reason: values.reason.trim(),
            })
          else
            await request('/stock/movements', 'POST', {
              product_id: target.product.id,
              from_status: 'MANUTENCAO',
              to_status: 'DISPONIVEL',
              quantity: decimalInput(values.quantity),
              reason: values.reason.trim(),
              request_key: key,
            })
          done()
        } catch (e) {
          setFailure(actionError(e, 'Não foi possível liberar da manutenção.'))
        }
      })}
    >
      <p>
        {'unit' in target
          ? 'A unidade ' +
            target.unit.code +
            ' sai da manutenção e volta a Disponível, podendo ser retirada em novos contratos.'
          : 'A quantidade informada sai da manutenção e volta ao saldo Disponível do produto.'}{' '}
        O movimento fica registrado no histórico do estoque.
      </p>
      {'product' in target && (
        <Field
          label="Quantidade a liberar"
          inputMode="decimal"
          maxLength={13}
          autoComplete="off"
          hint={
            'Em manutenção: ' +
            brQuantity(balance) +
            ' ' +
            target.product.unit +
            ' · até três casas.'
          }
          {...form.register('quantity', {
            validate: (value) => {
              const milli = scaled(value, 3)
              if (milli === null || milli === 0n) return 'Informe uma quantidade maior que zero.'
              return milli <= scaled(balance, 3)! || 'A quantidade supera o saldo em manutenção.'
            },
          })}
          error={form.formState.errors.quantity?.message}
        />
      )}
      <Field
        label="Motivo da liberação"
        maxLength={500}
        autoComplete="off"
        hint="Obrigatório · pelo menos 5 caracteres. Ex.: reparo concluído e testado."
        {...form.register('reason', {
          validate: (value) =>
            value.trim().length >= 5 || 'Informe o motivo com pelo menos 5 caracteres.',
        })}
        error={form.formState.errors.reason?.message}
      />
      <ActionFailure failure={failure} onReload={reload} reloadLabel="Recarregar manutenção" />
      <div className="modal-actions">
        <Button variant="secondary" onClick={close}>
          Voltar
        </Button>
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Liberando…' : 'Confirmar liberação'}
        </Button>
      </div>
    </form>
  )
}

export function Maintenance() {
  const { request, user } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [offset, setOffset] = useState(0)
  const [target, setTarget] = useState<Target | null>(null)
  const has = (code: string) => !!user?.permissions.includes(code)
  const canUnits = has('equipment.read')
  const canRelease = has('stock.write')
  const units = useQuery({
    queryKey: ['masters', 'maintenance-units', offset],
    queryFn: async () =>
      pageSchema(equipmentSchema).parse(
        await request('/equipment?status=MANUTENCAO&limit=20&offset=' + offset),
      ),
    enabled: canUnits,
    retry: false,
  })
  const balances = useQuery({
    queryKey: ['masters', 'maintenance-balances'],
    queryFn: async () => {
      // The stock API has no status filter: walk its pages and keep what is in maintenance.
      const rows: Balance[] = []
      let total: number
      do {
        const page = pageSchema(stockSchema).parse(
          await request('/stock?limit=100&offset=' + rows.length + '&q='),
        )
        total = page.total
        rows.push(...page.items)
        if (!page.items.length) break
      } while (rows.length < total && rows.length < 2000)
      return rows.filter((row) => !row.individual_tracking && positive(row.balances.MANUTENCAO))
    },
    retry: false,
  })
  const reload = () => {
    setTarget(null)
    void cache.invalidateQueries({ queryKey: ['masters'] })
  }
  if (!has('stock.read'))
    return (
      <>
        <PageHeader title="Manutenção" description="Equipamentos fora de locação para reparo." />
        <ErrorState message="Seu perfil não tem permissão para consultar o estoque." />
      </>
    )
  return (
    <>
      <PageHeader
        title="Manutenção"
        description="Unidades e saldos em manutenção. Libere o que voltou a ficar disponível para locação."
      />
      <Card
        title="Unidades em manutenção"
        description="Equipamentos com controle individual, como os devolvidos avariados."
      >
        {!canUnits ? (
          <ErrorState message="Seu perfil não tem permissão para consultar equipamentos." />
        ) : units.isPending ? (
          <Skeleton />
        ) : units.isError ? (
          <ErrorState message={units.error.message} onRetry={() => void units.refetch()} />
        ) : !units.data.items.length ? (
          <EmptyState
            initial
            title="Nenhuma unidade em manutenção"
            description="Unidades devolvidas como avariadas aparecem aqui."
          />
        ) : (
          <>
            <MasterTable
              label="Lista de unidades em manutenção"
              headers={['Código', 'Produto', 'Identificação', 'Ações']}
            >
              {units.data.items.map((unit) => (
                <tr key={unit.id}>
                  <td className="code-cell">{unit.code}</td>
                  <td>
                    <strong>{unit.product_name}</strong>
                    <span className="cell-description">{unit.product_code}</span>
                  </td>
                  <td>
                    {[
                      unit.asset_tag && 'Patrimônio ' + unit.asset_tag,
                      unit.serial_number && 'Série ' + unit.serial_number,
                      [unit.brand, unit.model].filter(Boolean).join(' '),
                    ]
                      .filter(Boolean)
                      .join(' · ') || '—'}
                  </td>
                  <td>
                    {canRelease ? (
                      <Button
                        variant="secondary"
                        aria-label={'Liberar unidade ' + unit.code}
                        onClick={() => setTarget({ unit })}
                      >
                        Liberar
                      </Button>
                    ) : (
                      <span className="cell-description">Sem permissão para liberar</span>
                    )}
                  </td>
                </tr>
              ))}
            </MasterTable>
            <Pager total={units.data.total} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      <Card
        title="Saldos em manutenção"
        description="Produtos controlados por quantidade com saldo em manutenção."
      >
        {balances.isPending ? (
          <Skeleton />
        ) : balances.isError ? (
          <ErrorState message={balances.error.message} onRetry={() => void balances.refetch()} />
        ) : !balances.data.length ? (
          <EmptyState
            initial
            title="Nenhum saldo em manutenção"
            description="Quantidades devolvidas para manutenção aparecem aqui."
          />
        ) : (
          <MasterTable
            label="Lista de saldos em manutenção"
            headers={['Produto', 'Em manutenção', 'Disponível', 'Ações']}
          >
            {balances.data.map((row) => (
              <tr key={row.id}>
                <td>
                  <strong>{row.name}</strong>
                  <span className="cell-description">{row.code}</span>
                </td>
                <td>
                  {brQuantity(row.balances.MANUTENCAO)} {row.unit}
                </td>
                <td>
                  {brQuantity(row.balances.DISPONIVEL)} {row.unit}
                </td>
                <td>
                  {canRelease && row.is_active ? (
                    <Button
                      variant="secondary"
                      aria-label={'Liberar saldo de ' + row.name}
                      onClick={() => setTarget({ product: row })}
                    >
                      Liberar
                    </Button>
                  ) : (
                    <span className="cell-description">
                      {row.is_active ? 'Sem permissão para liberar' : 'Produto inativo'}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </MasterTable>
        )}
      </Card>
      <Modal
        open={target !== null}
        onOpenChange={(open) => {
          if (!open) setTarget(null)
        }}
        title="Liberar da manutenção"
        description={
          target
            ? 'unit' in target
              ? target.unit.code + ' · ' + target.unit.product_name
              : target.product.code + ' · ' + target.product.name
            : ''
        }
      >
        {target && (
          <ReleaseForm
            key={'unit' in target ? 'u' + target.unit.id : 'p' + target.product.id}
            target={target}
            close={() => setTarget(null)}
            reload={reload}
            done={() => {
              toast('Liberado da manutenção. Estoque atualizado.')
              reload()
            }}
          />
        )}
      </Modal>
    </>
  )
}
