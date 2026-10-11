import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { AuthUser } from '../auth/api'
import { useAuth } from '../auth/context'
import { getCustomerLink, setCustomerLink } from '../lib/portal'
import { failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { ErrorState, Skeleton } from '../components/ui'
import { Failure } from './masters-shared'
import { RecordPicker } from './quotes-editor'

/** Links a customer account to the customer whose data it sees in the portal. */
export function CustomerLinkForm({
  account,
  canWrite,
  onDone,
}: {
  account: AuthUser
  canWrite: boolean
  onDone: (message: string) => void
}) {
  const { request } = useAuth()
  const [customerId, setCustomerId] = useState('')
  const [label, setLabel] = useState('')
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  const query = useQuery({
    queryKey: ['users', 'customer-link', account.id],
    queryFn: () => getCustomerLink(request, account.id),
    retry: false,
    gcTime: 0,
  })
  if (query.isPending) return <Skeleton rows={2} />
  if (query.isError)
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
  const current = query.data
  const save = (next: number | null, message: string) => {
    setFailure('')
    setBusy(true)
    void setCustomerLink(request, account.id, next)
      .then(() => onDone(message))
      .catch((e) => {
        setFailure(failureMessage(e, 'Não foi possível salvar o vínculo.'))
        setBusy(false)
      })
  }
  return (
    <div className="form-stack">
      <p>
        Vínculo atual:{' '}
        <strong>{current.customer || 'nenhum — a conta ainda não acessa o portal'}</strong>
      </p>
      {canWrite ? (
        <>
          <RecordPicker
            kind="customers"
            searchLabel="Buscar cliente para vincular"
            label="Cliente do portal"
            placeholder="Selecione um cliente"
            value={customerId}
            knownLabel={label}
            onChange={(id, text) => {
              setCustomerId(id)
              setLabel(text)
            }}
          />
          <p className="quote-notice" role="note">
            A conta passa a ver somente os contratos, orçamentos e documentos do cliente vinculado.
            Trocar ou remover o vínculo encerra as sessões abertas dessa conta e é auditado.
          </p>
          <Failure message={failure} />
          <div className="modal-actions">
            {current.customer_id !== null && (
              <Button
                variant="danger"
                disabled={busy}
                onClick={() => save(null, 'Vínculo removido. A conta deixou de acessar o portal.')}
              >
                Remover vínculo
              </Button>
            )}
            <Button
              disabled={busy || !customerId || Number(customerId) === current.customer_id}
              onClick={() => save(Number(customerId), 'Cliente vinculado à conta.')}
            >
              {busy ? 'Salvando…' : 'Salvar vínculo'}
            </Button>
          </div>
        </>
      ) : (
        <p className="field-hint">Seu perfil pode consultar o vínculo, mas não alterá-lo.</p>
      )}
    </div>
  )
}
