import { z } from 'zod'

export const states = {
  DISPONIVEL: 'Disponível',
  RESERVADO: 'Reservado',
  LOCADO: 'Locado',
  MANUTENCAO: 'Manutenção',
  INDISPONIVEL: 'Indisponível',
  BAIXADO: 'Baixado',
}
export const periods = {
  DIARIA: 'Diária',
  SEMANAL: 'Semanal',
  QUINZENAL: 'Quinzenal',
  MENSAL: 'Mensal',
}
export const addressSchema = z.object({
  label: z.string(),
  street: z.string(),
  city: z.string(),
  state: z.string(),
  postal_code: z.string(),
})
export type Address = z.infer<typeof addressSchema>
const stamp = { id: z.number().int().positive(), created_at: z.number(), created_by: z.number() }
const editable = { ...stamp, version: z.number().int().positive(), updated_at: z.number() }
export const customerSchema = z.object({
  ...editable,
  person_type: z.enum(['PF', 'PJ']),
  legal_name: z.string(),
  trade_name: z.string(),
  document: z.string(),
  state_registration: z.string(),
  phone: z.string(),
  mobile: z.string(),
  email: z.string(),
  contact: z.string(),
  notes: z.string(),
  is_active: z.boolean(),
  addresses: z.array(addressSchema),
})
export const productSchema = z.object({
  ...editable,
  code: z.string(),
  name: z.string(),
  description: z.string(),
  category: z.string(),
  unit: z.string(),
  individual_tracking: z.boolean(),
  is_active: z.boolean(),
})
export const equipmentSchema = z.object({
  ...editable,
  product_id: z.number(),
  product_name: z.string(),
  product_code: z.string(),
  code: z.string(),
  asset_tag: z.string().nullable(),
  serial_number: z.string().nullable(),
  brand: z.string(),
  model: z.string(),
  notes: z.string(),
  status: z.enum(Object.keys(states) as [keyof typeof states, ...(keyof typeof states)[]]),
})
export const stockSchema = productSchema.extend({
  balances: z.object({
    DISPONIVEL: z.string(),
    RESERVADO: z.string(),
    LOCADO: z.string(),
    MANUTENCAO: z.string(),
    INDISPONIVEL: z.string(),
    BAIXADO: z.string(),
  }),
})
export const priceSchema = z.object({
  ...stamp,
  product_id: z.number(),
  product_name: z.string(),
  product_code: z.string(),
  period: z.enum(['DIARIA', 'SEMANAL', 'QUINZENAL', 'MENSAL']),
  effective_date: z.string(),
  amount: z.string().nullable(),
  is_active: z.boolean(),
  reason: z.string(),
  supersedes_id: z.number().nullable(),
})
export const movementSchema = z.object({
  ...stamp,
  product_id: z.number(),
  product_name: z.string(),
  product_code: z.string(),
  equipment_id: z.number().nullable(),
  from_status: z.string().nullable(),
  to_status: z.string(),
  quantity: z.string(),
  reason: z.string(),
})
export function pageSchema<T extends z.ZodType>(schema: T) {
  return z.object({ items: z.array(schema), total: z.number().int().nonnegative() })
}
export type MasterRow = { id: number; version?: number; [key: string]: unknown }
export type MasterKind = 'customers' | 'products' | 'equipment'
export const masterSchemas = {
  customers: customerSchema,
  products: productSchema,
  equipment: equipmentSchema,
}
export function value(row: MasterRow | undefined, key: string) {
  const v = row?.[key]
  return v === undefined || v === null ? '' : String(v)
}
export function decimalInput(value: string) {
  return value.trim().replace(',', '.')
}
export function money(value: string | null) {
  if (value === null) return 'Desativado'
  const [whole, cents] = value.split('.')
  return 'R$ ' + whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ',' + (cents || '00')
}
export function localDate() {
  const date = new Date()
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')
}
