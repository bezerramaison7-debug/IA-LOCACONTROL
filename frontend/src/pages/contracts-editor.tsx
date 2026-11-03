import { useId, useState } from 'react'
import { useQueries, type UseQueryResult } from '@tanstack/react-query'
import { useFieldArray, useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Plus } from 'lucide-react'
import { ApiError } from '../auth/api'
import { useAuth } from '../auth/context'
import { localDate } from '../lib/masters'
import {
  actionError,
  quantityInput,
  saveContract,
  useContractPermissions,
  type ActionError,
  type Contract,
} from '../lib/contracts'
import {
  brMoney,
  centsText,
  estimateCents,
  getPricing,
  priceInput,
  quoteFormSchema,
  type Pricing,
  type QuoteForm,
  type QuoteFormItem,
} from '../lib/quotes'
import { Button } from '../components/Button'
import { DraftNotice } from '../components/DraftNotice'
import { useDraft } from '../lib/drafts'
import { Card, Field } from '../components/ui'
import { Failure } from './masters-shared'
import { ActionFailure } from './contracts-shared'
import { ItemFields, RecordPicker, type Line } from './quotes-editor'

const emptyItem: QuoteFormItem = {
  product_id: '',
  quantity: '1',
  period: 'DIARIA',
  period_count: '1',
  unit_price: '',
}
const emptyLine: Line = {
  kept: false,
  tablePrice: null,
  missing: false,
  pending: false,
  failed: '',
  estimate: null,
}

/**
 * Contract draft. Items follow the quote rules, so the item form is shared with the quote
 * editor; `valid_until` only satisfies that shared schema and is never sent for a contract.
 */
