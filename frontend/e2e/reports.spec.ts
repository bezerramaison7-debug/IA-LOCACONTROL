import { test, expect } from '@playwright/test'
import {
  api,
  checkPages,
  heading,
  projectIndex,
  seedActiveContract,
  seedCustomer,
  seedProduct,
  signInAsAdmin,
  startsWith,
} from './helpers'

test('real dashboard, reports with export, customer summary and advanced search', async ({
  page,
}, info) => {
  test.setTimeout(240_000)
  const suffix = info.project.name.toUpperCase()
  const customerName = 'Cliente relatório ' + suffix
  const code = 'RPT-' + suffix
  await signInAsAdmin(page)
  const client = await api(page)
  const customer = await seedCustomer(client, customerName, '4444444444' + projectIndex(info))
  const product = await seedProduct(client, code, 'Andaime relatório ' + suffix)
  // One day: the contract is due soon, so the dashboard lists it.
  const contract = await seedActiveContract(client, customer.id, product.id, '3', 1)

  // Dashboard: numbers come from the API, never from fixtures.
  await page.goto('/#/')
  await page.reload()
  const cards = page.getByRole('list', { name: 'Indicadores' })
  const active = cards.getByRole('listitem').filter({ hasText: /^Contratos ativos/ })
  expect(Number(await active.locator('.metric-value').textContent())).toBeGreaterThan(0)
  await expect(cards.getByRole('listitem').filter({ hasText: 'Valor contratado' })).toContainText(
    'Não é valor recebido',
  )
  await expect(page.getByText('Modo demonstração')).toHaveCount(0)
  const due = page.getByRole('region', {
    name: 'Lista de contratos vencendo e vencidos',
    exact: true,
  })
  await expect(due.getByRole('row').filter({ hasText: customerName })).toContainText('Vencendo')
  await expect(
    page.getByRole('link', { name: 'contrato ' + contract.number, exact: true }).first(),
  ).toBeVisible()

  // Reports: generic table, note about contracted value and a real xlsx download.
  await page.goto('/#/relatorios')
  await expect(heading(page, 'Relatórios')).toBeVisible()
  const picker = page.getByLabel('Relatório', { exact: true })
  await expect(picker.getByRole('option')).toHaveCount(12)
  await picker.selectOption('active_rentals')
  const table = page.getByRole('region', { name: 'Tabela: Locações ativas', exact: true })
  const row = table.getByRole('row').filter({ hasText: customerName })
  await expect(row).toContainText('R$ 300,00')
  await expect(row.getByRole('link', { name: contract.number, exact: true })).toBeVisible()
  await page.getByLabel('Buscar cliente para filtrar').fill(customerName)
  const option = page.getByRole('option').filter({ hasText: customerName })
  await expect(option).toHaveCount(1)
  await page
    .getByLabel('Cliente do relatório')
    .selectOption({ label: (await option.textContent()) || '' })
  await expect(table.getByRole('row')).toHaveCount(2)
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Exportar Excel' }).click()
  const download = await pending
  expect(download.suggestedFilename()).toBe('relatorio-active_rentals.xlsx')
  expect(await startsWith(download, 'PK')).toBe(true)
  await expect(page.getByText('Planilha Excel gerada.')).toBeVisible()
  await picker.selectOption('contracted_revenue')
  await expect(page.getByRole('note')).toContainText('não representam pagamentos recebidos')
  await expect(
    page.getByRole('region', { name: 'Tabela: Receita contratada por período', exact: true }),
  ).toContainText('R$ 300,00')

  // Customer page: contracts and documents of one customer.
  await page.goto('/#/clientes')
  await page.getByLabel('Buscar em clientes').fill(customerName)
  await page.getByRole('button', { name: 'Contratos e documentos de ' + customerName }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Valor contratado (contratos ativos)')
  await expect(dialog).toContainText('R$ 300,00')
  await expect(
    dialog.getByRole('link', { name: 'Abrir contrato ' + contract.number, exact: true }),
  ).toBeVisible()
  await expect(dialog.getByText('Nenhum documento gerado')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.keyboard.press('Escape')

  // Advanced contract search by product code.
  await page.goto('/#/contratos')
  await page.getByText('Filtros avançados').click()
  await page.getByLabel('Produto', { exact: true }).fill(code)
  await expect(page.getByRole('row').filter({ hasText: customerName })).toHaveCount(1)
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(2)
  await page.getByLabel('Origem').selectOption('RENOVACAO')
  await expect(page.getByText('Nenhum contrato encontrado')).toBeVisible()

  await checkPages(page, info, [
    ['/#/', 'Visão geral', 'dashboard'],
    ['/#/relatorios', 'Relatórios', 'relatorios'],
    ['/#/renovacoes', 'Renovações'],
  ])
})
