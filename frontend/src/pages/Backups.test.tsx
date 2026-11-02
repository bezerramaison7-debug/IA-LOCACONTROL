import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { ApiError } from '../auth/api'
import { mockRequest, renderPage, writes } from '../test/render'
import { Backups } from './Backups'

const name = 'locacontrol_2026-10-11_220000.zip'
const overview = {
  config: { enabled: false, time: '22:00', keep: 14, directory: '' },
  directory: 'C:\\LocaControl\\data\\backups',
  items: [{ name, size: 2_097_152, created_at: 1789254000, kind: 'backup' }],
}
const verification = {
  name,
  ok: true,
  errors: [],
  revision: '0010_backups',
  users: 3,
  created_at: '2026-10-11T22:00:00-03:00',
  kind: 'manual',
  app_version: '0.1.0',
  files: 5,
}
const restored = {
  restored: name,
  safety_backup: 'locacontrol_2026-10-12_090000_pre-restore.zip',
  revision: '0010_backups',
  upgraded_to: null,
  replaced_files: null,
  message: 'Backup restaurado. Entre novamente: as sessões voltaram ao estado do backup.',
}

function api(restore: () => unknown = () => restored, check: unknown = verification) {
  return mockRequest((path, method) => {
    if (path.endsWith('/verify')) return check
    if (path.endsWith('/restore')) return restore()
    if (path === '/auth/logout') return undefined
    return method === 'PUT'
      ? { ...overview, config: { ...overview.config, enabled: true } }
      : overview
  })
}
const restoreCalls = (request: ReturnType<typeof api>) =>
  writes(request).filter(([path]) => String(path).endsWith('/restore'))

it('lists the sets and validates the configuration before saving', async () => {
  const user = userEvent.setup()
  const request = api()
  renderPage(<Backups />, request)
  const row = (await screen.findByText(name)).closest('tr')!
  expect(within(row).getByText('2 MB')).toBeInTheDocument()
  await user.type(screen.getByLabelText('Pasta dos backups'), 'backups')
  await user.click(screen.getByRole('button', { name: 'Salvar configuração' }))
  expect(screen.getByText(/Informe o caminho completo da pasta/)).toBeInTheDocument()
  expect(writes(request)).toHaveLength(0)
  await user.clear(screen.getByLabelText('Pasta dos backups'))
  await user.type(screen.getByLabelText('Pasta dos backups'), 'D:\\Backups')
  await user.click(screen.getByLabelText(/Fazer backup automático todos os dias/))
  await user.click(screen.getByRole('button', { name: 'Salvar configuração' }))
  expect(await screen.findByText('Configuração de backup salva.')).toBeInTheDocument()
  expect(writes(request)).toEqual([
    [
      '/backups/config',
      'PUT',
      { enabled: true, time: '22:00', keep: 14, directory: 'D:\\Backups' },
    ],
  ])
})

it('only enables the restore with the verified set, the exact phrase and the password', async () => {
  const user = userEvent.setup()
  const clear = vi.fn()
  const request = api()
  renderPage(<Backups />, request, { clear })
  await user.click(await screen.findByRole('button', { name: 'Restaurar ' + name }))
  const dialog = within(screen.getByRole('dialog'))
  expect(await dialog.findByText('Backup íntegro: pode ser restaurado.')).toBeInTheDocument()
  for (const consequence of [
    /depois deste backup .* deixa de\s+aparecer/,
    /cópia de segurança do estado atual/,
    /terão de entrar novamente/,
  ])
    expect(dialog.getByRole('note')).toHaveTextContent(consequence)
  const confirm = dialog.getByRole('button', { name: 'Restaurar este backup' })
  const phrase = dialog.getByLabelText('Digite exatamente: RESTAURAR ' + name)
  expect(confirm).toBeDisabled()
  await user.type(phrase, 'restaurar ' + name)
  await user.type(dialog.getByLabelText('Sua senha'), 'Senha-do-administrador!')
  expect(confirm).toBeDisabled()
  await user.clear(phrase)
  await user.type(phrase, 'RESTAURAR ' + name)
  expect(confirm).toBeEnabled()
  await user.clear(dialog.getByLabelText('Sua senha'))
  expect(confirm).toBeDisabled()
  expect(restoreCalls(request)).toHaveLength(0)
  await user.type(dialog.getByLabelText('Sua senha'), 'Senha-do-administrador!')
  await user.click(confirm)
  await waitFor(() => expect(clear).toHaveBeenCalled())
  expect(restoreCalls(request)).toEqual([
    [
      '/backups/' + name + '/restore',
      'POST',
      { confirmation: 'RESTAURAR ' + name, password: 'Senha-do-administrador!' },
    ],
  ])
})

it('keeps the restore blocked for a set that failed verification and shows a wrong password', async () => {
  const user = userEvent.setup()
  const failed = { ...verification, ok: false, errors: ['Conteúdo alterado: locacontrol.db'] }
  const first = renderPage(<Backups />, api(undefined, failed))
  await user.click(await screen.findByRole('button', { name: 'Restaurar ' + name }))
  let dialog = within(screen.getByRole('dialog'))
  expect(await dialog.findByText('Conteúdo alterado: locacontrol.db')).toBeInTheDocument()
  expect(dialog.getByLabelText('Sua senha')).toBeDisabled()
  expect(dialog.getByRole('button', { name: 'Restaurar este backup' })).toBeDisabled()
  first.unmount()

  const clear = vi.fn()
  const request = api(() => {
    throw new ApiError(403, 'Senha incorreta. A restauração não foi executada.')
  })
  renderPage(<Backups />, request, { clear })
  await user.click(await screen.findByRole('button', { name: 'Restaurar ' + name }))
  dialog = within(screen.getByRole('dialog'))
  await dialog.findByText('Backup íntegro: pode ser restaurado.')
  await user.type(dialog.getByLabelText(/Digite exatamente/), 'RESTAURAR ' + name)
  await user.type(dialog.getByLabelText('Sua senha'), 'errada')
  await user.click(dialog.getByRole('button', { name: 'Restaurar este backup' }))
  expect(await dialog.findByRole('alert')).toHaveTextContent('Senha incorreta')
  expect(clear).not.toHaveBeenCalled()
})

it('local edition: restores with the exact phrase only, without a password field', async () => {
  const user = userEvent.setup()
  const clear = vi.fn()
  const request = api(() => ({ ...restored, message: 'Backup restaurado.' }))
  renderPage(<Backups />, request, { clear, local: true })
  await user.click(await screen.findByRole('button', { name: 'Restaurar ' + name }))
  const dialog = within(screen.getByRole('dialog'))
  expect(await dialog.findByText('Backup íntegro: pode ser restaurado.')).toBeInTheDocument()
  expect(dialog.queryByLabelText('Sua senha')).not.toBeInTheDocument()
  expect(dialog.getByRole('note')).not.toHaveTextContent(/terão de entrar novamente/)
  const confirm = dialog.getByRole('button', { name: 'Restaurar este backup' })
  const phrase = dialog.getByLabelText('Digite exatamente: RESTAURAR ' + name)
  await user.type(phrase, 'RESTAURAR')
  expect(confirm).toBeDisabled()
  await user.clear(phrase)
  await user.type(phrase, 'RESTAURAR ' + name)
  await user.click(confirm)
  await waitFor(() => expect(clear).toHaveBeenCalled())
  expect(restoreCalls(request)).toEqual([
    ['/backups/' + name + '/restore', 'POST', { confirmation: 'RESTAURAR ' + name }],
  ])
})
