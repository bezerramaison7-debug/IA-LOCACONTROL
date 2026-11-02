import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

test('real identity lifecycle and accessible security screens', async ({ page }, testInfo) => {
  const username = `worker_${testInfo.project.name.replace('-', '_')}`
  const password = 'Fixture-worker-password!'
  const replacement = 'Fixture-replacement-password!'
  const enter = async (name: string, secret: string) => {
    await page.getByLabel('Usuário', { exact: true }).fill(name)
    await page.getByLabel('Senha', { exact: true }).fill(secret)
    await page.getByRole('button', { name: 'Entrar', exact: true }).click()
  }
  const logout = async () => {
    if (page.viewportSize()!.width < 1024) {
      await page.getByRole('button', { name: 'Abrir menu' }).click()
      await page.getByRole('button', { name: 'Sair da conta' }).click()
    } else await page.getByRole('button', { name: 'Sair', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toBeVisible()
  }
  await page.goto('/#/usuarios')
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toBeVisible()
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme })
    expect(
      (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
        .violations,
    ).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`login-${theme}.png`), fullPage: true })
  }
  await enter('browser_admin', 'Fixture-browser-password!')
  await expect(page.getByRole('heading', { name: 'Usuários', exact: true })).toBeVisible()
  for (const theme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: theme })
    for (const [path, title] of [
      ['usuarios', 'Usuários'],
      ['perfis', 'Perfis e permissões'],
      ['perfil', 'Meu perfil'],
      ['auditoria', 'Auditoria'],
    ]) {
      await page.goto(`/#/${path}`)
      await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
      await expect(page.getByRole('status', { name: 'Carregando conteúdo' })).toHaveCount(0)
      expect(
        (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze())
          .violations,
      ).toEqual([])
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true)
      if (path === 'perfis')
        await page.screenshot({ path: testInfo.outputPath(`roles-${theme}.png`), fullPage: true })
    }
  }
  await page.goto('/#/usuarios')
  await page.getByRole('button', { name: 'Novo usuário' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Usuário', { exact: true }).fill(username)
  await dialog.getByLabel('Nome completo').fill(`Pessoa ${testInfo.project.name}`)
  await dialog.getByLabel('Perfil', { exact: true }).selectOption('CLIENTE')
  await dialog.getByLabel('Senha temporária', { exact: true }).fill(password)
  await dialog.getByRole('button', { name: 'Salvar usuário' }).click()
  await expect(dialog).toHaveCount(0)
  await page.getByLabel('Buscar usuários').fill(username)
  await expect(page.getByRole('table')).toContainText(username)
  await page.getByRole('button', { name: `Editar ${username}`, exact: true }).click()
  await dialog.getByLabel('Nome completo').fill(`Pessoa editada ${testInfo.project.name}`)
  await dialog.getByRole('button', { name: 'Salvar usuário' }).click()
  await expect(dialog).toHaveCount(0)
  await logout()
  await enter(username, password)
  await expect(page.getByRole('heading', { name: 'Meu perfil' })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('substitua a senha temporária')
  await page.getByLabel('Senha atual', { exact: true }).fill(password)
  await page.getByLabel('Nova senha', { exact: true }).fill(replacement)
  await page.getByLabel('Confirmar nova senha').fill(replacement)
  await page.getByRole('button', { name: 'Alterar senha', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toBeVisible()
  await enter(username, replacement)
  // A customer account lands on the portal; without a customer link it only explains why.
  await expect(page.getByRole('heading', { level: 1, name: 'Portal do cliente' })).toBeVisible()
  await expect(page.getByText('Portal ainda não liberado para esta conta')).toBeVisible()
  expect((await page.request.get('/api/users')).status()).toBe(403)
  await page.goto('/#/usuarios')
  await expect(page.getByRole('alert')).toContainText('não tem permissão')
  await page.getByRole('link', { name: 'Ir para meu perfil' }).click()
  await logout()
  await enter('browser_admin', 'Fixture-browser-password!')
  await page.goto('/#/usuarios')
  await page.getByLabel('Buscar usuários').fill(username)
  await page.getByRole('button', { name: `Desativar ${username}`, exact: true }).click()
  await page
    .getByRole('alertdialog')
    .getByRole('button', { name: 'Desativar', exact: true })
    .click()
  await expect(page.getByRole('table')).toContainText('Desativado')
  await page.goto('/#/auditoria')
  await expect(page.getByRole('table')).toContainText('user.updated')
  await expect(page.getByRole('table')).toContainText('password.changed')
  await logout()
  expect((await page.request.get('/api/auth/me')).status()).toBe(401)
  await enter(username, replacement)
  await expect(page.getByRole('alert')).toContainText('Usuário ou senha inválidos.')
})
