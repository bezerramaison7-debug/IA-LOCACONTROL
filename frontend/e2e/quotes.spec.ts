import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('real quote: table price, negotiation, send, approve and PDF', async ({ page }, info) => {
  const suffix = info.project.name.toUpperCase()
  const index = ['desktop', 'full-hd', 'tablet', 'mobile'].indexOf(info.project.name) + 1
  const customerName = 'Cliente orçamento ' + suffix
  const code = 'Q-' + suffix
  await page.goto('/#/login')
  await page.getByLabel('Usuário', { exact: true }).fill('browser_admin')
  await page.getByLabel('Senha', { exact: true }).fill('Fixture-browser-password!')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Visão geral' })).toBeVisible()

  // Master data is seeded through the real API with the session's own CSRF token.
  const session = await (
    await page.request.get('/api/auth/me', { headers: { 'X-LocaControl-Request': '1' } })
  ).json()
  const headers = {
    'X-LocaControl-Request': '1',
    'X-CSRF-Token': session.csrf_token,
    Origin: new URL(page.url()).origin,
  }
  const post = async (path: string, data: unknown) => {
    const response = await page.request.post('/api' + path, { headers, data })
    expect(response.ok(), path + ': ' + (await response.text())).toBe(true)
    return response.json()
  }
  await post('/customers', {
    person_type: 'PF',
    legal_name: customerName,
    trade_name: '',
    document: '2222222222' + index,
    state_registration: '',
    phone: '',
    mobile: '',
    email: '',
    contact: '',
    notes: '',
    is_active: true,
    addresses: [],
  })
  const product = await post('/products', {
    code,
    name: 'Betoneira orçamento ' + suffix,
    description: '',
    category: '',
    unit: 'UN',
    individual_tracking: false,
    is_active: true,
  })
  await post('/prices', {
    product_id: product.id,
    period: 'DIARIA',
    effective_date: '2020-01-01',
    amount: '350.00',
    reason: 'Preço E2E de orçamento',
  })
  await post('/stock/movements', {
    product_id: product.id,
    quantity: '5',
    from_status: null,
    to_status: 'DISPONIVEL',
    reason: 'Entrada E2E de orçamento',
    request_key: randomUUID(),
  })

  await page.goto('/#/orcamentos')
  await expect(page.getByRole('heading', { level: 1, name: 'Orçamentos' })).toBeVisible()
  await expect(page.getByText('Modo demonstração')).toHaveCount(0)
  await page.getByRole('button', { name: 'Novo orçamento', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Novo orçamento' })).toBeVisible()
  await page.getByLabel('Buscar cliente').fill(customerName)
  const customerOption = page.getByRole('option').filter({ hasText: customerName })
  await expect(customerOption).toHaveCount(1)
  await page
    .getByLabel('Cliente', { exact: true })
    .selectOption({ label: (await customerOption.textContent()) || '' })
  await page.getByLabel('Buscar produto do item 1').fill(code)
  const productOption = page.getByRole('option').filter({ hasText: code })
  await expect(productOption).toHaveCount(1)
  await page
    .getByLabel('Produto do item 1', { exact: true })
    .selectOption({ label: (await productOption.textContent()) || '' })
  await expect(page.getByText('Preço de tabela: R$ 350,00')).toBeVisible()
  await expect(page.getByText(/Disponível agora: 5 UN.*não reserva estoque/)).toBeVisible()

  // A period without a published price is shown as missing and blocks saving.
  await page.getByLabel('Período do item 1').selectOption('MENSAL')
  await expect(page.getByText('Preço ausente.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Salvar rascunho' })).toBeDisabled()
  await page.getByLabel('Período do item 1').selectOption('DIARIA')
  await expect(page.getByText('Preço de tabela: R$ 350,00')).toBeVisible()

  await page.getByLabel('Quantidade do item 1').fill('2')
  await page.getByLabel('Número de períodos do item 1').fill('3')
  await expect(page.getByText('Prévia do total: R$ 2.100,00')).toBeVisible()
  await page.getByLabel('Preço negociado do item 1 (R$)').fill('300,00')
  await expect(page.getByText('Prévia do total: R$ 1.800,00')).toBeVisible()
  await page.getByLabel('Observações').fill('Orçamento criado pelo teste E2E')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.getByRole('button', { name: 'Salvar rascunho' }).click()

  await expect(
    page.getByRole('heading', { level: 1, name: /Orçamento ORC-\d{4}-\d{6}/ }),
  ).toBeVisible()
  const summary = page.getByRole('region', { name: 'Resumo' })
  const items = page.getByRole('region', { name: 'Itens', exact: true })
  await expect(summary).toContainText('Rascunho')
  await expect(items).toContainText('Negociado')
  await expect(items).toContainText('Total pela tabelaR$ 2.100,00')
  await expect(items).toContainText('Desconto negociadoR$ 300,00')
  await expect(items).toContainText('Total do orçamentoR$ 1.800,00')

  await summary.getByRole('button', { name: 'Enviar', exact: true }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Confirmar envio' }).click()
  await expect(summary).toContainText('Enviado')
  await expect(summary.getByRole('button', { name: 'Editar' })).toHaveCount(0)

  // Rejecting needs a reason; the dialog keeps the error next to the field.
  await summary.getByRole('button', { name: 'Rejeitar', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Confirmar rejeição' }).click()
  await expect(dialog.getByText('Informe o motivo com pelo menos 5 caracteres.')).toBeVisible()
  await dialog.getByRole('button', { name: 'Voltar' }).click()

  await summary.getByRole('button', { name: 'Aprovar', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Confirmar aprovação' }).click()
  await expect(summary).toContainText('Aprovado')
  await expect(summary).toContainText('A conversão em contrato chega com o módulo de contratos')
  await expect(page.getByRole('button', { name: /Converter/ })).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Histórico', exact: true })).toContainText(
    'Enviado → Aprovado',
  )

  const pending = page.waitForEvent('download')
  await summary.getByRole('button', { name: 'Baixar PDF' }).click()
  const download = await pending
  expect(download.suggestedFilename()).toMatch(/^ORC-\d{4}-\d{6}\.pdf$/)
  expect(
    readFileSync(await download.path())
      .subarray(0, 5)
      .toString(),
  ).toBe('%PDF-')

  const detailUrl = page.url()
  for (const theme of ['light', 'dark']) {
    await page.evaluate((t) => {
      localStorage.setItem('locacontrol.theme', t)
    }, theme)
    for (const [url, title] of [
      [detailUrl, /Orçamento ORC-/],
      ['/#/orcamentos?novo=1', 'Novo orçamento'],
      ['/#/orcamentos', 'Orçamentos'],
    ] as const) {
      await page.goto(url)
      await page.reload()
      await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
      if (title === 'Novo orçamento')
        await expect(page.getByLabel('Cliente', { exact: true })).toBeVisible()
      else await expect(page.getByRole('table').first()).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(
        false,
      )
      const axe = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze()
      expect(
        axe.violations,
        JSON.stringify(
          axe.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
        ),
      ).toEqual([])
      if (title !== 'Orçamentos')
        await page.screenshot({
          path: info.outputPath(
            (title === 'Novo orçamento' ? 'editor-' : 'detalhe-') + theme + '.png',
          ),
          fullPage: true,
        })
    }
  }

  await page.getByLabel('Buscar em orçamentos').fill(customerName)
  const row = page.getByRole('row').filter({ hasText: customerName })
  await expect(row).toHaveCount(1)
  await expect(row).toContainText('Aprovado')
  await expect(row).toContainText('R$ 1.800,00')
  await page.getByLabel('Filtrar situação').selectOption('REJEITADO')
  await expect(page.getByText('Nenhum orçamento encontrado')).toBeVisible()
  await page.getByRole('button', { name: 'Limpar filtros' }).click()
  await expect(page.getByRole('table')).toBeVisible()
})
