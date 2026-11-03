import { test, expect } from '@playwright/test'
import { heading } from './helpers'

// Automatic draft (ADR-024): kept on the server, offered again after a reload, and the form
// survives the loss of the session (the local session is renewed without leaving the screen).
test('local edition: a quote draft survives a reload and an ended session', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/#/orcamentos?novo=1')
  const notes = page.getByLabel('Observações')
  await notes.fill('Rascunho do teste E2E')
  await expect(page.getByText(/Rascunho salvo automaticamente às/)).toBeVisible()
  await page.reload()
  await page.goto('/#/orcamentos?novo=1')
  const offer = page.getByRole('region', { name: 'Rascunho encontrado' })
  await expect(offer).toContainText('Nada dele foi gravado nos registros')
  await offer.getByRole('button', { name: 'Recuperar rascunho' }).click()
  await expect(notes).toHaveValue('Rascunho do teste E2E')

  // The session cookie is gone: the next save renews the session and the form stays.
  await page.context().clearCookies()
  await notes.fill('Rascunho do teste E2E, depois da sessão')
  await expect(page.getByText(/Rascunho salvo automaticamente às/)).toBeVisible({
    timeout: 30_000,
  })
  await expect(notes).toHaveValue('Rascunho do teste E2E, depois da sessão')
  const saved = await page.request.get('/api/drafts/quote/new', {
    headers: { 'X-LocaControl-Request': '1' },
  })
  expect((await saved.json()).draft.payload.values.notes).toBe(
    'Rascunho do teste E2E, depois da sessão',
  )
  await page.reload()
  await page.goto('/#/orcamentos?novo=1')
  await page.getByRole('button', { name: 'Descartar rascunho' }).click()
  await expect(notes).toHaveValue('')
})

// Server started by scripts/e2e-auth.py with LOCACONTROL_LOCAL_MODE=true and a temporary
// database without any user: the app must open by itself on this computer.
test('local edition: no login, no account areas, restore with the phrase only', async ({
  page,
}) => {
  test.setTimeout(180_000)
  await page.goto('/#/login')
  await expect(heading(page, 'Visão geral')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toHaveCount(0)
  for (const label of ['Usuários', 'Perfis e permissões', 'Meu perfil'])
    await expect(page.getByRole('link', { name: label, exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Sair', exact: true })).toHaveCount(0)

  // Disabled areas: blocked in the interface and absent from the API.
  await page.goto('/#/usuarios')
  await expect(page.getByText('Você não tem permissão para acessar esta área.')).toBeVisible()
  for (const path of ['/api/users', '/api/roles', '/api/portal/dashboard'])
    expect((await page.request.get(path)).status(), path).toBe(404)

  // The audit names the origin of the actions, never a person.
  await page.goto('/#/auditoria')
  await expect(page.getByText(/operador local · instalação [0-9a-f]{8}/).first()).toBeVisible()

  // Restore: verification and the exact phrase; there is no password to type.
  await page.goto('/#/backups')
  await expect(heading(page, 'Backups')).toBeVisible()
  await page.getByRole('button', { name: 'Fazer backup agora' }).click()
  await expect(page.getByText(/Backup criado: locacontrol_/)).toBeVisible()
  const list = page.getByRole('region', { name: 'Lista de backups' })
  const name = (
    (await list.getByRole('row').nth(1).locator('.code-cell').textContent()) || ''
  ).trim()
  await page.getByRole('button', { name: 'Restaurar ' + name }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Backup íntegro: pode ser restaurado.')).toBeVisible()
  await expect(dialog.getByLabel('Sua senha')).toHaveCount(0)
  const confirm = dialog.getByRole('button', { name: 'Restaurar este backup' })
  await dialog.getByLabel(/Digite exatamente/).fill('RESTAURAR')
  await expect(confirm).toBeDisabled()
  await dialog.getByLabel(/Digite exatamente/).fill('RESTAURAR ' + name)
  await confirm.click()
  await expect(page.getByText(/Backup restaurado\./)).toBeVisible({ timeout: 60_000 })
  // The app enters again by itself: no login screen after the sessions were replaced.
  await expect(heading(page, 'Backups')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toHaveCount(0)
  await expect(list.getByRole('row').filter({ hasText: '_pre-restore.zip' }).first()).toBeVisible()
})
