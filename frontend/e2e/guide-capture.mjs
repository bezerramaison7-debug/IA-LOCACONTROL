// Captures the screenshots of docs/guia-visual from a running, disposable LocaControl.
// Not a test: it lives here only so that "@playwright/test" resolves. Usage:
//   GUIDE_BASE=http://127.0.0.1:8790 GUIDE_OUT=<folder> node frontend/e2e/guide-capture.mjs
// The target must be a fresh temporary database with only the first-run admin/admin account.
import { chromium } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const base = process.env.GUIDE_BASE
const out = process.env.GUIDE_OUT
if (!base || !out) throw new Error('Defina GUIDE_BASE e GUIDE_OUT.')
mkdirSync(out, { recursive: true })

const PASSWORD = 'Guia-visual-senha-1'
const today = new Date()
const iso = (offset = 0) => {
  const day = new Date(today.getFullYear(), today.getMonth(), today.getDate() + offset)
  const pad = (n) => String(n).padStart(2, '0')
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}

const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
})
const context = await browser.newContext({
  viewport: { width: 1366, height: 768 },
  locale: 'pt-BR',
  colorScheme: 'light',
})
const page = await context.newPage()
let csrf = ''

async function api(method, path, body) {
  return page.evaluate(
    async ({ method, path, body, csrf }) => {
      const response = await fetch('/api' + path, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-LocaControl-Request': '1',
          'X-CSRF-Token': csrf,
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      const text = await response.text()
      if (!response.ok) throw new Error(`${method} ${path} -> ${response.status} ${text}`)
      return text ? JSON.parse(text) : null
    },
    { method, path, body, csrf },
  )
}

async function login(username, password) {
  const result = await api('POST', '/auth/login', { username, password })
  csrf = result.csrf_token
  return result
}

async function firstAccess(username, provisional) {
  await login(username, provisional)
  await api('POST', '/auth/password', { current_password: provisional, new_password: PASSWORD })
  await login(username, PASSWORD)
}

async function shot(name, route) {
  if (route) {
    await page.goto(`${base}/#${route}`)
    await page.reload()
  }
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(900)
  await page.screenshot({ path: join(out, `${name}.png`) })
  console.log('captura', name)
}

const uuid = () => globalThis.crypto.randomUUID()

// ---- 1. login screen, then the first-run account ---------------------------------------
await page.goto(`${base}/#/login`)
await shot('01-login')
await firstAccess('admin', 'admin')

// ---- 2. sample data --------------------------------------------------------------------
const customer = await api('POST', '/customers', {
  person_type: 'PJ',
  legal_name: 'Construtora Horizonte Ltda',
  trade_name: 'Horizonte Obras',
  document: '11.222.333/0001-81',
  phone: '(81) 3333-0000',
  email: 'compras@horizonte.example',
  contact: 'Marina Souza',
  addresses: [{ street: 'Av. Central, 100', city: 'Recife', state: 'PE', postal_code: '50000000' }],
})
await api('POST', '/customers', {
  person_type: 'PF',
  legal_name: 'João Pereira da Silva',
  document: '529.982.247-25',
  mobile: '(81) 99999-0000',
  addresses: [
    { street: 'Rua das Flores, 45', city: 'Olinda', state: 'PE', postal_code: '53000000' },
  ],
})
const scaffold = await api('POST', '/products', {
  code: 'AND-10',
  name: 'Andaime tubular 1,0 m',
  category: 'Andaimes',
  unit: 'UN',
})
const mixer = await api('POST', '/products', {
  code: 'BET-400',
  name: 'Betoneira 400 L',
  category: 'Concreto',
  unit: 'UN',
  individual_tracking: true,
})
const prop = await api('POST', '/products', {
  code: 'ESC-30',
  name: 'Escora metálica 3,0 m',
  category: 'Escoramento',
  unit: 'UN',
})
const prices = [
  [scaffold.id, 'DIARIA', '12.00'],
  [scaffold.id, 'SEMANAL', '70.00'],
  [scaffold.id, 'MENSAL', '220.00'],
  [mixer.id, 'DIARIA', '90.00'],
  [mixer.id, 'SEMANAL', '390.00'],
  [mixer.id, 'QUINZENAL', '650.00'],
  [mixer.id, 'MENSAL', '980.00'],
  [prop.id, 'SEMANAL', '18.00'],
  [prop.id, 'MENSAL', '55.00'],
]
for (const [product_id, period, amount] of prices) {
  await api('POST', '/prices', {
    product_id,
    period,
    effective_date: '2026-01-01',
    amount,
    reason: 'Tabela inicial',
  })
}
for (const [product_id, quantity] of [
  [scaffold.id, '60.000'],
  [prop.id, '120.000'],
]) {
  await api('POST', '/stock/movements', {
    product_id,
    quantity,
    from_status: null,
    to_status: 'DISPONIVEL',
    reason: 'Estoque inicial',
    request_key: uuid(),
  })
}
const units = []
for (const code of ['BET-01', 'BET-02', 'BET-03']) {
  units.push(await api('POST', '/equipment', { product_id: mixer.id, code, brand: 'CSM' }))
}

const line = (product_id, quantity, period, period_count) => ({
  product_id,
  quantity,
  period,
  period_count,
  unit_price: null,
})
const quote = await api('POST', '/quotes', {
  customer_id: customer.id,
  start_date: iso(),
  valid_until: iso(10),
  notes: 'Entrega na obra da Av. Central.',
  items: [line(scaffold.id, '20.000', 'SEMANAL', 2), line(mixer.id, '2.000', 'SEMANAL', 2)],
})
const approved = await api('POST', `/quotes/${quote.id}/approve`, {
  version: quote.version,
  reason: '',
})
const open = await api('POST', '/quotes', {
  customer_id: customer.id,
  start_date: iso(3),
  valid_until: iso(15),
  notes: '',
  items: [line(prop.id, '40.000', 'MENSAL', 1), line(scaffold.id, '10.000', 'MENSAL', 1)],
})
const sent = await api('POST', `/quotes/${open.id}/send`, { version: open.version, reason: '' })

await api('PUT', '/contracts/numbering', { next_number: 9193 })
const draft = await api('POST', `/contracts/from-quote/${quote.id}`, {
  version: approved.version,
  reason: '',
})
const confirmed = await api('POST', `/contracts/${draft.id}/confirm`, {
  version: draft.version,
  reason: '',
})
await api('POST', `/contracts/${draft.id}/documents`, { reason: '' })
const item = (contract, code) => contract.items.find((entry) => entry.product_code === code)
const active = await api('POST', `/contracts/${draft.id}/withdrawals`, {
  occurred_on: iso(),
  notes: '',
  request_key: uuid(),
  items: [
    { contract_item_id: item(confirmed, 'AND-10').id, quantity: '20.000', equipment_ids: [] },
    {
      contract_item_id: item(confirmed, 'BET-400').id,
      quantity: '2.000',
      equipment_ids: [units[0].id, units[1].id],
    },
  ],
})
const renewal = await api('POST', `/contracts/${draft.id}/renew`, {
  version: active.version,
  start_date: active.due_date,
  price_option: 'ANTERIORES',
  notes: '',
  items: [
    {
      source_item_id: item(active, 'AND-10').id,
      quantity: '20.000',
      period: 'SEMANAL',
      period_count: 1,
      unit_price: null,
      equipment_ids: [],
    },
    {
      source_item_id: item(active, 'BET-400').id,
      quantity: '2.000',
      period: 'SEMANAL',
      period_count: 1,
      unit_price: null,
      equipment_ids: [],
    },
  ],
})
await api('POST', `/contracts/${renewal.id}/documents`, { reason: '' })
await api('POST', `/contracts/${renewal.id}/returns`, {
  occurred_on: iso(),
  notes: '',
  request_key: uuid(),
  items: [
    {
      contract_item_id: item(renewal, 'AND-10').id,
      quantity: '8.000',
      equipment_id: null,
      condition: 'BOM',
      notes: '',
    },
    {
      contract_item_id: item(renewal, 'BET-400').id,
      quantity: '1.000',
      equipment_id: units[0].id,
      condition: 'AVARIADO',
      notes: 'Motor falhando',
    },
  ],
})
// A second contract, confirmed and waiting for pick-up, for the withdrawal screen.
const waitingDraft = await api('POST', '/contracts', {
  customer_id: customer.id,
  start_date: iso(),
  notes: '',
  items: [line(prop.id, '30.000', 'SEMANAL', 2), line(mixer.id, '1.000', 'SEMANAL', 2)],
})
const waiting = await api('POST', `/contracts/${waitingDraft.id}/confirm`, {
  version: waitingDraft.version,
  reason: '',
})
const fiscal = await api('POST', '/fiscal/documents', {
  customer_id: customer.id,
  contract_id: draft.id,
  period_start: iso(),
  period_end: iso(14),
  amount: '2180.00',
  description: 'Locação de equipamentos conforme contrato 9193',
  request_key: uuid(),
})
await api('POST', `/fiscal/documents/${fiscal.id}/emit`, { version: fiscal.version, reason: '' })
await api('POST', '/backups')
await api('PUT', '/backups/config', { enabled: true, time: '22:00', keep: 14, directory: '' })
const portalUser = await api('POST', '/users', {
  username: 'horizonte',
  name: 'Marina Souza',
  password: 'Provisoria-guia-1',
  role_codes: ['CLIENTE'],
})
await api('PUT', `/users/${portalUser.id}/customer`, { customer_id: customer.id })
await api('POST', '/users', {
  username: 'carla.vendas',
  name: 'Carla Mendes',
  password: 'Provisoria-guia-2',
  role_codes: ['COMERCIAL'],
})
await api('POST', '/users', {
  username: 'paulo.patio',
  name: 'Paulo Lima',
  password: 'Provisoria-guia-3',
  role_codes: ['OPERACAO'],
})

// ---- 3. internal screens ---------------------------------------------------------------
await shot('02-dashboard', '/')
await shot('03-clientes', '/clientes')
await shot('04-produtos', '/produtos')
await shot('05-estoque', '/estoque')
await shot('06-precos', '/precos')
await shot('07-orcamentos', '/orcamentos')
await shot('08-orcamento-novo', '/orcamentos?novo=1')
await shot('09-orcamento-detalhe', `/orcamentos?id=${sent.id}`)
await shot('10-contratos', '/contratos')
await shot('11-contrato-detalhe', `/contratos?id=${renewal.id}`)
await shot('12-retirada', `/contratos?id=${waiting.id}&acao=retirada`)
await shot('13-renovacao', `/contratos?id=${renewal.id}&acao=renovar`)
await shot('14-devolucao', `/contratos?id=${renewal.id}&acao=devolucao`)

// ---- 4. the customer asks for a renewal through the portal -----------------------------
await api('POST', '/auth/logout')
await firstAccess('horizonte', 'Provisoria-guia-1')
await api('POST', '/portal/renewal-requests', {
  contract_id: renewal.id,
  period: 'SEMANAL',
  period_count: 1,
  notes: 'A obra atrasou uma semana.',
})
await shot('22-portal', '/portal')
await shot('23-portal-contrato', `/portal/contratos?id=${renewal.id}`)

// ---- 5. back to the administrator for the management screens ---------------------------
await api('POST', '/auth/logout')
await login('admin', PASSWORD)
await shot('15-renovacoes', '/renovacoes')
await shot('16-manutencao', '/manutencao')
await shot('17-relatorios', '/relatorios')
await shot('18-fiscal', '/faturamento')
await shot('19-backups', '/backups')
await shot('20-usuarios', '/usuarios')
await shot('21-configuracoes', '/configuracoes')

await browser.close()
console.log('capturas concluidas')
