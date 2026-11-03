import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ChartNoAxesCombined,
  CircleCheck,
  ClipboardList,
  Clock3,
  Drill,
  FileText,
  Package,
  Plus,
  TriangleAlert,
  Truck,
  Undo2,
  Users,
  Wallet,
  Wrench,
} from 'lucide-react'
import { canOpen, useAuth } from '../auth/context'
import { getBackupStatus } from '../lib/backups'
import { eventKinds } from '../lib/contracts'
import { getDashboard, type Dashboard as DashboardData } from '../lib/reports'
import { brDateTime, brMoney, brQuantity } from '../lib/quotes'
import { Button } from '../components/Button'
import { Card, EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui'
import { ContractTable } from './contracts-shared'

const shortcuts = [
  {
    path: '/clientes',
    title: 'Clientes',
    description: 'Relacionamentos e cadastros',
    icon: Users,
  },
  {
    path: '/orcamentos',
    title: 'Orçamentos',
    description: 'Propostas e aprovações',
    icon: ClipboardList,
  },
  { path: '/contratos', title: 'Contratos', description: 'Locações e documentos', icon: FileText },
  { path: '/retiradas', title: 'Retiradas', description: 'Equipamentos a sair', icon: Truck },
  { path: '/devolucoes', title: 'Devoluções', description: 'Itens com clientes', icon: Undo2 },
  { path: '/produtos', title: 'Produtos', description: 'Catálogo de materiais', icon: Package },
  {
    path: '/equipamentos',
    title: 'Equipamentos',
    description: 'Unidades da sua frota',
    icon: Drill,
  },
  {
    path: '/relatorios',
    title: 'Relatórios',
    description: 'Consultas e exportações',
    icon: ChartNoAxesCombined,
  },
]

function Shortcuts() {
  const { user } = useAuth()
  const allowed = shortcuts.filter((item) => canOpen(user, item.path))
  if (!allowed.length) return null
  return (
    <>
      <div className="section-title">
        <h2>Acesso rápido</h2>
        <p>As áreas liberadas para o seu perfil.</p>
      </div>
      <nav className="shortcut-grid" aria-label="Acesso rápido">
        {allowed.map((item) => (
          <Link className="shortcut" to={item.path} key={item.path}>
            <span className="shortcut-icon">
              <item.icon size={21} aria-hidden="true" />
            </span>
            <span>
              <strong>{item.title}</strong>
              <small>{item.description}</small>
            </span>
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        ))}
      </nav>
    </>
  )
}

function Panel({ data }: { data: DashboardData }) {
  const cards = data.cards
  const days = data.due_soon_days
  const metrics = [
    {
      label: 'Contratos ativos',
      value: String(cards.active_contracts),
      detail: 'Locações em andamento',
      icon: FileText,
      tone: 'blue',
    },
    {
      label: 'Aguardando retirada',
      value: String(cards.awaiting_withdrawal),
      detail: 'Confirmados, equipamento ainda não saiu',
      icon: Truck,
      tone: 'violet',
    },
    {
      label: 'Vencendo em breve',
      value: String(cards.due_soon),
      detail:
        days === 0
          ? 'Devolução prevista para hoje'
          : 'Devolução prevista em até ' + days + (days === 1 ? ' dia' : ' dias'),
      icon: Clock3,
      tone: 'amber',
    },
    {
      label: 'Contratos vencidos',
      value: String(cards.overdue),
      detail: 'Devolução prevista já passou',
      icon: TriangleAlert,
      tone: 'rose',
    },
    {
      label: 'Itens locados',
      value: brQuantity(cards.rented_items),
      detail: 'Unidades e quantidades com clientes',
      icon: Package,
      tone: 'blue',
    },
    {
      label: 'Equipamentos disponíveis',
      value: String(cards.equipment_available),
      detail: 'Unidades individuais prontas para locar',
      icon: CircleCheck,
      tone: 'green',
    },
    {
      label: 'Equipamentos em manutenção',
      value: String(cards.equipment_maintenance),
      detail: 'Unidades individuais fora de locação',
      icon: Wrench,
      tone: 'amber',
    },
    {
      label: 'Orçamentos em aberto',
      value: String(cards.open_quotes),
      detail: 'Enviados e ainda dentro da validade',
      icon: ClipboardList,
      tone: 'violet',
    },
    {
      label: 'Valor contratado',
      value: brMoney(cards.contracted_value),
      detail: 'Soma dos contratos ativos. Não é valor recebido.',
      icon: Wallet,
      tone: 'green',
    },
  ]
  return (
    <>
      <div className="metrics-grid" role="list" aria-label="Indicadores">
        {metrics.map((metric) => (
          <div role="listitem" className="card metric-card" key={metric.label}>
            <div className="metric-top">
              <span>{metric.label}</span>
              <span className={`metric-icon tone-${metric.tone}`}>
                <metric.icon size={20} aria-hidden="true" />
              </span>
            </div>
            <strong className="metric-value">{metric.value}</strong>
            <p>{metric.detail}</p>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <Card
          title="Contratos vencendo e vencidos"
          description="Ativos com devolução prevista vencida ou próxima, do mais antigo ao mais recente."
          action={
            <Link className="text-link" to="/contratos">
              Ver todos os contratos
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          }
        >
          {data.due_contracts.length ? (
            <ContractTable
              label="Lista de contratos vencendo e vencidos"
              rows={data.due_contracts}
              actions={(row) => (
                <Button asChild variant="ghost">
                  <Link to={'/contratos?id=' + row.id} aria-label={'Abrir contrato ' + row.number}>
                    Abrir
                  </Link>
                </Button>
              )}
            />
          ) : (
            <EmptyState
              initial
              title="Nenhum contrato vencendo ou vencido"
              description="Quando uma devolução prevista se aproximar, o contrato aparece aqui."
            />
          )}
        </Card>
        <div className="dashboard-side">
          <Card
            title="Movimentações recentes"
            description="Últimos eventos registrados nos contratos."
          >
            {data.recent_events.length ? (
              <ul className="activity-list">
                {data.recent_events.map((event) => (
                  <li key={event.id}>
                    <div>
                      <strong>
                        {eventKinds[event.kind] || event.kind} ·{' '}
                        <Link to={'/contratos?id=' + event.contract_id}>
                          contrato {event.contract_number}
                        </Link>
                      </strong>
                      <p>{event.customer}</p>
                      <p>{event.description}</p>
                      <small>{brDateTime(event.created_at)}</small>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                initial
                title="Nenhuma movimentação ainda"
                description="Os eventos dos contratos aparecem aqui conforme forem registrados."
              />
            )}
          </Card>
        </div>
      </div>
    </>
  )
}

/** Visible only to who manages backups, and only when there is something to do. */
function BackupAlert() {
  const { request } = useAuth()
  const status = useQuery({
    queryKey: ['backups', 'status'],
    queryFn: () => getBackupStatus(request),
    retry: false,
    refetchInterval: 5 * 60_000,
  })
  const alert = status.data?.alert
  if (!alert) return null
  return (
    <div
      className={'quote-notice' + (alert.level === 'danger' ? ' quote-notice-danger' : '')}
      role="alert"
      aria-label="Aviso de backup"
    >
      <strong>
        <TriangleAlert size={16} aria-hidden="true" /> {alert.message}
      </strong>
      <Link to="/backups">Abrir Backups</Link>
    </div>
  )
}

export function Dashboard() {
  const { user, request } = useAuth()
  const has = (code: string) => !!user?.permissions.includes(code)
  const canRead = has('contracts.read')
  const query = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => getDashboard(request),
    enabled: canRead,
    retry: false,
  })
  return (
    <>
      <PageHeader
        eyebrow="SEU DIA, EM ORDEM"
        title="Visão geral"
        description={
          canRead
            ? 'Indicadores calculados agora, a partir dos contratos e do estoque reais.'
            : 'Use o acesso rápido para chegar às áreas liberadas para o seu perfil.'
        }
        actions={
          has('quotes.write') && (
            <Button asChild>
              <Link to="/orcamentos?novo=1">
                <Plus size={18} aria-hidden="true" />
                Novo orçamento
              </Link>
            </Button>
          )
        }
      />
      {has('backups.manage') && <BackupAlert />}
      {has('imports.write') && (
        <Card title="Comece pelo seu Excel">
          <div className="import-body">
            <p>
              Traga os dados da planilha que sua empresa já usa. Envie o arquivo, revise o
              mapeamento e confirme a conversão.
            </p>
            <Link className="button button-primary" to="/importacoes">
              Enviar Excel e converter dados
            </Link>
          </div>
        </Card>
      )}
      {!canRead ? (
        <Card title="Seu painel">
          <div className="padded">
            <p>
              Os indicadores de contratos não fazem parte do seu perfil. As áreas que você pode usar
              estão no menu e no acesso rápido abaixo.
            </p>
          </div>
        </Card>
      ) : query.isPending ? (
        <Skeleton rows={4} />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <Panel data={query.data} />
      )}
      <Shortcuts />
    </>
  )
}
