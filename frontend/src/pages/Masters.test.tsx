import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { it, expect, vi } from 'vitest'
import { AuthContext } from '../auth/context'
import { adminSession } from '../test/auth-fixture'
import { ToastProvider } from '../components/ToastProvider'
import { Masters } from './Masters'

const customer = {
  id: 1,
  version: 1,
  created_at: 1,
  updated_at: 1,
  created_by: 1,
  person_type: 'PF',
  legal_name: 'Cliente existente',
  trade_name: '',
  document: '52998224725',
  state_registration: '',
  phone: '',
  mobile: '',
  email: '',
  contact: '',
  notes: '',
  is_active: true,
  addresses: [],
}
function setup(request: ReturnType<typeof vi.fn>, writable = true) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <AuthContext.Provider
        value={{
          ...{
            user: {
              ...adminSession.user,
              permissions: writable ? adminSession.user.permissions : ['customers.read'],
            },
            loading: false,
            error: '',
            refresh: async () => {},
            login: async () => adminSession.user,
            logout: async () => {},
            clear: () => {},
            request,
          },
        }}
      >
        <ToastProvider>
          <MemoryRouter>
            <Masters kind="customers" />
          </MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}
it('saves real customer data and refreshes the server list', async () => {
  let saved = false
  const request = vi.fn(async (_path: string, method = 'GET', body?: unknown) => {
    if (method === 'POST') {
      saved = true
      return { ...customer, ...(body as object) }
    }
    return {
      items: saved ? [{ ...customer, legal_name: 'Nova cliente' }] : [],
      total: saved ? 1 : 0,
    }
  })
  setup(request)
  await screen.findByText('Nenhum registro encontrado')
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Novo cliente' }))
  const dialog = screen.getByRole('dialog')
  await user.type(within(dialog).getByLabelText('Nome / razão social'), 'Nova cliente')
  await user.type(within(dialog).getByLabelText('CPF / CNPJ'), '52998224725')
  await user.click(within(dialog).getByRole('button', { name: 'Salvar cliente' }))
  expect(await screen.findByText('Nova cliente')).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith(
    '/customers',
    'POST',
    expect.objectContaining({
      legal_name: 'Nova cliente',
      document: '52998224725',
      person_type: 'PF',
      is_active: true,
      addresses: [],
    }),
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
it('keeps duplicate errors visible in the editor', async () => {
  const request = vi.fn(async (_path: string, method = 'GET') => {
    if (method === 'POST') throw new Error('CPF/CNPJ já cadastrado.')
    return { items: [], total: 0 }
  })
  setup(request)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Novo cliente' }))
  const dialog = screen.getByRole('dialog')
  await user.type(within(dialog).getByLabelText('Nome / razão social'), 'Duplicado')
  await user.type(within(dialog).getByLabelText('CPF / CNPJ'), '52998224725')
  await user.click(within(dialog).getByRole('button', { name: 'Salvar cliente' }))
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('CPF/CNPJ já cadastrado.')
  expect(within(dialog).getByLabelText('Nome / razão social')).toHaveValue('Duplicado')
})
it('hides mutation actions from a reader', async () => {
  setup(
    vi.fn(async () => ({ items: [customer], total: 1 })),
    false,
  )
  await screen.findByText('Cliente existente')
  expect(screen.queryByRole('button', { name: 'Novo cliente' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Editar/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Desativar' })).not.toBeInTheDocument()
})
it('retries a failed server query without replacing it with demo data', async () => {
  let fail = true
  const request = vi.fn(async () => {
    if (fail) throw new Error('Servidor indisponível')
    return { items: [customer], total: 1 }
  })
  setup(request)
  expect(await screen.findByRole('alert')).toHaveTextContent('Servidor indisponível')
  fail = false
  await userEvent.setup().click(screen.getByRole('button', { name: 'Tentar novamente' }))
  expect(await screen.findByText('Cliente existente')).toBeInTheDocument()
  expect(screen.queryByText('Modo demonstração')).not.toBeInTheDocument()
})
