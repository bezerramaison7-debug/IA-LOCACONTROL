import { useState } from 'react'
import { Plus, Rows3, LayoutGrid } from 'lucide-react'
import { Card, EmptyState, PageHeader, Select } from '../components/ui'
import { Button } from '../components/Button'
import { DemoForm } from '../components/DemoForm'
import { DataTable } from '../components/DataTable'
import { catalogData } from '../demo/data'

const definitions = {
  clientes: {
    title: 'Clientes',
    description: 'Organize os relacionamentos que movimentam o seu negócio.',
    action: 'Novo cliente',
    name: 'Cliente',
    detail: 'Localidade',
    date: 'Referência',
    eyebrow: 'COMERCIAL',
    empty: 'Seu cadastro de clientes começa aqui',
  },
  produtos: {
    title: 'Produtos',
    description: 'Um catálogo organizado para cada tipo de locação.',
    action: 'Novo produto',
    name: 'Produto / categoria',
    detail: 'Controle',
    date: 'Referência',
    eyebrow: 'OPERAÇÃO',
    empty: 'Prepare o seu catálogo de produtos',
  },
  equipamentos: {
    title: 'Equipamentos',
    description: 'Cada unidade física identificada, do pátio à obra.',
    action: 'Novo equipamento',
    name: 'Equipamento',
    detail: 'Localização',
    date: 'Referência',
    eyebrow: 'OPERAÇÃO',
    empty: 'Conheça a visão da sua frota',
  },
  orcamentos: {
    title: 'Orçamentos',
    description: 'Acompanhe as propostas desde o primeiro contato.',
    action: 'Novo orçamento',
    name: 'Cliente / itens',
    detail: 'Período',
    date: 'Validade',
    eyebrow: 'COMERCIAL',
    empty: 'Uma boa locação começa com uma proposta',
  },
  contratos: {
    title: 'Contratos',
    description: 'As informações de cada locação reunidas em um só lugar.',
    action: 'Novo contrato',
    name: 'Cliente / equipamentos',
    detail: 'Período',
    date: 'Vencimento',
    eyebrow: 'COMERCIAL',
    empty: 'Todas as locações, em uma visão',
  },
}
export type CatalogKind = keyof typeof definitions

export function Catalog({ kind }: { kind: CatalogKind }) {
  const config = definitions[kind]
  const [view, setView] = useState('example')
  return (
    <>
      <PageHeader
        title={config.title}
        description={config.description}
        eyebrow={config.eyebrow}
        actions={
          <DemoForm
            title={`Prévia: ${config.action.toLowerCase()}`}
            trigger={
              <Button>
                <Plus size={18} aria-hidden="true" />
                {config.action}
              </Button>
            }
          />
        }
      />
      <div className="catalog-summary">
        <span className="summary-icon">
          <LayoutGrid size={22} aria-hidden="true" />
        </span>
        <div>
          <h2>Explore a visão de {config.title.toLowerCase()}</h2>
          <p>Exemplos visuais para avaliar a organização, a busca e os filtros.</p>
        </div>
        <div className="sample-count">
          <strong>{catalogData[kind].length}</strong>
          <span>exemplos fictícios</span>
        </div>
      </div>
      <Card
        title={`Lista de ${config.title.toLowerCase()}`}
        description="Prévia da interface · os cadastros reais virão nas próximas etapas."
        action={<Rows3 size={20} aria-hidden="true" />}
      >
        <div className="preview-control">
          <Select label="Estado da prévia" value={view} onChange={(e) => setView(e.target.value)}>
            <option value="example">Exemplos</option>
            <option value="empty">Lista vazia</option>
            <option value="loading">Carregando</option>
            <option value="error">Erro de carregamento</option>
          </Select>
        </div>
        {view === 'empty' ? (
          <EmptyState
            initial
            title={config.empty}
            description="A operação comercial será conectada nas próximas etapas. Por enquanto, explore a prévia visual."
            action={
              <Button variant="secondary" onClick={() => setView('example')}>
                Ver exemplos
              </Button>
            }
          />
        ) : (
          <DataTable
            title={config.title.toLowerCase()}
            rows={catalogData[kind]}
            nameLabel={config.name}
            detailLabel={config.detail}
            dateLabel={config.date}
            loading={view === 'loading'}
            error={
              view === 'error'
                ? 'Este é um erro simulado para demonstrar a recuperação da interface.'
                : undefined
            }
            onRetry={() => setView('example')}
          />
        )}
      </Card>
      <p className="page-footnote">
        Os exemplos não representam clientes, produtos ou operações reais.
      </p>
    </>
  )
}
