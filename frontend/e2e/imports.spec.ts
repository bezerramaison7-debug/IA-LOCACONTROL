import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('upload existing Excel, dry run, partial conversion and report', async ({ page }, info) => {
  await page.goto('/#/login')
  await page.getByLabel('Usuário', { exact: true }).fill('browser_admin')
  await page.getByLabel('Senha', { exact: true }).fill('Fixture-browser-password!')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Visão geral' })).toBeVisible()
  await page.goto('/#/importacoes')
  const fixture = process.env.E2E_EXCEL_FILE!.replace('.xlsx', '-' + info.project.name + '.xlsx')
  await page.getByLabel('Arquivo Excel', { exact: true }).setInputFiles(fixture)
  await page.getByRole('button', { name: 'Enviar e analisar Excel' }).click()
  await expect(page.getByText(/3 linhas · 4 colunas/)).toBeVisible()
  await page.getByLabel(/Tipo de pessoa/).selectOption('1')
  await page.getByLabel(/Nome \/ razão social/).selectOption('2')
  await page.getByRole('combobox', { name: 'CPF/CNPJ *', exact: true }).selectOption('3')
  await page.getByRole('button', { name: 'Validar e gerar prévia' }).click()
  await expect(page.getByRole('status')).toContainText('Válidos: 1')
  await expect(page.getByRole('status')).toContainText('Erros: 1')
  const clients = await page.request.get(
    '/api/customers?q=' + encodeURIComponent('Cliente importado ' + info.project.name),
  )
  expect((await clients.json()).total).toBe(0)
  await page
    .getByLabel('Revisei os avisos, os erros e as informações que ficaram sem destino.')
    .check()
  await page.getByRole('button', { name: 'Confirmar importação das linhas válidas' }).click()
  await expect(page.getByRole('status')).toContainText('Importados: 1')
  await expect(page.getByRole('status')).toContainText('Erros: 1')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Baixar relatório JSON' }).click()
  expect((await download).suggestedFilename()).toContain('importacao-')
  await page.reload()
  await page.getByRole('button', { name: 'Abrir arquivo e relatório' }).first().click()
  await expect(page.getByRole('heading', { name: 'Resultado da importação' })).toBeVisible()
  for (const theme of ['light', 'dark']) {
    await page.evaluate((value) => {
      document.documentElement.dataset.theme = value
      document.documentElement.style.colorScheme = value
    }, theme)
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
    await page.screenshot({ path: info.outputPath('importacao-' + theme + '.png'), fullPage: true })
  }
  await page.goto('/#/clientes')
  await page.getByLabel('Buscar em clientes').fill('Cliente importado ' + info.project.name)
  await expect(
    page.getByRole('cell', { name: 'Cliente importado ' + info.project.name, exact: true }),
  ).toBeVisible()
})
