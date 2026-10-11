import { z } from 'zod'

const healthSchema = z.object({
  status: z.literal('ok'),
  database: z.literal('ok'),
  schema: z.literal('ok'),
  version: z.string().min(1),
})

export type Health = z.infer<typeof healthSchema>

export async function getHealth(signal?: AbortSignal): Promise<Health> {
  const timeout = AbortSignal.timeout(8000)
  let response: Response
  try {
    response = await fetch('/health', {
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      headers: { Accept: 'application/json' },
    })
  } catch {
    throw new Error(
      'Não foi possível conectar ao servidor. Verifique se o backend está em execução.',
    )
  }
  if (!response.ok) {
    throw new Error(
      'O serviço não está pronto. Verifique o banco e execute as migrations pendentes.',
    )
  }
  const parsed = healthSchema.safeParse(await response.json().catch(() => null))
  if (!parsed.success) {
    throw new Error('O servidor retornou uma resposta inesperada. Tente verificar novamente.')
  }
  return parsed.data
}
