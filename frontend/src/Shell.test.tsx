import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from './App'
import { adminSession, customerSession, dashboard } from './test/auth-fixture'

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

function renderApp(session: unknown = adminSession, portalLinked = false) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation((url: string) => {
      if (url === '/api/auth/me') return Promise.resolve(json(session))
      if (url === '/api/dashboard') return Promise.resolve(json(dashboard))
      if (url.startsWith('/api/portal/'))
        return Promise.resolve(
          portalLinked
            ? json({
                active_contracts: 1,
                rented_items: '2.000',
                next_due: [],
                pending_requests: 0,
              })
            : json(
                {
                  detail: 'Sua conta ainda não está vinculada a um cliente. Fale com a locadora.',
                },
                403,
              ),
        )
      if (url.startsWith('/api/customers')) return Promise.resolve(json({ items: [], total: 0 }))
      if (url === '/api/contracts/numbering')
        return Promise.resolve(json({ configured: null, highest_used: null, next_number: 1 }))
      if (url === '/api/contracts/templates')
        return Promise.resolve(json({ items: [], fields: [], blocks: [] }))
      return Promise.resolve(json({ status: 'ok', database: 'ok', schema: 'ok', version: '0.1.0' }))
    }),
  )
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <App />
    </QueryClientProvider>,
  )
}
const onlyReads = () =>
  vi.mocked(fetch).mock.calls.every(([, options]) => !options?.method || options.method === 'GET')

it('navigates between pages, persists sidebar state and shows no demo data', async () => {
  const user = userEvent.setup()
  renderApp()
  expect(await screen.findByRole('heading', { level: 1, name: 'Visão geral' })).toBeInTheDocument()
  expect(await screen.findByText('Contratos ativos')).toBeInTheDocument()
  expect(screen.queryByText('Modo demonstração')).not.toBeInTheDocument()
  const navigation = screen.getByRole('navigation', { name: 'Navegação principal' })
  for (const name of ['Relatórios', 'Faturamento e fiscal', 'Backups'])
    expect(within(navigation).getByRole('link', { name })).toBeInTheDocument()
  expect(within(navigation).queryByRole('link', { name: 'Meus contratos' })).toBeNull()
  await user.click(within(navigation).getByRole('link', { name: 'Clientes' }))
  expect(await screen.findByRole('heading', { level: 1, name: 'Clientes' })).toBeInTheDocument()
  expect(
    within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText('Clientes'),
  ).toHaveAttribute('aria-current', 'page')
  await user.click(screen.getByRole('button', { name: 'Recolher menu' }))
  expect(localStorage.getItem('locacontrol.sidebar')).toBe('collapsed')
  expect(screen.getByRole('button', { name: 'Expandir menu' })).toHaveAttribute(
    'aria-expanded',
    'false',
  )
  expect(onlyReads()).toBe(true)
})

it('gives a customer account only the portal menu and shows the missing link as a state', async () => {
  renderApp(customerSession)
  expect(
    await screen.findByRole('heading', { level: 1, name: 'Portal do cliente' }),
  ).toBeInTheDocument()
  const navigation = screen.getByRole('navigation', { name: 'Navegação principal' })
  expect(
    within(navigation)
      .getAllByRole('link')
      .map((link) => link.textContent),
  ).toEqual([
    'Início',
    'Meus contratos',
    'Meus equipamentos',
    'Orçamentos',
    'Renovações',
    'Documentos',
    'Meu cadastro',
    'Meu perfil',
  ])
  expect(await screen.findByText('Portal ainda não liberado para esta conta')).toBeInTheDocument()
  expect(
    screen.getByText('Sua conta ainda não está vinculada a um cliente. Fale com a locadora.'),
  ).toBeInTheDocument()
  expect(screen.getByText(/funciona na rede local da locadora/)).toBeInTheDocument()
  expect(screen.getByText(/acesso pela internet é uma etapa futura/)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it('keeps internal routes closed to a customer account', async () => {
  window.history.replaceState(null, '', '/#/contratos')
  renderApp(customerSession, true)
  expect(await screen.findByRole('alert')).toHaveTextContent('não tem permissão')
  expect(screen.queryByRole('heading', { level: 1, name: 'Contratos' })).toBeNull()
  expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/api/contracts'))).toBe(
    false,
  )
})

it('supports a deep link, restores appearance only after confirmation and keeps health real', async () => {
  window.history.replaceState(null, '', '/#/configuracoes')
  localStorage.setItem('locacontrol.theme', 'dark')
  const user = userEvent.setup()
  renderApp()
  expect(await screen.findByText('Ambiente conectado')).toBeInTheDocument()
  expect(screen.queryByText('Interações de exemplo')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Restaurar padrão' }))
  const dialog = screen.getByRole('alertdialog')
  expect(within(dialog).getByRole('button', { name: 'Voltar' })).toHaveFocus()
  await user.click(within(dialog).getByRole('button', { name: 'Voltar' }))
  expect(localStorage.getItem('locacontrol.theme')).toBe('dark')
  await user.click(screen.getByRole('button', { name: 'Restaurar padrão' }))
  await user.click(
    within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Restaurar aparência' }),
  )
  expect(localStorage.getItem('locacontrol.theme')).toBe('system')
})

it('renders a useful 404 for unknown addresses', async () => {
  window.history.replaceState(null, '', '/#/nao-existe')
  renderApp()
  expect(await screen.findByRole('heading', { name: 'Página não encontrada' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Voltar ao dashboard' })).toHaveAttribute('href', '#/')
})
