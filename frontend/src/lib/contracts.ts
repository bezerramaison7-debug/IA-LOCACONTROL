import { z } from 'zod'
import { ApiError } from '../auth/api'
import { useAuth, type AuthContextValue } from '../auth/context'
import { pageSchema } from './masters'
import {
  downloadPdf,
  failureMessage,
  isConflict,
  quoteBody,
  quoteCustomerSchema,
  scaled,
  type QuoteForm,
} from './quotes'

export const contractStatuses = {
  RASCUNHO: 'Rascunho',
  AGUARDANDO_RETIRADA: 'Aguardando retirada',
  ATIVO: 'Ativo',
  VENCENDO: 'Vencendo',
  VENCIDO: 'Vencido',
  ENCERRADO: 'Encerrado',
  CANCELADO: 'Cancelado',
}
export type ContractStatus = keyof typeof contractStatuses
export const contractOrigins: Record<string, string> = {
  DIRETO: 'Contrato direto',
  ORCAMENTO: 'Orçamento aprovado',
  RENOVACAO: 'Renovação',
  IMPORTADO: 'Importado',
}
export const priceOptions = {
  ANTERIORES: 'Manter os preços anteriores',
  ATUAIS: 'Aplicar os preços atuais da tabela',
  NEGOCIADOS: 'Informar preços negociados',
}
export type PriceOption = keyof typeof priceOptions
export const eventKinds: Record<string, string> = {
  CRIADO: 'Criado',
  CONFIRMADO: 'Confirmado',
  RETIRADA: 'Retirada',
  RENOVADO: 'Renovado',
  RENOVACAO: 'Renovação',
  DEVOLUCAO: 'Devolução',
  ENCERRADO: 'Encerrado',
  CANCELADO: 'Cancelado',
  DOCUMENTO: 'Documento',
  ASSINADO: 'Assinado',
}
export const documentStatuses = {
  GERADO: 'Gerado',
  ASSINADO: 'Assinado',
  SUBSTITUIDO: 'Substituído',
}
export type DocumentStatus = keyof typeof documentStatuses
export const unitStates = {
  EM_POSSE: 'Com o cliente',
  DEVOLVIDO: 'Devolvido',
  RENOVADO: 'Renovado',
}
export const conditions = { BOM: 'Bom estado', AVARIADO: 'Avariado' }
export type Condition = keyof typeof conditions
export const destinations = { DISPONIVEL: 'Disponível', MANUTENCAO: 'Manutenção' }
export type Destination = keyof typeof destinations
export const contractActions = {
  confirm: { label: 'Confirmar contrato', done: 'Contrato confirmado. Aguardando retirada.' },
  cancel: { label: 'Cancelar contrato', done: 'Contrato cancelado.' },
  close: { label: 'Encerrar contrato', done: 'Contrato encerrado.' },
}
export type ContractAction = keyof typeof contractActions

