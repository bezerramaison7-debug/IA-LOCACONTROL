import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { DataTable } from './DataTable'
import { contracts } from '../demo/data'

it('searches, filters, paginates and resets filters without changing the fixtures', async () => {
  const user = userEvent.setup()
  const original = JSON.stringify(contracts)
  render(<DataTable rows={contracts} title="contratos" />)
  expect(screen.getByText('1–5 de 7 registros')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Próxima página' }))
  expect(screen.getByText('6–7 de 7 registros')).toBeInTheDocument()
  await user.type(screen.getByRole('textbox', { name: 'Buscar em contratos' }), 'Horizonte')
  expect(screen.getByText('1–1 de 1 registros')).toBeInTheDocument()
  await user.selectOptions(
    screen.getByRole('combobox', { name: 'Filtrar status em contratos' }),
    'Vencido',
  )
  expect(screen.getByText('Nenhum resultado encontrado')).toBeInTheDocument()
  await user.click(screen.getAllByRole('button', { name: 'Limpar filtros' })[0])
  expect(screen.getByText('1–5 de 7 registros')).toBeInTheDocument()
  expect(JSON.stringify(contracts)).toBe(original)
})

it('exposes sort direction and restores focus after dismissing details with Escape', async () => {
  const user = userEvent.setup()
  render(<DataTable rows={contracts} title="contratos" />)
  const sort = screen.getByRole('button', { name: 'Código' })
  await user.click(sort)
  expect(sort.closest('th')).toHaveAttribute('aria-sort', 'ascending')
  await user.click(sort)
  expect(sort.closest('th')).toHaveAttribute('aria-sort', 'descending')
  const trigger = screen.getByRole('button', { name: 'Ver detalhes de DEMO-1042' })
  await user.click(trigger)
  expect(within(screen.getByRole('dialog')).getByText(/Registro fictício/)).toBeInTheDocument()
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus()
})
