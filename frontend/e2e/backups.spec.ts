import { test, expect } from '@playwright/test'
import { ADMIN, checkPages, enter, heading, signInAsAdmin, startsWith } from './helpers'

// scripts/e2e-auth.py points the database, documents, imports, fiscal files and backup sets to a
// temporary folder, so the restore below replaces only temporary data.
test('backups: configure, run now, verify, download and assisted restore', async ({
  page,
}, info) => {
  test.setTimeout(240_000)
  await signInAsAdmin(page)
  await page.goto('/#/backups')
  await expect(heading(page, 'Backups')).toBeVisible()

  // Configuration is validated and persisted.
  await page.getByLabel('Pasta dos backups').fill('pasta-relativa')
  await page.getByRole('button', { name: 'Salvar configuração' }).click()
  await expect(page.getByText(/Informe o caminho completo da pasta/)).toBeVisible()
  await page.getByLabel('Pasta dos backups').fill('')
  // Protection status and the warning that the computer must be on.
  await expect(page.getByText(/Última cópia concluída:/)).toBeVisible()
  await expect(page.getByText(/só acontece enquanto este computador/).first()).toBeVisible()
  await page.getByLabel(/Fazer backup automático/).check()
  await page.getByLabel('Frequência').selectOption('daily')
  await page.getByLabel('Horário do backup diário').fill('23:30')
  await page.getByLabel('Dias com cópia guardada').fill('9')
  await page.getByRole('button', { name: 'Salvar configuração' }).click()
  await expect(page.getByText('Configuração de backup salva.')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Horário do backup diário')).toHaveValue('23:30')
  await expect(page.getByLabel('Dias com cópia guardada')).toHaveValue('9')
  await expect(page.getByLabel(/Fazer backup automático/)).toBeChecked()

  // Backup now: the newest set is the first row.
  await page.getByRole('button', { name: 'Fazer backup agora' }).click()
  await expect(page.getByText(/Backup criado: locacontrol_/)).toBeVisible()
  const list = page.getByRole('region', { name: 'Lista de backups' })
  const name = (
    (await list.getByRole('row').nth(1).locator('.code-cell').textContent()) || ''
  ).trim()
  expect(name).toMatch(/^locacontrol_\d{4}-\d{2}-\d{2}_\d{6}\.zip$/)
  await page.getByRole('button', { name: 'Verificar ' + name }).click()
  await expect(page.getByRole('status', { name: 'Verificação de ' + name })).toContainText(
    'Backup íntegro: pode ser restaurado.',
  )
  const pending = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Baixar ' + name }).click()
  const download = await pending
  expect(download.suggestedFilename()).toBe(name)
  expect(await startsWith(download, 'PK')).toBe(true)
  await expect(
    page.getByRole('region', { name: 'Execuções recentes de backup' }).getByText(name),
  ).toBeVisible()

  // Recovery from another disk: the same set is recognised instead of copied twice.
  const copy = info.outputPath(name)
  await download.saveAs(copy)
  await page.getByLabel('Arquivo do backup (.zip)').setInputFiles(copy)
  await page.getByRole('button', { name: 'Importar backup' }).click()
  await expect(page.getByText(/Este backup já está na pasta de backups/)).toBeVisible()

  await checkPages(page, info, [['/#/backups', 'Backups', 'backups']])

  // Restore: verification shown, exact phrase and password required.
  await page.getByRole('button', { name: 'Restaurar ' + name }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Backup íntegro: pode ser restaurado.')).toBeVisible()
  await expect(dialog.getByRole('note')).toContainText('terão de entrar novamente')
  await expect(dialog.getByRole('note')).toContainText('cópia de segurança do estado atual')
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  const confirm = dialog.getByRole('button', { name: 'Restaurar este backup' })
  await expect(confirm).toBeDisabled()
  await dialog.getByLabel(/Digite exatamente/).fill('restaurar ' + name)
  await dialog.getByLabel('Sua senha').fill('senha-errada-do-teste')
  await expect(confirm).toBeDisabled()
  await dialog.getByLabel(/Digite exatamente/).fill('RESTAURAR ' + name)
  await confirm.click()
  await expect(dialog.getByRole('alert')).toContainText('Senha incorreta')
  await dialog.getByLabel('Sua senha').fill(ADMIN.password)
  await confirm.click()

  // After the restore everyone signs in again; the previous state was kept as a safety copy.
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toBeVisible({
    timeout: 60_000,
  })
  await enter(page, ADMIN.username, ADMIN.password)
  await page.goto('/#/backups')
  await expect(heading(page, 'Backups')).toBeVisible()
  await expect(list.getByRole('row').filter({ hasText: '_pre-restore.zip' }).first()).toContainText(
    'Anterior a uma restauração',
  )
  await expect(page.getByLabel('Dias com cópia guardada')).toHaveValue('9')
})
