import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from '../App'
import { adminSession } from '../test/auth-fixture'

function renderAuth(handler: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) => Promise.resolve(handler(url, init))),
  )
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <App />
    </QueryClientProvider>,
  )
}
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })

it('requires login, submits credentials and csrf logout without persisting tokens', async () => {
  const user = userEvent.setup()
  renderAuth((url) => {
    if (url.endsWith('/login')) return json(adminSession)
    if (url.endsWith('/logout')) return new Response(null, { status: 204 })
    return json({ detail: 'Entre novamente.' }, 401)
  })
  await screen.findByRole('heading', { name: 'Entrar na sua conta' })
  await user.type(screen.getByLabelText('Usuário'), 'admin')
  await user.type(screen.getByLabelText('Senha'), 'Fixture-only-password')
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
  await screen.findByRole('heading', { name: 'Visão geral' })
  expect(localStorage.getItem('locacontrol_session')).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Sair' }))
  await screen.findByRole('heading', { name: 'Entrar na sua conta' })
  expect(fetch).toHaveBeenCalledWith(
    '/api/auth/logout',
    expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'X-CSRF-Token': 'test-only-csrf' }),
    }),
  )
})

it('shows invalid login feedback and does not render private content', async () => {
  const user = userEvent.setup()
  renderAuth(() => json({ detail: 'Usuário ou senha inválidos.' }, 401))
  await screen.findByRole('heading', { name: 'Entrar na sua conta' })
  await user.type(screen.getByLabelText('Usuário'), 'admin')
  await user.type(screen.getByLabelText('Senha'), 'wrong')
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Usuário ou senha inválidos.')
  expect(screen.queryByRole('navigation', { name: 'Navegação principal' })).not.toBeInTheDocument()
})

it('restricts Cliente to their profile and hides administrative links', async () => {
  const data = {
    ...adminSession,
    user: { ...adminSession.user, role_codes: ['CLIENTE'], permissions: [] },
  }
  renderAuth(() => json(data))
  await screen.findByRole('heading', { name: 'Meu perfil' })
  const nav = screen.getByRole('navigation', { name: 'Navegação principal' })
  expect(within(nav).queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
  expect(within(nav).queryByRole('link', { name: 'Clientes' })).not.toBeInTheDocument()
})

it('forces password change, validates confirmation, then ends the session', async () => {
  const user = userEvent.setup()
  const data = { ...adminSession, user: { ...adminSession.user, must_change_password: true } }
  renderAuth((url) =>
    url === '/api/auth/password' ? new Response(null, { status: 204 }) : json(data),
  )
  await screen.findByRole('heading', { name: 'Meu perfil' })
  expect(screen.getByRole('alert')).toHaveTextContent('substitua a senha temporária')
  await user.type(screen.getByLabelText('Senha atual'), 'Fixture-old-password')
  await user.type(screen.getByLabelText('Nova senha'), 'Fixture-new-password')
  await user.type(screen.getByLabelText('Confirmar nova senha'), 'mismatch')
  await user.click(screen.getByRole('button', { name: 'Alterar senha' }))
  expect(await screen.findByText('As senhas não conferem.')).toBeInTheDocument()
  await user.clear(screen.getByLabelText('Confirmar nova senha'))
  await user.type(screen.getByLabelText('Confirmar nova senha'), 'Fixture-new-password')
  await user.click(screen.getByRole('button', { name: 'Alterar senha' }))
  await screen.findByRole('heading', { name: 'Entrar na sua conta' })
})

it('fails closed on unavailable API and supports retry', async () => {
  let failed = true
  const user = userEvent.setup()
  renderAuth(() => (failed ? json({ detail: 'Banco indisponível.' }, 503) : json(adminSession)))
  expect(await screen.findByRole('alert')).toHaveTextContent('Banco indisponível.')
  failed = false
  await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))
  await screen.findByRole('heading', { name: 'Visão geral' })
})