const statusSchema = z.enum(
  Object.keys(contractStatuses) as [ContractStatus, ...ContractStatus[]],
  'Situação desconhecida.',
)
const periodSchema = z.enum(['DIARIA', 'SEMANAL', 'QUINZENAL', 'MENSAL'])
export const contractSummarySchema = z.object({
  id: z.number().int().positive(),
  number: z.string(),
  base_number: z.number(),
  renewal_number: z.number(),
  chain_id: z.number(),
  previous_id: z.number().nullable(),
  customer_id: z.number(),
  customer: quoteCustomerSchema,
  quote_id: z.number().nullable(),
  origin: z.string(),
  price_option: z.enum(['ANTERIORES', 'ATUAIS', 'NEGOCIADOS']).nullable(),
  status: statusSchema,
  stored_status: z.string(),
  status_reason: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  due_date: z.string().nullable(),
  notes: z.string(),
  total: z.string(),
  item_count: z.number(),
  version: z.number().int().positive(),
  created_at: z.number(),
  updated_at: z.number(),
  created_by: z.number(),
})
export const contractItemSchema = z.object({
  id: z.number(),
  position: z.number(),
  product_id: z.number(),
  product_code: z.string(),
  product_name: z.string(),
  description: z.string(),
  unit: z.string(),
  individual_tracking: z.boolean(),
  quantity: z.string(),
  period: periodSchema,
  period_count: z.number(),
  table_price: z.string(),
  unit_price: z.string(),
  negotiated: z.boolean(),
  discount: z.string(),
  total: z.string(),
  start_date: z.string(),
  end_date: z.string(),
  source_item_id: z.number().nullable(),
  withdrawn: z.string(),
  returned: z.string(),
  renewed: z.string(),
  outstanding: z.string(),
  to_withdraw: z.string(),
  units: z.array(
    z.object({
      equipment_id: z.number(),
      code: z.string(),
      state: z.enum(['EM_POSSE', 'DEVOLVIDO', 'RENOVADO']),
    }),
  ),
})
export const contractDocumentSchema = z.object({
  id: z.number(),
  contract_id: z.number(),
  template_id: z.number(),
  version: z.number(),
  status: z.enum(['GERADO', 'ASSINADO', 'SUBSTITUIDO']),
  reason: z.string(),
  checksum: z.string(),
  size: z.number(),
  signed_at: z.number().nullable(),
  signed_by: z.number().nullable(),
  created_at: z.number(),
  created_by: z.number(),
})
const movement = {
  id: z.number(),
  occurred_on: z.string(),
  notes: z.string(),
  created_at: z.number(),
  created_by: z.number(),
}
const movementLine = {
  contract_item_id: z.number(),
  quantity: z.string(),
  equipment_id: z.number().nullable(),
}
export const contractSchema = contractSummarySchema.extend({
  quote_number: z.string().nullable(),
  table_total: z.string(),
  negotiated_difference: z.string(),
  items: z.array(contractItemSchema),
  chain: z.array(
    z.object({
      id: z.number(),
      number: z.string(),
      status: statusSchema,
      start_date: z.string(),
      end_date: z.string(),
      total: z.string(),
    }),
  ),
  events: z.array(
    z.object({
      id: z.number(),
      contract_id: z.number(),
      kind: z.string(),
      description: z.string(),
      created_at: z.number(),
      created_by: z.number(),
    }),
  ),
  documents: z.array(contractDocumentSchema),
  withdrawals: z.array(z.object({ ...movement, items: z.array(z.object(movementLine)) })),
  returns: z.array(
    z.object({
      ...movement,
      items: z.array(
        z.object({
          ...movementLine,
          condition: z.string(),
          destination: z.string(),
          notes: z.string(),
        }),
      ),
    }),
  ),
})
export const numberingSchema = z.object({
  configured: z.number().nullable(),
  highest_used: z.number().nullable(),
  next_number: z.number(),
})
export const templatesSchema = z.object({
  items: z.array(
    z.object({
      id: z.number(),
      name: z.string(),
      version: z.number(),
      is_provisional: z.boolean(),
      is_active: z.boolean(),
      body: z.string(),
      created_at: z.number(),
      // The initial model is seeded by the migration, without an author.
      created_by: z.number().nullable(),
    }),
  ),
  fields: z.array(z.string()),
  blocks: z.array(z.string()),
})
export type ContractSummary = z.infer<typeof contractSummarySchema>
export type Contract = z.infer<typeof contractSchema>
export type ContractItem = z.infer<typeof contractItemSchema>
export type ContractDocument = z.infer<typeof contractDocumentSchema>
export type Templates = z.infer<typeof templatesSchema>

/** True when the exact decimal text is above zero ("0.000" is not). */
export function positive(value: string) {
  return (scaled(value, 3) ?? 0n) > 0n
}
/** Whole units of an individually tracked item ("2.000" → 2). */
export function wholeUnits(value: string) {
  return Number((scaled(value, 3) ?? 0n) / 1000n)
}
/** "2.000" → "2", "1.250" → "1,25": an editable pt-BR default for a quantity field. */
export function quantityInput(value: string) {
  const [whole, fraction = ''] = value.split('.')
  const trimmed = fraction.replace(/0+$/, '')
  return trimmed ? whole + ',' + trimmed : whole
}
export function expectedReturn(contract: Pick<ContractSummary, 'due_date' | 'end_date'>) {
  return contract.due_date || contract.end_date
}

export function useContractPermissions() {
  const { user } = useAuth()
  const has = (code: string) => !!user?.permissions.includes(code)
  return {
    has,
    read: has('contracts.read'),
    write: has('contracts.write'),
    negotiate: has('contracts.negotiate'),
    configure: has('contracts.configure'),
    operate: has('operations.write'),
  }
}

export type ActionError = { message: string; conflict: boolean }
export function actionError(error: unknown, fallback: string): ActionError {
  return {
    message:
      error instanceof ApiError && error.status === 422
        ? error.message + ' Corrija os dados e tente de novo.'
        : failureMessage(error, fallback),
    conflict: isConflict(error),
  }
}
export function customerLine(contract: Pick<ContractSummary, 'customer'>) {
  return contract.customer.legal_name + ' · ' + contract.customer.document
}

type Request = AuthContextValue['request']
export type ContractFilters = {
  q: string
  status: string
  offset: number
  origin?: string
  product?: string
  equipment?: string
  period?: string
  start_from?: string
  start_to?: string
}
export const advancedFilterKeys = [
  'origin',
  'product',
  'equipment',
  'period',
  'start_from',
  'start_to',
] as const
export async function listContracts(request: Request, filters: ContractFilters, limit = 20) {
  return pageSchema(contractSummarySchema).parse(
    await request(
      '/contracts?limit=' +
        limit +
        '&offset=' +
        filters.offset +
        '&q=' +
        encodeURIComponent(filters.q) +
        (filters.status ? '&status=' + filters.status : '') +
        advancedFilterKeys
          .map((key) => {
            const value = (filters[key] || '').trim()
            return value ? '&' + key + '=' + encodeURIComponent(value) : ''
          })
          .join(''),
    ),
  )
}
/**
 * Operational views need every contract of a status; the API pages by 100, so this walks the
 * pages up to a fixed ceiling and reports when the list was cut.
 */
