import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import App from './App'
import { adminSession } from './test/auth-fixture'

function renderApp() {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockImplementation((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url === '/api/auth/me'
                ? adminSession
                : url.startsWith('/api/customers')
                  ? { items: [], total: 0 }
                  : url === '/api/contracts/numbering'
                    ? { configured: null, highest_used: null, next_number: 1 }
                    : url === '/api/contracts/templates'
                      ? { items: [], fields: [], blocks: [] }
                      : { status: 'ok', database: 'ok', schema: 'ok', version: '0.1.0' },
            ),
          ),
        ),
      ),
  )
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <App />
    </QueryClientProvider>,
  )
}

it('navigates between pages, persists sidebar state and shows 404', async () => {
  const user = userEvent.setup()
  renderApp()
  expect(await screen.findByRole('heading', { level: 1, name: 'Visão geral' })).toBeInTheDocument()
  expect(screen.getByText('Modo demonstração')).toBeInTheDocument()
  const navigation = screen.getByRole('navigation', { name: 'Navegação principal' })
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
  expect(
    vi
      .mocked(fetch)
      .mock.calls.every(([, options]) => !options?.method || options.method === 'GET'),
  ).toBe(true)
})

it('validates a demo form without performing network writes', async () => {
  const user = userEvent.setup()
  renderApp()
  await screen.findByRole('heading', { level: 1, name: 'Visão geral' })
  await user.click(screen.getByRole('button', { name: 'Novo orçamento' }))
  const dialog = screen.getByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: 'Validar prévia' }))
  expect(await within(dialog).findByText('Informe pelo menos 2 caracteres.')).toBeInTheDocument()
  await user.type(within(dialog).getByLabelText('Nome de exemplo'), 'Obra fictícia')
  await user.click(within(dialog).getByRole('button', { name: 'Validar prévia' }))
  expect(await screen.findByText('Prévia validada. Nenhum registro foi salvo.')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(
    vi
      .mocked(fetch)
      .mock.calls.every(([, options]) => !options?.method || options.method === 'GET'),
  ).toBe(true)
})

it('supports a deep link, restores appearance only after confirmation and keeps health real', async () => {
  window.history.replaceState(null, '', '/#/configuracoes')
  localStorage.setItem('locacontrol.theme', 'dark')
  const user = userEvent.setup()
  renderApp()
  expect(await screen.findByText('Ambiente conectado')).toBeInTheDocument()
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
