import { z } from 'zod'
import type { AuthContextValue } from '../auth/context'
import { contractStatuses, type ContractStatus } from './contracts'
import { addressSchema, pageSchema } from './masters'
import { downloadPdf, quoteStatuses, type QuoteStatus } from './quotes'

export const requestStatuses = {
  PENDENTE: 'Em análise',
  APROVADA: 'Aprovada',
  RECUSADA: 'Recusada',
  CANCELADA: 'Cancelada',
}
export type RequestStatus = keyof typeof requestStatuses

const contractStatus = z.enum(
  Object.keys(contractStatuses) as [ContractStatus, ...ContractStatus[]],
  'Situação desconhecida.',
)
const quoteStatus = z.enum(
  Object.keys(quoteStatuses) as [QuoteStatus, ...QuoteStatus[]],
  'Situação desconhecida.',
)
const periodSchema = z.enum(['DIARIA', 'SEMANAL', 'QUINZENAL', 'MENSAL'])
const documentStatus = z.enum(['GERADO', 'ASSINADO', 'SUBSTITUIDO'])
export const portalContractSchema = z.object({
  id: z.number(),
  number: z.string(),
  status: contractStatus,
  start_date: z.string(),
  end_date: z.string(),
  due_date: z.string().nullable(),
  total: z.string(),
})
export const portalDashboardSchema = z.object({
  active_contracts: z.number(),
  rented_items: z.string(),
  next_due: z.array(portalContractSchema),
  pending_requests: z.number(),
})
export const portalContractDetailSchema = portalContractSchema.extend({
  origin: z.string(),
  items: z.array(
    z.object({
      product_code: z.string(),
      product_name: z.string(),
      unit: z.string(),
      quantity: z.string(),
      period: periodSchema,
      period_count: z.number(),
      unit_price: z.string(),
      total: z.string(),
      start_date: z.string(),
      end_date: z.string(),
      withdrawn: z.string(),
      returned: z.string(),
      outstanding: z.string(),
      units: z.array(z.object({ code: z.string(), state: z.string() })),
    }),
  ),
  chain: z.array(
    z.object({
      id: z.number(),
      number: z.string(),
      status: contractStatus,
      start_date: z.string(),
      end_date: z.string(),
      total: z.string(),
    }),
  ),
  events: z.array(z.object({ kind: z.string(), description: z.string(), created_at: z.number() })),
  documents: z.array(
    z.object({
      id: z.number(),
      version: z.number(),
      status: documentStatus,
      created_at: z.number(),
      signed_at: z.number().nullable(),
    }),
  ),
})
export const portalEquipmentSchema = z.object({
  items: z.array(
    z.object({
      contract_id: z.number(),
      contract_number: z.string(),
      product_code: z.string(),
      product_name: z.string(),
      unit: z.string(),
      quantity: z.string(),
      units: z.array(z.string()),
      due_date: z.string(),
    }),
  ),
})
export const portalDocumentSchema = z.object({
  id: z.number(),
  contract_id: z.number(),
  contract_number: z.string(),
  version: z.number(),
  status: documentStatus,
  created_at: z.number(),
  signed_at: z.number().nullable(),
})
export const portalQuoteSchema = z.object({
  id: z.number(),
  number: z.string(),
  status: quoteStatus,
  start_date: z.string(),
  valid_until: z.string(),
  total: z.string(),
})
export const portalQuoteDetailSchema = portalQuoteSchema.extend({
  items: z.array(
    z.object({
      product_code: z.string(),
      product_name: z.string(),
      unit: z.string(),
      quantity: z.string(),
      period: periodSchema,
      period_count: z.number(),
      unit_price: z.string(),
      total: z.string(),
      end_date: z.string(),
    }),
  ),
})
export const portalProfileSchema = z.object({
  person_type: z.string(),
  legal_name: z.string(),
  trade_name: z.string(),
  document: z.string(),
  state_registration: z.string(),
  phone: z.string(),
  mobile: z.string(),
  email: z.string(),
  contact: z.string(),
  addresses: z.array(addressSchema),
})
const requestFields = {
  id: z.number(),
  contract_id: z.number(),
  contract_number: z.string(),
  period: periodSchema,
  period_count: z.number(),
  notes: z.string(),
  status: z.enum(['PENDENTE', 'APROVADA', 'RECUSADA', 'CANCELADA']),
  decision_reason: z.string(),
  decided_at: z.number().nullable(),
  created_at: z.number(),
}
export const renewalRequestSchema = z.object(requestFields)
export const internalRequestSchema = z.object({
  ...requestFields,
  customer_id: z.number(),
  customer: z.string(),
  requested_by: z.number(),
  decided_by: z.number().nullable(),
})
export const customerLinkSchema = z.object({
  user_id: z.number(),
  customer_id: z.number().nullable(),
  customer: z.string().nullable(),
})
export type PortalContract = z.infer<typeof portalContractSchema>
export type PortalContractDetail = z.infer<typeof portalContractDetailSchema>
export type PortalDocument = z.infer<typeof portalDocumentSchema>
export type PortalQuote = z.infer<typeof portalQuoteSchema>
export type RenewalRequest = z.infer<typeof renewalRequestSchema>
export type InternalRequest = z.infer<typeof internalRequestSchema>
export type CustomerLink = z.infer<typeof customerLinkSchema>

