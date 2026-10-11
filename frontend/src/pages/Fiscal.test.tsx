import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { adminSession } from '../test/auth-fixture'
import { mockRequest, renderPage, writes } from '../test/render'
import { Fiscal } from './Fiscal'

const provider = { name: 'fake', environment: 'SIMULACAO', is_simulation: true, document_kind: '' }
const document = {
  id: 7,
  customer_id: 3,
  customer: { legal_name: 'Cliente Alfa', document: '11222333000181' },
  contract_id: null,
  period_start: '2026-10-01',
  period_end: '2026-10-31',
  amount: '1500.00',
  description: 'Locação de outubro',
  status: 'EMITIDO',
  provider: 'fake',
  environment: 'SIMULACAO',
  is_simulation: true,
  provider_ref: 'SIM-ABC',
  number: '000123',
  series: 'SIM',
  access_key: null,
  error_message: '',
  cancel_reason: '',
  has_pdf: true,
  has_xml: true,
  version: 3,
  created_at: 1789254000,
  updated_at: 1789254000,
  created_by: 1,
  events: [
    {
      action: 'EMIT',
      status: 'EMITIDO',
      response: { simulacao: true },
      created_at: 1789254000,
      created_by: 1,
    },
  ],
}
const api = (mutate: () => unknown = () => ({ ...document, status: 'CANCELADO', version: 4 })) =>
  mockRequest((path, method) =>
    method !== 'GET'
      ? mutate()
      : path === '/fiscal/provider'
        ? provider
        : path.startsWith('/fiscal/documents?')
          ? { items: [document], total: 1 }
          : document,
  )

it('keeps the simulation warning permanent and does not invent a document type', async () => {
  renderPage(<Fiscal />, api())
  const notice = await screen.findByRole('note', { name: 'Aviso de simulação' })
  expect(notice).toHaveTextContent('SIMULAÇÃO — sem valor fiscal.')
  expect(notice).toHaveTextContent('Nenhum documento é transmitido')
  expect(notice).toHaveTextContent(
    'depende das regras definidas com a contabilidade, da escolha do provedor e de credenciais de teste',
  )
  expect(
    screen.getByText(/tipo de documento: ainda não definido com a contabilidade/),
  ).toBeVisible()
  const row = (await screen.findByText('000123')).closest('tr')!
  expect(within(row).getByText('R$ 1.500,00')).toBeInTheDocument()
  expect(within(row).getByText('Emitido')).toBeInTheDocument()
  expect(within(row).getByText('Simulação')).toBeInTheDocument()
})

it('requires a reason of five characters before cancelling', async () => {
  const user = userEvent.setup()
  const request = api()
  renderPage(<Fiscal />, request, { entry: '/?id=7' })
  expect(await screen.findByRole('note', { name: 'Aviso de simulação' })).toBeInTheDocument()
  await user.click(await screen.findByRole('button', { name: 'Cancelar documento' }))
  const dialog = within(screen.getByRole('dialog'))
  await user.type(dialog.getByLabelText('Motivo do cancelamento'), 'erro')
  await user.click(dialog.getByRole('button', { name: 'Confirmar cancelamento' }))
  expect(dialog.getByText('Informe o motivo com pelo menos 5 caracteres.')).toBeInTheDocument()
  expect(writes(request)).toHaveLength(0)
  await user.type(dialog.getByLabelText('Motivo do cancelamento'), ' de valor')
  await user.click(dialog.getByRole('button', { name: 'Confirmar cancelamento' }))
  expect(await screen.findByText('Documento cancelado.')).toBeInTheDocument()
  expect(writes(request)).toEqual([
    ['/fiscal/documents/7/cancel', 'POST', { version: 3, reason: 'erro de valor' }],
  ])
  expect(screen.queryByRole('button', { name: 'Cancelar documento' })).toBeNull()
})

it('hides every write action from a read-only profile', async () => {
  renderPage(<Fiscal />, api(), {
    entry: '/?id=7',
    permissions: adminSession.user.permissions.filter((code) => code !== 'fiscal.write'),
  })
  expect(await screen.findByRole('button', { name: 'Baixar PDF' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Cancelar documento' })).toBeNull()
  expect(screen.queryByRole('button', { name: 'Novo documento' })).toBeNull()
})
