import type { ReactNode } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import {
  getContract,
  listAllContracts,
  positive,
  useContractPermissions,
  type ContractSummary,
} from '../lib/contracts'
import { Button } from '../components/Button'
import { Card, EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui'
import { ContractTable } from './contracts-shared'
import { RenewalRequests } from './renewal-requests'

const active = ['VENCIDO', 'VENCENDO', 'ATIVO']
type View = 'retiradas' | 'devolucoes' | 'renovacoes'

/** Every contract of the given statuses, in that order (overdue first when listed first). */
function useContracts(statuses: string[], origin = '') {
  const { request } = useAuth()
  return useQuery({
    queryKey: ['contracts', 'all', statuses, origin],
    queryFn: async () => {
      const pages = await Promise.all(
        statuses.map((status) => listAllContracts(request, status, 500, origin)),
      )
      return {
        items: pages.flatMap((page) => page.items),
        truncated: pages.some((page) => page.truncated),
      }
    },
    retry: false,
  })
}

function OpenLink({
  row,
  action,
  label,
}: {
  row: ContractSummary
  action?: string
  label: string
}) {
  return (
    <Button asChild variant={action ? 'secondary' : 'ghost'}>
      <Link
        to={'/contratos?id=' + row.id + (action ? '&acao=' + action : '')}
        aria-label={label + ' ' + row.number}
      >
        {label}
      </Link>
    </Button>
  )
}

function ContractsCard({
  title,
  description,
  query,
  rows,
  empty,
  actions,
}: {
  title: string
  description: string
  query: {
    isPending: boolean
    isError: boolean
    error: Error | null
    refetch: () => unknown
    data?: { truncated: boolean }
  }
  rows: ContractSummary[]
  empty: string
  actions: (row: ContractSummary) => ReactNode
}) {
  return (
    <Card title={title} description={description}>
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorState
          message={query.error?.message || 'Não foi possível carregar.'}
          onRetry={() => void query.refetch()}
        />
      ) : !rows.length ? (
        <EmptyState initial title={empty} description="Nada pendente nesta visão no momento." />
      ) : (
        <>
          <ContractTable label={'Lista: ' + title} rows={rows} actions={actions} />
          <div className="table-footer">
            <span>
              {rows.length} {rows.length === 1 ? 'contrato' : 'contratos'}
              {query.data?.truncated &&
                ' · lista parcial: use a busca em Contratos para localizar os demais'}
            </span>
          </div>
        </>
      )}
    </Card>
  )
}

function Withdrawals() {
  const { request } = useAuth()
  const can = useContractPermissions()
  const waiting = useContracts(['AGUARDANDO_RETIRADA'])
  const running = useContracts(active)
  // The list has no balance per item, so active contracts are checked one by one.
  const details = useQueries({
    queries: (running.data?.items || []).map((row) => ({
      queryKey: ['contracts', 'detail', row.id],
      queryFn: () => getContract(request, row.id),
      retry: false,
    })),
  })
  const checking = details.some((detail) => detail.isPending)
  const failed = details.find((detail) => detail.isError)
  const partial = (running.data?.items || []).filter((_, index) =>
    details[index]?.data?.items.some((item) => positive(item.to_withdraw)),
  )
  const actions = (row: ContractSummary) => (
    <>
      {can.operate && <OpenLink row={row} action="retirada" label="Registrar retirada" />}
      <OpenLink row={row} label="Abrir" />
    </>
  )
  return (
    <>
      <ContractsCard
        title="Aguardando retirada"
        description="Contratos confirmados cujo equipamento ainda não saiu."
        query={waiting}
        rows={waiting.data?.items || []}
        empty="Nenhum contrato aguardando retirada"
        actions={actions}
      />
      <ContractsCard
        title="Ativos com saldo a retirar"
        description="Contratos com retirada parcial: parte dos itens ainda não saiu."
        query={{
          isPending: running.isPending || checking,
          isError: running.isError || !!failed,
          error: running.error || failed?.error || null,
          refetch: () => {
            void running.refetch()
            details.forEach((detail) => detail.isError && void detail.refetch())
          },
          data: running.data,
        }}
        rows={partial}
        empty="Nenhum contrato ativo com saldo a retirar"
        actions={actions}
      />
    </>
  )
}

function Returns() {
  const can = useContractPermissions()
  const query = useContracts(active)
  return (
    <ContractsCard
      title="Contratos com devolução pendente"
      description="Vencidos primeiro, depois os que vencem em breve e os demais ativos."
      query={query}
      rows={query.data?.items || []}
      empty="Nenhum contrato ativo"
      actions={(row) => (
        <>
          {can.operate && <OpenLink row={row} action="devolucao" label="Registrar devolução" />}
          <OpenLink row={row} label="Abrir" />
        </>
      )}
    />
  )
}

function Renewals() {
  const can = useContractPermissions()
  const renewable = useContracts(active)
  const renewals = useContracts([''], 'RENOVACAO')
  // Requests come from the customer portal, which the local edition does not have.
  const { local } = useAuth()
  return (
    <>
      {!local && <RenewalRequests />}
      <ContractsCard
        title="Contratos que podem ser renovados"
        description="Ativos, vencendo e vencidos. A renovação cria o próximo número da cadeia (9193 → 9193.1)."
        query={renewable}
        rows={renewable.data?.items || []}
        empty="Nenhum contrato ativo para renovar"
        actions={(row) => (
          <>
            {can.write && <OpenLink row={row} action="renovar" label="Renovar" />}
            <OpenLink row={row} label="Abrir" />
          </>
        )}
      />
      <ContractsCard
        title="Renovações registradas"
        description="Contratos criados por renovação, com a opção de preço escolhida."
        query={renewals}
        rows={renewals.data?.items || []}
        empty="Nenhuma renovação registrada"
        actions={(row) => <OpenLink row={row} label="Abrir" />}
      />
    </>
  )
}

const views = {
  retiradas: {
    title: 'Retiradas',
    description: 'Contratos com equipamento a sair: registre a retirada para baixar o estoque.',
    Body: Withdrawals,
  },
  devolucoes: {
    title: 'Devoluções',
    description: 'Contratos com itens com o cliente: registre a devolução total ou parcial.',
    Body: Returns,
  },
  renovacoes: {
    title: 'Renovações',
    description:
      'Decida os pedidos dos clientes, renove contratos ativos e acompanhe as renovações registradas.',
    Body: Renewals,
  },
}

export function Operations({ view }: { view: View }) {
  const can = useContractPermissions()
  const { title, description, Body } = views[view]
  return (
    <>
      <PageHeader title={title} description={description} />
      {can.read ? (
        <Body />
      ) : (
        <ErrorState message="Seu perfil não tem permissão para consultar contratos." />
      )}
    </>
  )
}
