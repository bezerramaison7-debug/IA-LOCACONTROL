import { randomUUID } from 'node:crypto'
import { test, expect } from '@playwright/test'
import {
  api,
  checkPages,
  heading,
  projectIndex,
  seedCustomer,
  signInAsAdmin,
  startsWith,
  today,
} from './helpers'

test('billing document in simulation: create, emit, download, cancel and provider returns', async ({
  page,
}, info) => {
  test.setTimeout(240_000)
  const suffix = info.project.name.toUpperCase()
  const customerName = 'Cliente fiscal ' + suffix
  await signInAsAdmin(page)
  const client = await api(page)
  const customer = await seedCustomer(client, customerName, '7777777777' + projectIndex(info))

  await page.goto('/#/fiscal')
  await expect(heading(page, 'Faturamento e fiscal')).toBeVisible()
  await expect(page).toHaveURL(/#\/faturamento$/)
  const notice = page.getByRole('note', { name: 'Aviso de simulação' })
  await expect(notice).toContainText('SIMULAÇÃO — sem valor fiscal.')
  await expect(notice).toContainText('Nenhum documento é transmitido')
  await expect(notice).toContainText('contabilidade')

  // Create: pending, nothing sent yet.
  await page.getByRole('button', { name: 'Novo documento' }).click()
  const form = page.getByRole('dialog')
  await form.getByRole('button', { name: 'Criar documento' }).click()
  await expect(form.getByText('Selecione um cliente.')).toBeVisible()
  await form.getByLabel('Buscar cliente').fill(customerName)
  const option = form.getByRole('option').filter({ hasText: customerName })
  await expect(option).toHaveCount(1)
  await form
    .getByLabel('Cliente', { exact: true })
    .selectOption({ label: (await option.textContent()) || '' })
  await form.getByLabel('Valor (R$)').fill('1500,00')
  await form.getByLabel('Descrição do faturamento').fill('Locação E2E fiscal ' + suffix)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await form.getByRole('button', { name: 'Criar documento' }).click()
  await expect(form).toHaveCount(0)
  const summary = page.getByRole('region', { name: /^Documento / })
  const actions = page.getByRole('group', { name: 'Ações do documento' })
  await expect(summary).toContainText('Pendente')
  await expect(summary).toContainText('R$ 1.500,00')
  await expect(summary).toContainText(customerName)
  await expect(notice).toBeVisible()
  const detailUrl = page.url()

  // Emit in simulation and download the generated files.
  await actions.getByRole('button', { name: 'Enviar ao provedor' }).click()
  await expect(summary).toContainText('Emitido')
  await expect(summary).toContainText('/ SIM')
  await expect(summary).toContainText('não tem valor fiscal')
  let pending = page.waitForEvent('download')
  await actions.getByRole('button', { name: 'Baixar PDF' }).click()
  let download = await pending
  expect(download.suggestedFilename()).toMatch(/^documento-fiscal-\d{6}\.pdf$/)
  expect(await startsWith(download, '%PDF-')).toBe(true)
  pending = page.waitForEvent('download')
  await actions.getByRole('button', { name: 'Baixar XML' }).click()
  download = await pending
  expect(await startsWith(download, '<?xml')).toBe(true)
  const returns = page.getByRole('region', { name: 'Retornos do provedor' })
  await expect(returns.getByRole('row')).toHaveCount(3)
  await expect(returns).toContainText('Envio ao provedor')

  // Cancel needs a reason.
  await actions.getByRole('button', { name: 'Cancelar documento' }).click()
  const cancelling = page.getByRole('dialog')
  await cancelling.getByRole('button', { name: 'Confirmar cancelamento' }).click()
  await expect(cancelling.getByText('Informe o motivo com pelo menos 5 caracteres.')).toBeVisible()
  await cancelling.getByLabel('Motivo do cancelamento').fill('Valor informado errado no E2E')
  await cancelling.getByRole('button', { name: 'Confirmar cancelamento' }).click()
  await expect(cancelling).toHaveCount(0)
  await expect(summary).toContainText('Cancelado')
  await expect(summary).toContainText('Valor informado errado no E2E')
  await expect(actions.getByRole('button', { name: 'Cancelar documento' })).toHaveCount(0)

  // Provider rejection and processing, reached through the simulation's test markers.
  const create = (description: string) =>
    client.post('/fiscal/documents', {
      customer_id: customer.id,
      contract_id: null,
      period_start: today(),
      period_end: today(),
      amount: '10.00',
      description,
      request_key: randomUUID(),
    })
  const rejected = await create('Rejeitado ' + suffix + ' [ERRO]')
  await page.goto('/#/faturamento?id=' + rejected.id)
  await actions.getByRole('button', { name: 'Enviar ao provedor' }).click()
  await expect(summary).toContainText('Erro')
  await expect(
    page.getByText('Retorno do provedor: Rejeição simulada pelo provedor.'),
  ).toBeVisible()
  await expect(actions.getByRole('button', { name: 'Enviar novamente ao provedor' })).toBeVisible()
  const slow = await create('Em fila ' + suffix + ' [PROCESSANDO]')
  await page.goto('/#/faturamento?id=' + slow.id)
  await actions.getByRole('button', { name: 'Enviar ao provedor' }).click()
  await expect(summary).toContainText('Processando')
  await actions.getByRole('button', { name: 'Consultar situação' }).click()
  await expect(summary).toContainText('Emitido')

  // List with the status filter.
  await page.getByRole('button', { name: 'Voltar para a lista' }).click()
  await page.getByLabel('Filtrar situação').selectOption('ERRO')
  const list = page.getByRole('region', { name: 'Lista de documentos de faturamento' })
  await expect(list.getByRole('row').filter({ hasText: 'Rejeitado ' + suffix })).toHaveCount(1)
  await expect(list.getByRole('row').filter({ hasText: 'Em fila ' + suffix })).toHaveCount(0)

  await checkPages(page, info, [
    ['/#/faturamento', 'Faturamento e fiscal', 'faturamento'],
    [detailUrl, 'Faturamento e fiscal', 'faturamento-detalhe'],
  ])
})
