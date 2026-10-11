import { describe, expect, it, vi } from 'vitest'
import { getHealth } from './api'

const healthy = { status: 'ok', database: 'ok', schema: 'ok', version: '0.1.0' }

describe('health API client', () => {
  it('accepts only a healthy validated response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(healthy))))
    await expect(getHealth()).resolves.toEqual(healthy)
    expect(fetch).toHaveBeenCalledWith(
      '/health',
      expect.objectContaining({ headers: { Accept: 'application/json' } }),
    )
  })

  it('reports a network failure in Portuguese', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(getHealth()).rejects.toThrow('Não foi possível conectar ao servidor')
  })

  it('reports an unavailable database instead of treating 503 as success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })))
    await expect(getHealth()).rejects.toThrow('migrations pendentes')
  })

  it.each([
    '<html>wrong proxy</html>',
    JSON.stringify({ status: 'ok' }),
    JSON.stringify({ ...healthy, schema: 'outdated' }),
  ])('rejects malformed or incomplete successful responses (%s)', async (body) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body)))
    await expect(getHealth()).rejects.toThrow('resposta inesperada')
  })

  it('propagates caller cancellation to the request signal', async () => {
    const controller = new AbortController()
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(healthy)))
    vi.stubGlobal('fetch', fetchMock)
    await getHealth(controller.signal)
    controller.abort()
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
  })
})
