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
import { navigation, navigationItems } from './navigation'
import { Button } from '../components/Button'
import { ThemeSelect } from '../components/ThemeSelect'
import { Modal } from '../components/Modal'
import { DemoNotice } from '../components/ui'
import { readPreference, writePreference } from '../lib/preferences'
import { useAuth, pathPermission } from '../auth/context'

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth()
  return (
    <nav aria-label="Navegação principal" className="navigation">
      {navigation.map((group) => (
        <div className="nav-group" key={group.label}>
          <p className="nav-group-label">{group.label}</p>
          {group.items
            .filter((item) => {
              const permission = pathPermission(item.path)
              return (
                (!user?.must_change_password || item.path === '/perfil') &&
                (!permission || user?.permissions.includes(permission))
              )
            })
            .map((item) => (
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
                {!item.ready && <span className="future-dot" aria-label="Etapa futura" />}
              </NavLink>
            ))}
        </div>
      ))}
    </nav>
  )
}

export function AppShell() {
  const { user, logout } = useAuth()
  const [logoutError, setLogoutError] = useState('')
  const [loggingOut, setLoggingOut] = useState(false)
  const allowedItems = navigationItems.filter((item) => {
    const permission = pathPermission(item.path)
    return (
      (!user?.must_change_password || item.path === '/perfil') &&
      (!permission || user?.permissions.includes(permission))
    )
  })
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
  const current = navigationItems.find((item) => item.path === location.pathname)
  const group = navigation.find((group) =>
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
        <Link className="brand" to="/" aria-label="LocaControl, início">
          <span className="brand-mark">
            <Boxes size={22} aria-hidden="true" />
          </span>
          <span>
            LocaControl<small>GESTÃO DE LOCAÇÕES</small>
          </span>
        </Link>
        <Navigation />
        <div className="sidebar-footer">
          <ThemeSelect compact={collapsed} />
          <div className="profile">
            <span className="avatar">{user?.name.slice(0, 1).toUpperCase()}</span>
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
                <Button variant="secondary" disabled={loggingOut} onClick={() => void signOut()}>
                  Sair da conta
                </Button>
              </Modal>
            </div>
            <nav aria-label="Breadcrumb">
              <ol className="breadcrumbs">
                <li>
                  <Link to="/">Início</Link>
                </li>
                <li>
                  <ChevronRight size={14} aria-hidden="true" />
                </li>
                {group && group !== 'Principal' && (
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
                  placeholder="Clientes, contratos, produtos…"
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
          {![
            '/perfil',
            '/usuarios',
            '/perfis',
            '/auditoria',
            '/clientes',
            '/produtos',
            '/equipamentos',
            '/estoque',
            '/precos',
            '/orcamentos',
            '/importacoes',
          ].includes(location.pathname) && <DemoNotice />}
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>
            LocaControl <span aria-hidden="true">·</span> Ambiente local
          </span>
          <span>Cadastros, estoque e preços</span>
        </footer>
      </div>
    </div>
  )
}
