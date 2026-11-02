import type { ReactNode } from 'react'
import {
  Ban,
  CircleCheck,
  CircleMinus,
  Clock3,
  FileText,
  PencilLine,
  TriangleAlert,
  Truck,
} from 'lucide-react'
import {
  contractStatuses,
  documentStatuses,
  expectedReturn,
  type ActionError,
  type ContractStatus,
  type ContractSummary,
  type DocumentStatus,
} from '../lib/contracts'
import { brDate, brMoney } from '../lib/quotes'
import { Button } from '../components/Button'
import { MasterTable } from './masters-shared'

const badges = {
  RASCUNHO: ['muted', PencilLine],
  AGUARDANDO_RETIRADA: ['info', Truck],
  ATIVO: ['success', CircleCheck],
  VENCENDO: ['warning', Clock3],
  VENCIDO: ['danger', TriangleAlert],
  ENCERRADO: ['muted', CircleCheck],
  CANCELADO: ['muted', Ban],
} as const
const documentBadges = {
  GERADO: ['info', FileText],
  ASSINADO: ['success', CircleCheck],
  SUBSTITUIDO: ['muted', CircleMinus],
} as const

/** Status is always icon + text + colour, never colour alone. */
export function ContractBadge({ status }: { status: ContractStatus }) {
  const [tone, Icon] = badges[status]
  return (
    <span className={`badge badge-${tone}`}>
      <Icon size={14} aria-hidden="true" />
      {contractStatuses[status]}
    </span>
  )
}
export function DocumentBadge({ status }: { status: DocumentStatus }) {
  const [tone, Icon] = documentBadges[status]
  return (
    <span className={`badge badge-${tone}`}>
      <Icon size={14} aria-hidden="true" />
      {documentStatuses[status]}
    </span>
  )
}

/** API failure next to the action; a 409 offers to reload the current version. */
export function ActionFailure({
  failure,
  onReload,
  reloadLabel = 'Recarregar contrato',
}: {
  failure: ActionError | null
  onReload?: () => void
  reloadLabel?: string
}) {
  if (!failure) return null
  return (
    <div className="quote-notice quote-notice-danger" role="alert">
      <p>{failure.message}</p>
      {failure.conflict && onReload && (
        <Button variant="secondary" onClick={onReload}>
          {reloadLabel}
        </Button>
      )}
    </div>
  )
}

/** Contract rows shared by the list and by the operational views. */
export function ContractTable({
  label,
  rows,
  actions,
}: {
  label: string
  rows: ContractSummary[]
  actions: (row: ContractSummary) => ReactNode
}) {
  return (
    <MasterTable
      label={label}
      headers={['Número', 'Cliente', 'Início', 'Devolução prevista', 'Total', 'Situação', 'Ações']}
    >
      {rows.map((row) => (
        <tr key={row.id}>
          <td className="code-cell">{row.number}</td>
          <td>
            <span className="cell-title">{row.customer.legal_name}</span>
            <span className="cell-description">
              {row.customer.document} · {row.item_count} {row.item_count === 1 ? 'item' : 'itens'}
            </span>
          </td>
          <td className="date-cell">{brDate(row.start_date)}</td>
          <td className="date-cell">{brDate(expectedReturn(row))}</td>
          <td className="date-cell">{brMoney(row.total)}</td>
          <td>
            <ContractBadge status={row.status} />
          </td>
          <td>
            <div className="row-actions">{actions(row)}</div>
          </td>
        </tr>
      ))}
    </MasterTable>
  )
}
