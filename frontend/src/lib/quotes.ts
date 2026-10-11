import { z } from 'zod'
import { ApiError } from '../auth/api'
import type { AuthContextValue } from '../auth/context'
import { decimalInput, pageSchema } from './masters'

export const quoteStatuses = {
  RASCUNHO: 'Rascunho',
  ENVIADO: 'Enviado',
  APROVADO: 'Aprovado',
  REJEITADO: 'Rejeitado',
  EXPIRADO: 'Expirado',
  CANCELADO: 'Cancelado',
  CONVERTIDO: 'Convertido',
}
export type QuoteStatus = keyof typeof quoteStatuses
export const periodDays = { DIARIA: 1, SEMANAL: 7, QUINZENAL: 15, MENSAL: 30 }
export type QuotePeriod = keyof typeof periodDays
export const quoteActions = {
  send: { label: 'Enviar', done: 'Orçamento enviado.' },
  approve: { label: 'Aprovar', done: 'Orçamento aprovado.' },
  reject: { label: 'Rejeitar', done: 'Orçamento rejeitado.' },
  cancel: { label: 'Cancelar orçamento', done: 'Orçamento cancelado.' },
  reopen: { label: 'Reabrir', done: 'Orçamento reaberto como rascunho.' },
}
export type QuoteAction = keyof typeof quoteActions

const statusSchema = z.enum(
  Object.keys(quoteStatuses) as [QuoteStatus, ...QuoteStatus[]],
  'Situação desconhecida.',
)
const periodSchema = z.enum(['DIARIA', 'SEMANAL', 'QUINZENAL', 'MENSAL'])
export const quoteCustomerSchema = z.object({
  person_type: z.string(),
  legal_name: z.string(),
  trade_name: z.string(),
  document: z.string(),
  state_registration: z.string(),
  phone: z.string(),
  mobile: z.string(),
  email: z.string(),
  contact: z.string(),
  address: z
    .object({ street: z.string(), city: z.string(), state: z.string(), postal_code: z.string() })
    .nullable(),
})
export const quoteSummarySchema = z.object({
  id: z.number().int().positive(),
  number: z.string(),
  status: statusSchema,
  status_reason: z.string(),
  customer_id: z.number(),
  customer: quoteCustomerSchema,
  start_date: z.string(),
  valid_until: z.string(),
  notes: z.string(),
  total: z.string(),
  item_count: z.number(),
  duplicated_from_id: z.number().nullable(),
  version: z.number().int().positive(),
  created_at: z.number(),
  updated_at: z.number(),
  created_by: z.number(),
})
export const quoteItemSchema = z.object({
  id: z.number(),
  position: z.number(),
  product_id: z.number(),
  product_code: z.string(),
  product_name: z.string(),
  unit: z.string(),
  quantity: z.string(),
  period: periodSchema,
  period_count: z.number(),
  table_price: z.string(),
  unit_price: z.string(),
  negotiated: z.boolean(),
  total: z.string(),
  end_date: z.string(),
})
export const quoteSchema = quoteSummarySchema.extend({
  table_total: z.string(),
  negotiated_difference: z.string(),
  items: z.array(quoteItemSchema),
  transitions: z.array(
    z.object({
      from_status: z.string().nullable(),
      to_status: z.string(),
      reason: z.string(),
      created_at: z.number(),
      created_by: z.number(),
    }),
  ),
})
export const duplicatedQuoteSchema = quoteSchema.extend({ warnings: z.array(z.string()) })
export const pricingSchema = z.object({
  product_id: z.number(),
  product_code: z.string(),
  product_name: z.string(),
  unit: z.string(),
  individual_tracking: z.boolean(),
  period: periodSchema,
  at: z.string(),
  price_id: z.number().nullable(),
  table_price: z.string().nullable(),
  available: z.string(),
  period_days: z.number(),
})
export type QuoteSummary = z.infer<typeof quoteSummarySchema>
export type Quote = z.infer<typeof quoteSchema>
export type QuoteItem = z.infer<typeof quoteItemSchema>
export type Pricing = z.infer<typeof pricingSchema>

const quantityPattern = /^\d{1,6}([.,]\d{1,3})?$/
const pricePattern = /^\d{1,9}([.,]\d{1,2})?$/
export const quoteFormSchema = z
  .object({
    customer_id: z.string().min(1, 'Selecione um cliente.'),
    start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Informe o início previsto.'),
    valid_until: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Informe a validade do orçamento.'),
    notes: z.string().max(2000, 'Use até 2000 caracteres.'),
    refresh_prices: z.boolean(),
    items: z
      .array(
        z.object({
          product_id: z.string().min(1, 'Selecione um produto.'),
          quantity: z
            .string()
            .trim()
            .regex(quantityPattern, 'Use um número com até três casas decimais.')
            .refine((v) => (scaled(v, 3) ?? 0n) > 0n, 'A quantidade deve ser maior que zero.'),
          period: periodSchema,
          period_count: z
            .string()
            .trim()
            .regex(/^[1-9]\d{0,2}$/, 'Informe um número inteiro de 1 a 999.'),
          unit_price: z
            .string()
            .trim()
            .refine((v) => !v || pricePattern.test(v), 'Use um valor com até duas casas decimais.'),
        }),
      )
      .min(1, 'Adicione pelo menos um item.')
      .max(100, 'Um orçamento aceita até 100 itens.'),
  })
  .superRefine((data, context) => {
    const seen = new Set<string>()
    data.items.forEach((item, index) => {
      const key = item.product_id + '|' + item.period
      if (item.product_id && seen.has(key))
        context.addIssue({
          code: 'custom',
          path: ['items', index, 'product_id'],
          message: 'Produto repetido no mesmo período; some as quantidades.',
        })
      seen.add(key)
    })
  })
