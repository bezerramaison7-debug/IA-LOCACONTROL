import {
  LayoutDashboard,
  Users,
  ClipboardList,
  FileText,
  RefreshCw,
  Package,
  Drill,
  Warehouse,
  Truck,
  Undo2,
  Wrench,
  Wallet,
  Receipt,
  ChartNoAxesCombined,
  Upload,
  UserRoundCog,
  History,
  Settings,
  DatabaseBackup,
  Home,
  FileCheck,
  ClipboardCheck,
  IdCard,
} from 'lucide-react'

export const navigation = [
  {
    label: 'Principal',
    items: [{ path: '/', label: 'Dashboard', icon: LayoutDashboard, ready: true }],
  },
  {
    label: 'Comercial',
    items: [
      { path: '/clientes', label: 'Clientes', icon: Users, ready: true },
      { path: '/orcamentos', label: 'Orçamentos', icon: ClipboardList, ready: true },
      { path: '/contratos', label: 'Contratos', icon: FileText, ready: true },
      { path: '/renovacoes', label: 'Renovações', icon: RefreshCw, ready: true },
    ],
  },
  {
    label: 'Operação',
    items: [
      { path: '/produtos', label: 'Produtos', icon: Package, ready: true },
      { path: '/equipamentos', label: 'Equipamentos', icon: Drill, ready: true },
      { path: '/estoque', label: 'Estoque', icon: Warehouse, ready: true },
      { path: '/precos', label: 'Preços', icon: Receipt, ready: true },
      { path: '/retiradas', label: 'Retiradas', icon: Truck, ready: true },
      { path: '/devolucoes', label: 'Devoluções', icon: Undo2, ready: true },
      { path: '/manutencao', label: 'Manutenção', icon: Wrench, ready: true },
    ],
  },
  {
    label: 'Financeiro',
    items: [{ path: '/faturamento', label: 'Faturamento e fiscal', icon: Wallet, ready: true }],
  },
  {
    label: 'Gestão',
    items: [
      { path: '/relatorios', label: 'Relatórios', icon: ChartNoAxesCombined, ready: true },
      { path: '/importacoes', label: 'Importações', icon: Upload, ready: true },
      { path: '/usuarios', label: 'Usuários', icon: UserRoundCog, ready: true },
      { path: '/perfis', label: 'Perfis e permissões', icon: Users, ready: true },
      { path: '/auditoria', label: 'Auditoria', icon: History, ready: true },
      { path: '/backups', label: 'Backups', icon: DatabaseBackup, ready: true },
      { path: '/perfil', label: 'Meu perfil', icon: UserRoundCog, ready: true },
      { path: '/configuracoes', label: 'Configurações', icon: Settings, ready: true },
    ],
  },
]
export const navigationItems = navigation.flatMap((group) => group.items)

/** Customer accounts get this menu only; no internal area is listed for them. */
export const portalNavigation: typeof navigation = [
  {
    label: 'Portal do cliente',
    items: [
      { path: '/portal', label: 'Início', icon: Home, ready: true },
      { path: '/portal/contratos', label: 'Meus contratos', icon: FileText, ready: true },
      { path: '/portal/equipamentos', label: 'Meus equipamentos', icon: Drill, ready: true },
      { path: '/portal/orcamentos', label: 'Orçamentos', icon: ClipboardList, ready: true },
      { path: '/portal/renovacoes', label: 'Renovações', icon: ClipboardCheck, ready: true },
      { path: '/portal/documentos', label: 'Documentos', icon: FileCheck, ready: true },
      { path: '/portal/cadastro', label: 'Meu cadastro', icon: IdCard, ready: true },
    ],
  },
  {
    label: 'Conta',
    items: [{ path: '/perfil', label: 'Meu perfil', icon: UserRoundCog, ready: true }],
  },
]
