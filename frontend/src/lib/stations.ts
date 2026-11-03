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
})
const eventSchema = z.object({
  at: z.number(),
  action: z.string(),
  station_id: z.string().optional(),
  station_name: z.string().optional(),
  peer: z.string().optional(),
  reason: z.string().optional(),
})
export const stationsSchema = z.object({
  installation_id: z.string(),
  server: z.object({ id: z.string(), created_at: z.number() }),
  network: z.boolean(),
  pairing: z.object({ expires_at: z.number(), attempts_left: z.number() }).nullable(),
  stations: z.array(stationSchema),
  events: z.array(eventSchema),
})
export const pairingCodeSchema = z.object({
  code: z.string(),
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
export async function revokeStation(request: Request, id: string) {
  return request('/stations/' + encodeURIComponent(id) + '/revoke', 'POST')
}
/** Called by a computer without a session: it exchanges the code for its own credential. */
export async function pairThisComputer(code: string, name: string) {
  return send('/stations/pair', '', 'POST', { code, name })
}
