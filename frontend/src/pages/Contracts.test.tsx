import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { ApiError } from '../auth/api'
import { AuthContext } from '../auth/context'
import { adminSession } from '../test/auth-fixture'
import { ToastProvider } from '../components/ToastProvider'
import { Contracts } from './Contracts'
import { Operations } from './Operations'
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
  number: '9193',
  base_number: 9193,
  renewal_number: 0,
  chain_id: 1,
  previous_id: null,
  customer_id: 3,
  customer,
  quote_id: null,
  origin: 'DIRETO',
  price_option: null,
  status: 'ATIVO',
  stored_status: 'ATIVO',
  status_reason: '',
  start_date: '2026-10-01',
  end_date: '2026-10-31',
  due_date: '2026-10-31',
  notes: '',
  total: '1234.56',
  item_count: 2,
  version: 4,
  created_at: 1789254000,
  updated_at: 1789254000,
  created_by: 1,
}
const item = {
  position: 1,
  description: '',
  unit: 'UN',
  period: 'MENSAL',
  period_count: 1,
  table_price: '100.00',
  unit_price: '100.00',
  negotiated: false,
  discount: '0.00',
  total: '1000.00',
  start_date: '2026-10-01',
  end_date: '2026-10-31',
  source_item_id: null,
  renewed: '0.000',
  units: [],
}
const contract = {
  ...summary,
  quote_number: null,
  table_total: '1234.56',
  negotiated_difference: '0.00',
  items: [
    {
      ...item,
      id: 11,
      product_id: 7,
      product_code: 'AND-01',
      product_name: 'Andaime tubular',
      individual_tracking: false,
      quantity: '10.000',
      withdrawn: '6.000',
      returned: '1.000',
      outstanding: '5.000',
      to_withdraw: '4.000',
    },
    {
      ...item,
      id: 12,
      position: 2,
      product_id: 8,
      product_code: 'BET-400',
      product_name: 'Betoneira 400 L',
      individual_tracking: true,
      quantity: '2.000',
      withdrawn: '1.000',
      returned: '0.000',
      outstanding: '1.000',
      to_withdraw: '1.000',
      total: '234.56',
      units: [{ equipment_id: 31, code: 'BET-001', state: 'EM_POSSE' }],
    },
  ],
  chain: [
    {
      id: 1,
      number: '9193',
      status: 'ATIVO',
      start_date: '2026-10-01',
      end_date: '2026-10-31',
      total: '1234.56',
    },
    {
      id: 2,
      number: '9193.1',
      status: 'ATIVO',
      start_date: '2026-10-31',
      end_date: '2026-11-30',
      total: '500.00',
    },
  ],
  events: [
    {
      id: 1,
      contract_id: 1,
      kind: 'CRIADO',
      description: 'Contrato 9193 criado.',
      created_at: 1789254000,
      created_by: 1,
    },
    {
      id: 2,
      contract_id: 2,
      kind: 'RENOVACAO',
      description: 'Renovação 9193.1 criada.',
      created_at: 1789254100,
      created_by: 1,
    },
  ],
  documents: [],
  withdrawals: [],
  returns: [],
}
const renewed = {
  ...contract,
  id: 2,
  number: '9193.1',
  renewal_number: 1,
  previous_id: 1,
  origin: 'RENOVACAO',
  price_option: 'ANTERIORES',
}
const signedDocument = {
  id: 5,
  contract_id: 1,
  template_id: 1,
  version: 1,
  status: 'ASSINADO',
  reason: '',
  checksum: 'abc',
  size: 1200,
  signed_at: 1789254200,
  signed_by: 1,
  created_at: 1789254100,
  created_by: 1,
}
const templates = {
  items: [
    {
      id: 1,
      name: 'Modelo inicial',
      version: 1,
      is_provisional: true,
      is_active: true,
      body: '# Contrato\n{{ items }}',
      created_at: 1789254000,
      created_by: 1,
    },
  ],
  fields: ['contract.number'],
  blocks: ['items'],
}
const available = {
  id: 41,
  version: 1,
  created_at: 1,
  updated_at: 1,
  created_by: 1,
  product_id: 8,
  product_name: 'Betoneira 400 L',
  product_code: 'BET-400',
  code: 'BET-002',
  asset_tag: null,
  serial_number: null,
  brand: '',
  model: '',
  notes: '',
  status: 'DISPONIVEL',
}
const approvedQuote = {
  id: 1,
  number: 'ORC-2026-000001',
  status: 'APROVADO',
  status_reason: '',
  customer_id: 3,
  customer,
  start_date: '2026-10-20',
  valid_until: '2026-10-30',
  notes: '',
  total: '700.00',
  item_count: 0,
  duplicated_from_id: null,
  version: 3,
  created_at: 1789254000,
  updated_at: 1789254000,
  created_by: 1,
  table_total: '700.00',
  negotiated_difference: '0.00',
  items: [],
  transitions: [],
}

