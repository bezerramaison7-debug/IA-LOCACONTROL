import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { HealthPanel } from './components/HealthPanel'

const healthy = { status: 'ok', database: 'ok', schema: 'ok', version: '0.1.0' }

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <HealthPanel />
    </QueryClientProvider>,
  )
}

describe('foundation screen', () => {
  it('shows the loading state without claiming the environment is connected', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    )
    renderApp()
    expect(screen.getByText('Conectando ao servidor…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Verificando…' })).toBeDisabled()
    expect(screen.queryByText('Ambiente conectado')).not.toBeInTheDocument()
  })

  it('renders the real response and clearly identifies the foundation scope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(healthy))))
    renderApp()
    expect(await screen.findByText('Ambiente conectado')).toBeInTheDocument()
    expect(screen.getByText('0.1.0')).toBeInTheDocument()
    expect(screen.getByText('Esta tela não contém dados comerciais.')).toBeInTheDocument()
  })

  it('recovers from an error using keyboard navigation and retry', async () => {
    const user = userEvent.setup()
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Network down'))
      .mockResolvedValueOnce(new Response(JSON.stringify(healthy)))
    vi.stubGlobal('fetch', fetchMock)
    renderApp()
    expect(await screen.findByRole('alert')).toHaveTextContent('Conexão indisponível')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Verificar novamente' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(await screen.findByText('Ambiente conectado')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
