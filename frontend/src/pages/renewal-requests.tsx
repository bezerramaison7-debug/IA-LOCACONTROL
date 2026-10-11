import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { actionError, useContractPermissions, type ActionError } from '../lib/contracts'
import {
  decideRequest,
  listRenewalRequests,
  requestStatuses,
  type Decision,
  type InternalRequest,
} from '../lib/portal'
import { brDateTime } from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { ActionFailure } from './contracts-shared'
import { MasterTable, Pager } from './masters-shared'
import { PeriodText, RequestBadge } from './portal-shared'

const renewLink = (row: InternalRequest) => '/contratos?id=' + row.contract_id + '&acao=renovar'

function DecisionDialog({
  row,
  decision,
  onClose,
  onDone,
}: {
  row: InternalRequest
  decision: Decision
  onClose: () => void
  onDone: (row: InternalRequest) => void
}) {
  const { request } = useAuth()
  const [reason, setReason] = useState('')
  const [reasonError, setReasonError] = useState('')
  const [failure, setFailure] = useState<ActionError | null>(null)
  const [busy, setBusy] = useState(false)
  const approving = decision === 'APROVADA'
  return (
    <Modal
      open
      onOpenChange={(open) => !open && onClose()}
      title={approving ? 'Aprovar solicitação' : 'Recusar solicitação'}
      description={'Contrato ' + row.contract_number + ' · ' + row.customer}
    >
      <form
        className="form-stack"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          if (!approving && reason.trim().length < 5) {
            setReasonError('Informe o motivo da recusa com pelo menos 5 caracteres.')
            return
          }
          setReasonError('')
          setFailure(null)
          setBusy(true)
          void decideRequest(request, row.id, decision, reason)
            .then(onDone)
            .catch((e) => {
              setFailure(actionError(e, 'Não foi possível registrar a decisão.'))
              setBusy(false)
            })
        }}
      >
        {approving ? (
          <p className="quote-notice" role="note">
            Aprovar NÃO cria a renovação. A aprovação apenas registra a decisão e avisa o cliente; o
            contrato continua igual até você renová-lo em “Renovar contrato”.
          </p>
        ) : (
          <p className="quote-notice" role="note">
            O cliente verá a recusa e o motivo no portal. O contrato não é alterado.
          </p>
        )}
        <Field
          label={approving ? 'Observação para o cliente (opcional)' : 'Motivo da recusa'}
          maxLength={500}
          autoComplete="off"
          value={reason}
          error={reasonError}
          onChange={(e) => setReason(e.target.value)}
        />
        <ActionFailure failure={failure} />
        <div className="modal-actions">
          <Button variant="secondary" onClick={onClose}>
            Voltar
          </Button>
          <Button type="submit" variant={approving ? 'primary' : 'danger'} disabled={busy}>
            {busy ? 'Salvando…' : approving ? 'Confirmar aprovação' : 'Confirmar recusa'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** Renewal requests sent by customers through the portal, decided by the rental company. */
export function RenewalRequests() {
  const { request } = useAuth()
  const can = useContractPermissions()
  const cache = useQueryClient()
  const toast = useToast()
  const [status, setStatus] = useState('PENDENTE')
  const [offset, setOffset] = useState(0)
  const [dialog, setDialog] = useState<{ row: InternalRequest; decision: Decision } | null>(null)
  const [approved, setApproved] = useState<InternalRequest | null>(null)
  const query = useQuery({
    queryKey: ['renewal-requests', status, offset],
    queryFn: () => listRenewalRequests(request, status, offset),
    retry: false,
  })
  return (
    <Card
      title="Solicitações de renovação dos clientes"
      description="Pedidos enviados pelo portal. Aprovar não renova o contrato: a renovação é feita por você, em seguida."
    >
      <div className="master-filters">
        <Select
          label="Situação das solicitações"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value)
            setOffset(0)
          }}
        >
          <option value="">Todas</option>
          {Object.entries(requestStatuses).map(([key, text]) => (
            <option key={key} value={key}>
              {text}
            </option>
          ))}
        </Select>
      </div>
      {approved && (
        <div className="padded">
          <div className="quote-notice" role="status">
            <span>
              Solicitação do contrato {approved.contract_number} aprovada. A renovação ainda não foi
              criada.
            </span>
            {can.write && (
              <Button asChild>
                <Link to={renewLink(approved)}>Renovar contrato {approved.contract_number}</Link>
              </Button>
            )}
          </div>
        </div>
      )}
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : !query.data.items.length ? (
        <EmptyState
          initial
          title={
            status === 'PENDENTE' ? 'Nenhuma solicitação em análise' : 'Nenhuma solicitação aqui'
          }
          description="Os pedidos de renovação feitos pelos clientes no portal aparecem nesta lista."
        />
      ) : (
        <>
          <MasterTable
            label="Solicitações de renovação"
            headers={['Contrato', 'Cliente', 'Período pedido', 'Enviada em', 'Situação', 'Ações']}
          >
            {query.data.items.map((row) => (
              <tr key={row.id}>
                <td className="code-cell">
                  <Link
                    to={'/contratos?id=' + row.contract_id}
                    aria-label={'Abrir contrato ' + row.contract_number}
                  >
                    {row.contract_number}
                  </Link>
                </td>
                <td>{row.customer}</td>
                <td>
                  <PeriodText period={row.period} count={row.period_count} />
                  {row.notes && <span className="cell-description">{row.notes}</span>}
                </td>
                <td className="date-cell">{brDateTime(row.created_at)}</td>
                <td>
                  <RequestBadge status={row.status} />
                  {row.decision_reason && (
                    <span className="cell-description">{row.decision_reason}</span>
                  )}
                </td>
                <td>
                  <div className="row-actions">
                    {row.status === 'PENDENTE' && can.write && (
                      <>
                        <Button
                          variant="secondary"
                          aria-label={'Aprovar solicitação do contrato ' + row.contract_number}
                          onClick={() => setDialog({ row, decision: 'APROVADA' })}
                        >
                          Aprovar
                        </Button>
                        <Button
                          variant="ghost"
                          aria-label={'Recusar solicitação do contrato ' + row.contract_number}
                          onClick={() => setDialog({ row, decision: 'RECUSADA' })}
                        >
                          Recusar
                        </Button>
                      </>
                    )}
                    {row.status === 'APROVADA' && can.write && (
                      <Button asChild variant="secondary">
                        <Link
                          to={renewLink(row)}
                          aria-label={'Renovar contrato ' + row.contract_number}
                        >
                          Renovar contrato
                        </Link>
                      </Button>
                    )}
                    {row.status === 'PENDENTE' && !can.write && <span>Somente consulta</span>}
                  </div>
                </td>
              </tr>
            ))}
          </MasterTable>
          <Pager total={query.data.total} offset={offset} onChange={setOffset} />
        </>
      )}
      {dialog && (
        <DecisionDialog
          key={dialog.row.id + dialog.decision}
          row={dialog.row}
          decision={dialog.decision}
          onClose={() => setDialog(null)}
          onDone={(row) => {
            setDialog(null)
            setApproved(row.status === 'APROVADA' ? row : null)
            toast(
              row.status === 'APROVADA'
                ? 'Solicitação aprovada. Falta renovar o contrato.'
                : 'Solicitação recusada.',
            )
            void cache.invalidateQueries({ queryKey: ['renewal-requests'] })
          }}
        />
      )}
    </Card>
  )
}
