import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import { exportPath, reportPath, type Report } from '../lib/reports'
import { mockRequest, renderPage } from '../test/render'
import { ReportTable, Reports } from './Reports'

const report: Report = {
  key: 'renewals',
  title: 'Renovações',
  note: 'Valores contratados conforme os contratos; não representam pagamentos recebidos.',
  columns: [
    { key: 'number', label: 'Renovação', type: 'text' },
    { key: 'start_date', label: 'Início', type: 'date' },
    { key: 'price_option', label: 'Preços', type: 'status' },
    { key: 'items', label: 'Itens', type: 'int' },
    { key: 'quantity', label: 'Quantidade', type: 'quantity' },
    { key: 'total', label: 'Valor contratado', type: 'money' },
    { key: 'due_date', label: 'Devolução prevista', type: 'date' },
  ],
  total: 1,
  rows: [
    {
      contract_id: 7,
      number: '9193.1',
      start_date: '2026-10-05',
      price_option: 'ANTERIORES',
      items: 1500,
      quantity: '2.500',
      total: '1234.50',
      due_date: null,
    },
  ],
}

it('renders each cell by the column type declared by the server', () => {
  render(
    <MemoryRouter>
      <ReportTable report={report} linkContracts />
    </MemoryRouter>,
  )
  const cells = within(screen.getAllByRole('row')[1])
    .getAllByRole('cell')
    .map((cell) => cell.textContent)
  expect(cells).toEqual([
    '9193.1',
    '05/10/2026',
    'Preços anteriores',
    '1.500',
    '2,5',
    'R$ 1.234,50',
    '—',
  ])
  expect(screen.getByRole('link', { name: '9193.1' })).toHaveAttribute('href', '/contratos?id=7')
})

it('builds the report and export addresses with only the filters the report applies', () => {
  const filters = {
    date_from: '2026-10-01',
    date_to: '2026-10-31',
    customer_id: '3',
    product_id: '8',
    q: 'bet 400',
  }
  expect(exportPath('renewals', 'xlsx', filters)).toBe(
    '/reports/renewals/export?date_from=2026-10-01&date_to=2026-10-31&customer_id=3&format=xlsx',
  )
  expect(exportPath('rented_products', 'pdf', filters)).toBe(
    '/reports/rented_products/export?product_id=8&q=bet+400&format=pdf',
  )
  expect(reportPath('renewals', filters, 50)).toBe(
    '/reports/renewals?date_from=2026-10-01&date_to=2026-10-31&customer_id=3&offset=50&limit=50',
  )
})

it('lists the catalogue, shows the note and exports with the chosen period', async () => {
  const user = userEvent.setup()
  const request = mockRequest((path) =>
    path === '/reports'
      ? { items: [{ key: 'renewals', title: 'Renovações' }] }
      : path.startsWith('/reports/')
        ? report
        : { items: [], total: 0 },
  )
  const fetchMock = vi.fn().mockResolvedValue(new Response(new Blob(['x'])))
  vi.stubGlobal('fetch', fetchMock)
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  renderPage(<Reports />, request)
  expect(await screen.findByRole('note')).toHaveTextContent('não representam pagamentos recebidos')
  expect(screen.getByRole('option', { name: 'Renovações' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Buscar produto para filtrar')).not.toBeInTheDocument()
  await user.type(screen.getByLabelText('Período: de'), '2026-10-01')
  await screen.findByRole('table')
  expect(request).toHaveBeenCalledWith('/reports/renewals?date_from=2026-10-01&offset=0&limit=50')
  await user.click(screen.getByRole('button', { name: 'Exportar Excel' }))
  expect(await screen.findByText('Planilha Excel gerada.')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/reports/renewals/export?date_from=2026-10-01&format=xlsx',
    expect.objectContaining({ credentials: 'same-origin' }),
  )
})