const list = <T extends z.ZodType>(schema: T) => z.object({ items: z.array(schema) })
type Request = AuthContextValue['request']

export async function getPortalDashboard(request: Request) {
  return portalDashboardSchema.parse(await request('/portal/dashboard'))
}
export async function listPortalContracts(request: Request, status: string) {
  return list(portalContractSchema).parse(
    await request('/portal/contracts' + (status ? '?status=' + status : '')),
  )
}
export async function getPortalContract(request: Request, id: number) {
  return portalContractDetailSchema.parse(await request('/portal/contracts/' + id))
}
export async function getPortalEquipment(request: Request) {
  return portalEquipmentSchema.parse(await request('/portal/equipment'))
}
export async function listPortalDocuments(request: Request) {
  return list(portalDocumentSchema).parse(await request('/portal/documents'))
}
export async function listPortalQuotes(request: Request) {
  return list(portalQuoteSchema).parse(await request('/portal/quotes'))
}
export async function getPortalQuote(request: Request, id: number) {
  return portalQuoteDetailSchema.parse(await request('/portal/quotes/' + id))
}
export async function getPortalProfile(request: Request) {
  return portalProfileSchema.parse(await request('/portal/profile'))
}
export async function listMyRequests(request: Request) {
  return list(renewalRequestSchema).parse(await request('/portal/renewal-requests'))
}
export type RenewalRequestBody = {
  contract_id: number
  period: string
  period_count: number
  notes: string
}
export async function requestRenewal(request: Request, body: RenewalRequestBody) {
  return renewalRequestSchema.parse(await request('/portal/renewal-requests', 'POST', body))
}
export async function cancelMyRequest(request: Request, id: number) {
  return renewalRequestSchema.parse(
    await request('/portal/renewal-requests/' + id + '/cancel', 'POST'),
  )
}
export function downloadPortalDocument(document: {
  id: number
  contract_number: string
  version: number
}) {
  return downloadPdf(
    '/portal/documents/' + document.id + '/download',
    'Contrato-' + document.contract_number + '-v' + document.version + '.pdf',
  )
}
export function downloadPortalQuote(quote: Pick<PortalQuote, 'id' | 'number'>) {
  return downloadPdf('/portal/quotes/' + quote.id + '/pdf', quote.number + '.pdf')
}

// ---- internal side: account link and renewal requests ---------------------------------

export async function getCustomerLink(request: Request, userId: number) {
  return customerLinkSchema.parse(await request('/users/' + userId + '/customer'))
}
export async function setCustomerLink(request: Request, userId: number, customerId: number | null) {
  return customerLinkSchema.parse(
    await request('/users/' + userId + '/customer', 'PUT', { customer_id: customerId }),
  )
}
export async function listRenewalRequests(request: Request, status: string, offset: number) {
  return pageSchema(internalRequestSchema).parse(
    await request(
      '/renewal-requests?limit=20&offset=' + offset + (status ? '&status=' + status : ''),
    ),
  )
}
export type Decision = 'APROVADA' | 'RECUSADA'
export async function decideRequest(
  request: Request,
  id: number,
  decision: Decision,
  reason: string,
) {
  return internalRequestSchema.parse(
    await request('/renewal-requests/' + id + '/decide', 'POST', {
      decision,
      reason: reason.trim(),
    }),
  )
}
