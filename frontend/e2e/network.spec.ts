import { test, expect } from '@playwright/test'
import { heading } from './helpers'

// Network edition (ADR-025): the main computer (127.0.0.1) shows a pairing code; a station at
// this computer's network address types it once, works without a password and is revoked.
test('network: pairing a station, its limits and the revocation', async ({ page, browser }) => {
  test.setTimeout(120_000)
  const context = await browser.newContext({ baseURL: process.env.E2E_STATION_BASE_URL })
  const station = await context.newPage()
  await station.goto('/#/')
  await expect(heading(station, 'Conectar este computador à loja')).toBeVisible()
  // Página servida por HTTPS: nenhum aviso de conexão insegura.
  expect(station.url()).toMatch(/^https:/)
  await expect(station.getByText('Esta conexão não é segura.')).toHaveCount(0)
  await expect(station.getByLabel('Senha')).toHaveCount(0)

  await page.goto('/#/estacoes')
  await expect(heading(page, 'Estações da rede')).toBeVisible()
  await page.getByRole('button', { name: 'Gerar código de pareamento' }).click()
  const code = ((await page.locator('.pairing-code').textContent()) || '').trim()
  // 26 caracteres (130 bits), em grupos de 4 (P1-E).
  expect(code).toMatch(/^([A-Z0-9]{4}-){6}[A-Z0-9]{2}$/)

  await station.getByLabel('Nome desta estação').fill('Balcão E2E')
  await station.getByLabel('Código de pareamento').fill('ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZ')
  await station.getByRole('button', { name: 'Conectar à loja' }).click()
  await expect(station.getByText(/Código incorreto/)).toBeVisible()
  await station.getByLabel('Código de pareamento').fill(code)
  await station.getByRole('button', { name: 'Conectar à loja' }).click()
  await expect(heading(station, 'Visão geral')).toBeVisible()
  await expect(station.getByText('Estação Balcão E2E · rede da loja').first()).toBeVisible()
  await expect(station.getByRole('link', { name: 'Estações da rede' })).toHaveCount(0)

  // The station works on the same data; sensitive functions stay on the main computer.
  await station.goto('/#/backups')
  await expect(station.getByText(/só no computador principal/)).toBeVisible()
  await station.getByRole('button', { name: 'Fazer backup agora' }).click()
  await expect(station.getByText(/Backup criado: locacontrol_/)).toBeVisible()
  await expect(station.getByRole('button', { name: /^Restaurar / })).toHaveCount(0)

  await page.reload()
  const list = page.getByRole('region', { name: 'Lista de estações' })
  await expect(list.getByText('Balcão E2E')).toBeVisible()
  await page.getByRole('button', { name: 'Revogar Balcão E2E' }).click()
  await page.getByRole('button', { name: 'Revogar estação' }).click()
  await expect(page.getByText('Estação Balcão E2E revogada.')).toBeVisible()
  await station.reload()
  await expect(heading(station, 'Conectar este computador à loja')).toBeVisible()
  await context.close()
})
