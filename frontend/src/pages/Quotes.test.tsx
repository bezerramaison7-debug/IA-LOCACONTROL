import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ApiError } from '../auth/api'
import { AuthContext } from '../auth/context'
import { adminSession } from '../test/auth-fixture'
import { ToastProvider } from '../components/ToastProvider'
import { Quotes } from './Quotes'

const customer = {
  person_type: 'PJ',
  legal_name: 'Cliente Alfa',
  trade_name: '',
  document: '11222333000181',
  state_registration: '',
  phone: '',
  mobile: '',
  email: '',
  contact: '',
  address: null,
}
const summary = {
  id: 1,
  number: 'ORC-2026-000001',
  status: 'ENVIADO',
  status_reason: '',
  customer_id: 3,
  customer,
  start_date: '2026-10-20',
  valid_until: '2026-10-30',
  notes: '',
  total: '1234.56',
  item_count: 1,
  duplicated_from_id: null,
  version: 3,
  created_at: 1789254000,
  updated_at: 1789254000,
  created_by: 1,
}
const quote = {
  ...summary,
  table_total: '1300.00',
  negotiated_difference: '65.44',
  items: [
    {
      id: 9,
      position: 1,
      product_id: 7,
      product_code: 'BET-400',
      product_name: 'Betoneira 400 L',
      unit: 'UN',
      quantity: '2.000',
      period: 'DIARIA',
      period_count: 2,
      table_price: '325.00',
      unit_price: '308.64',
      negotiated: true,
      total: '1234.56',
      end_date: '2026-10-22',
    },
  ],
  transitions: [
    { from_status: null, to_status: 'RASCUNHO', reason: '', created_at: 1789254000, created_by: 1 },
    {
      from_status: 'RASCUNHO',
      to_status: 'ENVIADO',
      reason: '',
      created_at: 1789254100,
      created_by: 1,
    },
  ],
}
const stamp = { version: 1, created_at: 1, updated_at: 1, created_by: 1, is_active: true }
const customerRow = { ...customer, ...stamp, id: 3, notes: '', addresses: [] }
const productRow = {
  ...stamp,
  id: 7,
  code: 'BET-400',
  name: 'Betoneira 400 L',
  description: '',
  category: '',
  unit: 'UN',
  individual_tracking: false,
}
type Handler = (path: string, method: string, body?: unknown) => unknown
/** Routes the mocked authenticated client like the real API; `mutate` handles writes. */
function api(mutate: Handler = () => quote) {
  return vi.fn(async (path: string, method = 'GET', body?: unknown) => {
    if (method !== 'GET') return mutate(path, method, body)
    if (path.startsWith('/customers')) return { items: [customerRow], total: 1 }
    if (path.startsWith('/products')) return { items: [productRow], total: 1 }
    if (path.startsWith('/quotes/pricing'))
      return {
        product_id: 7,
        product_code: 'BET-400',
        product_name: 'Betoneira 400 L',
        unit: 'UN',
        individual_tracking: false,
        period: path.includes('SEMANAL') ? 'SEMANAL' : 'DIARIA',
        at: '2026-10-20',
        price_id: path.includes('SEMANAL') ? null : 5,
        table_price: path.includes('SEMANAL') ? null : '350.00',
        available: '4.000',
        period_days: path.includes('SEMANAL') ? 7 : 1,
      }
    if (path.startsWith('/quotes?')) return { items: [summary], total: 1 }
    return quote
  })
}
function setup(request: ReturnType<typeof api>, entry = '/', without: string[] = []) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <AuthContext.Provider
        value={{
          user: {
            ...adminSession.user,
            permissions: adminSession.user.permissions.filter((code) => !without.includes(code)),
          },
          loading: false,
          error: '',
          refresh: async () => {},
          login: async () => adminSession.user,
          logout: async () => {},
          clear: () => {},
          request,
        }}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={[entry]}>
            <Quotes />
          </MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}
async function pickProduct(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('option', { name: 'BET-400 · Betoneira 400 L' })
  await user.selectOptions(screen.getByLabelText('Produto do item 1'), '7')
}

it('renders the quote list returned by the API with pt-BR money, dates and named status', async () => {
  const request = api()
  setup(request)
  const row = (await screen.findByText('ORC-2026-000001')).closest('tr')!
  expect(within(row).getByText('Cliente Alfa')).toBeInTheDocument()
  expect(within(row).getByText('R$ 1.234,56')).toBeInTheDocument()
  expect(within(row).getByText('20/10/2026')).toBeInTheDocument()
  expect(within(row).getByText('30/10/2026')).toBeInTheDocument()
  expect(within(row).getByText('Enviado')).toBeInTheDocument()
  expect(within(row).getByRole('button', { name: 'Abrir ORC-2026-000001' })).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/quotes?limit=20&offset=0&q=')
  expect(screen.queryByText('Modo demonstração')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Converter/ })).not.toBeInTheDocument()
})

