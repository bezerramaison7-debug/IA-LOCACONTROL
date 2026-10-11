import { screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import { adminSession, dashboard } from '../test/auth-fixture'
import { mockRequest, renderPage } from '../test/render'
import { Dashboard } from './Dashboard'

it('shows the indicators returned by the API and labels the contracted value honestly', async () => {
  const request = mockRequest(() => dashboard)
  renderPage(<Dashboard />, request)
  const cards = within(await screen.findByRole('list', { name: 'Indicadores' }))
  const card = (label: string) => cards.getByText(label).closest('[role="listitem"]') as HTMLElement
  expect(within(card('Contratos ativos')).getByText('4')).toBeInTheDocument()
  expect(within(card('Itens locados')).getByText('12,5')).toBeInTheDocument()
  expect(within(card('Vencendo em breve')).getByText(/em até 3 dias/)).toBeInTheDocument()
  const value = card('Valor contratado')
  expect(within(value).getByText('R$ 15.234,50')).toBeInTheDocument()
  expect(within(value).getByText(/Não é valor recebido/)).toBeInTheDocument()
  expect(screen.getByText('Nenhum contrato vencendo ou vencido')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'contrato 9193' })).toHaveAttribute(
    'href',
    '/contratos?id=1',
  )
  expect(request).toHaveBeenCalledWith('/dashboard')
  expect(screen.queryByText(/exemplo|demonstração/i)).not.toBeInTheDocument()
})

it('gives a neutral panel, without request or error, to a profile without contracts', async () => {
  const request = mockRequest(() => {
    throw new Error('unexpected request')
  })
  renderPage(<Dashboard />, request, {
    permissions: adminSession.user.permissions.filter(
      (code) => !['contracts.read', 'quotes.write'].includes(code),
    ),
  })
  expect(screen.getByText(/não fazem parte do seu perfil/)).toBeInTheDocument()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(request).not.toHaveBeenCalled()
  const shortcuts = within(screen.getByRole('navigation', { name: 'Acesso rápido' }))
  expect(shortcuts.getByRole('link', { name: /Clientes/ })).toBeInTheDocument()
  expect(shortcuts.queryByRole('link', { name: /Contratos/ })).toBeNull()
  expect(screen.queryByRole('link', { name: 'Novo orçamento' })).toBeNull()
})
