import {
  CircleCheck,
  Clock3,
  CircleX,
  CircleMinus,
  TriangleAlert,
  Info,
  SearchX,
  RefreshCw,
  Inbox,
} from 'lucide-react'
import type { ReactNode, InputHTMLAttributes, SelectHTMLAttributes } from 'react'
import { useId } from 'react'
import { Button } from './Button'

export type Status =
  | 'Ativo'
  | 'Vencendo'
  | 'Vencido'
  | 'Encerrado'
  | 'Cancelado'
  | 'Disponível'
  | 'Manutenção'
  | 'Rascunho'
const statusMap = {
  Ativo: ['success', CircleCheck],
  Disponível: ['success', CircleCheck],
  Vencendo: ['warning', Clock3],
  Manutenção: ['warning', TriangleAlert],
  Vencido: ['danger', TriangleAlert],
  Cancelado: ['muted', CircleX],
  Encerrado: ['muted', CircleCheck],
  Rascunho: ['info', CircleMinus],
} as const

export function Badge({ status }: { status: Status }) {
  const [tone, Icon] = statusMap[status]
  return (
    <span className={`badge badge-${tone}`}>
      <Icon size={14} aria-hidden="true" />
      {status}
    </span>
  )
}

export function Card({
  children,
  className = '',
  title,
  description,
  action,
}: {
  children: ReactNode
  className?: string
  title?: string
  description?: string
  action?: ReactNode
}) {
  const id = useId()
  return (
    <section className={`card ${className}`} aria-labelledby={title ? id : undefined}>
      {title && (
        <div className="card-heading">
          <div>
            <h2 id={id}>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Field({
  label,
  error,
  hint,
  id,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }) {
  const generated = useId()
  const fieldId = id || generated
  return (
    <div className="field">
      <label htmlFor={fieldId}>{label}</label>
      <input
        id={fieldId}
        aria-invalid={!!error}
        aria-describedby={error || hint ? `${fieldId}-help` : undefined}
        {...props}
      />
      {(error || hint) && (
        <p className={error ? 'field-error' : 'field-hint'} id={`${fieldId}-help`}>
          {error || hint}
        </p>
      )}
    </div>
  )
}

export function Select({
  label,
  id,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label: string; children: ReactNode }) {
  const generated = useId()
  const fieldId = id || generated
  return (
    <div className="field">
      <label htmlFor={fieldId}>{label}</label>
      <select id={fieldId} {...props}>
        {children}
      </select>
    </div>
  )
}

export function EmptyState({
  title = 'Nenhum resultado encontrado',
  description = 'Experimente outro termo ou ajuste os filtros.',
  action,
  initial = false,
}: {
  title?: string
  description?: string
  action?: ReactNode
  initial?: boolean
}) {
  const Icon = initial ? Inbox : SearchX
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={28} aria-hidden="true" />
      </span>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <TriangleAlert size={24} aria-hidden="true" />
      <div>
        <h3>Não foi possível carregar</h3>
        <p>{message}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={16} aria-hidden="true" />
          Tentar novamente
        </Button>
      )}
    </div>
  )
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-group" role="status" aria-label="Carregando conteúdo">
      <span className="sr-only">Carregando conteúdo…</span>
      {Array.from({ length: rows }, (_, i) => (
        <div aria-hidden="true" className="skeleton" key={i} />
      ))}
    </div>
  )
}

export function DemoNotice() {
  return (
    <div className="demo-notice">
      <Info size={16} aria-hidden="true" />
      <p>
        <strong>Modo demonstração</strong>
        <span> · Dados fictícios para avaliação visual. Nenhuma operação comercial é salva.</span>
      </p>
    </div>
  )
}

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
}: {
  title: string
  description: string
  eyebrow?: string
  actions?: ReactNode
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}
