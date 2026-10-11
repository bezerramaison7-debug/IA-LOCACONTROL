import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useAuth } from '../auth/context'
import {
  contractStatuses,
  getContract,
  listContracts,
  useContractPermissions,
  type Contract,
  type ContractFilters,
} from '../lib/contracts'
import { Button } from '../components/Button'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Pager } from './masters-shared'
import { ContractTable } from './contracts-shared'
import { ContractDetail, type Operation } from './contracts-detail'
import { ContractEditor } from './contracts-editor'
import { ContractOperation } from './contracts-operations'

function ContractList({
  filters,
  setFilters,
  canWrite,
  onOpen,
  onEdit,
  onNew,
}: {
  filters: ContractFilters
  setFilters: (filters: ContractFilters) => void
  canWrite: boolean
  onOpen: (id: number) => void
  onEdit: (id: number) => void
  onNew: () => void
}) {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['contracts', 'list', filters],
    queryFn: () => listContracts(request, filters),
    retry: false,
  })
  const filtered = !!filters.q || !!filters.status
  return (
    <Card
      title="Lista de contratos"
      description="Busque por cliente, documento ou número: 9193 traz o contrato e as renovações; 9193.1, só a renovação."
    >
      <div className="master-filters">
        <Field
          label="Buscar em contratos"
          value={filters.q}
          maxLength={160}
          placeholder="Cliente, documento ou número"
          onChange={(e) => setFilters({ ...filters, q: e.target.value, offset: 0 })}
        />
        <Select
          label="Filtrar situação"
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value, offset: 0 })}
        >
          <option value="">Todas</option>
          {Object.entries(contractStatuses).map(([key, text]) => (
            <option key={key} value={key}>
              {text}
            </option>
          ))}
        </Select>
      </div>
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data.items.length ? (
        filtered ? (
          <EmptyState
            title="Nenhum contrato encontrado"
            description="Experimente outro termo ou ajuste a situação."
            action={
              <Button
                variant="secondary"
                onClick={() => setFilters({ q: '', status: '', offset: 0 })}
              >
                Limpar filtros
              </Button>
            }
          />
        ) : (
          <EmptyState
            initial
            title="Nenhum contrato ainda"
            description={
              canWrite
                ? 'Crie um contrato direto ou converta um orçamento aprovado.'
                : 'Quando houver contratos, eles aparecerão aqui.'
            }
            action={
              canWrite ? (
                <Button variant="secondary" onClick={onNew}>
                  Criar contrato
                </Button>
              ) : undefined
            }
          />
        )
      ) : (
        <>
          <ContractTable
            label="Contratos"
            rows={query.data.items}
            actions={(row) => (
              <>
                <Button
                  variant="ghost"
                  aria-label={'Abrir contrato ' + row.number}
                  onClick={() => onOpen(row.id)}
                >
                  Abrir
                </Button>
                {canWrite && row.stored_status === 'RASCUNHO' && (
                  <Button
                    variant="ghost"
                    aria-label={'Editar contrato ' + row.number}
                    onClick={() => onEdit(row.id)}
                  >
                    Editar
                  </Button>
                )}
              </>
            )}
          />
          <Pager
            total={query.data.total}
            offset={filters.offset}
            onChange={(offset) => setFilters({ ...filters, offset })}
          />
        </>
      )}
    </Card>
  )
}

function DraftEditor({
  id,
  onSaved,
  onBack,
}: {
  id: number
  onSaved: (contract: Contract) => void
  onBack: () => void
}) {
  const { request } = useAuth()
  const query = useQuery({
    queryKey: ['contracts', 'detail', id],
    queryFn: () => getContract(request, id),
    retry: false,
  })
  const back = (
    <Button variant="secondary" onClick={onBack}>
      Voltar ao contrato
    </Button>
  )
  if (query.isPending)
    return (
      <>
        <PageHeader title="Editar contrato" description="Carregando o rascunho." actions={back} />
        <Skeleton rows={4} />
      </>
    )
  if (query.isError)
    return (
      <>
        <PageHeader title="Editar contrato" description="Não foi possível abrir." actions={back} />
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      </>
    )
  const contract = query.data
  return (
    <>
      <PageHeader
        title={'Editar contrato ' + contract.number}
        description="Altere o rascunho. O salvamento é auditado e confere a versão atual."
        actions={back}
      />
      {contract.stored_status !== 'RASCUNHO' ? (
        <ErrorState
          message={
            'Somente rascunhos podem ser editados. Este contrato está em ' +
            contractStatuses[contract.status].toLocaleLowerCase('pt-BR') +
            '.'
          }
        />
      ) : (
        <ContractEditor
          key={contract.id + ':' + contract.version}
          contract={contract}
          onSaved={onSaved}
          onCancel={onBack}
          onReload={() => void query.refetch()}
        />
      )}
    </>
  )
}

