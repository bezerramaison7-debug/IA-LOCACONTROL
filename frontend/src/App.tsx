import { lazy, Suspense } from 'react'
import { HashRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from './theme/ThemeProvider'
import { ToastProvider } from './components/ToastProvider'
import { AppShell } from './layout/AppShell'
import { navigationItems } from './layout/navigation'
import { Skeleton } from './components/ui'
import { Placeholder } from './pages/Placeholder'
import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth } from './auth/RequireAuth'
import { Login } from './pages/Login'

const Imports = lazy(() => import('./pages/Imports').then((m) => ({ default: m.Imports })))
const Masters = lazy(() => import('./pages/Masters').then((m) => ({ default: m.Masters })))
const Stock = lazy(() => import('./pages/Stock').then((m) => ({ default: m.Stock })))
const Quotes = lazy(() => import('./pages/Quotes').then((m) => ({ default: m.Quotes })))
const Prices = lazy(() => import('./pages/Prices').then((m) => ({ default: m.Prices })))
const Profile = lazy(() => import('./pages/Profile').then((m) => ({ default: m.Profile })))
const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Catalog = lazy(() => import('./pages/Catalog').then((m) => ({ default: m.Catalog })))
const Users = lazy(() => import('./pages/Users').then((m) => ({ default: m.Users })))
const Roles = lazy(() => import('./pages/Roles').then((m) => ({ default: m.Roles })))
const Audit = lazy(() => import('./pages/Audit').then((m) => ({ default: m.Audit })))

const Settings = lazy(() =>
  import('./pages/Settings').then((module) => ({ default: module.Settings })),
)

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <HashRouter>
          <AuthProvider>
            <Suspense fallback={<Skeleton />}>
              <Routes>
                <Route path="login" element={<Login />} />
                <Route element={<RequireAuth />}>
                  <Route element={<AppShell />}>
                    <Route path="perfil" element={<Profile />} />
                    <Route path="usuarios" element={<Users />} />
                    <Route path="perfis" element={<Roles />} />
                    <Route path="auditoria" element={<Audit />} />
                    <Route index element={<Dashboard />} />
                    <Route path="clientes" element={<Masters key="customers" kind="customers" />} />
                    <Route path="produtos" element={<Masters key="products" kind="products" />} />
                    <Route
                      path="equipamentos"
                      element={<Masters key="equipment" kind="equipment" />}
                    />
                    <Route path="estoque" element={<Stock />} />
                    <Route path="precos" element={<Prices />} />
                    <Route path="importacoes" element={<Imports />} />
                    <Route path="orcamentos" element={<Quotes />} />
                    <Route path="contratos" element={<Catalog kind="contratos" />} />
                    <Route
                      path="configuracoes"
                      element={
                        <Suspense fallback={<Skeleton />}>
                          <Settings />
                        </Suspense>
                      }
                    />
                    {navigationItems
                      .filter((item) => !item.ready)
                      .map((item) => (
                        <Route
                          key={item.path}
                          path={item.path}
                          element={<Placeholder title={item.label} />}
                        />
                      ))}
                    <Route path="*" element={<Placeholder />} />
                  </Route>
                </Route>
              </Routes>
            </Suspense>
          </AuthProvider>
        </HashRouter>
      </ToastProvider>
    </ThemeProvider>
  )
}
