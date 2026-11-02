import { test, expect } from '@playwright/test'
import {
  api,
  checkPages,
  enter,
  heading,
  projectIndex,
  seedActiveContract,
  seedCustomer,
  seedProduct,
  signInAsAdmin,
  signOut,
  startsWith,
} from './helpers'

test('customer portal: own data only, renewal request and internal decision', async ({
  page,
}, info) => {
  test.setTimeout(300_000)
  const suffix = info.project.name.toUpperCase()
  const index = projectIndex(info)
  const username = 'portal_' + info.project.name.replace('-', '_')
  const temporary = 'Fixture-portal-temporary!'
  const password = 'Fixture-portal-password!'
  const ownName = 'Cliente portal ' + suffix
  const otherName = 'Empresa vizinha ' + suffix

  await signInAsAdmin(page)
  const client = await api(page)
  const own = await seedCustomer(client, ownName, '5555555555' + index)
  const other = await seedCustomer(client, otherName, '6666666666' + index)
  const product = await seedProduct(client, 'PTL-' + suffix, 'Escora portal ' + suffix)
  const contract = await seedActiveContract(client, own.id, product.id)
  const foreign = await seedActiveContract(client, other.id, product.id)
  await client.post('/contracts/' + contract.id + '/documents', { reason: '' })
  await client.post('/users', {
    username,
    name: 'Pessoa portal ' + suffix,
    password: temporary,
    role_codes: ['CLIENTE'],
  })

  // The link between the account and the customer is made on the Usuários page.
  await page.goto('/#/usuarios')
  await page.getByLabel('Buscar usuários').fill(username)
  await page.getByRole('button', { name: 'Vincular cliente a ' + username }).click()
  const linking = page.getByRole('dialog')
  await expect(linking).toContainText('nenhum — a conta ainda não acessa o portal')
  await linking.getByLabel('Buscar cliente para vincular').fill(ownName)
  const option = linking.getByRole('option').filter({ hasText: ownName })
  await expect(option).toHaveCount(1)
  await linking
    .getByLabel('Cliente do portal')
    .selectOption({ label: (await option.textContent()) || '' })
  await linking.getByRole('button', { name: 'Salvar vínculo' }).click()
  await expect(page.getByText('Cliente vinculado à conta.')).toBeVisible()
  await signOut(page)

  // First access: the temporary password must be replaced.
  await enter(page, username, temporary)
  await expect(page.getByRole('heading', { name: 'Meu perfil' })).toBeVisible()
  await page.getByLabel('Senha atual', { exact: true }).fill(temporary)
  await page.getByLabel('Nova senha', { exact: true }).fill(password)
  await page.getByLabel('Confirmar nova senha').fill(password)
  await page.getByRole('button', { name: 'Alterar senha', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Entrar na sua conta' })).toBeVisible()
  await enter(page, username, password)
  await expect(heading(page, 'Portal do cliente')).toBeVisible()
  await expect(page.getByText(/funciona na rede local da locadora/)).toBeVisible()
  await expect(page.getByText(/acesso pela internet é uma etapa futura/)).toBeVisible()

  // Only the portal menu, no internal item.
  const narrow = page.viewportSize()!.width < 1024
  if (narrow) await page.getByRole('button', { name: 'Abrir menu' }).click()
  const menu = narrow
    ? page.getByRole('dialog').getByRole('navigation', { name: 'Navegação principal' })
    : page.getByRole('navigation', { name: 'Navegação principal' })
  await expect(menu.getByRole('link')).toHaveText([
    'Início',
    'Meus contratos',
    'Meus equipamentos',
    'Orçamentos',
    'Renovações',
    'Documentos',
    'Meu cadastro',
    'Meu perfil',
  ])
  await menu.getByRole('link', { name: 'Meus contratos' }).click()

  // Own contract only; another customer's contract answers "not found".
  await expect(heading(page, 'Meus contratos')).toBeVisible()
  const list = page.getByRole('region', { name: 'Meus contratos', exact: true })
  await expect(list.getByRole('row')).toHaveCount(2)
  await expect(list.getByRole('row').nth(1)).toContainText(contract.number)
  expect((await page.request.get('/api/portal/contracts/' + foreign.id)).status()).toBe(404)
  expect((await page.request.get('/api/contracts/' + foreign.id)).status()).toBe(403)
  await page.goto('/#/portal/contratos?id=' + foreign.id)
  await expect(page.getByText('Registro não encontrado')).toBeVisible()
  await expect(page.getByText(/Contrato não encontrado\./)).toBeVisible()
  await expect(page.getByText(otherName)).toHaveCount(0)
  await page.goto('/#/contratos?id=' + foreign.id)
  await expect(page.getByRole('alert')).toContainText('não tem permissão')

  // Renewal request: clearly a request, pending the rental company's decision.
  await page.goto('/#/portal/contratos?id=' + contract.id)
  await expect(page.getByRole('heading', { name: 'Contrato ' + contract.number })).toBeVisible()
  await page.getByRole('button', { name: 'Solicitar renovação' }).click()
  const asking = page.getByRole('dialog')
  await expect(asking.getByRole('note')).toContainText('Este é um pedido, não uma renovação')
  await asking.getByLabel('Período desejado').selectOption('SEMANAL')
  await asking.getByLabel('Quantidade de períodos').fill('2')
  await asking.getByLabel('Observações para a locadora').fill('Obra prorrogada no E2E')
  await asking.getByRole('button', { name: 'Enviar solicitação' }).click()
  await expect(asking).toHaveCount(0)
  await page.goto('/#/portal/renovacoes')
  const mine = page.getByRole('region', { name: 'Minhas solicitações de renovação' })
  await expect(mine.getByRole('row').nth(1)).toContainText('Em análise')
  await expect(mine.getByRole('row').nth(1)).toContainText('2 × Semanal')
  await expect(page.getByRole('button', { name: 'Solicitar renovação' })).toHaveCount(0)

  // Documents and equipment of the customer.
  await page.goto('/#/portal/documentos')
  const pending = page.waitForEvent('download')
  await page
    .getByRole('button', { name: 'Baixar documento do contrato ' + contract.number + ', versão 1' })
    .click()
  const download = await pending
  expect(download.suggestedFilename()).toBe('Contrato-' + contract.number + '-v1.pdf')
  expect(await startsWith(download, '%PDF-')).toBe(true)
  await page.goto('/#/portal/equipamentos')
  await expect(page.getByRole('row').filter({ hasText: 'Escora portal ' + suffix })).toContainText(
    '2 UN',
  )

  await checkPages(page, info, [
    ['/#/portal', 'Portal do cliente', 'portal'],
    ['/#/portal/contratos', 'Meus contratos'],
    ['/#/portal/contratos?id=' + contract.id, 'Meus contratos', 'portal-contrato'],
    ['/#/portal/equipamentos', 'Meus equipamentos'],
    ['/#/portal/orcamentos', 'Orçamentos'],
    ['/#/portal/renovacoes', 'Renovações'],
    ['/#/portal/documentos', 'Documentos'],
    ['/#/portal/cadastro', 'Meu cadastro'],
  ])
  await signOut(page)

  // Internal side: approving records the decision and offers the existing renewal flow.
  await enter(page, 'browser_admin', 'Fixture-browser-password!')
  await expect(heading(page, 'Visão geral')).toBeVisible()
  await page.goto('/#/renovacoes')
  const requests = page.getByRole('region', { name: 'Solicitações de renovação', exact: true })
  await expect(requests.getByRole('row').filter({ hasText: ownName })).toContainText('Em análise')
  await page
    .getByRole('button', { name: 'Aprovar solicitação do contrato ' + contract.number })
    .click()
  const deciding = page.getByRole('dialog')
  await expect(deciding.getByRole('note')).toContainText('Aprovar NÃO cria a renovação')
  await deciding.getByRole('button', { name: 'Confirmar aprovação' }).click()
  await expect(deciding).toHaveCount(0)
  await expect(page.getByRole('status').filter({ hasText: 'aprovada' })).toContainText(
    'A renovação ainda não foi criada.',
  )
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  await page.getByRole('link', { name: 'Renovar contrato ' + contract.number }).click()
  await expect(heading(page, 'Renovar contrato · contrato ' + contract.number)).toBeVisible()
  // Nothing was renewed by the approval itself.
  await page.goto('/#/renovacoes')
  await expect(requests.getByRole('row').filter({ hasText: ownName })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Renovações registradas' })).toBeVisible()
  await expect(page.getByRole('status', { name: 'Carregando conteúdo' })).toHaveCount(0)
  await expect(
    page
      .getByRole('region', { name: 'Lista: Renovações registradas', exact: true })
      .getByRole('row')
      .filter({ hasText: ownName }),
  ).toHaveCount(0)
})
