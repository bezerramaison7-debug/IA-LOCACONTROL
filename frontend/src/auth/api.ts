import { z } from 'zod'

export const userSchema = z.object({
  id: z.number(),
  username: z.string(),
  name: z.string(),
  is_active: z.boolean(),
  must_change_password: z.boolean(),
  role_codes: z.array(z.string()),
  permissions: z.array(z.string()),
  created_at: z.number(),
  updated_at: z.number(),
})
export type AuthUser = z.infer<typeof userSchema>
export const sessionSchema = z.object({
  user: userSchema,
  csrf_token: z.string(),
  /** "local": no login, users or portal (ADR-023). Absent means the login-based edition. */
  edition: z.string().optional(),
  installation_id: z.string().optional(),
  /** Local edition (ADR-025): this server, the network mode and the calling station. */
  server_id: z.string().optional(),
  network: z.boolean().optional(),
  station: z.object({ id: z.string(), name: z.string() }).nullable().optional(),
})
export type SessionData = z.infer<typeof sessionSchema>
export const roleSchema = z.object({
  id: z.number(),
  code: z.string(),
  name: z.string(),
  permission_codes: z.array(z.string()),
  protected: z.boolean(),
})
export type Role = z.infer<typeof roleSchema>
export const rolesSchema = z.array(roleSchema)
export const permissionsSchema = z.array(z.object({ code: z.string(), description: z.string() }))
export const usersSchema = z.object({ items: z.array(userSchema), total: z.number() })
export const auditSchema = z.object({
  total: z.number(),
  items: z.array(
    z.object({
      id: z.number(),
      occurred_at: z.number(),
      actor: z.string(),
      actor_id: z.number().nullable(),
      action: z.string(),
      entity: z.string(),
      entity_id: z.string().nullable(),
      changes: z.record(z.string(), z.unknown()),
    }),
  ),
})

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** The server runs the local edition: a 401 means "no access", never "sign in". */
    public local = false,
    /** "csrf": the session changed (renewed in another tab); fetch the current token. */
    public retry = '',
    /** A computer of the store network that can be paired with a code (ADR-025). */
    public pairing = false,
  ) {
    super(message)
  }
}

export async function send(path: string, csrf: string, method = 'GET', body?: unknown) {
  let response: Response
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: {
        ...(body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        'X-LocaControl-Request': '1',
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      },
      ...(body !== undefined
        ? { body: body instanceof FormData ? body : JSON.stringify(body) }
        : {}),
    })
  } catch {
    throw new ApiError(0, 'Não foi possível conectar. Verifique se o servidor está ativo.')
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new ApiError(
      response.status,
      typeof error.detail === 'string' ? error.detail : 'Não foi possível concluir a ação.',
      response.headers.get('X-LocaControl-Edition') === 'local',
      response.headers.get('X-LocaControl-Retry') || '',
      response.headers.get('X-LocaControl-Pairing') === 'available',
    )
  }
  return response.status === 204 ? undefined : response.json()
}
