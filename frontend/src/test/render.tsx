// Test-only harness: a page inside the providers it needs, with a mocked authenticated client.
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthContext } from '../auth/context'
import { ToastProvider } from '../components/ToastProvider'
import { adminSession } from './auth-fixture'

export type Handler = (path: string, method: string, body?: unknown) => unknown
export function mockRequest(handler: Handler) {
  return vi.fn(async (path: string, method = 'GET', body?: unknown) => handler(path, method, body))
}
export function renderPage(
  ui: ReactNode,
  request: ReturnType<typeof mockRequest>,
  options: {
    entry?: string
    permissions?: string[]
    clear?: () => void
    local?: boolean
    station?: { id: string; name: string } | null
    network?: boolean
  } = {},
) {
  const user = {
    ...adminSession.user,
    permissions: options.permissions || adminSession.user.permissions,
  }
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}
    >
      <AuthContext.Provider
        value={{
          user,
          local: options.local,
          station: options.station ?? null,
          network: options.network,
          loading: false,
          error: '',
          refresh: async () => {},
          login: async () => user,
          logout: async () => {},
          clear: options.clear || (() => {}),
          request,
        }}
      >
        <ToastProvider>
          <MemoryRouter initialEntries={[options.entry || '/']}>{ui}</MemoryRouter>
        </ToastProvider>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}
/** Writes to the records; automatic drafts (/drafts, ADR-024) are checked by their own tests. */
export const writes = (request: ReturnType<typeof mockRequest>) =>
  request.mock.calls.filter(
    ([path, method]) => method && method !== 'GET' && !String(path).startsWith('/drafts/'),
  )
export const draftCalls = (request: ReturnType<typeof mockRequest>) =>
  request.mock.calls.filter(([path]) => String(path).startsWith('/drafts/'))
