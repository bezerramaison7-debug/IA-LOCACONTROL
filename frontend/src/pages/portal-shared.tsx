import { Ban, CircleCheck, CircleX, Hourglass } from 'lucide-react'
import { periods } from '../lib/masters'
import { requestStatuses, type RequestStatus } from '../lib/portal'
import { Tag } from '../components/ui'

const badges = {
  PENDENTE: ['warning', Hourglass],
  APROVADA: ['success', CircleCheck],
  RECUSADA: ['danger', CircleX],
  CANCELADA: ['muted', Ban],
} as const

/** Renewal request status, shared by the portal and by the internal Renovações page. */
export function RequestBadge({ status }: { status: RequestStatus }) {
  const [tone, icon] = badges[status]
  return (
    <Tag tone={tone} icon={icon}>
      {requestStatuses[status]}
    </Tag>
  )
}

/** "2 × Semanal": the period the customer asked for. */
export function PeriodText({ period, count }: { period: string; count: number }) {
  return (
    <>
      {count} × {periods[period as keyof typeof periods] || period}
    </>
  )
}
