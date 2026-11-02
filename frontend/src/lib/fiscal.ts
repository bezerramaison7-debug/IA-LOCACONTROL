import { z } from 'zod'
import type { AuthContextValue } from '../auth/context'
import { decimalInput, pageSchema } from './masters'
import { downloadFile, quoteCustomerSchema } from './quotes'

export const fiscalStatuses = {
  PENDENTE: 'Pendente',
  PROCESSANDO: 'Processando',
  EMITIDO: 'Emitido',
  ERRO: 'Erro',
  CANCELADO: 'Cancelado',
}
export type FiscalStatus = keyof typeof fiscalStatuses
export const fiscalEventActions: Record<string, string> = {
  CREATE: 'Registro criado',
  EMIT: 'Envio ao provedor',
  STATUS: 'Consulta de situação',
  CANCEL: 'Cancelamento',
}
export const fiscalActions = {
  emit: { label: 'Enviar ao provedor', done: 'Documento enviado ao provedor.' },
  refresh: { label: 'Consultar situação', done: 'Situação consultada no provedor.' },
  cancel: { label: 'Cancelar documento', done: 'Cancelamento registrado.' },
}
export type FiscalAction = keyof typeof fiscalActions

export const providerSchema = z.object({
  name: z.string(),
  environment: z.string(),
  is_simulation: z.boolean(),
  document_kind: z.string(),
})
export const fiscalDocumentSchema = z.object({
  id: z.number(),
  customer_id: z.number(),
  customer: quoteCustomerSchema.partial().extend({ legal_name: z.string(), document: z.string() }),
  contract_id: z.number().nullable(),
  period_start: z.string(),
  period_end: z.string(),
  amount: z.string(),
  description: z.string(),
  status: z.enum(
    Object.keys(fiscalStatuses) as [FiscalStatus, ...FiscalStatus[]],
    'Situação desconhecida.',
  ),
  provider: z.string(),
  environment: z.string(),
  is_simulation: z.boolean(),
  provider_ref: z.string().nullable(),
  number: z.string().nullable(),
  series: z.string().nullable(),
  access_key: z.string().nullable(),
  error_message: z.string(),
  cancel_reason: z.string(),
  has_pdf: z.boolean(),
  has_xml: z.boolean(),
  version: z.number().int().positive(),
  created_at: z.number(),
  updated_at: z.number(),
  created_by: z.number(),
})
export const fiscalDetailSchema = fiscalDocumentSchema.extend({
  events: z.array(
    z.object({
      action: z.string(),
      status: z.string(),
      response: z.record(z.string(), z.unknown()),
      created_at: z.number(),
      created_by: z.number(),
    }),
  ),
})
export type FiscalProvider = z.infer<typeof providerSchema>
export type FiscalDocument = z.infer<typeof fiscalDocumentSchema>
export type FiscalDetail = z.infer<typeof fiscalDetailSchema>

export const fiscalFormSchema = z
  .object({
    customer_id: z.string().min(1, 'Selecione um cliente.'),
    contract_id: z.string(),
    period_start: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Informe o início do período.'),
    period_end: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Informe o fim do período.'),
    amount: z
      .string()
      .trim()
      .regex(/^\d{1,9}([.,]\d{1,2})?$/, 'Use um valor com até duas casas decimais.')
      .refine((value) => Number(decimalInput(value)) > 0, 'O valor deve ser maior que zero.'),
    description: z
      .string()
      .trim()
      .min(5, 'Descreva o faturamento com pelo menos 5 caracteres.')
      .max(500, 'Use até 500 caracteres.'),
  })
  .refine((data) => !data.period_end || data.period_end >= data.period_start, {
    path: ['period_end'],
    message: 'O fim do período não pode ser anterior ao início.',
  })
export type FiscalForm = z.infer<typeof fiscalFormSchema>

type Request = AuthContextValue['request']
export type FiscalFilters = { status: string; customer_id: string; offset: number }
export async function getProvider(request: Request) {
  return providerSchema.parse(await request('/fiscal/provider'))
}
export async function listFiscal(request: Request, filters: FiscalFilters) {
  return pageSchema(fiscalDocumentSchema).parse(
    await request(
      '/fiscal/documents?limit=20&offset=' +
        filters.offset +
        (filters.status ? '&status=' + filters.status : '') +
        (filters.customer_id ? '&customer_id=' + filters.customer_id : ''),
    ),
  )
}
export async function getFiscal(request: Request, id: number) {
  return fiscalDetailSchema.parse(await request('/fiscal/documents/' + id))
}
/** `requestKey` is generated once per form, so a repeated submit never duplicates the record. */
export async function createFiscal(request: Request, values: FiscalForm, requestKey: string) {
  return fiscalDocumentSchema.parse(
    await request('/fiscal/documents', 'POST', {
      customer_id: Number(values.customer_id),
      contract_id: values.contract_id ? Number(values.contract_id) : null,
      period_start: values.period_start,
      period_end: values.period_end,
      amount: decimalInput(values.amount),
      description: values.description.trim(),
      request_key: requestKey,
    }),
  )
}
export async function actOnFiscal(
  request: Request,
  document: Pick<FiscalDocument, 'id' | 'version'>,
  action: FiscalAction,
  reason: string,
) {
  return fiscalDetailSchema.parse(
    await request('/fiscal/documents/' + document.id + '/' + action, 'POST', {
      version: document.version,
      reason: reason.trim(),
    }),
  )
}
export function downloadFiscal(
  document: Pick<FiscalDocument, 'id' | 'number'>,
  kind: 'pdf' | 'xml',
) {
  return downloadFile(
    '/fiscal/documents/' + document.id + '/' + kind,
    'documento-fiscal-' + (document.number || document.id) + '.' + kind,
    'Não foi possível baixar o arquivo do documento.',
  )
}
