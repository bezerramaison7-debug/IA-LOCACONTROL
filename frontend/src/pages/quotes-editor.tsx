import { useId, useState } from 'react'
import { useQueries, useQuery, type UseQueryResult } from '@tanstack/react-query'
import { useFieldArray, useForm, useWatch, type UseFormReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Plus, Trash2 } from 'lucide-react'
import { useAuth } from '../auth/context'
import { customerSchema, localDate, pageSchema, periods, productSchema } from '../lib/masters'
import {
  brDate,
  brMoney,
  brQuantity,
  centsText,
  estimateCents,
  estimateEndDate,
  failureMessage,
  getPricing,
  isConflict,
  priceInput,
  quoteFormSchema,
  saveQuote,
  type Pricing,
  type Quote,
  type QuoteForm,
  type QuoteFormItem,
} from '../lib/quotes'
import { Button } from '../components/Button'
import { Card, ErrorState, Field, Select } from '../components/ui'
import { Failure } from './masters-shared'

const emptyItem: QuoteFormItem = {
  product_id: '',
  quantity: '1',
  period: 'DIARIA',
  period_count: '1',
  unit_price: '',
}

/** Search box plus a labelled select; the chosen option stays listed while the search changes. */
function RecordPicker({
  kind,
  searchLabel,
  label,
  placeholder,
  value,
  knownLabel,
  error,
  onChange,
}: {
  kind: 'customers' | 'products'
  searchLabel: string
  label: string
  placeholder: string
  value: string
  knownLabel: string
  error?: string
  onChange: (id: string, label: string) => void
}) {
  const { request } = useAuth()
  const errorId = useId()
  const [q, setQ] = useState('')
  const query = useQuery({
    queryKey: ['quotes', kind, q],
    queryFn: async () => {
      const raw = await request(
        '/' + kind + '?active=true&limit=20&offset=0&q=' + encodeURIComponent(q),
      )
      return kind === 'customers'
        ? pageSchema(customerSchema)
            .parse(raw)
            .items.map((row) => ({
              id: String(row.id),
              text: row.legal_name + ' · ' + row.document,
            }))
        : pageSchema(productSchema)
            .parse(raw)
            .items.map((row) => ({ id: String(row.id), text: row.code + ' · ' + row.name }))
    },
    retry: false,
  })
  const options = query.data || []
  return (
    <div className="quote-picker">
      <Field
        label={searchLabel}
        value={q}
        maxLength={160}
        autoComplete="off"
        onChange={(e) => setQ(e.target.value)}
        hint={
          query.isPending
            ? 'Buscando…'
            : query.isSuccess && !options.length
              ? 'Nenhum registro ativo encontrado para esta busca.'
              : undefined
        }
      />
      <div>
        <Select
          label={label}
          value={value}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : undefined}
          onChange={(e) => onChange(e.target.value, e.target.selectedOptions[0]?.text || '')}
        >
          <option value="">{placeholder}</option>
          {value && !options.some((option) => option.id === value) && (
            <option value={value}>{knownLabel || 'Registro selecionado'}</option>
          )}
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.text}
            </option>
          ))}
        </Select>
        {error && (
          <p className="field-error" id={errorId}>
            {error}
          </p>
        )}
      </div>
      {query.isError && (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      )}
    </div>
  )
}

type Line = {
  /** Saved lines keep their snapshot price until the user asks to refresh the table. */
  kept: boolean
  tablePrice: string | null
  missing: boolean
  pending: boolean
  failed: string
  pricing?: Pricing
  estimate: bigint | null
}

