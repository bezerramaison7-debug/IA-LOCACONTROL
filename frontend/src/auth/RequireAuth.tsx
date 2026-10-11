import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth, pathPermission } from './context'
import { ErrorState, Skeleton } from '../components/ui'

export function RequireAuth() {
  const { user, loading, error, refresh } = useAuth()
  const location = useLocation()
  if (loading)
    return (
      <main className="auth-page">
        <Skeleton />
      </main>
    )
  if (error)
    return (
      <main className="auth-page">
        <ErrorState message={error} onRetry={() => void refresh()} />
      </main>
    )
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (user.must_change_password && location.pathname !== '/perfil')
    return <Navigate to="/perfil" replace />
  const permission = pathPermission(location.pathname)
  if (permission && !user.permissions.includes(permission)) {
    if (location.pathname === '/') return <Navigate to="/perfil" replace />
    return (
      <main className="auth-page">
        <ErrorState message="Você não tem permissão para acessar esta área." />
        <a href="#/perfil">Ir para meu perfil</a>
      </main>
    )
  }
  return <Outlet />
}