type Handler = (path: string, method: string, body?: unknown) => unknown
/** Routes the mocked authenticated client like the real API; `mutate` handles writes. */
function api(mutate: Handler = () => contract, detail: unknown = contract) {
  return vi.fn(async (path: string, method = 'GET', body?: unknown) => {
    if (method !== 'GET') return mutate(path, method, body)
    if (path.startsWith('/contracts/templates')) return templates
    if (path.startsWith('/contracts?')) return { items: [summary], total: 1 }
    if (path.startsWith('/equipment')) return { items: [available], total: 1 }
    if (path.startsWith('/quotes/')) return approvedQuote
    if (path === '/contracts/2') return renewed
    return detail
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
            <Routes>
              <Route path="/" element={<Contracts />} />
              <Route path="/contratos" element={<Contracts />} />
              <Route path="/orcamentos" element={<Quotes />} />
              <Route path="/devolucoes" element={<Operations view="devolucoes" />} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}
const writes = (request: ReturnType<typeof api>) =>
  request.mock.calls.filter(([, method]) => method && method !== 'GET')

it('renders the contract list with pt-BR values, named status and the derived filters', async () => {
  const request = api()
  setup(request)
  const row = (await screen.findByText('9193')).closest('tr')!
  expect(within(row).getByText('Cliente Alfa')).toBeInTheDocument()
  expect(within(row).getByText('01/10/2026')).toBeInTheDocument()
  expect(within(row).getByText('31/10/2026')).toBeInTheDocument()
  expect(within(row).getByText('R$ 1.234,56')).toBeInTheDocument()
  expect(within(row).getByText('Ativo')).toBeInTheDocument()
  expect(within(row).getByRole('button', { name: 'Abrir contrato 9193' })).toBeInTheDocument()
  const filter = screen.getByLabelText('Filtrar situação')
  expect(within(filter).getByRole('option', { name: 'Vencendo' })).toBeInTheDocument()
  expect(within(filter).getByRole('option', { name: 'Vencido' })).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/contracts?limit=20&offset=0&q=')
  await userEvent.setup().selectOptions(filter, 'VENCIDO')
  await screen.findByText('9193')
  expect(request).toHaveBeenCalledWith('/contracts?limit=20&offset=0&q=&status=VENCIDO')
  expect(screen.queryByText('Modo demonstração')).not.toBeInTheDocument()
})

it('shows item balances, physical units, the renewal chain and the chain timeline', async () => {
  setup(api(), '/?id=1')
  expect(await screen.findByRole('heading', { level: 1, name: 'Contrato 9193' })).toBeVisible()
  const items = within(screen.getByRole('region', { name: 'Itens do contrato 9193' }))
  expect(items.getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
    'Produto',
    'Contratado',
    'Retirado',
    'Com o cliente',
    'Devolvido',
    'Renovado',
    'A retirar',
    'Períodos',
    'Devolução prevista',
  ])
  const scaffold = items.getByText('Andaime tubular').closest('tr')!
  expect(
    within(scaffold)
      .getAllByRole('cell')
      .map((cell) => cell.textContent)
      .slice(1, 7),
  ).toEqual(['10 UN', '6', '5', '1', '0', '4'])
  expect(
    within(items.getByRole('list', { name: 'Unidades físicas de Betoneira 400 L' })).getByText(
      /Com o cliente/,
    ),
  ).toHaveTextContent('BET-001 · Com o cliente')
  expect(screen.getByRole('link', { name: 'Abrir contrato 9193.1' })).toBeInTheDocument()
  const timeline = within(screen.getByRole('list', { name: 'Linha do tempo da cadeia 9193' }))
  expect(timeline.getByText('Renovação 9193.1 criada.')).toBeInTheDocument()
  expect(timeline.getByText(/contrato 9193\.1/)).toBeInTheDocument()
  expect(await screen.findByText('Modelo provisório.')).toBeInTheDocument()
  for (const name of ['Registrar retirada', 'Registrar devolução', 'Renovar'])
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Encerrar contrato' })).not.toBeInTheDocument()
})

it('hides operations and write actions from a profile that only reads contracts', async () => {
  setup(api(), '/?id=1', ['contracts.write', 'operations.write'])
  await screen.findByRole('heading', { level: 1, name: 'Contrato 9193' })
  for (const name of ['Registrar retirada', 'Registrar devolução', 'Renovar', 'Gerar documento'])
    expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Baixar prévia (PDF)' })).toBeInTheDocument()
})

it('requires one physical unit per withdrawn unit of an individually tracked item', async () => {
  const request = api()
  const user = userEvent.setup()
  setup(request, '/?id=1&acao=retirada')
  await screen.findByRole('checkbox', { name: 'BET-002' })
  await user.clear(screen.getByLabelText('Quantidade a retirar de Andaime tubular'))
  await user.click(screen.getByRole('button', { name: 'Revisar retirada' }))
  expect(
    await screen.findByText('Selecione exatamente 1 unidade física de Betoneira 400 L.'),
  ).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(writes(request)).toEqual([])
  await user.click(screen.getByRole('checkbox', { name: 'BET-002' }))
  await user.click(screen.getByRole('button', { name: 'Revisar retirada' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('1 UN de Betoneira 400 L · BET-002')
  expect(dialog).toHaveTextContent('saem do estoque disponível')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar retirada' }))
  expect(await screen.findByText('Retirada registrada no contrato 9193.')).toBeInTheDocument()
  expect(writes(request)).toEqual([
    [
      '/contracts/1/withdrawals',
      'POST',
      {
        occurred_on: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        notes: '',
        request_key: expect.stringMatching(/^[0-9a-f-]{36}$/),
        items: [{ contract_item_id: 12, quantity: '1', equipment_ids: [41] }],
      },
    ],
  ])
})

it('sends a damaged return to maintenance and explains a partial return', async () => {
  const request = api()
  const user = userEvent.setup()
  setup(request, '/?id=1&acao=devolucao')
  const destination = await screen.findByLabelText('Destino de Betoneira 400 L BET-001')
  expect(destination).toHaveValue('DISPONIVEL')
  expect(destination).toBeEnabled()
  await user.selectOptions(screen.getByLabelText('Condição de Betoneira 400 L BET-001'), 'AVARIADO')
  expect(destination).toHaveValue('MANUTENCAO')
  expect(destination).toBeDisabled()
  await user.click(screen.getByRole('checkbox', { name: /^Devolver Andaime tubular/ }))
  await user.click(screen.getByRole('button', { name: 'Revisar devolução' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('Betoneira 400 L BET-001 · Avariado → Manutenção')
  expect(dialog).toHaveTextContent('Devolução parcial')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar devolução' }))
  expect(await screen.findByText('Devolução registrada no contrato 9193.')).toBeInTheDocument()
  expect(writes(request)).toEqual([
    [
      '/contracts/1/returns',
      'POST',
      expect.objectContaining({
        request_key: expect.stringMatching(/^[0-9a-f-]{36}$/),
        items: [
          {
            contract_item_id: 12,
            quantity: '1.000',
            equipment_id: 31,
            condition: 'AVARIADO',
            destination: 'MANUTENCAO',
            notes: '',
          },
        ],
      }),
    ],
  ])
})

it('refuses a returned quantity above what is with the customer', async () => {
  const request = api()
  const user = userEvent.setup()
  setup(request, '/?id=1&acao=devolucao')
  const quantity = await screen.findByLabelText('Quantidade devolvida de Andaime tubular')
  expect(quantity).toHaveValue('5')
  await user.clear(quantity)
  await user.type(quantity, '5,5')
  await user.click(screen.getByRole('button', { name: 'Revisar devolução' }))
  expect(
    await screen.findByText('A quantidade devolvida supera a quantidade com o cliente (5 UN).'),
  ).toBeInTheDocument()
  expect(writes(request)).toEqual([])
})

it('requires an explicit price option to renew and sends it with the request', async () => {
  const request = api(() => renewed)
  const user = userEvent.setup()
  setup(request, '/?id=1&acao=renovar')
  await screen.findByRole('heading', { level: 1, name: 'Renovar contrato · contrato 9193' })
  for (const radio of screen.getAllByRole('radio')) expect(radio).not.toBeChecked()
  await user.click(screen.getByRole('button', { name: 'Revisar renovação' }))
  expect(await screen.findByText('Escolha a opção de preço da renovação.')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(writes(request)).toEqual([])
  await user.click(screen.getByRole('radio', { name: /Manter os preços anteriores/ }))
  expect(screen.getByLabelText('Período de Andaime tubular')).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Revisar renovação' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('Opção de preço: Manter os preços anteriores')
  expect(dialog).toHaveTextContent('continua ativo porque ainda tem saldo a retirar')
  expect(dialog).not.toHaveTextContent('Renovação parcial')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar renovação' }))
  expect(await screen.findByRole('heading', { level: 1, name: 'Contrato 9193.1' })).toBeVisible()
  expect(screen.getByText('Manter os preços anteriores')).toBeInTheDocument()
  expect(writes(request)).toEqual([
    [
      '/contracts/1/renew',
      'POST',
      {
        version: 4,
        start_date: '2026-10-31',
        price_option: 'ANTERIORES',
        notes: '',
        items: [
          {
            source_item_id: 11,
            quantity: '5',
            period: 'MENSAL',
            period_count: 1,
            unit_price: null,
            equipment_ids: [],
          },
          {
            source_item_id: 12,
            quantity: '1',
            period: 'MENSAL',
            period_count: 1,
            unit_price: null,
            equipment_ids: [31],
          },
        ],
      },
    ],
  ])
})

it('asks for the negotiated price of each renewed item', async () => {
  const request = api(() => renewed)
  const user = userEvent.setup()
  setup(request, '/?id=1&acao=renovar', ['quotes.read'])
  await user.click(await screen.findByRole('radio', { name: /Informar preços negociados/ }))
  await user.click(screen.getByRole('checkbox', { name: /^Renovar Betoneira 400 L/ }))
  await user.click(screen.getByRole('button', { name: 'Revisar renovação' }))
  expect(
    await screen.findByText('Informe o preço negociado com até duas casas decimais.'),
  ).toBeInTheDocument()
  await user.type(screen.getByLabelText('Preço negociado de Andaime tubular (R$)'), '90,5')
  expect(screen.getByText('Prévia do item: R$ 452,50')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Revisar renovação' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('Renovação parcial')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar renovação' }))
  await screen.findByRole('heading', { level: 1, name: 'Contrato 9193.1' })
  expect(writes(request)[0][2]).toMatchObject({
    price_option: 'NEGOCIADOS',
    items: [{ source_item_id: 11, quantity: '5', unit_price: '90.5', equipment_ids: [] }],
  })
})

it('keeps the signed document and requires a reason for a new version', async () => {
  const request = api(() => ({ ...signedDocument, id: 6, version: 2, status: 'GERADO' }), {
    ...contract,
    documents: [signedDocument],
  })
  const user = userEvent.setup()
  setup(request, '/?id=1')
  const versions = await screen.findByRole('region', {
    name: 'Versões do documento do contrato 9193',
  })
  expect(within(versions).getByText('Assinado')).toBeInTheDocument()
  expect(within(versions).queryByRole('button', { name: /como assinada/ })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Gerar documento' }))
  const dialog = screen.getByRole('dialog')
  expect(dialog).toHaveTextContent('Já existe documento assinado (versão 1).')
  expect(dialog).toHaveTextContent('será preservado')
  await user.click(within(dialog).getByRole('button', { name: 'Gerar documento' }))
  expect(
    await within(dialog).findByText('Informe o motivo com pelo menos 5 caracteres.'),
  ).toBeInTheDocument()
  expect(writes(request)).toEqual([])
  await user.type(within(dialog).getByLabelText('Motivo da nova versão'), 'Aditivo de prazo')
  await user.click(within(dialog).getByRole('button', { name: 'Gerar documento' }))
  expect(await screen.findByText('Documento gerado.')).toBeInTheDocument()
  expect(writes(request)).toEqual([
    ['/contracts/1/documents', 'POST', { reason: 'Aditivo de prazo' }],
  ])
})

it('shows a 409 with the server message and offers to reload the contract', async () => {
  const request = api(
    () => {
      throw new ApiError(409, 'Contrato com retirada registrada não pode ser cancelado.')
    },
    { ...contract, status: 'AGUARDANDO_RETIRADA', stored_status: 'AGUARDANDO_RETIRADA' },
  )
  const user = userEvent.setup()
  setup(request, '/?id=1')
  await user.click(await screen.findByRole('button', { name: 'Cancelar contrato' }))
  const dialog = screen.getByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar cancelamento' }))
  expect(
    await within(dialog).findByText('Informe o motivo com pelo menos 5 caracteres.'),
  ).toBeInTheDocument()
  await user.type(within(dialog).getByLabelText('Motivo'), 'Cliente desistiu')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar cancelamento' }))
  const alert = await within(dialog).findByRole('alert')
  expect(alert).toHaveTextContent('Contrato com retirada registrada não pode ser cancelado.')
  expect(request).toHaveBeenCalledWith('/contracts/1/cancel', 'POST', {
    version: 4,
    reason: 'Cliente desistiu',
  })
  await user.click(within(alert).getByRole('button', { name: 'Recarregar contrato' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('converts an approved quote into a contract and opens it', async () => {
  // The created contract has id 2; the detail is then read from the API like any other.
  const request = api(() => ({ ...contract, id: 2, number: '9193.1', origin: 'ORCAMENTO' }))
  const user = userEvent.setup()
  setup(request, '/orcamentos?id=1')
  await user.click(await screen.findByRole('button', { name: 'Converter em contrato' }))
  const dialog = screen.getByRole('dialog')
  expect(dialog).toHaveTextContent('a conversão só pode ser feita uma vez')
  await user.click(within(dialog).getByRole('button', { name: 'Confirmar conversão' }))
  expect(await screen.findByRole('heading', { level: 1, name: 'Contrato 9193.1' })).toBeVisible()
  expect(writes(request)).toEqual([['/contracts/from-quote/1', 'POST', { version: 3, reason: '' }]])
})

it('does not offer the conversion without contracts.write', async () => {
  setup(api(), '/orcamentos?id=1', ['contracts.write'])
  expect(await screen.findByText(/exige a permissão de criar contratos/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Converter em contrato' })).not.toBeInTheDocument()
})

it('lists overdue contracts first in the returns view with a direct action', async () => {
  const request = vi.fn(async (path: string) => ({
    items: path.includes('status=VENCIDO')
      ? [{ ...summary, id: 9, number: '9100', status: 'VENCIDO' }]
      : path.includes('status=ATIVO')
        ? [summary]
        : [],
    total: 1,
  }))
  setup(request as unknown as ReturnType<typeof api>, '/devolucoes')
  const rows = (await screen.findAllByRole('row')).slice(1)
  expect(rows.map((row) => within(row).getAllByRole('cell')[0].textContent)).toEqual([
    '9100',
    '9193',
  ])
  expect(within(rows[0]).getByText('Vencido')).toBeInTheDocument()
  expect(within(rows[0]).getByRole('link', { name: 'Registrar devolução 9100' })).toHaveAttribute(
    'href',
    '/contratos?id=9&acao=devolucao',
  )
})