export async function listAllContracts(
  request: Request,
  status: string,
  ceiling = 500,
  origin = '',
) {
  const items: ContractSummary[] = []
  let total: number
  do {
    const page = await listContracts(request, { q: '', status, offset: items.length, origin }, 100)
    total = page.total
    items.push(...page.items)
    if (!page.items.length) break
  } while (items.length < total && items.length < ceiling)
  return { items, total, truncated: items.length < total }
}
export async function getContract(request: Request, id: number) {
  return contractSchema.parse(await request('/contracts/' + id))
}
/** The contract draft reuses the quote item form; only the quote validity is left out. */
export function contractBody(values: QuoteForm) {
  const { customer_id, start_date, notes, items } = quoteBody(values)
  return { customer_id, start_date, notes, items }
}
export async function saveContract(request: Request, values: QuoteForm, current?: Contract) {
  return contractSchema.parse(
    current
      ? await request('/contracts/' + current.id, 'PUT', {
          ...contractBody(values),
          version: current.version,
          refresh_prices: values.refresh_prices,
        })
      : await request('/contracts', 'POST', contractBody(values)),
  )
}
export async function transitionContract(
  request: Request,
  contract: Pick<Contract, 'id' | 'version'>,
  action: ContractAction,
  reason: string,
) {
  return contractSchema.parse(
    await request('/contracts/' + contract.id + '/' + action, 'POST', {
      version: contract.version,
      reason: reason.trim(),
    }),
  )
}
export async function contractFromQuote(request: Request, quote: { id: number; version: number }) {
  return contractSchema.parse(
    await request('/contracts/from-quote/' + quote.id, 'POST', {
      version: quote.version,
      reason: '',
    }),
  )
}
/** Finds the contract created from a quote; the quote itself does not carry the link. */
export async function findContractOfQuote(
  request: Request,
  quote: { id: number; customer_id: number },
) {
  const page = pageSchema(contractSummarySchema).parse(
    await request('/contracts?limit=100&offset=0&customer_id=' + quote.customer_id),
  )
  return page.items.find((row) => row.quote_id === quote.id) ?? null
}
export async function getNumbering(request: Request) {
  return numberingSchema.parse(await request('/contracts/numbering'))
}
export async function setNumbering(request: Request, next: number) {
  return numberingSchema.parse(await request('/contracts/numbering', 'PUT', { next_number: next }))
}
export async function getTemplates(request: Request) {
  return templatesSchema.parse(await request('/contracts/templates'))
}
export async function publishTemplate(
  request: Request,
  values: { name: string; body: string; is_provisional: boolean },
) {
  return request('/contracts/templates', 'POST', { ...values, name: values.name.trim() })
}
export async function generateDocument(request: Request, contractId: number, reason: string) {
  return contractDocumentSchema.parse(
    await request('/contracts/' + contractId + '/documents', 'POST', { reason: reason.trim() }),
  )
}
export async function signDocument(request: Request, documentId: number, notes: string) {
  return request('/contracts/documents/' + documentId + '/sign', 'POST', { notes: notes.trim() })
}
export function downloadPreview(contract: Pick<Contract, 'id' | 'number'>) {
  return downloadPdf(
    '/contracts/' + contract.id + '/preview.pdf',
    'Contrato-' + contract.number + '-previa.pdf',
  )
}
export function downloadDocument(contract: Pick<Contract, 'number'>, document: ContractDocument) {
  return downloadPdf(
    '/contracts/documents/' + document.id + '/download',
    'Contrato-' + contract.number + '-v' + document.version + '.pdf',
  )
}

export type WithdrawalBody = {
  occurred_on: string
  notes: string
  request_key: string
  items: { contract_item_id: number; quantity: string; equipment_ids: number[] }[]
}
export async function registerWithdrawal(request: Request, id: number, body: WithdrawalBody) {
  return contractSchema.parse(await request('/contracts/' + id + '/withdrawals', 'POST', body))
}
export type ReturnBody = {
  occurred_on: string
  notes: string
  request_key: string
  items: {
    contract_item_id: number
    quantity: string
    equipment_id: number | null
    condition: Condition
    destination: Destination
    notes: string
  }[]
}
export async function registerReturn(request: Request, id: number, body: ReturnBody) {
  return contractSchema.parse(await request('/contracts/' + id + '/returns', 'POST', body))
}
export type RenewalBody = {
  version: number
  start_date: string
  price_option: PriceOption
  notes: string
  items: {
    source_item_id: number
    quantity: string
    period: string
    period_count: number
    unit_price: string | null
    equipment_ids: number[]
  }[]
}
export async function renewContract(request: Request, id: number, body: RenewalBody) {
  return contractSchema.parse(await request('/contracts/' + id + '/renew', 'POST', body))
}
