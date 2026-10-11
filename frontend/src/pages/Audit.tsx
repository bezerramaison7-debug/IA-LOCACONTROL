import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../auth/context'
import { auditSchema } from '../auth/api'
import { Button } from '../components/Button'
import { Card, EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui'

export function Audit() {
  const { user, request } = useAuth()
  const [offset, setOffset] = useState(0)
  const query = useQuery({
    queryKey: ['audit', user?.id, offset],
    retry: false,
    queryFn: async () => auditSchema.parse(await request(`/audit-logs?offset=${offset}&limit=20`)),
  })
  return (
    <>
      <PageHeader
        title="Auditoria"
        description="Histórico real de acesso e alterações administrativas. Senhas e tokens não são registrados."
        actions={
          <Button variant="secondary" onClick={() => void query.refetch()}>
            Atualizar histórico
          </Button>
        }
      />
      <Card title="Eventos de segurança">
        {query.isPending ? (
          <Skeleton />
        ) : query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhum evento registrado" />
        ) : (
          <>
            <div
              className="table-scroll"
              tabIndex={0}
              role="region"
              aria-label="Histórico de auditoria"
            >
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Data e hora</th>
                    <th>Responsável</th>
                    <th>Ação</th>
                    <th>Registro</th>
                    <th>Alterações</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((event) => (
                    <tr key={event.id}>
                      <td>{new Date(event.occurred_at * 1000).toLocaleString('pt-BR')}</td>
                      <td>{event.actor}</td>
                      <td>{event.action}</td>
                      <td>
                        {event.entity} {event.entity_id ? `#${event.entity_id}` : ''}
                      </td>
                      <td>
                        {Object.keys(event.changes).length ? (
                          <details>
                            <summary>Ver alterações</summary>
                            <pre className="audit-details">
                              {JSON.stringify(event.changes, null, 2)}
                            </pre>
                          </details>
                        ) : (
                          'Sem campos alterados'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span>{query.data.total} eventos · Horário local do navegador</span>
              <div className="pagination">
                <Button
                  variant="secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 20))}
                >
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  disabled={offset + 20 >= query.data.total}
                  onClick={() => setOffset(offset + 20)}
                >
                  Próxima
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </>
  )
}
