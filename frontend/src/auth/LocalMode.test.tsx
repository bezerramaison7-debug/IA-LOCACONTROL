import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import App from '../App'
import { adminSession, dashboard } from '../test/auth-fixture'

const hidden = /^(users|roles|portal)\./
const localSession = {
  ...adminSession,
  user: {
    ...adminSession.user,
    username: 'operador.local',
    name: 'Operador local',
    permissions: adminSession.user.permissions.filter((code) => !hidden.test(code)),
  },
  edition: 'local',
  installation_id: '3f2b9c1e-0000-4000-8000-000000000000',
}
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(value), { status, headers })

function renderApp(handler: (url: string) => Response, hash = '#/') {
  window.location.hash = hash
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => Promise.resolve(handler(url))),
  )
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <App />
    </QueryClientProvider>,
  )
}

it('local edition enters without login and hides account, users, roles and portal', async () => {
  renderApp((url) => (url.endsWith('/dashboard') ? json(dashboard) : json(localSession)), '#/login')
  await screen.findByRole('heading', { name: 'Visão geral' })
  expect(screen.queryByRole('heading', { name: 'Entrar na sua conta' })).not.toBeInTheDocument()
  const nav = screen.getByRole('navigation', { name: 'Navegação principal' })
  for (const label of ['Usuários', 'Perfis e permissões', 'Meu perfil'])
    expect(within(nav).queryByRole('link', { name: label })).not.toBeInTheDocument()
  expect(within(nav).getByRole('link', { name: 'Clientes' })).toBeInTheDocument()
  expect(within(nav).getByRole('link', { name: 'Auditoria' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Sair' })).not.toBeInTheDocument()
  expect(screen.getByText('Uso neste computador, sem login')).toBeInTheDocument()
  expect(fetch).not.toHaveBeenCalledWith('/api/auth/login', expect.anything())
})

it('local edition sends the profile address home and blocks the portal', async () => {
  renderApp(
    (url) => (url.endsWith('/dashboard') ? json(dashboard) : json(localSession)),
    '#/perfil',
  )
  await screen.findByRole('heading', { name: 'Visão geral' })
  expect(screen.queryByLabelText('Senha atual')).not.toBeInTheDocument()
  window.location.hash = '#/portal'
  expect(
    await screen.findByText('Você não tem permissão para acessar esta área.'),
  ).toBeInTheDocument()
})

it('local edition shows a clear error instead of a password form when access is refused', async () => {
  renderApp(() =>
    json({ detail: 'Este computador não tem acesso ao LocaControl desta loja.' }, 401, {
      'X-LocaControl-Edition': 'local',
    }),
  )
  expect(
    await screen.findByText('Este computador não tem acesso ao LocaControl desta loja.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Entrar na sua conta' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Senha')).not.toBeInTheDocument()
})

it('standard edition is unchanged: a refused session shows the login screen', async () => {
  renderApp(() => json({ detail: 'Entre novamente.' }, 401))
  await screen.findByRole('heading', { name: 'Entrar na sua conta' })
})

it('standard edition keeps logout, profile and user management for an administrator', async () => {
  renderApp((url) => (url.endsWith('/dashboard') ? json(dashboard) : json(adminSession)))
  await screen.findByRole('heading', { name: 'Visão geral' })
  const nav = screen.getByRole('navigation', { name: 'Navegação principal' })
  for (const label of ['Usuários', 'Perfis e permissões', 'Meu perfil'])
    expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sair' })).toBeInTheDocument()
})
