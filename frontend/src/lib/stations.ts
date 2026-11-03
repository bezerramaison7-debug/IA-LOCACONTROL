import { z } from 'zod'
import type { AuthContextValue } from '../auth/context'
import { send } from '../auth/api'

/** Network edition (ADR-025): stations of the store network, paired with a temporary code. */
const stationSchema = z.object({
  id: z.string(),
  name: z.string(),
  paired_at: z.number(),
  paired_from: z.string().nullable().optional(),
  last_seen_at: z.number(),
  last_address: z.string().nullable().optional(),
  revoked_at: z.number().nullable(),
  revoked_reason: z.string().nullable().optional(),
})
const eventSchema = z.object({
  at: z.number(),
  action: z.string(),
  station_id: z.string().optional(),
  station_name: z.string().optional(),
  peer: z.string().optional(),
  reason: z.string().optional(),
  agent: z.string().optional(),
  last_address: z.string().nullable().optional(),
})
export const stationsSchema = z.object({
  installation_id: z.string(),
  server: z.object({ id: z.string(), created_at: z.number() }).nullable(),
  network: z.boolean(),
  /** A2: the station list could not be read (stations blocked) or was recovered from its copy. */
  registry: z.object({ unavailable: z.boolean(), recovered_from_backup: z.boolean() }),
  /** P1-E: HTTPS of the store network (local CA and server certificate). */
  tls: z
    .union([
      z.object({
        available: z.literal(true),
        ca_fingerprint: z.string(),
        ca_expires: z.string(),
        server_expires: z.string(),
        server_names: z.array(z.string()),
        server_addresses: z.array(z.string()),
        renamed_outside_ca: z.array(z.string()),
        protection: z.string(),
      }),
      z.object({ available: z.literal(false), error: z.string() }),
    ])
    .nullable()
    .optional(),
  pairing: z.object({ expires_at: z.number(), attempts_left: z.number() }).nullable(),
  stations: z.array(stationSchema),
  events: z.array(eventSchema),
})
export const pairingCodeSchema = z.object({
  code: z.string(),
  bits: z.number().optional(),
  expires_at: z.number(),
  attempts_left: z.number(),
})
export type Station = z.infer<typeof stationSchema>
export type StationEvent = z.infer<typeof eventSchema>
export type Stations = z.infer<typeof stationsSchema>
export type PairingCode = z.infer<typeof pairingCodeSchema>

export const eventLabels: Record<string, string> = {
  'pairing.started': 'Código de pareamento gerado',
  'pairing.cancelled': 'Código cancelado',
  'pairing.failed': 'Tentativa de pareamento recusada',
  'pairing.exhausted': 'Código cancelado por excesso de tentativas',
  'station.paired': 'Estação pareada',
  'station.revoked': 'Estação revogada',
  'station.reuse_detected': 'Reuso de credencial detectado (estação revogada)',
  'registry.recovered_from_backup': 'Lista de estações recuperada da cópia',
  'registry.reset': 'Lista de estações recomeçada',
}
export const RESET_PHRASE = 'RECOMEÇAR ESTAÇÕES'
/** Reuse detected in the last 7 days: something the main computer must look at (A1). */
export function recentReuse(data: Stations, now = Date.now() / 1000) {
  return data.events.filter(
    (event) => event.action === 'station.reuse_detected' && now - event.at < 7 * 86400,
  )
}

type Request = AuthContextValue['request']
export async function getStations(request: Request) {
  return stationsSchema.parse(await request('/stations'))
}
export async function startPairing(request: Request) {
  return pairingCodeSchema.parse(await request('/stations/pairing', 'POST'))
}
export async function cancelPairing(request: Request) {
  await request('/stations/pairing', 'DELETE')
}
export async function resetRegistry(request: Request, confirmation: string) {
  return request('/stations/registry/reset', 'POST', { confirmation })
}
export async function revokeStation(request: Request, id: string) {
  return request('/stations/' + encodeURIComponent(id) + '/revoke', 'POST')
}
/** Called by a computer without a session: it exchanges the code for its own credential. */
/** The pairing code the "Conectar à loja" installer put in the address (#/parear?codigo=…).
 * It never reaches the server or its logs; it is erased from the address bar once read. */
export function codeFromAddress(): string {
  const hash = window.location.hash
  const query = hash.includes('?') ? hash.slice(hash.indexOf('?') + 1) : ''
  const code = new URLSearchParams(query).get('codigo') || ''
  if (code) {
    try {
      window.history.replaceState(null, '', window.location.pathname + '#/')
    } catch {
      /* the code stays only in this tab */
    }
  }
  return code.toUpperCase()
}
export const codeLength = (code: string) => code.replace(/[^A-Za-z0-9]/g, '').length
export async function pairThisComputer(code: string, name: string) {
  return send('/stations/pair', '', 'POST', { code, name })
}
