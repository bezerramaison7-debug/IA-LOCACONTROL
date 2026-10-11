import { createContext, useContext } from 'react'
import type { AuthUser } from './api'

export type AuthContextValue = {
  user: AuthUser | null
  loading: boolean
  error: string
  refresh: () => Promise<void>
  login: (username: string, password: string) => Promise<AuthUser>
  logout: () => Promise<void>
  request: (path: string, method?: string, body?: unknown) => Promise<unknown>
  clear: () => void
}
export const AuthContext = createContext<AuthContextValue | null>(null)
export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('AuthProvider ausente')
  return context
}
export function pathPermission(path: string) {
  const masters: Record<string, string> = {
    '/clientes': 'customers.read',
    '/produtos': 'products.read',
    '/equipamentos': 'equipment.read',
    '/estoque': 'stock.read',
    '/precos': 'prices.read',
    '/importacoes': 'imports.read',
  }
  if (masters[path]) return masters[path]
  if (path === '/usuarios') return 'users.read'
  if (path === '/perfis') return 'roles.read'
  if (path === '/auditoria') return 'audit.read'
  if (path === '/perfil' || path === '/configuracoes') return null
  return 'workspace.view'
}
