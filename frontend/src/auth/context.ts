import { createContext, useContext } from 'react'
import type { AuthUser } from './api'

export type AuthContextValue = {
  user: AuthUser | null
  /** Local edition: no login screen, profile, logout, users or portal. */
  local?: boolean
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
    '/orcamentos': 'quotes.read',
    '/contratos': 'contracts.read',
    '/renovacoes': 'contracts.read',
    '/retiradas': 'contracts.read',
    '/devolucoes': 'contracts.read',
    '/manutencao': 'stock.read',
    '/importacoes': 'imports.read',
    '/relatorios': 'reports.read',
    '/faturamento': 'fiscal.read',
    '/fiscal': 'fiscal.read',
    '/backups': 'backups.manage',
  }
  if (masters[path]) return masters[path]
  if (path === '/portal' || path.startsWith('/portal/')) return 'portal.access'
  if (path === '/usuarios') return 'users.read'
  if (path === '/perfis') return 'roles.read'
  if (path === '/auditoria') return 'audit.read'
  if (path === '/perfil' || path === '/configuracoes') return null
  return 'workspace.view'
}
type Permitted = Pick<AuthUser, 'permissions'> | null | undefined
/** Customer accounts live in the portal and never see the internal workspace. */
export function isPortalUser(user: Permitted) {
  return !!user?.permissions.includes('portal.access')
}
export function canOpen(user: Permitted, path: string) {
  if (!user) return false
  if (isPortalUser(user))
    return path === '/perfil' || path === '/portal' || path.startsWith('/portal/')
  const permission = pathPermission(path)
  return !permission || user.permissions.includes(permission)
}
export function homePath(user: Permitted) {
  return isPortalUser(user) ? '/portal' : '/'
}
