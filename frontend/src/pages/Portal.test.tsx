import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { ApiError } from '../auth/api'
import { mockRequest, renderPage, writes } from '../test/render'
import { Portal } from './Portal'
import { RenewalRequests } from './renewal-requests'

const contract = {
  id: 4,
  number: '9193',
  status: 'ATIVO',
  start_date: '2026-10-01',
  end_date: '2026-10-31',
  due_date: '2026-10-31',
  total: '700.00',
}
const detail = {
  ...contract,
  origin: 'DIRETO',
  items: [
    {
      product_code: 'BET-400',
      product_name: 'Betoneira 400 L',
      unit: 'UN',
      quantity: '2.000',
      period: 'SEMANAL',
      period_count: 1,
      unit_price: '350.00',
      total: '700.00',
      start_date: '2026-10-01',
      end_date: '2026-10-08',
      withdrawn: '2.000',
      returned: '0.000',
      outstanding: '2.000',
      units: [{ code: 'BET-001', state: 'EM_POSSE' }],
    },
  ],
  chain: [],
  events: [{ kind: 'RETIRADA', description: 'Retirada registrada.', created_at: 1789254000 }],
  documents: [],
}
const pending = {
  id: 3,
  contract_id: 4,
  contract_number: '9193',
  period: 'MENSAL',
  period_count: 2,
  notes: 'Obra atrasou',
  status: 'PENDENTE',
  decision_reason: '',
  decided_at: null,
  created_at: 1789254000,
  customer_id: 5,
  customer: 'Cliente Alfa',
  requested_by: 9,
  decided_by: null,
}
const portalOnly = { permissions: ['portal.access'] }

it('shows the missing customer link as a screen state, with the server explanation', async () => {
  const message = 'Sua conta ainda não está vinculada a um cliente. Fale com a locadora.'
  const request = mockRequest(() => {
    throw new ApiError(403, message)
  })
  renderPage(<Portal view="contratos" />, request, portalOnly)
  expect(await screen.findByText('Portal ainda não liberado para esta conta')).toBeInTheDocument()
  expect(screen.getByText(message)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Tentar novamente' })).toBeNull()
})

it('answers "não encontrado" for a contract that is not the customer own', async () => {
  const request = mockRequest(() => {
    throw new ApiError(404, 'Contrato não encontrado.')
  })
  renderPage(<Portal view="contratos" />, request, { ...portalOnly, entry: '/?id=99' })
  expect(await screen.findByText('Registro não encontrado')).toBeInTheDocument()
  expect(screen.getByText(/Contrato não encontrado\./)).toBeInTheDocument()
})

it('sends a renewal request that is clearly subject to approval', async () => {
  const user = userEvent.setup()
  const request = mockRequest((_path, method) =>
    method === 'POST' ? { ...pending, period_count: 3 } : detail,
  )
  renderPage(<Portal view="contratos" />, request, { ...portalOnly, entry: '/?id=4' })
  await user.click(await screen.findByRole('button', { name: 'Solicitar renovação' }))
  const dialog = within(screen.getByRole('dialog'))
  expect(dialog.getByRole('note')).toHaveTextContent('Este é um pedido, não uma renovação')
  expect(dialog.getByRole('note')).toHaveTextContent('depois que a locadora analisar e aprovar')
  await user.clear(dialog.getByLabelText('Quantidade de períodos'))
  await user.click(dialog.getByRole('button', { name: 'Enviar solicitação' }))
  expect(dialog.getByText('Informe um número inteiro de 1 a 999.')).toBeInTheDocument()
  expect(writes(request)).toHaveLength(0)
  await user.type(dialog.getByLabelText('Quantidade de períodos'), '3')
  await user.selectOptions(dialog.getByLabelText('Período desejado'), 'SEMANAL')
  await user.click(dialog.getByRole('button', { name: 'Enviar solicitação' }))
  expect(await screen.findByText(/Solicitação enviada para o contrato 9193/)).toBeInTheDocument()
  expect(writes(request)).toEqual([
    [
      '/portal/renewal-requests',
      'POST',
      { contract_id: 4, period: 'SEMANAL', period_count: 3, notes: '' },
    ],
  ])
})

it('requires a reason to refuse and warns that approving does not renew', async () => {
  const user = userEvent.setup()
  const request = mockRequest((_path, method, body) =>
    method === 'POST'
      ? { ...pending, status: (body as { decision: string }).decision, decided_by: 1 }
      : { items: [pending], total: 1 },
  )
  renderPage(<RenewalRequests />, request)
  await user.click(
    await screen.findByRole('button', { name: 'Recusar solicitação do contrato 9193' }),
  )
  let dialog = within(screen.getByRole('dialog'))
  await user.type(dialog.getByLabelText('Motivo da recusa'), 'não')
  await user.click(dialog.getByRole('button', { name: 'Confirmar recusa' }))
  expect(
    dialog.getByText('Informe o motivo da recusa com pelo menos 5 caracteres.'),
  ).toBeInTheDocument()
  expect(writes(request)).toHaveLength(0)
  await user.click(dialog.getByRole('button', { name: 'Voltar' }))

  await user.click(screen.getByRole('button', { name: 'Aprovar solicitação do contrato 9193' }))
  dialog = within(screen.getByRole('dialog'))
  expect(dialog.getByRole('note')).toHaveTextContent('Aprovar NÃO cria a renovação')
  await user.click(dialog.getByRole('button', { name: 'Confirmar aprovação' }))
  expect(await screen.findByRole('link', { name: 'Renovar contrato 9193' })).toHaveAttribute(
    'href',
    '/contratos?id=4&acao=renovar',
  )
  expect(writes(request)).toEqual([
    ['/renewal-requests/3/decide', 'POST', { decision: 'APROVADA', reason: '' }],
  ])
})