it('fills the table price from the API and saves exact decimal strings', async () => {
  const request = api()
  const user = userEvent.setup()
  setup(request, '/?novo=1')
  await screen.findByRole('option', { name: 'Cliente Alfa · 11222333000181' })
  await user.selectOptions(screen.getByLabelText('Cliente'), '3')
  await pickProduct(user)
  expect(await screen.findByText('Preço de tabela: R$ 350,00')).toBeInTheDocument()
  expect(screen.getByText(/orçamento não reserva estoque/)).toBeInTheDocument()
  await user.clear(screen.getByLabelText('Quantidade do item 1'))
  await user.type(screen.getByLabelText('Quantidade do item 1'), '2,5')
  await user.clear(screen.getByLabelText('Número de períodos do item 1'))
  await user.type(screen.getByLabelText('Número de períodos do item 1'), '3')
  expect(screen.getByText('R$ 2.625,00')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Salvar rascunho' }))
  expect(await screen.findByRole('heading', { level: 1, name: /ORC-2026-000001/ })).toBeVisible()
  expect(request).toHaveBeenCalledWith(
    '/quotes',
    'POST',
    expect.objectContaining({
      customer_id: 3,
      items: [
        { product_id: 7, quantity: '2.5', period: 'DIARIA', period_count: 3, unit_price: null },
      ],
    }),
  )
})

it('shows the missing price state and refuses to save that item', async () => {
  const request = api()
  const user = userEvent.setup()
  setup(request, '/?novo=1')
  await pickProduct(user)
  await screen.findByText('Preço de tabela: R$ 350,00')
  await user.selectOptions(screen.getByLabelText('Período do item 1'), 'SEMANAL')
  expect(await screen.findByText('Preço ausente.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Salvar rascunho' })).toBeDisabled()
  expect(screen.getByText(/Prévia do total indisponível/)).toBeInTheDocument()
  expect(request.mock.calls.every(([, method]) => !method || method === 'GET')).toBe(true)
})

it('lets only users with quotes.negotiate edit the negotiated price', async () => {
  const { unmount } = setup(api(), '/?novo=1', ['quotes.negotiate'])
  const locked = await screen.findByLabelText('Preço negociado do item 1 (R$)')
  expect(locked).toHaveAttribute('readonly')
  expect(screen.getByText('Seu perfil não permite alterar o preço de tabela.')).toBeInTheDocument()
  await userEvent.setup().type(locked, '10')
  expect(locked).toHaveValue('')
  unmount()
  setup(api(), '/?novo=1')
  expect(await screen.findByLabelText('Preço negociado do item 1 (R$)')).not.toHaveAttribute(
    'readonly',
  )
})

it('requires a reason before cancelling a quote', async () => {
  const request = api()
  const user = userEvent.setup()
  setup(request, '/?id=1')
  await user.click(await screen.findByRole('button', { name: 'Cancelar orçamento' }))
  const dialog = screen.getByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar cancelamento' }))
  expect(
    await within(dialog).findByText('Informe o motivo com pelo menos 5 caracteres.'),
  ).toBeInTheDocument()
  expect(within(dialog).getByLabelText('Motivo')).toHaveAttribute('aria-invalid', 'true')
  expect(request.mock.calls.every(([, method]) => !method || method === 'GET')).toBe(true)
  await user.type(within(dialog).getByLabelText('Motivo'), 'Cliente desistiu')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar cancelamento' }))
  expect(await screen.findByText('Orçamento cancelado.')).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/quotes/1/cancel', 'POST', {
    version: 3,
    reason: 'Cliente desistiu',
  })
})

it('shows the version conflict message and offers to reload', async () => {
  const request = api(() => {
    throw new ApiError(409, 'Orçamento alterado por outra operação. Atualize e tente novamente.')
  })
  const user = userEvent.setup()
  setup(request, '/?id=1')
  await user.click(await screen.findByRole('button', { name: 'Aprovar' }))
  const dialog = screen.getByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar aprovação' }))
  const alert = await within(dialog).findByRole('alert')
  expect(alert).toHaveTextContent('Orçamento alterado por outra operação.')
  expect(alert).toHaveTextContent('Recarregue os dados')
  await user.click(within(alert).getByRole('button', { name: 'Recarregar orçamento' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/quotes/1')
})

it('hides write actions from a reader and handles a 403 from the API', async () => {
  const request = vi.fn(async () => {
    throw new ApiError(403, 'Permissão insuficiente.')
  })
  setup(request, '/', ['quotes.write', 'quotes.approve', 'quotes.negotiate'])
  expect(await screen.findByRole('alert')).toHaveTextContent('Permissão insuficiente.')
  expect(screen.queryByRole('button', { name: 'Novo orçamento' })).not.toBeInTheDocument()
})
