import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('real master data, exact stock and historical prices', async ({ page }, info) => {
  const suffix = info.project.name.toUpperCase()
  const bulk = 'B-' + suffix,
    individual = 'I-' + suffix
  const name = 'Produto ' + suffix
  await page.goto('/#/login')
  await page.getByLabel('Usuário', { exact: true }).fill('browser_admin')
  await page.getByLabel('Senha', { exact: true }).fill('Fixture-browser-password!')
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Visão geral' })).toBeVisible()
  await page.goto('/#/clientes')
  await page.getByRole('button', { name: 'Novo cliente', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nome / razão social').fill('Cliente ' + suffix)
  await dialog
    .getByLabel('CPF / CNPJ')
    .fill(
      '0000000000' +
        (info.project.name === 'desktop'
          ? '1'
          : info.project.name === 'full-hd'
            ? '2'
            : info.project.name === 'tablet'
              ? '3'
              : '4'),
    )
  await dialog.getByRole('button', { name: 'Adicionar endereço' }).click()
  await dialog.getByLabel('Endereço completo 1').fill('Rua de teste, 20')
  await dialog.getByLabel('Cidade 1', { exact: true }).fill('São Paulo')
  await dialog.getByLabel('UF 1', { exact: true }).fill('SP')
  await dialog.getByLabel('CEP 1', { exact: true }).fill('01001000')
  await dialog.getByRole('button', { name: 'Salvar cliente' }).click()
  await expect(page.getByRole('row').filter({ hasText: 'Cliente ' + suffix })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('row').filter({ hasText: 'Cliente ' + suffix })).toBeVisible()
  await page.goto('/#/produtos')
  for (const [code, productName, tracking] of [
    [bulk, name, 'false'],
    [individual, 'Unidade ' + suffix, 'true'],
  ]) {
    await page.getByRole('button', { name: 'Novo produto', exact: true }).click()
    dialog = page.getByRole('dialog')
    await dialog.getByLabel('Código', { exact: true }).fill(code)
    await dialog.getByLabel('Nome do produto').fill(productName)
    await dialog.getByLabel('Unidade de medida').fill('UN')
    await dialog.getByLabel('Controla equipamento individual').selectOption(tracking)
    await dialog.getByRole('button', { name: 'Salvar produto' }).click()
    await expect(page.getByRole('row').filter({ hasText: code })).toBeVisible()
  }
  await page.goto('/#/estoque')
  const stockRow = page.getByRole('row').filter({ hasText: bulk })
  await stockRow.getByRole('button', { name: 'Movimentar' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Quantidade', { exact: true }).fill('1,125')
  await dialog.getByLabel('Motivo', { exact: true }).fill('Entrada E2E')
  await dialog.getByRole('button', { name: 'Confirmar movimentação' }).click()
  await expect(stockRow).toContainText('1.125')
  await stockRow.getByRole('button', { name: 'Movimentar' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Origem', { exact: true }).selectOption('DISPONIVEL')
  await dialog.getByLabel('Destino', { exact: true }).selectOption('LOCADO')
  await dialog.getByLabel('Quantidade', { exact: true }).fill('2')
  await dialog.getByLabel('Motivo', { exact: true }).fill('Tentativa acima do saldo')
  await dialog.getByRole('button', { name: 'Confirmar movimentação' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Saldo insuficiente')
  await dialog.getByRole('button', { name: 'Fechar janela' }).click()
  await page.goto('/#/equipamentos')
  await page.getByRole('button', { name: 'Novo equipamento', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Buscar produto para selecionar').fill(individual)
  const option = dialog.getByRole('option').filter({ hasText: individual })
  await expect(option).toHaveCount(1)
  await dialog
    .getByLabel('Produto', { exact: true })
    .selectOption({ label: (await option.textContent()) || '' })
  await dialog.getByLabel('Código interno').fill('EQ-' + suffix)
  await dialog.getByLabel('Patrimônio').fill('PAT-' + suffix)
  await dialog.getByRole('button', { name: 'Salvar equipamento' }).click()
  const eq = page.getByRole('row').filter({ hasText: 'EQ-' + suffix })
  await expect(eq).toBeVisible()
  await eq.getByRole('button', { name: 'Alterar situação' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Nova situação').selectOption('MANUTENCAO')
  await dialog.getByLabel('Motivo da alteração').fill('Manutenção preventiva')
  await dialog.getByRole('button', { name: 'Confirmar alteração' }).click()
  await expect(eq).toContainText('Manutenção')
  await page.goto('/#/precos')
  await page.getByRole('button', { name: 'Novo preço', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Buscar produto para selecionar').fill(bulk)
  const priceOption = dialog.getByRole('option').filter({ hasText: bulk })
  await expect(priceOption).toHaveCount(1)
  await dialog
    .getByLabel('Produto', { exact: true })
    .selectOption({ label: (await priceOption.textContent()) || '' })
  await dialog.getByLabel('Início da vigência').fill('2026-10-01')
  await dialog.getByLabel('Valor (R$)').fill('0,10')
  await dialog.getByLabel('Motivo', { exact: true }).fill('Preço inicial E2E')
  await dialog.getByRole('button', { name: 'Publicar preço' }).click()
  const first = page.getByRole('row').filter({ hasText: bulk }).filter({ hasText: 'R$ 0,10' })
  await expect(first).toBeVisible()
  await first.getByRole('button', { name: 'Revisar' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Valor (R$)').fill('0,20')
  await dialog.getByLabel('Motivo', { exact: true }).fill('Revisão E2E')
  await dialog.getByRole('button', { name: 'Publicar preço' }).click()
  await expect(
    page.getByRole('row').filter({ hasText: bulk }).filter({ hasText: 'R$ 0,20' }),
  ).toBeVisible()
  await expect(first).toBeVisible()
  const lookup = page.getByRole('region', { name: 'Consultar preço vigente' })
  await lookup.getByLabel('Buscar produto para selecionar').fill(bulk)
  const lookupOption = lookup.getByRole('option').filter({ hasText: bulk })
  await expect(lookupOption).toHaveCount(1)
  await lookup
    .getByLabel('Produto', { exact: true })
    .selectOption({ label: (await lookupOption.textContent()) || '' })
  await lookup.getByLabel('Data da consulta').fill('2026-10-15')
  await lookup.getByRole('button', { name: 'Consultar preço', exact: true }).click()
  await expect(lookup.getByRole('status')).toContainText('R$ 0,20')
  for (const theme of ['light', 'dark']) {
    await page.evaluate((t) => {
      localStorage.setItem('locacontrol.theme', t)
    }, theme)
    for (const [path, title] of [
      ['clientes', 'Clientes'],
      ['produtos', 'Produtos'],
      ['equipamentos', 'Equipamentos'],
      ['estoque', 'Estoque'],
      ['precos', 'Preços'],
    ]) {
      await page.goto('/#/' + path)
      await page.reload()
      await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible()
      await expect(page.getByRole('table').first()).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(
        false,
      )
      const axe = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze()
      expect(axe.violations).toEqual([])
      if (path === 'estoque' || path === 'clientes')
        await page.screenshot({
          path: info.outputPath(path + '-' + theme + '.png'),
          fullPage: true,
        })
    }
  }
})
