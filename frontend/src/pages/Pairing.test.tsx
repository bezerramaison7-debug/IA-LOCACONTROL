import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from '../App'
import { adminSession, dashboard } from '../test/auth-fixture'

/** ADR-025: a computer of the store network pairs once with the code; no password. */
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), { status, headers })
const local = { 'X-LocaControl-Edition': 'local' }
const stationSession = {
  ...adminSession,
  edition: 'local',
  network: true,
  server_id: 'srv-1',
  station: { id: '7c1d2e3f-0000-4000-8000-000000000000', name: 'Balcão 1' },
}

it('pairs this computer with the code and then opens as a station', async () => {
  const user = userEvent.setup()
  let paired = false
  const fetchMock = vi.fn((url: string, init: RequestInit = {}) => {
    if (url === '/api/auth/me')
      return Promise.resolve(
        paired
          ? json(stationSession, 200, local)
          : json({ detail: 'Este computador não tem acesso.' }, 401, {
              ...local,
              'X-LocaControl-Pairing': 'available',
            }),
      )
    if (url === '/api/stations/pair') {
      const body = JSON.parse(String(init.body))
      if (body.code !== 'ABCD-EFGH')
        return Promise.resolve(json({ detail: 'Código incorreto. Restam 4 tentativas.' }, 403))
      paired = true
      return Promise.resolve(json({ station: stationSession.station }, 201))
    }
    if (url.endsWith('/dashboard')) return Promise.resolve(json(dashboard))
    return Promise.resolve(json({ runs: [], alert: null, requires_running: '' }))
  })
  vi.stubGlobal('fetch', fetchMock)
  window.location.hash = '#/'
  render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  )
  await screen.findByRole('heading', { name: 'Conectar este computador à loja' })
  expect(screen.queryByLabelText('Senha')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Conectar à loja' }))
  expect(screen.getByText(/Dê um nome a este computador/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Nome desta estação'), 'Balcão 1')
  await user.type(screen.getByLabelText('Código de pareamento'), 'abcd-xxxx')
  await user.click(screen.getByRole('button', { name: 'Conectar à loja' }))
  expect(await screen.findByText('Código incorreto. Restam 4 tentativas.')).toBeInTheDocument()
  await user.clear(screen.getByLabelText('Código de pareamento'))
  await user.type(screen.getByLabelText('Código de pareamento'), 'abcd-efgh')
  await user.click(screen.getByRole('button', { name: 'Conectar à loja' }))
  await screen.findByRole('heading', { name: 'Visão geral' })
  expect(screen.getAllByText('Estação Balcão 1 · rede da loja').length).toBeGreaterThan(0)
  const nav = screen.getAllByRole('navigation', { name: 'Navegação principal' })[0]
  expect(within(nav).queryByRole('link', { name: 'Estações da rede' })).toBeNull()
  const pair = fetchMock.mock.calls.filter(([url]) => url === '/api/stations/pair')
  expect(pair.at(-1)![1]).toMatchObject({
    method: 'POST',
    headers: expect.objectContaining({ 'X-LocaControl-Request': '1' }),
  })
})
