import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { AuthProvider, SESSION_RENEWED } from './AuthProvider'
import { useAuth } from './context'
import { adminSession } from '../test/auth-fixture'

/** P1-C: in the local edition an expired or renewed session never unmounts the form being
 * typed, and a write is never repeated on its own. */
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), { status, headers })
const session = (csrf: string) => ({ ...adminSession, csrf_token: csrf, edition: 'local' })
const local = { 'X-LocaControl-Edition': 'local' }

function Probe() {
  const { request, user } = useAuth()
  const [text, setText] = useState('')
  const [result, setResult] = useState('')
  if (!user) return <p>Sem sessão</p>
  const run = (method: string) =>
    request('/customers', method, method === 'GET' ? undefined : { note: text })
      .then(() => setResult(method === 'GET' ? 'lido' : 'gravado'))
      .catch((e: Error) => setResult(e.message))
  return (
    <>
      <label>
        Observação
        <input value={text} onChange={(e) => setText(e.target.value)} />
      </label>
      <button onClick={() => void run('GET')}>Ler</button>
      <button onClick={() => void run('POST')}>Gravar</button>
      <p role="status">{result}</p>
    </>
  )
}

function setup(handler: (url: string, init: RequestInit) => Response) {
  const fetchMock = vi.fn((url: string, init: RequestInit = {}) =>
    Promise.resolve(handler(url, init)),
  )
  vi.stubGlobal('fetch', fetchMock)
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return fetchMock
}
const calls = (fetchMock: ReturnType<typeof setup>, path: string, method = 'GET') =>
  fetchMock.mock.calls.filter(([url, init]) => url === path && (init?.method || 'GET') === method)

it('renews an expired local session, repeats a read once and keeps the typed form', async () => {
  const user = userEvent.setup()
  let sessions = 0
  let expired = true
  const fetchMock = setup((url, init) => {
    if (url === '/api/auth/me') return json(session('csrf-' + ++sessions), 200, local)
    if (url === '/api/customers' && (init.method || 'GET') === 'GET') {
      if (expired) {
        expired = false
        return json({ detail: 'Sua sessão expirou.' }, 401, local)
      }
      return json({ items: [], total: 0 }, 200, local)
    }
    return json({}, 404, local)
  })
  await user.type(await screen.findByLabelText('Observação'), 'Entregar às 8h')
  await user.click(screen.getByRole('button', { name: 'Ler' }))
  expect(await screen.findByText('lido')).toBeInTheDocument()
  expect(screen.getByLabelText('Observação')).toHaveValue('Entregar às 8h')
  expect(calls(fetchMock, '/api/auth/me')).toHaveLength(2)
  expect(calls(fetchMock, '/api/customers')).toHaveLength(2)
})

it('never repeats a write by itself: the form stays and the next send uses the new token', async () => {
  const user = userEvent.setup()
  let sessions = 0
  let posts = 0
  const fetchMock = setup((url, init) => {
    if (url === '/api/auth/me') return json(session('csrf-' + ++sessions), 200, local)
    if (url === '/api/customers' && init.method === 'POST') {
      posts++
      if (posts === 1) return json({ detail: 'Sua sessão expirou.' }, 401, local)
      if (posts === 2)
        // Another tab renewed the session: the token of this one is stale.
        return json({ detail: 'Solicitação inválida.' }, 403, {
          ...local,
          'X-LocaControl-Retry': 'csrf',
        })
      return json({ id: 1 }, 201, local)
    }
    return json({}, 404, local)
  })
  await user.type(await screen.findByLabelText('Observação'), 'Cliente novo')
  await user.click(screen.getByRole('button', { name: 'Gravar' }))
  expect(await screen.findByText(SESSION_RENEWED)).toBeInTheDocument()
  expect(posts).toBe(1)
  expect(screen.getByLabelText('Observação')).toHaveValue('Cliente novo')
  await user.click(screen.getByRole('button', { name: 'Gravar' }))
  expect(await screen.findByText(SESSION_RENEWED)).toBeInTheDocument()
  expect(posts).toBe(2)
  await user.click(screen.getByRole('button', { name: 'Gravar' }))
  expect(await screen.findByText('gravado')).toBeInTheDocument()
  const sent = calls(fetchMock, '/api/customers', 'POST').map(
    ([, init]) => (init?.headers as Record<string, string>)['X-CSRF-Token'],
  )
  expect(sent).toEqual(['csrf-1', 'csrf-2', 'csrf-3'])
  expect(screen.getByLabelText('Observação')).toHaveValue('Cliente novo')
})

it('a check on focus that cannot reach the server keeps the screen', async () => {
  const user = userEvent.setup()
  let down = false
  setup((url) => {
    if (down) throw new TypeError('Failed to fetch')
    if (url === '/api/auth/me') return json(session('csrf-1'), 200, local)
    return json({}, 404, local)
  })
  await user.type(await screen.findByLabelText('Observação'), 'Rascunho em curso')
  down = true
  await act(async () => {
    window.dispatchEvent(new Event('focus'))
  })
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 20))
  })
  expect(screen.getByLabelText('Observação')).toHaveValue('Rascunho em curso')
  expect(screen.queryByText('Sem sessão')).not.toBeInTheDocument()
})
