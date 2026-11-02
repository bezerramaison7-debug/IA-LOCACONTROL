import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { test, expect, type Download } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const isPdf = async (download: Download) =>
  readFileSync(await download.path())
    .subarray(0, 5)
    .toString() === '%PDF-'

test('real contract: withdrawal, document, renewal, returns and automatic closing', async ({
  page,
}, info) => {
  test.setTimeout(300_000)
  const suffix = info.project.name.toUpperCase()
  const index = ['desktop', 'full-hd', 'tablet', 'mobile'].indexOf(info.project.name) + 1
  const customerName = 'Cliente contrato ' + suffix
  const bulkCode = 'CTX-' + suffix
  const unitCode = 'CTY-' + suffix
  const bulkName = 'Andaime contrato ' + suffix
  const unitName = 'Betoneira contrato ' + suffix
  const equipment = 'UNX1-' + suffix
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
    document: '3333333333' + index,
    state_registration: '',
    phone: '',
    mobile: '',
    email: '',
    contact: '',
    notes: '',
    is_active: true,
    addresses: [],
  })
  const product = (code: string, name: string, individual: boolean) =>
    post('/products', {
      code,
      name,
      description: '',
      category: '',
      unit: 'UN',
      individual_tracking: individual,
      is_active: true,
    })
  const bulk = await product(bulkCode, bulkName, false)
  const tracked = await product(unitCode, unitName, true)
  for (const [id, amount] of [
    [bulk.id, '100.00'],
    [tracked.id, '50.00'],
  ])
    await post('/prices', {
      product_id: id,
      period: 'DIARIA',
      effective_date: '2020-01-01',
      amount,
      reason: 'Preço E2E de contrato',
    })
  await post('/stock/movements', {
    product_id: bulk.id,
    quantity: '5',
    from_status: null,
    to_status: 'DISPONIVEL',
    reason: 'Entrada E2E de contrato',
    request_key: randomUUID(),
  })
  for (const code of [equipment, 'UNX2-' + suffix])
    await post('/equipment', {
      product_id: tracked.id,
      code,
      asset_tag: null,
      serial_number: null,
      brand: '',
      model: '',
      notes: '',
    })

  const summary = page.getByRole('region', { name: 'Resumo' })
  const heading = (name: string | RegExp) =>
    page.getByRole('heading', { level: 1, name, exact: true })
  const confirmInDialog = async (name: string) => {
    await page.getByRole('dialog').getByRole('button', { name, exact: true }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
  }

  // Direct contract: draft with one item by quantity and one physical unit.
  await page.goto('/#/contratos')
  await expect(heading('Contratos')).toBeVisible()
  await expect(page.getByText('Modo demonstração')).toHaveCount(0)
  await page.getByRole('button', { name: 'Novo contrato', exact: true }).click()
  await expect(heading('Novo contrato')).toBeVisible()
  await page.getByLabel('Buscar cliente').fill(customerName)
  const customerOption = page.getByRole('option').filter({ hasText: customerName })
  await expect(customerOption).toHaveCount(1)
  await page
    .getByLabel('Cliente', { exact: true })
    .selectOption({ label: (await customerOption.textContent()) || '' })
  const pick = async (item: number, code: string) => {
    await page.getByLabel('Buscar produto do item ' + item).fill(code)
    const select = page.getByLabel('Produto do item ' + item, { exact: true })
    const option = select.getByRole('option').filter({ hasText: code + ' ·' })
    await expect(option).toHaveCount(1)
    await expect(select.getByRole('option')).toHaveCount(2)
    await select.selectOption({ label: (await option.textContent()) || '' })
  }
  await pick(1, bulkCode)
  await expect(page.getByText('Preço de tabela: R$ 100,00')).toBeVisible()
  await page.getByLabel('Quantidade do item 1').fill('3')
  await page.getByLabel('Número de períodos do item 1').fill('10')
  await page.getByRole('button', { name: 'Adicionar item' }).click()
  await pick(2, unitCode)
  await expect(page.getByText('Preço de tabela: R$ 50,00')).toBeVisible()
  await page.getByLabel('Número de períodos do item 2').fill('10')
  await expect(page.getByText('Prévia do total: R$ 3.500,00')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.getByRole('button', { name: 'Salvar rascunho' }).click()

  await expect(heading(/^Contrato \d+$/)).toBeVisible()
  const number = ((await heading(/^Contrato \d+$/).textContent()) || '').replace('Contrato ', '')
  await expect(summary).toContainText('Rascunho')
  await expect(page.getByRole('region', { name: 'Valores', exact: true })).toContainText(
    'Total do contratoR$ 3.500,00',
  )
  const documents = page.getByRole('region', { name: 'Documentos', exact: true })
  let pending = page.waitForEvent('download')
  await documents.getByRole('button', { name: 'Baixar prévia (PDF)' }).click()
  let download = await pending
  expect(download.suggestedFilename()).toBe('Contrato-' + number + '-previa.pdf')
  expect(await isPdf(download)).toBe(true)
  await expect(documents.getByRole('button', { name: 'Gerar documento' })).toHaveCount(0)
  await expect(documents.getByText('Modelo provisório.')).toBeVisible()

  await summary.getByRole('button', { name: 'Confirmar contrato' }).click()
  await confirmInDialog('Confirmar contrato')
  await expect(summary).toContainText('Aguardando retirada')
  await expect(summary.getByRole('button', { name: 'Editar' })).toHaveCount(0)

  // Withdrawal: the physical unit is mandatory for the individually tracked item.
  await summary.getByRole('button', { name: 'Registrar retirada' }).click()
  await expect(heading('Registrar retirada · contrato ' + number)).toBeVisible()
  await page.getByRole('button', { name: 'Revisar retirada' }).click()
  await expect(
    page.getByText('Selecione exatamente 1 unidade física de ' + unitName + '.'),
  ).toBeVisible()
  await page.getByRole('checkbox', { name: equipment, exact: true }).check()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.getByRole('button', { name: 'Revisar retirada' }).click()
  await expect(page.getByRole('dialog')).toContainText('saem do estoque disponível')
  await confirmInDialog('Confirmar retirada')
  await expect(heading('Contrato ' + number)).toBeVisible()
  await expect(summary).toContainText('Ativo')
  const items = page.getByRole('region', { name: 'Itens do contrato ' + number })
  await expect(items).toContainText(equipment + ' · Com o cliente')
  await expect(summary.getByRole('button', { name: 'Registrar retirada' })).toHaveCount(0)

  // Document: generate, download, sign; a new version keeps the signed one.
  await documents.getByRole('button', { name: 'Gerar documento' }).click()
  await confirmInDialog('Gerar documento')
  const versions = page.getByRole('region', {
    name: 'Versões do documento do contrato ' + number,
  })
  await expect(versions.getByRole('row').filter({ hasText: 'v1' })).toContainText('Gerado')
  pending = page.waitForEvent('download')
  await versions.getByRole('button', { name: 'Baixar versão 1' }).click()
  download = await pending
  expect(download.suggestedFilename()).toBe('Contrato-' + number + '-v1.pdf')
  expect(await isPdf(download)).toBe(true)
  await versions.getByRole('button', { name: 'Marcar versão 1 como assinada' }).click()
  await confirmInDialog('Confirmar assinatura')
  await expect(versions.getByRole('row').filter({ hasText: 'v1' })).toContainText('Assinado')
  await documents.getByRole('button', { name: 'Gerar documento' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Já existe documento assinado (versão 1).')
  await dialog.getByRole('button', { name: 'Gerar documento' }).click()
  await expect(dialog.getByText('Informe o motivo com pelo menos 5 caracteres.')).toBeVisible()
  await dialog.getByLabel('Motivo da nova versão').fill('Nova via solicitada no E2E')
  await confirmInDialog('Gerar documento')
  await expect(versions.getByRole('row').filter({ hasText: 'v2' })).toContainText('Gerado')
  await expect(versions.getByRole('row').filter({ hasText: 'v1' })).toContainText('Assinado')

  // Partial renewal: only the physical unit moves to the next link of the chain.
  await summary.getByRole('button', { name: 'Renovar' }).click()
  await expect(heading('Renovar contrato · contrato ' + number)).toBeVisible()
  await page.getByRole('button', { name: 'Revisar renovação' }).click()
  await expect(page.getByText('Escolha a opção de preço da renovação.')).toBeVisible()
  await page.getByRole('radio', { name: /Manter os preços anteriores/ }).check()
  await page.getByRole('checkbox', { name: new RegExp('^Renovar ' + bulkName) }).uncheck()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.getByRole('button', { name: 'Revisar renovação' }).click()
  await expect(page.getByRole('dialog')).toContainText('Renovação parcial')
  await confirmInDialog('Confirmar renovação')
  await expect(heading('Contrato ' + number + '.1')).toBeVisible()
  const renewalUrl = page.url()
  await expect(summary).toContainText('Renovação')
  await expect(summary).toContainText('Manter os preços anteriores')
  await expect(summary).toContainText('Ativo')
  await expect(
    page.getByRole('region', { name: 'Itens do contrato ' + number + '.1' }),
  ).toContainText(equipment + ' · Com o cliente')

  // The original contract keeps the item that was not renewed.
  await page.getByRole('link', { name: 'Abrir contrato ' + number, exact: true }).click()
  await expect(heading('Contrato ' + number)).toBeVisible()
  const detailUrl = page.url()
  await expect(items).toContainText(equipment + ' · Renovado')
  await expect(summary).toContainText('Ativo')

  // Partial return, damaged: goes to maintenance and the contract stays active.
  await summary.getByRole('button', { name: 'Registrar devolução' }).click()
  await expect(heading('Registrar devolução · contrato ' + number)).toBeVisible()
  await page.getByLabel('Quantidade devolvida de ' + bulkName).fill('9')
  await page.getByRole('button', { name: 'Revisar devolução' }).click()
  await expect(
    page.getByText('A quantidade devolvida supera a quantidade com o cliente (3 UN).'),
  ).toBeVisible()
  await page.getByLabel('Quantidade devolvida de ' + bulkName).fill('1')
  await page.getByLabel('Condição de ' + bulkName).selectOption('AVARIADO')
  await expect(page.getByLabel('Destino de ' + bulkName)).toBeDisabled()
  await expect(page.getByLabel('Destino de ' + bulkName)).toHaveValue('MANUTENCAO')
  await page.getByRole('button', { name: 'Revisar devolução' }).click()
  await expect(page.getByRole('dialog')).toContainText('Devolução parcial')
  await confirmInDialog('Confirmar devolução')
  await expect(heading('Contrato ' + number)).toBeVisible()
  await expect(summary).toContainText('Ativo')
  await expect(page.getByRole('region', { name: 'Retiradas e devoluções' })).toContainText(
    'Avariado → Manutenção',
  )

  // Total return: nothing is left with the customer, so the contract closes by itself.
  await summary.getByRole('button', { name: 'Registrar devolução' }).click()
  await expect(page.getByLabel('Quantidade devolvida de ' + bulkName)).toHaveValue('2')
  await page.getByRole('button', { name: 'Revisar devolução' }).click()
  await expect(page.getByRole('dialog')).toContainText(
    'Devolução total: o contrato será encerrado automaticamente.',
  )
  await confirmInDialog('Confirmar devolução')
  await expect(heading('Contrato ' + number)).toBeVisible()
  await expect(summary).toContainText('Encerrado')
  await expect(summary.getByRole('button')).toHaveCount(0)
  const timeline = page.getByRole('list', { name: 'Linha do tempo da cadeia ' + number })
  for (const text of ['Criado', 'Confirmado', 'Retirada', 'Devolução', 'Encerrado', number + '.1'])
    await expect(timeline).toContainText(text)
  await expect(page.getByRole('region', { name: 'Cadeia de renovações' })).toContainText(
    number + '.1',
  )

  // Maintenance: the damaged quantity is released back to the available balance.
  await page.goto('/#/manutencao')
  await expect(heading('Manutenção')).toBeVisible()
  const balances = page.getByRole('region', { name: 'Saldos em manutenção', exact: true })
  await expect(balances.getByRole('row').filter({ hasText: bulkName })).toContainText('1 UN')
  await page.getByRole('button', { name: 'Liberar saldo de ' + bulkName }).click()
  await page.getByRole('dialog').getByLabel('Motivo da liberação').fill('Reparo concluído no E2E')
  await confirmInDialog('Confirmar liberação')
  await expect(page.getByRole('row').filter({ hasText: bulkName })).toHaveCount(0)

  // Operational views reach the renewed contract, still with the customer.
  await page.goto('/#/devolucoes')
  await expect(
    page
      .getByRole('row')
      .filter({ hasText: customerName })
      .filter({ hasText: number + '.1' }),
  ).toBeVisible()
  await page.goto('/#/renovacoes')
  await expect(
    page
      .getByRole('region', { name: 'Renovações registradas', exact: true })
      .getByRole('row')
      .filter({ hasText: customerName }),
  ).toContainText(number + '.1')

  for (const theme of ['light', 'dark']) {
    await page.evaluate((t) => {
      localStorage.setItem('locacontrol.theme', t)
    }, theme)
    for (const [url, title, shot] of [
      [detailUrl, 'Contrato ' + number, 'detalhe'],
      [
        renewalUrl + '&acao=devolucao',
        'Registrar devolução · contrato ' + number + '.1',
        'devolucao',
      ],
      [renewalUrl + '&acao=renovar', 'Renovar contrato · contrato ' + number + '.1', 'renovacao'],
      ['/#/contratos?novo=1', 'Novo contrato', ''],
      ['/#/contratos', 'Contratos', ''],
      ['/#/retiradas', 'Retiradas', ''],
      ['/#/devolucoes', 'Devoluções', ''],
      ['/#/renovacoes', 'Renovações', ''],
      ['/#/manutencao', 'Manutenção', ''],
      ['/#/configuracoes', 'Configurações', 'configuracoes'],
    ] as const) {
      await page.goto(url)
      await page.reload()
      await expect(heading(title)).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.getByRole('status', { name: 'Carregando conteúdo' })).toHaveCount(0)
      if (title === 'Novo contrato')
        await expect(page.getByLabel('Cliente', { exact: true })).toBeVisible()
      else if (title === 'Configurações') {
        await expect(page.getByLabel('Próximo número de contrato')).toBeVisible()
        await expect(page.getByLabel('Texto do modelo')).not.toHaveValue('')
        await expect(page.getByText(/Este modelo é provisório/)).toBeVisible()
      } else if (title.startsWith('Re') && title.includes('·'))
        await expect(page.getByRole('button', { name: /^Revisar/ })).toBeVisible()
      else if (!['Manutenção', 'Retiradas'].includes(title))
        await expect(page.getByRole('table').first()).toBeVisible()
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        url + ': sem overflow horizontal',
      ).toBe(false)
      const axe = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze()
      expect(
        axe.violations,
        url +
          ' ' +
          JSON.stringify(
            axe.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
          ),
      ).toEqual([])
      if (shot)
        await page.screenshot({
          path: info.outputPath(shot + '-' + theme + '.png'),
          fullPage: true,
        })
    }
  }

  // Search by number brings the whole chain; "N.1" only the renewal.
  await page.goto('/#/contratos')
  await page.getByLabel('Buscar em contratos').fill(number)
  await expect(page.getByRole('row').filter({ hasText: customerName })).toHaveCount(2)
  await page.getByLabel('Buscar em contratos').fill(number + '.1')
  await expect(page.getByRole('row').filter({ hasText: customerName })).toHaveCount(1)
  await page.getByLabel('Filtrar situação').selectOption('CANCELADO')
  await expect(page.getByText('Nenhum contrato encontrado')).toBeVisible()
  await page.getByRole('button', { name: 'Limpar filtros' }).click()
  await expect(page.getByRole('table')).toBeVisible()
})