export type QuoteForm = z.infer<typeof quoteFormSchema>
export type QuoteFormItem = QuoteForm['items'][number]

/** Exact decimal text ("2,5" or "2.5") to a scaled integer; null when it is not a valid number. */
export function scaled(value: string, digits: number) {
  const match = /^(\d+)(?:[.,](\d+))?$/.exec(value.trim())
  if (!match || (match[2] || '').length > digits) return null
  return BigInt(match[1] + (match[2] || '').padEnd(digits, '0'))
}
export function centsText(cents: bigint) {
  const text = cents.toString().padStart(3, '0')
  return text.slice(0, -2) + '.' + text.slice(-2)
}
/** Preview only: quantity × period price × periods, half cent up. The server total is official. */
export function estimateCents(quantity: string, price: string, periodCount: string) {
  const milli = scaled(quantity, 3)
  const cents = scaled(price, 2)
  if (milli === null || cents === null || !/^[1-9]\d{0,2}$/.test(periodCount.trim())) return null
  return (milli * cents * BigInt(periodCount.trim()) + 500n) / 1000n
}
export function estimateEndDate(start: string, period: QuotePeriod, periodCount: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(start)
  if (!match || !/^[1-9]\d{0,2}$/.test(periodCount.trim())) return null
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
  date.setUTCDate(date.getUTCDate() + periodDays[period] * Number(periodCount.trim()))
  return date.toISOString().slice(0, 10)
}
export function brMoney(value: string) {
  const negative = value.startsWith('-')
  const [whole, cents] = value.replace('-', '').split('.')
  return (
    (negative ? '-' : '') +
    'R$ ' +
    whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.') +
    ',' +
    (cents || '00').padEnd(2, '0')
  )
}
export function brDate(iso: string) {
  const [year, month, day] = iso.split('-')
  return day && month ? `${day}/${month}/${year}` : iso
}
export function brDateTime(epoch: number) {
  return new Date(epoch * 1000).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}
/** "2.000" → "2"; "1.250" → "1,25". Display only. */
export function brQuantity(value: string) {
  const [whole, fraction = ''] = value.split('.')
  const trimmed = fraction.replace(/0+$/, '')
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (trimmed ? ',' + trimmed : '')
}
export function priceInput(value: string) {
  return value.replace('.', ',')
}
export function failureMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.status === 409)
    return error.message + ' Recarregue os dados para ver a versão atual antes de tentar de novo.'
  if (error instanceof ApiError && error.status === 403)
    return error.message + ' Peça a liberação ao administrador, se necessário.'
  return error instanceof Error ? error.message : fallback
}
export function isConflict(error: unknown) {
  return error instanceof ApiError && error.status === 409
}

type Request = AuthContextValue['request']
export async function listQuotes(
  request: Request,
  filters: { q: string; status: string; offset: number },
) {
  return pageSchema(quoteSummarySchema).parse(
    await request(
      '/quotes?limit=20&offset=' +
        filters.offset +
        '&q=' +
        encodeURIComponent(filters.q) +
        (filters.status ? '&status=' + filters.status : ''),
    ),
  )
}
export async function getQuote(request: Request, id: number) {
  return quoteSchema.parse(await request('/quotes/' + id))
}
export async function getPricing(request: Request, productId: string, period: string, at: string) {
  return pricingSchema.parse(
    await request('/quotes/pricing?product_id=' + productId + '&period=' + period + '&at=' + at),
  )
}
export function quoteBody(values: QuoteForm) {
  return {
    customer_id: Number(values.customer_id),
    start_date: values.start_date,
    valid_until: values.valid_until,
    notes: values.notes.trim(),
    items: values.items.map((item) => ({
      product_id: Number(item.product_id),
      quantity: decimalInput(item.quantity),
      period: item.period,
      period_count: Number(item.period_count.trim()),
      unit_price: item.unit_price.trim() ? decimalInput(item.unit_price) : null,
    })),
  }
}
export async function saveQuote(request: Request, values: QuoteForm, current?: Quote) {
  return quoteSchema.parse(
    current
      ? await request('/quotes/' + current.id, 'PUT', {
          ...quoteBody(values),
          version: current.version,
          refresh_prices: values.refresh_prices,
        })
      : await request('/quotes', 'POST', quoteBody(values)),
  )
}
export async function transitionQuote(
  request: Request,
  quote: Pick<Quote, 'id' | 'version'>,
  action: QuoteAction,
  reason: string,
) {
  return quoteSchema.parse(
    await request('/quotes/' + quote.id + '/' + action, 'POST', {
      version: quote.version,
      reason: reason.trim(),
    }),
  )
}
export async function duplicateQuote(request: Request, id: number) {
  return duplicatedQuoteSchema.parse(await request('/quotes/' + id + '/duplicate', 'POST', {}))
}
export function downloadQuotePdf(quote: Pick<Quote, 'id' | 'number'>) {
  return downloadPdf('/quotes/' + quote.id + '/pdf', quote.number + '.pdf')
}
/** Authenticated same-origin download; the PDF never goes through the JSON client. */
export async function downloadPdf(path: string, filename: string) {
  let response: Response
  try {
    response = await fetch('/api' + path, {
      credentials: 'same-origin',
      headers: { 'X-LocaControl-Request': '1' },
    })
  } catch {
    throw new ApiError(0, 'Não foi possível conectar. Verifique se o servidor está ativo.')
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      typeof error.detail === 'string' ? error.detail : 'Não foi possível gerar o PDF.',
    )
  }
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
