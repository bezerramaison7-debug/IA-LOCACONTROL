import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  Search,
  ChevronRight,
  LogOut,
  Boxes,
  ArrowUpRight,
} from 'lucide-react'
import { navigation, portalNavigation } from './navigation'
import { Button } from '../components/Button'
import { ThemeSelect } from '../components/ThemeSelect'
import { Modal } from '../components/Modal'
import { readPreference, writePreference } from '../lib/preferences'
import { canOpen, homePath, isPortalUser, useAuth } from '../auth/context'
import type { AuthUser } from '../auth/api'

/** The menu of the signed-in account: the portal for customers, the workspace otherwise. */
function allowedNavigation(user: AuthUser | null, local?: boolean) {
  return (isPortalUser(user) ? portalNavigation : navigation)
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) =>
          (!user?.must_change_password || item.path === '/perfil') &&
          !(local && item.path === '/perfil') &&
          canOpen(user, item.path),
      ),
    }))
    .filter((group) => group.items.length)
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user, local } = useAuth()
  return (
    <nav aria-label="Navegação principal" className="navigation">
      {allowedNavigation(user, local).map((group) => (
        <div className="nav-group" key={group.label}>
          <p className="nav-group-label">{group.label}</p>
          {group.items.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end
              title={item.label}
              onClick={onNavigate}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <item.icon size={18} aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  )
}

export function AppShell() {
  const { user, local, logout } = useAuth()
  const [logoutError, setLogoutError] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  const portal = isPortalUser(user)
  const groups = allowedNavigation(user, local)
  const allowedItems = groups.flatMap((group) => group.items)
  const signOut = async () => {
    setLoggingOut(true)
    setLogoutError('')
    try {
      await logout()
    } catch (e) {
      setLogoutError(e instanceof Error ? e.message : 'Erro ao sair.')
    } finally {
      setLoggingOut(false)
    }
  }
  const location = useLocation()
  const current = allowedItems.find((item) => item.path === location.pathname)
  const group = groups.find((group) =>
    group.items.some((item) => item.path === location.pathname),
  )?.label
  const [collapsed, setCollapsed] = useState(
    () => readPreference('locacontrol.sidebar') === 'collapsed',
  )
  const [mobileOpen, setMobileOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [search, setSearch] = useState('')
  const main = useRef<HTMLElement>(null)
  const previousPath = useRef(location.pathname)

  useEffect(() => {
    document.title = `${current?.label || 'Página não encontrada'} | LocaControl`
    if (previousPath.current !== location.pathname) {
      main.current?.focus()
      main.current?.scrollTo?.(0, 0)
      previousPath.current = location.pathname
    }
  }, [location.pathname, current?.label])

  useEffect(() => {
    const media = window.matchMedia('(min-width: 1024px)')
    const close = () => {
      if (media.matches) setMobileOpen(false)
    }
    media.addEventListener('change', close)
    return () => media.removeEventListener('change', close)
  }, [])

  return (
    <div className={`app-shell ${collapsed ? 'sidebar-collapsed' : ''}`}>
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault()
          main.current?.focus()
        }}
      >
        Pular para o conteúdo
      </a>
      <aside className="sidebar" aria-label="Menu lateral">
        <Link className="brand" to={homePath(user)} aria-label="LocaControl, início">
          <span className="brand-mark">
            <Boxes size={22} aria-hidden="true" />
          </span>
          <span>
            LocaControl<small>{portal ? 'PORTAL DO CLIENTE' : 'GESTÃO DE LOCAÇÕES'}</small>
          </span>
        </Link>
        <Navigation />
        <div className="sidebar-footer">
          <ThemeSelect compact={collapsed} />
          <div className="profile">
            <span className="avatar">{user?.name.slice(0, 1).toUpperCase()}</span>
            {local ? (
              <div>
                <strong>{user?.name}</strong>
                <small>Uso neste computador, sem login</small>
              </div>
            ) : (
              <>
                <div>
                  <Link to="/perfil">
                    <strong>{user?.name}</strong>
                  </Link>
                  <small>{user?.role_codes.join(', ')}</small>
                </div>
                <Button
                  variant="ghost"
                  iconOnly
                  aria-label="Sair"
                  disabled={loggingOut}
                  onClick={() => void signOut()}
                >
                  <LogOut size={18} aria-hidden="true" />
                </Button>
              </>
            )}
          </div>
        </div>
      </aside>

      <div className="app-body">
        <header className="topbar">
          <div className="topbar-left">
            <Button
              variant="ghost"
              iconOnly
              className="desktop-toggle"
              aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
              aria-expanded={!collapsed}
              onClick={() => {
                setCollapsed(!collapsed)
                writePreference('locacontrol.sidebar', !collapsed ? 'collapsed' : 'expanded')
              }}
            >
              {collapsed ? (
                <PanelLeftOpen size={20} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={20} aria-hidden="true" />
              )}
            </Button>
            <div className="mobile-toggle">
              <Modal
                className="mobile-drawer"
                open={mobileOpen}
                onOpenChange={setMobileOpen}
                title="Navegação"
                description="Escolha uma área do LocaControl."
                trigger={
                  <Button variant="ghost" iconOnly aria-label="Abrir menu">
                    <Menu size={20} aria-hidden="true" />
                  </Button>
                }
              >
                <Navigation onNavigate={() => setMobileOpen(false)} />
                <ThemeSelect />
                {!local && (
                  <Button variant="secondary" disabled={loggingOut} onClick={() => void signOut()}>
                    Sair da conta
                  </Button>
                )}
              </Modal>
            </div>
            <nav aria-label="Breadcrumb">
              <ol className="breadcrumbs">
                <li>
                  <Link to={homePath(user)}>{portal ? 'Portal' : 'Início'}</Link>
                </li>
                <li>
                  <ChevronRight size={14} aria-hidden="true" />
                </li>
                {group && group !== 'Principal' && group !== 'Portal do cliente' && (
                  <>
                    <li>{group}</li>
                    <li>
                      <ChevronRight size={14} aria-hidden="true" />
                    </li>
                  </>
                )}
                <li aria-current="page">{current?.label || 'Página não encontrada'}</li>
              </ol>
            </nav>
          </div>
          <div className="topbar-right">
            <Modal
              open={searchOpen}
              onOpenChange={setSearchOpen}
              title="Ir para uma área"
              description="Pesquise as páginas disponíveis para sua conta."
              trigger={
                <Button variant="ghost" className="global-search" aria-label="Buscar páginas">
                  <Search size={18} aria-hidden="true" />
                  <span>Buscar páginas</span>
                </Button>
              }
            >
              <label className="search-field">
                <Search size={18} aria-hidden="true" />
                <span className="sr-only">Nome da página</span>
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={portal ? 'Contratos, documentos…' : 'Clientes, contratos, produtos…'}
                />
              </label>
              <div className="command-results">
                {allowedItems
                  .filter((item) =>
                    item.label
                      .toLocaleLowerCase('pt-BR')
                      .includes(search.toLocaleLowerCase('pt-BR')),
                  )
                  .map((item) => (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={() => {
                        setSearchOpen(false)
                        setSearch('')
                      }}
                    >
                      <item.icon size={18} aria-hidden="true" />
                      {item.label}
                      <ArrowUpRight size={16} aria-hidden="true" />
                    </Link>
                  ))}
                {!allowedItems.some((item) =>
                  item.label.toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR')),
                ) && <p>Nenhuma página encontrada.</p>}
              </div>
            </Modal>
            <span className="workspace-label">
              <span className="workspace-dot" />
              Ambiente local
            </span>
          </div>
        </header>
        <main id="main-content" ref={main} tabIndex={-1} className="main-content">
          {logoutError && (
            <p role="alert" className="field-error">
              {logoutError}
            </p>
          )}
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>
            LocaControl <span aria-hidden="true">·</span> Ambiente local
          </span>
          <span>
            {portal
              ? 'Portal disponível na rede local da locadora'
              : 'Locações, estoque e documentos'}
          </span>
        </footer>
      </div>
    </div>
  )
}