export function ContractEditor({
  contract,
  onSaved,
  onCancel,
  onReload,
}: {
  contract?: Contract
  onSaved: (contract: Contract) => void
  onCancel: () => void
  onReload?: () => void
}) {
  const { request } = useAuth()
  const can = useContractPermissions()
  const canPrice = can.has('quotes.read')
  const notesId = useId()
  const [failure, setFailure] = useState<ActionError | null>(null)
  const [labels, setLabels] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (contract?.items || []).map((item) => [
        String(item.product_id),
        item.product_code + ' · ' + item.product_name,
      ]),
    ),
  )
  const [customerLabel, setCustomerLabel] = useState(
    contract ? contract.customer.legal_name + ' · ' + contract.customer.document : '',
  )
  const form = useForm<QuoteForm>({
    resolver: zodResolver(quoteFormSchema),
    defaultValues: contract
      ? {
          customer_id: String(contract.customer_id),
          start_date: contract.start_date,
          valid_until: contract.start_date,
          notes: contract.notes,
          refresh_prices: false,
          items: contract.items.map((item) => ({
            product_id: String(item.product_id),
            quantity: quantityInput(item.quantity),
            period: item.period,
            period_count: String(item.period_count),
            unit_price: item.negotiated ? priceInput(item.unit_price) : '',
          })),
        }
      : {
          customer_id: '',
          start_date: localDate(),
          valid_until: localDate(),
          notes: '',
          refresh_prices: false,
          items: [emptyItem],
        },
  })
  const rows = useFieldArray({ control: form.control, name: 'items' })
  const items = useWatch({ control: form.control, name: 'items' })
  const startDate = useWatch({ control: form.control, name: 'start_date' })
  const customerId = useWatch({ control: form.control, name: 'customer_id' })
  const refresh = useWatch({ control: form.control, name: 'refresh_prices' })
  const values = useWatch({ control: form.control })
  // Automatic draft (ADR-024): the form as typed, never a contract record until it is saved.
  const draft = useDraft({
    kind: 'contract',
    scope: contract ? String(contract.id) : 'new',
    value: { values, labels, customerLabel },
    baseVersion: contract?.version,
    onRestore: (saved) => {
      setLabels(saved.labels || {})
      setCustomerLabel(saved.customerLabel || '')
      form.reset(saved.values as QuoteForm)
    },
  })
  const validStart = /^\d{4}-\d{2}-\d{2}$/.test(startDate)
  const pricing: UseQueryResult<Pricing>[] = useQueries({
    queries: items.map((item) => ({
      queryKey: ['quotes', 'pricing', item.product_id, item.period, startDate],
      queryFn: () => getPricing(request, item.product_id, item.period, startDate),
      enabled: canPrice && !!item.product_id && validStart,
      retry: false,
    })),
  })
  // The price lookup belongs to quotes; without that permission the server prices on save.
  const denied =
    !canPrice || pricing.some((q) => q.error instanceof ApiError && q.error.status === 403)
  const lines: Line[] = items.map((item, index) => {
    const query = pricing[index]
    const saved = contract?.items.find(
      (row) => String(row.product_id) === item.product_id && row.period === item.period,
    )
    const snapshot = saved && !refresh && startDate === contract?.start_date ? saved : undefined
    const kept = !!snapshot
    const tablePrice = snapshot ? snapshot.table_price : (query?.data?.table_price ?? null)
    const active = !denied && !!item.product_id && validStart
    return {
      kept,
      tablePrice,
      pricing: query?.data,
      missing: active && !kept && !!query?.isSuccess && query.data.table_price === null,
      pending: active && !kept && !!query?.isPending,
      failed: active && !kept && query?.isError ? query.error.message : '',
      estimate:
        item.product_id && (item.unit_price.trim() || tablePrice)
          ? estimateCents(item.quantity, item.unit_price.trim() || tablePrice!, item.period_count)
          : null,
    }
  })
  const missing = lines.some((line) => line.missing)
  const unresolved = lines.some((line) => line.pending || line.failed)
  const total = lines.every((line) => line.estimate !== null)
    ? lines.reduce((sum, line) => sum + line.estimate!, 0n)
    : null
  const errors = form.formState.errors
  const saving = form.formState.isSubmitting
  return (
    <form
      className="form-stack"
      noValidate
      aria-label={contract ? 'Editar contrato ' + contract.number : 'Novo contrato'}
      onSubmit={form.handleSubmit(async (values) => {
        setFailure(null)
        if (missing || unresolved) {
          setFailure({
            message: missing
              ? 'Há item sem preço de tabela vigente. Ajuste ou remova o item para salvar.'
              : 'Aguarde ou refaça a consulta de preço de todos os itens antes de salvar.',
            conflict: false,
          })
          return
        }
        try {
          const result = await saveContract(request, values, contract)
          draft.finish()
          onSaved(result)
        } catch (e) {
          setFailure(actionError(e, 'Não foi possível salvar o contrato.'))
        }
      })}
    >
      <DraftNotice draft={draft} />
      <Card
        title="Dados do contrato"
        description="Rascunho editável. O número é definitivo e o estoque só sai na retirada."
      >
        <div className="padded form-stack">
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
              form.setValue('customer_id', id, { shouldDirty: true, shouldValidate: true })
            }}
          />
          <div className="master-form-grid">
            <Field
              label="Início da locação"
              type="date"
              hint="Define o preço vigente e a devolução prevista de cada item."
              {...form.register('start_date')}
              error={errors.start_date?.message}
            />
          </div>
          <div className="field">
            <label htmlFor={notesId}>Observações</label>
            <textarea
              id={notesId}
              rows={3}
              maxLength={2000}
              aria-invalid={!!errors.notes}
              aria-describedby={notesId + '-help'}
              {...form.register('notes')}
            />
            <p className={errors.notes ? 'field-error' : 'field-hint'} id={notesId + '-help'}>
              {errors.notes?.message || 'Opcional · aparece no documento do contrato.'}
            </p>
          </div>
          {contract && (
            <label className="quote-check">
              <input type="checkbox" {...form.register('refresh_prices')} />
              <span>
                Atualizar preços de tabela dos itens já salvos
                <small>
                  Desmarcado, os itens salvos mantêm o preço de tabela registrado no contrato.
                </small>
              </span>
            </label>
          )}
        </div>
      </Card>
      <Card
        title="Itens"
        description="Valor do item = quantidade × preço do período × número de períodos."
        action={
          <Button
            variant="secondary"
            disabled={rows.fields.length >= 100}
            onClick={() => rows.append(emptyItem)}
          >
            <Plus size={16} aria-hidden="true" />
            Adicionar item
          </Button>
        }
      >
        <div className="padded form-stack">
          {rows.fields.map((field, index) => (
            <ItemFields
              key={field.id}
              index={index}
              form={form}
              item={items[index] || emptyItem}
              line={lines[index] || emptyLine}
              startDate={startDate}
              label={labels[items[index]?.product_id || ''] || ''}
              canNegotiate={can.negotiate}
              canRemove={rows.fields.length > 1}
              noun="contrato"
              stockNote="Apenas informativo: o estoque é conferido e baixado na retirada."
              priceOnSave={denied}
              onProduct={(id, text) => {
                setLabels((known) => ({ ...known, [id]: text }))
                form.setValue(`items.${index}.product_id`, id, {
                  shouldDirty: true,
                  shouldValidate: form.formState.isSubmitted,
                })
                form.setValue(`items.${index}.unit_price`, '')
              }}
              onRemove={() => rows.remove(index)}
              onRetry={() => void pricing[index]?.refetch()}
            />
          ))}
          <Failure message={errors.items?.message || errors.items?.root?.message || ''} />
        </div>
      </Card>
      <Card title="Prévia e salvamento">
        <div className="padded form-stack">
          <p className="quote-preview-total" role="status">
            {denied ? (
              'O preço de tabela e o total serão calculados pelo servidor ao salvar.'
            ) : total === null ? (
              'Prévia do total indisponível: complete os itens e os preços.'
            ) : (
              <>
                Prévia do total: <strong>{brMoney(centsText(total))}</strong>
              </>
            )}
          </p>
          <p className="field-hint">
            A prévia é uma estimativa. O valor oficial e a devolução prevista são calculados pelo
            servidor ao salvar. Depois de confirmado, o contrato não pode mais ser editado.
          </p>
          <ActionFailure
            failure={failure}
            onReload={onReload}
            reloadLabel="Recarregar contrato (descarta esta edição)"
          />
          <div className="row-actions">
            <Button type="submit" disabled={saving || missing}>
              {saving ? 'Salvando…' : 'Salvar rascunho'}
            </Button>
            <Button variant="secondary" disabled={saving} onClick={onCancel}>
              Descartar e voltar
            </Button>
          </div>
        </div>
      </Card>
    </form>
  )
}
