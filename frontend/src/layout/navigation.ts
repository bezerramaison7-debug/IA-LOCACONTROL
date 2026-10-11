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
    items: [
      { path: '/faturamento', label: 'Faturamento', icon: Wallet, ready: false },
      { path: '/fiscal', label: 'Fiscal', icon: Receipt, ready: false },
    ],
  },
  {
    label: 'Gestão',
    items: [
      { path: '/relatorios', label: 'Relatórios', icon: ChartNoAxesCombined, ready: false },
      { path: '/importacoes', label: 'Importações', icon: Upload, ready: true },
      { path: '/usuarios', label: 'Usuários', icon: UserRoundCog, ready: true },
      { path: '/perfis', label: 'Perfis e permissões', icon: Users, ready: true },
      { path: '/auditoria', label: 'Auditoria', icon: History, ready: true },
      { path: '/perfil', label: 'Meu perfil', icon: UserRoundCog, ready: true },
      { path: '/configuracoes', label: 'Configurações', icon: Settings, ready: true },
    ],
  },
]
export const navigationItems = navigation.flatMap((group) => group.items)
