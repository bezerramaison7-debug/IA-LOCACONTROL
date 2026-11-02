import { randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { expect, type Download, type Page, type TestInfo } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

export const ADMIN = { username: 'browser_admin', password: 'Fixture-browser-password!' }
/** Business date of the server (UTC-3), so seeded contracts start "today". */
export const today = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10)
export const projectIndex = (info: TestInfo) =>
  ['desktop', 'full-hd', 'tablet', 'mobile'].indexOf(info.project.name) + 1
export const startsWith = async (download: Download, magic: string) =>
  readFileSync(await download.path())
    .subarray(0, magic.length)
    .toString('latin1') === magic
export const heading = (page: Page, name: string | RegExp) =>
  page.getByRole('heading', { level: 1, name, exact: true })

export async function enter(page: Page, username: string, password: string) {
  await page.getByLabel('Usuário', { exact: true }).fill(username)
  await page.getByLabel('Senha', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Entrar', exact: true }).click()
}
export async function signInAsAdmin(page: Page) {
  await page.goto('/#/login')
  await enter(page, ADMIN.username, ADMIN.password)
  await expect(heading(page, 'Visão geral')).toBeVisible()
}
export async function signOut(page: Page) {
  if (page.viewportSize()!.width < 1024) {
    await page.getByRole('button', { name: 'Abrir menu' }).click()
    await page.getByRole('button', { name: 'Sair da conta' }).click()
  } else await page.getByRole('button', { name: 'Sair', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toBeVisible()
}

/** Real API calls with the signed-in session's own CSRF token. */
export async function api(page: Page) {
  const session = await (
    await page.request.get('/api/auth/me', { headers: { 'X-LocaControl-Request': '1' } })
  ).json()
  const headers = {
    'X-LocaControl-Request': '1',
    'X-CSRF-Token': session.csrf_token,
    Origin: new URL(page.url()).origin,
  }
  const send = (method: 'post' | 'put') => async (path: string, data: unknown) => {
    const response = await page.request[method]('/api' + path, { headers, data })
    expect(response.ok(), path + ': ' + (await response.text())).toBe(true)
    return response.json()
  }
  return { post: send('post'), put: send('put') }
}
type Api = Awaited<ReturnType<typeof api>>

export function seedCustomer(client: Api, name: string, document: string) {
  return client.post('/customers', {
    person_type: 'PF',
    legal_name: name,
    trade_name: '',
    document,
    state_registration: '',
    phone: '',
    mobile: '',
    email: '',
    contact: '',
    notes: '',
    is_active: true,
    addresses: [],
  })
}
/** A quantity-controlled product with a daily price and stock available. */
export async function seedProduct(client: Api, code: string, name: string, amount = '100.00') {
  const product = await client.post('/products', {
    code,
    name,
    description: '',
    category: '',
    unit: 'UN',
    individual_tracking: false,
    is_active: true,
  })
  await client.post('/prices', {
    product_id: product.id,
    period: 'DIARIA',
    effective_date: '2020-01-01',
    amount,
    reason: 'Preço E2E',
  })
  await client.post('/stock/movements', {
    product_id: product.id,
    quantity: '50',
    from_status: null,
    to_status: 'DISPONIVEL',
    reason: 'Entrada E2E',
    request_key: randomUUID(),
  })
  return product
}
/** Confirmed contract with everything withdrawn: stored status ATIVO. */
export async function seedActiveContract(
  client: Api,
  customerId: number,
  productId: number,
  quantity = '2',
  days = 10,
) {
  const draft = await client.post('/contracts', {
    customer_id: customerId,
    start_date: today(),
    notes: '',
    items: [
      {
        product_id: productId,
        quantity,
        period: 'DIARIA',
        period_count: days,
        unit_price: null,
      },
    ],
  })
  const confirmed = await client.post('/contracts/' + draft.id + '/confirm', {
    version: draft.version,
    reason: '',
  })
  return client.post('/contracts/' + draft.id + '/withdrawals', {
    occurred_on: today(),
    notes: '',
    request_key: randomUUID(),
    items: [
      {
        contract_item_id: confirmed.items[0].id,
        quantity: confirmed.items[0].quantity,
        equipment_ids: [],
      },
    ],
  })
}

/** Each page in light and dark: loaded, no horizontal overflow and no WCAG A/AA violation. */
export async function checkPages(
  page: Page,
  info: TestInfo,
  pages: readonly (readonly [url: string, title: string, shot?: string])[],
) {
  for (const theme of ['light', 'dark']) {
    await page.evaluate((value) => localStorage.setItem('locacontrol.theme', value), theme)
    for (const [url, title, shot] of pages) {
      await page.goto(url)
      await page.reload()
      await expect(heading(page, title)).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      await expect(page.getByRole('status', { name: 'Carregando conteúdo' })).toHaveCount(0)
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
  await page.evaluate(() => localStorage.setItem('locacontrol.theme', 'system'))
}
