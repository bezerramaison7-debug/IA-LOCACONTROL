import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { mockRequest, renderPage, writes } from '../test/render'
import { Stations } from './Stations'
import { Backups } from './Backups'
import { Dashboard } from './Dashboard'
import { dashboard } from '../test/auth-fixture'

const now = Math.floor(Date.now() / 1000)
const overview = {
  installation_id: 'base-1111',
  server: { id: 'servidor-2222', created_at: now - 1000 },
  network: true,
  registry: { unavailable: false, recovered_from_backup: false },
  pairing: null,
  stations: [
    {
      id: 'aaaaaaaa-0000-4000-8000-000000000000',
      name: 'Balcão 1',
      paired_at: now - 500,
      paired_from: '192.168.0.21',
      last_seen_at: now - 10,
      last_address: '192.168.0.21',
      revoked_at: null,
    },
  ],
  events: [{ at: now - 500, action: 'station.paired', station_name: 'Balcão 1' }],
}

it('generates a code, lists the stations with three identities and revokes one', async () => {
  const user = userEvent.setup()
  const request = mockRequest((path, method) => {
    if (path === '/stations/pairing' && method === 'POST')
      return { code: 'ABCD-EFGH', expires_at: now + 600, attempts_left: 5 }
    if (path.endsWith('/revoke')) return { station: { ...overview.stations[0], revoked_at: now } }
    return overview
  })
  renderPage(<Stations />, request, { local: true })
  const list = await screen.findByRole('region', { name: 'Lista de estações' })
  expect(within(list).getByText('Balcão 1')).toBeInTheDocument()
  expect(screen.getByText('base-1111')).toBeInTheDocument()
  expect(screen.getByText('servidor-2222')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Gerar código de pareamento' }))
  const code = await screen.findByRole('status', { name: 'Código de pareamento' })
  expect(code).toHaveTextContent('ABCD-EFGH')
  expect(code).toHaveTextContent('5 tentativas erradas o cancelam')
  await user.click(screen.getByRole('button', { name: 'Revogar Balcão 1' }))
  await user.click(screen.getByRole('button', { name: 'Revogar estação' }))
  expect(await screen.findByText('Estação Balcão 1 revogada.')).toBeInTheDocument()
  expect(writes(request).map(([path, method]) => [path, method])).toEqual([
    ['/stations/pairing', 'POST'],
    ['/stations/aaaaaaaa-0000-4000-8000-000000000000/revoke', 'POST'],
  ])
})

it('explains that the network is off on this computer', async () => {
  renderPage(
    <Stations />,
    mockRequest(() => ({ ...overview, network: false, stations: [] })),
    {
      local: true,
    },
  )
  expect(await screen.findByText(/rede da loja está desativada/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Gerar código de pareamento' })).toBeNull()
})

it('a station sees backups but cannot configure, download, import or restore', async () => {
  const name = 'locacontrol_2026-11-02_150000.zip'
  const run = {
    started_at: '2026-11-02T15:00:00-03:00',
    finished_at: '2026-11-02T15:00:02-03:00',
    kind: 'auto',
    status: 'ok',
    name,
    size: 10,
  }
  const request = mockRequest(() => ({
    config: {
      enabled: true,
      frequency: '20min',
      time: '22:00',
      keep: 14,
      directory: '',
      mirror_directory: '',
      max_total_gb: 10,
      min_free_gb: 10,
      margin_percent: 5,
      margin_max_gb: 20,
    },
    directory: 'C:\\dados\\backups',
    items: [{ name, size: 10, created_at: now, kind: 'backup' }],
    total_size: 10,
    status: {
      last_success: run,
      last_failure: null,
      runs: [run],
      alert: null,
      requires_running: 'Computador ligado.',
    },
  }))
  renderPage(<Backups />, request, { local: true, station: { id: 's1', name: 'Balcão 1' } })
  expect(await screen.findByText(/só no computador principal/)).toBeInTheDocument()
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Verificar ' + name })).toBeVisible(),
  )
  for (const label of [
    'Baixar ' + name,
    'Restaurar ' + name,
    'Importar backup',
    'Salvar configuração',
  ])
    expect(screen.queryByRole('button', { name: label })).toBeNull()
  expect(screen.getByRole('button', { name: 'Fazer backup agora' })).toBeInTheDocument()
})

it('warns about a detected credential reuse and shows why the station was revoked', async () => {
  const reused = {
    ...overview,
    stations: [
      {
        ...overview.stations[0],
        revoked_at: now - 60,
        revoked_reason: 'reuso de credencial detectado',
      },
    ],
    events: [
      {
        at: now - 60,
        action: 'station.reuse_detected',
        station_id: overview.stations[0].id,
        station_name: 'Balcão 1',
        peer: '192.168.0.99',
        last_address: '192.168.0.21',
      },
    ],
  }
  renderPage(
    <Stations />,
    mockRequest(() => reused),
    { local: true },
  )
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('usada por mais de um computador')
  expect(alert).toHaveTextContent('192.168.0.99')
  expect(screen.getByText(/reuso de credencial detectado/)).toBeInTheDocument()
  // No principal, a Visão geral também avisa.
  renderPage(
    <Dashboard />,
    mockRequest((path) => (path === '/stations' ? reused : dashboard)),
    {
      local: true,
      network: true,
      permissions: ['contracts.read'],
    },
  )
  const banner = await screen.findByRole('alert', { name: 'Aviso da rede' })
  expect(banner).toHaveTextContent('Balcão 1')
})

it('an unreadable station list blocks stations and is reset only with the exact phrase', async () => {
  const user = userEvent.setup()
  const request = mockRequest((path) =>
    path === '/stations/registry/reset'
      ? { server: { id: 'novo' }, registry: { unavailable: false, recovered_from_backup: false } }
      : {
          ...overview,
          server: null,
          registry: { unavailable: true, recovered_from_backup: false },
          stations: [],
          events: [],
        },
  )
  renderPage(<Stations />, request, { local: true })
  expect(await screen.findByText(/todas as estações estão bloqueadas/)).toBeInTheDocument()
  const button = screen.getByRole('button', { name: 'Recomeçar a lista de estações' })
  expect(button).toBeDisabled()
  await user.type(screen.getByLabelText(/Digite exatamente/), 'RECOMEÇAR ESTAÇÕES')
  await user.click(button)
  await waitFor(() =>
    expect(writes(request)).toEqual([
      ['/stations/registry/reset', 'POST', { confirmation: 'RECOMEÇAR ESTAÇÕES' }],
    ]),
  )
})
