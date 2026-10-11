import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { adminSession } from '../src/test/auth-fixture'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/me', (route) => route.fulfill({ json: adminSession }))
  for (const module of ['customers', 'products', 'equipment'])
    await page.route('**/api/' + module + '**', (route) =>
      route.fulfill({ json: { items: [], total: 0 } }),
    )
  // Somente o diagnóstico é simulado neste teste de UI. Smoke testa HTTP/banco reais.
  await page.route('**/health', (route) =>
    route.fulfill({ json: { status: 'ok', database: 'ok', schema: 'ok', version: '0.1.0' } }),
  )
})

for (const theme of ['light', 'dark'] as const) {
  test(`seven pages, accessibility and responsive layout — ${theme}`, async ({
    page,
  }, testInfo) => {
    const errors: string[] = []
    page.on('pageerror', (error) => errors.push(error.message))
    await page.emulateMedia({ colorScheme: theme })
    for (const [path, title] of [
      ['/', 'Visão geral'],
      ['/clientes', 'Clientes'],
      ['/produtos', 'Produtos'],
      ['/equipamentos', 'Equipamentos'],
      ['/orcamentos', 'Orçamentos'],
      ['/contratos', 'Contratos'],
      ['/configuracoes', 'Configurações'],
    ]) {
      await page.goto(`/#${path}`)
      await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      if (!['/clientes', '/produtos', '/equipamentos'].includes(path))
        await expect(page.getByText('Modo demonstração')).toBeVisible()
      else await expect(page.getByText('Modo demonstração')).toHaveCount(0)
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      )
      expect(overflow, `${path}: document should not overflow horizontally`).toBe(false)
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        .analyze()
      expect(
        results.violations,
        JSON.stringify(
          results.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })),
        ),
      ).toEqual([])
      if (path === '/' || path === '/configuracoes')
        await page.screenshot({
          path: testInfo.outputPath(`${path === '/' ? 'dashboard' : 'settings'}-${theme}.png`),
          fullPage: true,
        })
    }
    expect(errors).toEqual([])
  })
}

test('themes persist across reload and react to the operating system', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.goto('/#/configuracoes')
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('radio', { name: /Claro/ }).check()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await page.emulateMedia({ colorScheme: 'light' })
  await page.getByRole('radio', { name: /Sistema/ }).check()
  await page.emulateMedia({ colorScheme: 'dark' })
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.getByRole('button', { name: 'Restaurar padrão' }).click()
  await expect(page.getByRole('alertdialog').getByRole('button', { name: 'Voltar' })).toBeFocused()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Voltar' }).click()
})

test('keyboard, dialogs, search, table filters and page navigation', async ({ page }) => {
  const writes: string[] = []
  page.on('request', (request) => {
    if (!['GET', 'HEAD'].includes(request.method())) writes.push(request.url())
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Visão geral' })).toBeVisible()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('link', { name: 'Pular para o conteúdo' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.locator('main')).toBeFocused()
  await page.getByRole('button', { name: 'Novo orçamento' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('button', { name: 'Validar prévia' }).click()
  await expect(dialog.getByLabel('Nome de exemplo')).toHaveAttribute('aria-invalid', 'true')
  await dialog.getByLabel('Nome de exemplo').fill('Prévia fictícia')
  for (let i = 0; i < 7; i++) {
    await page.keyboard.press('Tab')
    expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  }
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Novo orçamento' })).toBeFocused()
  await page.getByRole('button', { name: 'Buscar páginas' }).click()
  await page.getByRole('textbox', { name: 'Nome da página' }).fill('Orçamentos')
  await page.getByRole('dialog').getByRole('link', { name: 'Orçamentos' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Orçamentos' })).toBeVisible()
  await page.getByRole('textbox', { name: 'Buscar em orçamentos' }).fill('Ninguém')
  await expect(page.getByText('Nenhum resultado encontrado')).toBeVisible()
  await page.getByRole('button', { name: 'Limpar filtros' }).first().click()
  await page.getByRole('combobox', { name: 'Estado da prévia' }).selectOption('error')
  await expect(page.getByRole('alert')).toContainText('erro simulado')
  await page.getByRole('button', { name: 'Tentar novamente' }).click()
  await expect(page.getByRole('table')).toBeVisible()
  if (page.viewportSize()!.width < 1024) {
    await page.getByRole('button', { name: 'Abrir menu' }).click()
    await page.getByRole('dialog').getByRole('link', { name: 'Produtos', exact: true }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
  } else {
    await page.getByRole('button', { name: 'Recolher menu' }).click()
    await page.reload()
    await expect(page.getByRole('button', { name: 'Expandir menu' })).toBeVisible()
    await page
      .getByRole('navigation', { name: 'Navegação principal' })
      .getByRole('link', { name: 'Produtos', exact: true })
      .click()
  }
  await expect(page.getByRole('heading', { level: 1, name: 'Produtos' })).toBeVisible()
  await page.goto('/#/endereco-inexistente')
  await expect(page.getByRole('heading', { level: 1, name: 'Página não encontrada' })).toBeVisible()
  await page.getByRole('link', { name: 'Voltar ao dashboard' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Visão geral' })).toBeVisible()
  expect(writes).toEqual([])
})