function ItemFields({
  index,
  form,
  item,
  line,
  startDate,
  label,
  canNegotiate,
  canRemove,
  onProduct,
  onRemove,
  onRetry,
}: {
  index: number
  form: UseFormReturn<QuoteForm>
  item: QuoteFormItem
  line: Line
  startDate: string
  label: string
  canNegotiate: boolean
  canRemove: boolean
  onProduct: (id: string, label: string) => void
  onRemove: () => void
  onRetry: () => void
}) {
  const number = index + 1
  const errors = form.formState.errors.items?.[index]
  const endDate = estimateEndDate(startDate, item.period, item.period_count)
  const current = line.pricing?.table_price
  return (
    <fieldset className="master-address quote-item">
      <legend>Item {number}</legend>
      <div className="form-stack">
        <RecordPicker
          kind="products"
          searchLabel={'Buscar produto do item ' + number}
          label={'Produto do item ' + number}
          placeholder="Selecione um produto"
          value={item.product_id}
          knownLabel={label}
          error={errors?.product_id?.message}
          onChange={onProduct}
        />
        <div className="quote-item-grid">
          <Field
            label={'Quantidade do item ' + number}
            inputMode="decimal"
            maxLength={10}
            autoComplete="off"
            hint={line.pricing ? 'Unidade: ' + line.pricing.unit : 'Até três casas decimais.'}
            {...form.register(`items.${index}.quantity`)}
            error={errors?.quantity?.message}
          />
          <Select label={'Período do item ' + number} {...form.register(`items.${index}.period`)}>
            {Object.entries(periods).map(([key, text]) => (
              <option key={key} value={key}>
                {text}
              </option>
            ))}
          </Select>
          <Field
            label={'Número de períodos do item ' + number}
            inputMode="numeric"
            maxLength={3}
            autoComplete="off"
            hint="De 1 a 999, em dias corridos."
            {...form.register(`items.${index}.period_count`)}
            error={errors?.period_count?.message}
          />
          <Field
            label={'Preço negociado do item ' + number + ' (R$)'}
            inputMode="decimal"
            maxLength={12}
            autoComplete="off"
            readOnly={!canNegotiate}
            placeholder={canNegotiate ? 'Em branco usa a tabela' : undefined}
            hint={
              canNegotiate
                ? 'Opcional. Em branco, vale o preço de tabela.'
                : 'Seu perfil não permite alterar o preço de tabela.'
            }
            {...form.register(`items.${index}.unit_price`)}
            error={errors?.unit_price?.message}
          />
        </div>
        {!item.product_id ? (
          <p className="field-hint">
            Selecione um produto para consultar o preço de tabela e a disponibilidade.
          </p>
        ) : line.failed ? (
          <ErrorState message={line.failed} onRetry={onRetry} />
        ) : line.pending ? (
          <p className="field-hint" role="status">
            Consultando preço de tabela…
          </p>
        ) : (
          <div className="quote-line-info">
            {line.missing ? (
              <p className="quote-notice quote-notice-danger" role="alert">
                <strong>Preço ausente.</strong> Não há preço {periods[item.period]} vigente para
                este produto em {brDate(startDate)}. Cadastre o preço, mude o período ou remova o
                item para salvar o orçamento.
              </p>
            ) : (
              line.tablePrice && (
                <p>
                  <strong>Preço de tabela: {brMoney(line.tablePrice)}</strong> por período (
                  {periods[item.period]}){line.kept && ' · preço salvo neste orçamento'}
                </p>
              )
            )}
            {line.kept && current !== undefined && current !== line.tablePrice && (
              <p className="field-hint">
                A tabela atual indica {current === null ? 'preço ausente' : brMoney(current)}.
                Marque “Atualizar preços de tabela” para aplicar a tabela atual aos itens já salvos.
              </p>
            )}
            {line.pricing && (
              <p className="field-hint">
                Disponível agora: {brQuantity(line.pricing.available)} {line.pricing.unit}. Apenas
                informativo: orçamento não reserva estoque.
              </p>
            )}
            {line.estimate !== null && (
              <p>
                Prévia do item: {brMoney(centsText(line.estimate))}
                {endDate && ' · devolução prevista em ' + brDate(endDate)}
              </p>
            )}
          </div>
        )}
        <div className="row-actions">
          <Button variant="ghost" disabled={!canRemove} onClick={onRemove}>
            <Trash2 size={16} aria-hidden="true" />
            Remover item {number}
          </Button>
        </div>
      </div>
    </fieldset>
  )
}