const operationNames = ['retirada', 'devolucao', 'renovar']

export function Contracts() {
  const can = useContractPermissions()
  const cache = useQueryClient()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState<ContractFilters>({ q: '', status: '', offset: 0 })
  const id = /^[1-9]\d*$/.test(params.get('id') || '') ? Number(params.get('id')) : null
  const operation = operationNames.includes(params.get('acao') || '')
    ? (params.get('acao') as Operation)
    : null
  const view = params.has('novo')
    ? 'new'
    : !id
      ? 'list'
      : params.has('editar')
        ? 'edit'
        : operation
          ? 'operation'
          : 'detail'
  const place = view + ':' + (id ?? '') + ':' + (operation ?? '')
  const mounted = useRef(false)
  useEffect(() => {
    // Views change without a route change, so focus moves to the content like a page change.
    if (mounted.current) document.getElementById('main-content')?.focus()
    mounted.current = true
  }, [place])
  const openList = () => setParams({})
  const openDetail = (contractId: number) => setParams({ id: String(contractId) })
  const openEdit = (contractId: number) => setParams({ id: String(contractId), editar: '1' })
  const openNew = () => setParams({ novo: '1' })
  const saved = (contract: Contract) => {
    toast('Contrato ' + contract.number + ' salvo como rascunho.')
    void cache.invalidateQueries({ queryKey: ['contracts'] })
    openDetail(contract.id)
  }
  const description = 'Locações com número definitivo, saldos por item, documentos e renovações.'
  if (!can.read)
    return (
      <>
        <PageHeader title="Contratos" description={description} />
        <ErrorState message="Seu perfil não tem permissão para consultar contratos." />
      </>
    )
  if ((view === 'new' || view === 'edit') && !can.write)
    return (
      <>
        <PageHeader
          title="Contratos"
          description={description}
          actions={
            <Button variant="secondary" onClick={openList}>
              Voltar para a lista
            </Button>
          }
        />
        <ErrorState message="Seu perfil não tem permissão para criar ou editar contratos." />
      </>
    )
  if (view === 'new')
    return (
      <>
        <PageHeader
          title="Novo contrato"
          description="Contrato direto, sem orçamento. Salvo como rascunho até a confirmação."
          actions={
            <Button variant="secondary" onClick={openList}>
              Voltar para a lista
            </Button>
          }
        />
        <ContractEditor onSaved={saved} onCancel={openList} />
      </>
    )
  if (view === 'edit' && id)
    return <DraftEditor key={id} id={id} onSaved={saved} onBack={() => openDetail(id)} />
  if (view === 'operation' && id && operation)
    return (
      <ContractOperation
        key={id + operation}
        id={id}
        operation={operation}
        onBack={() => openDetail(id)}
        onOpen={openDetail}
      />
    )
  if (view === 'detail' && id)
    return (
      <ContractDetail
        key={id}
        id={id}
        onBack={openList}
        onEdit={() => openEdit(id)}
        onOperation={(next) => setParams({ id: String(id), acao: next })}
      />
    )
  return (
    <>
      <PageHeader
        title="Contratos"
        description={description}
        actions={
          can.write && (
            <Button onClick={openNew}>
              <Plus size={18} aria-hidden="true" />
              Novo contrato
            </Button>
          )
        }
      />
      <ContractList
        filters={filters}
        setFilters={setFilters}
        canWrite={can.write}
        onOpen={openDetail}
        onEdit={openEdit}
        onNew={openNew}
      />
    </>
  )
}
