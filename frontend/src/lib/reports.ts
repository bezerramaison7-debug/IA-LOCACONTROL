import { z } from 'zod'
import type { AuthContextValue } from '../auth/context'
import {
  conditions,
  contractDocumentSchema,
  contractStatuses,
  contractSummarySchema,
  destinations,
} from './contracts'
import { states } from './masters'
import { brDate, brMoney, brQuantity, downloadFile } from './quotes'

export const dashboardSchema = z.object({
  cards: z.object({
    active_contracts: z.number(),
    awaiting_withdrawal: z.number(),
    due_soon: z.number(),
    overdue: z.number(),
    rented_items: z.string(),
    equipment_available: z.number(),
    equipment_maintenance: z.number(),
    contracted_value: z.string(),
    open_quotes: z.number(),
  }),
  due_soon_days: z.number(),
  due_contracts: z.array(contractSummarySchema),
  recent_events: z.array(
    z.object({
      id: z.number(),
      contract_id: z.number(),
      contract_number: z.string(),
      customer: z.string(),
      kind: z.string(),
      description: z.string(),
      created_at: z.number(),
    }),
  ),
})
export const customerSummarySchema = z.object({
  active_contracts: z.number(),
  total_contracts: z.number(),
  rented_items: z.string(),
  contracted_value: z.string(),
  contracts: z.array(contractSummarySchema),
  documents: z.array(contractDocumentSchema.extend({ contract_number: z.string() })),
})
export const catalogSchema = z.object({
  items: z.array(z.object({ key: z.string(), title: z.string() })),
})
const columnSchema = z.object({
  key: z.string(),
  label: z.string(),
  type: z.enum(['text', 'money', 'quantity', 'date', 'int', 'status']),
})
const cellSchema = z.union([z.string(), z.number(), z.null()])
export const reportSchema = z.object({
  key: z.string(),
  title: z.string(),
  note: z.string(),
  columns: z.array(columnSchema),
  total: z.number(),
  rows: z.array(z.record(z.string(), cellSchema)),
})
export type Dashboard = z.infer<typeof dashboardSchema>
export type CustomerSummary = z.infer<typeof customerSummarySchema>
export type Report = z.infer<typeof reportSchema>
export type ReportColumn = z.infer<typeof columnSchema>
export type ReportCell = z.infer<typeof cellSchema>

export type ReportFilters = {
  date_from: string
  date_to: string
  customer_id: string
  product_id: string
  q: string
}
export const emptyFilters: ReportFilters = {
  date_from: '',
  date_to: '',
  customer_id: '',
  product_id: '',
  q: '',
}
export type FilterKind = 'period' | 'customer' | 'product' | 'q'
/** Filters each report really applies on the server; an unknown report offers all of them. */
const supported: Record<string, FilterKind[]> = {
  active_rentals: ['period', 'customer', 'product'],
  due_soon: ['period', 'customer', 'product'],
  overdue: ['period', 'customer', 'product'],
  rented_products: ['product', 'q'],
  available_products: ['product', 'q'],
  equipment_by_customer: ['customer', 'product'],
  equipment_history: ['period', 'product', 'q'],
  renewals: ['period', 'customer'],
  returns: ['period', 'customer', 'product'],
  contracted_revenue: ['period', 'customer'],
  top_products: ['period', 'customer', 'product'],
  top_customers: ['period', 'customer'],
}
export function reportFilterKinds(key: string): FilterKind[] {
  return supported[key] || ['period', 'customer', 'product', 'q']
}
/** Only the filters the report applies are sent, so a hidden field never narrows the result. */
export function reportParams(key: string, filters: ReportFilters) {
  const kinds = reportFilterKinds(key)
  const params = new URLSearchParams()
  if (kinds.includes('period')) {
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
  }
  if (kinds.includes('customer') && filters.customer_id)
    params.set('customer_id', filters.customer_id)
  if (kinds.includes('product') && filters.product_id) params.set('product_id', filters.product_id)
  if (kinds.includes('q') && filters.q.trim()) params.set('q', filters.q.trim())
  return params
}
export const REPORT_PAGE = 50
export function reportPath(key: string, filters: ReportFilters, offset: number) {
  const params = reportParams(key, filters)
  params.set('offset', String(offset))
  params.set('limit', String(REPORT_PAGE))
  return '/reports/' + key + '?' + params.toString()
}
export type ExportFormat = 'xlsx' | 'pdf'
export function exportPath(key: string, format: ExportFormat, filters: ReportFilters) {
  const params = reportParams(key, filters)
  params.set('format', format)
  return '/reports/' + key + '/export?' + params.toString()
}

const statusLabels: Record<string, string> = {
  ...states,
  ...contractStatuses,
  ...conditions,
  ...destinations,
  ANTERIORES: 'Preços anteriores',
  ATUAIS: 'Preços atuais da tabela',
  NEGOCIADOS: 'Preços negociados',
}
export function reportStatus(value: string) {
  return statusLabels[value] || value
}
/** Display text of a report cell by the column type declared by the server. */
export function formatCell(type: ReportColumn['type'], value: ReportCell | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  const text = String(value)
  if (type === 'money') return brMoney(text)
  if (type === 'quantity') return brQuantity(text)
  if (type === 'date') return brDate(text)
  if (type === 'int') return Number(value).toLocaleString('pt-BR')
  if (type === 'status') return reportStatus(text)
  return text
}
export const numericTypes: ReportColumn['type'][] = ['money', 'quantity', 'int']

type Request = AuthContextValue['request']
export async function getDashboard(request: Request) {
  return dashboardSchema.parse(await request('/dashboard'))
}
export async function getCustomerSummary(request: Request, customerId: number) {
  return customerSummarySchema.parse(await request('/customers/' + customerId + '/summary'))
}
export async function getCatalog(request: Request) {
  return catalogSchema.parse(await request('/reports'))
}
export async function getReport(
  request: Request,
  key: string,
  filters: ReportFilters,
  offset: number,
) {
  return reportSchema.parse(await request(reportPath(key, filters, offset)))
}
export function downloadReport(key: string, format: ExportFormat, filters: ReportFilters) {
  return downloadFile(
    exportPath(key, format, filters),
    'relatorio-' + key + '.' + format,
    'Não foi possível exportar o relatório.',
  )
}