export function QuoteEditor({
  quote,
  onSaved,
  onCancel,
  onReload,
}: {
  quote?: Quote
  onSaved: (quote: Quote) => void
  onCancel: () => void
  onReload?: () => void
}) {
  const { request, user } = useAuth()
  const canNegotiate = !!user?.permissions.includes('quotes.negotiate')
  const notesId = useId()
  const [failure, setFailure] = useState<{ message: string; conflict: boolean } | null>(null)
  const [labels, setLabels] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (quote?.items || []).map((item) => [
        String(item.product_id),
        item.product_code + ' · ' + item.product_name,
      ]),
    ),
  )
  const [customerLabel, setCustomerLabel] = useState(
    quote ? quote.customer.legal_name + ' · ' + quote.customer.document : '',
  )
  const form = useForm<QuoteForm>({
    resolver: zodResolver(quoteFormSchema),
    defaultValues: quote
      ? {
          customer_id: String(quote.customer_id),
          start_date: quote.start_date,
          valid_until: quote.valid_until,
          notes: quote.notes,
          refresh_prices: false,
          items: quote.items.map((item) => ({
            product_id: String(item.product_id),
            quantity: priceInput(item.quantity).replace(/,?0+$/, ''),
            period: item.period,
            period_count: String(item.period_count),
            unit_price: item.negotiated ? priceInput(item.unit_price) : '',
          })),
        }
      : {
          customer_id: '',
          start_date: localDate(),
          valid_until: estimateEndDate(localDate(), 'SEMANAL', '1') || '',
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
  const validStart = /^\d{4}-\d{2}-\d{2}$/.test(startDate)
  const pricing: UseQueryResult<Pricing>[] = useQueries({
    queries: items.map((item) => ({
      queryKey: ['quotes', 'pricing', item.product_id, item.period, startDate],
      queryFn: () => getPricing(request, item.product_id, item.period, startDate),
      enabled: !!item.product_id && validStart,
      retry: false,
    })),
  })
  const lines: Line[] = items.map((item, index) => {
    const query = pricing[index]
    const saved = quote?.items.find(
      (row) => String(row.product_id) === item.product_id && row.period === item.period,
    )
    const snapshot = saved && !refresh && startDate === quote?.start_date ? saved : undefined
    const kept = !!snapshot
    const tablePrice = snapshot ? snapshot.table_price : (query?.data?.table_price ?? null)
    const active = !!item.product_id && validStart
    return {
      kept,
      tablePrice,
      pricing: query?.data,
      // A kept line is priced by its snapshot, so it never waits for or fails on the lookup.
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
      aria-label={quote ? 'Editar orçamento ' + quote.number : 'Novo orçamento'}
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
          onSaved(await saveQuote(request, values, quote))
        } catch (e) {
          setFailure({
            message: failureMessage(e, 'Não foi possível salvar o orçamento.'),
            conflict: isConflict(e),
          })
        }
      })}
    >
      <Card
        title="Dados do orçamento"
        description="Rascunho editável. Orçamento não reserva estoque."
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
              label="Início previsto"
              type="date"
              hint="Define o preço vigente e a devolução prevista."
              {...form.register('start_date')}
              error={errors.start_date?.message}
            />
            <Field
              label="Validade do orçamento"
              type="date"
              hint="Depois desta data, o orçamento enviado expira."
              {...form.register('valid_until')}
              error={errors.valid_until?.message}
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
              {errors.notes?.message || 'Opcional · aparece no PDF do orçamento.'}
            </p>
          </div>
          {quote && (
            <label className="quote-check">
              <input type="checkbox" {...form.register('refresh_prices')} />
              <span>
                Atualizar preços de tabela dos itens já salvos
                <small>
                  Desmarcado, os itens salvos mantêm o preço de tabela registrado no orçamento.
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
          {!rows.fields.length && (
            <p className="field-hint">Nenhum item. Adicione pelo menos um para salvar.</p>
          )}
          {rows.fields.map((field, index) => (
            <ItemFields
              key={field.id}
              index={index}
              form={form}
              item={items[index] || emptyItem}
              line={
                lines[index] || {
                  kept: false,
                  tablePrice: null,
                  missing: false,
                  pending: false,
                  failed: '',
                  estimate: null,
                }
              }
              startDate={startDate}
              label={labels[items[index]?.product_id || ''] || ''}
              canNegotiate={canNegotiate}
              canRemove={rows.fields.length > 1}
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
            {total === null ? (
              'Prévia do total indisponível: complete os itens e os preços.'
            ) : (
              <>
                Prévia do total: <strong>{brMoney(centsText(total))}</strong>
              </>
            )}
          </p>
          <p className="field-hint">
            A prévia é uma estimativa. O valor oficial e a devolução prevista são calculados pelo
            servidor ao salvar.
          </p>
          {failure && (
            <div className="quote-notice quote-notice-danger" role="alert">
              <p>{failure.message}</p>
              {failure.conflict && onReload && (
                <Button variant="secondary" onClick={onReload}>
                  Recarregar orçamento (descarta esta edição)
                </Button>
              )}
            </div>
          )}
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
