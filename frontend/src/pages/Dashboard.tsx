import { useAuth } from '../auth/context'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  ClipboardList,
  FileText,
  Package,
  Plus,
  TriangleAlert,
  Clock3,
  Truck,
  RotateCcw,
  Users,
  Drill,
} from 'lucide-react'
import { Card, PageHeader } from '../components/ui'
import { Button } from '../components/Button'
import { DataTable } from '../components/DataTable'
import { DemoForm } from '../components/DemoForm'
import { contracts } from '../demo/data'

export function Dashboard() {
  const { user } = useAuth()
  return (
    <>
      <PageHeader
        eyebrow="SEU DIA, EM ORDEM"
        title="Visão geral"
        description="Uma visão clara das suas locações e das próximas movimentações."
        actions={
          <>
            <span className="reference-date">
              <CalendarDays size={16} aria-hidden="true" />
              12 set. 2026 · exemplo
            </span>
            <DemoForm
              trigger={
                <Button>
                  <Plus size={18} aria-hidden="true" />
                  Novo orçamento
                </Button>
              }
            />
          </>
        }
      />
      {user?.permissions.includes('imports.write') && (
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
      <div className="metrics-grid">
        {[
          {
            label: 'Contratos ativos',
            value: '24',
            detail: 'Locações em andamento',
            icon: FileText,
            tone: 'blue',
          },
          {
            label: 'Itens locados',
            value: '86',
            detail: 'Em obras de clientes',
            icon: Package,
            tone: 'violet',
          },
          {
            label: 'Vencendo em breve',
            value: '05',
            detail: 'Acompanhar nos próximos dias',
            icon: Clock3,
            tone: 'amber',
          },
          {
            label: 'Contratos vencidos',
            value: '03',
            detail: 'Precisam da sua atenção',
            icon: TriangleAlert,
            tone: 'rose',
          },
        ].map((metric) => (
          <Card className="metric-card" key={metric.label}>
            <div className="metric-top">
              <span>{metric.label}</span>
              <span className={`metric-icon tone-${metric.tone}`}>
                <metric.icon size={20} aria-hidden="true" />
              </span>
            </div>
            <strong className="metric-value">{metric.value}</strong>
            <p>{metric.detail}</p>
          </Card>
        ))}
      </div>
      <div className="dashboard-grid">
        <Card
          title="Contratos a acompanhar"
          description="Vencimentos e situações da demonstração."
          action={
            <Link className="text-link" to="/contratos">
              Ver todos
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          }
        >
          <DataTable rows={contracts} title="contratos a acompanhar" />
        </Card>
        <div className="dashboard-side">
          <Card
            title="Disponibilidade da frota"
            description="Distribuição ilustrativa de equipamentos."
          >
            <div className="fleet-summary">
              <strong>
                42<span>equipamentos</span>
              </strong>
              <span className="fleet-percentage">
                57%<small>disponível</small>
              </span>
            </div>
            <div className="fleet-bar" aria-hidden="true">
              <span style={{ width: '57%' }} />
              <span style={{ width: '31%' }} />
              <span style={{ width: '12%' }} />
            </div>
            <ul className="fleet-legend">
              <li>
                <span>
                  <i className="dot dot-green" />
                  Disponíveis
                </span>
                <strong>24</strong>
              </li>
              <li>
                <span>
                  <i className="dot dot-blue" />
                  Locados
                </span>
                <strong>13</strong>
              </li>
              <li>
                <span>
                  <i className="dot dot-amber" />
                  Em manutenção
                </span>
                <strong>5</strong>
              </li>
            </ul>
            <Link className="card-link" to="/equipamentos">
              Consultar equipamentos
              <ArrowRight size={16} aria-hidden="true" />
            </Link>
          </Card>
          <Card title="Movimentações recentes" description="Exemplos do fluxo de uma locação.">
            <ul className="activity-list">
              <li>
                <span className="activity-icon tone-blue">
                  <Truck size={17} aria-hidden="true" />
                </span>
                <div>
                  <strong>Retirada de equipamentos</strong>
                  <p>DEMO-1042 · 2 betoneiras</p>
                  <small>Hoje, 09:40 · exemplo</small>
                </div>
              </li>
              <li>
                <span className="activity-icon tone-green">
                  <RotateCcw size={17} aria-hidden="true" />
                </span>
                <div>
                  <strong>Devolução registrada</strong>
                  <p>DEMO-1037 · 1 serra circular</p>
                  <small>Hoje, 08:15 · exemplo</small>
                </div>
              </li>
              <li>
                <span className="activity-icon tone-violet">
                  <ClipboardList size={17} aria-hidden="true" />
                </span>
                <div>
                  <strong>Orçamento em preparação</strong>
                  <p>Obras Almeida · exemplo</p>
                  <small>Ontem, 16:30 · exemplo</small>
                </div>
              </li>
            </ul>
          </Card>
        </div>
      </div>
      <div className="section-title">
        <h2>Acesso rápido</h2>
        <p>As áreas que fazem parte da sua rotina.</p>
      </div>
      <div className="shortcut-grid">
        {[
          {
            path: '/clientes',
            title: 'Clientes',
            description: 'Relacionamentos e cadastros',
            icon: Users,
          },
          {
            path: '/produtos',
            title: 'Produtos',
            description: 'Catálogo de materiais',
            icon: Package,
          },
          {
            path: '/equipamentos',
            title: 'Equipamentos',
            description: 'Unidades da sua frota',
            icon: Drill,
          },
          {
            path: '/contratos',
            title: 'Contratos',
            description: 'Histórico de locações',
            icon: FileText,
          },
        ].map((item) => (
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
      </div>
    </>
  )
}
