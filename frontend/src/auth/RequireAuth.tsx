import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { canOpen, homePath, isPortalUser, useAuth } from './context'
import { ErrorState, Skeleton } from '../components/ui'
import { Pairing } from '../pages/Pairing'

export function RequireAuth() {
  const { user, local, station, pairing, loading, error, refresh } = useAuth()
  const location = useLocation()
  if (loading)
    return (
      <main className="auth-page">
        <Skeleton />
      </main>
    )
  // A computer of the store network without access yet: it pairs with the code (ADR-025).
  if (pairing && !user) return <Pairing />
  if (error)
    return (
      <main className="auth-page">
        <ErrorState message={error} onRetry={() => void refresh()} />
      </main>
    )
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  // Local edition: there is no personal profile or password to change.
  if (local && location.pathname === '/perfil') return <Navigate to="/" replace />
  // Station management belongs to the main computer only.
  if (station && location.pathname === '/estacoes') return <Navigate to="/" replace />
  if (user.must_change_password && location.pathname !== '/perfil')
    return <Navigate to="/perfil" replace />
  if (!canOpen(user, location.pathname)) {
    if (location.pathname === '/')
      return <Navigate to={isPortalUser(user) ? homePath(user) : '/perfil'} replace />
    return (
      <main className="auth-page">
        <ErrorState message="Você não tem permissão para acessar esta área." />
        <a href="#/perfil">Ir para meu perfil</a>
      </main>
    )
  }
  return <Outlet />
}
