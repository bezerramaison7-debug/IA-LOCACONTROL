import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { downloadDocument, expectedReturn } from '../lib/contracts'
import { getCustomerSummary } from '../lib/reports'
import { brDate, brDateTime, brMoney, brQuantity, failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { EmptyState, ErrorState, Skeleton } from '../components/ui'
import { ContractBadge, DocumentBadge } from './contracts-shared'
import { Failure, MasterTable } from './masters-shared'

/** Customer page: what the customer holds now and the full contract and document history. */
export function CustomerSummary({ customerId, name }: { customerId: number; name: string }) {
  const { request } = useAuth()
  const [downloading, setDownloading] = useState<number | null>(null)
  const [error, setError] = useState('')
  const query = useQuery({
    queryKey: ['customers', 'summary', customerId],
    queryFn: () => getCustomerSummary(request, customerId),
    retry: false,
  })
  if (query.isPending) return <Skeleton rows={4} />
  if (query.isError)
    return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
  const data = query.data
  return (
    <div className="form-stack">
      <dl className="master-details">
        <div>
          <dt>Contratos ativos</dt>
          <dd>{data.active_contracts}</dd>
        </div>
        <div>
          <dt>Total de contratos</dt>
          <dd>{data.total_contracts}</dd>
        </div>
        <div>
          <dt>Itens locados agora</dt>
          <dd>{brQuantity(data.rented_items)}</dd>
        </div>
        <div>
          <dt>Valor contratado (contratos ativos)</dt>
          <dd>{brMoney(data.contracted_value)}</dd>
        </div>
      </dl>
      <p className="field-hint">
        Valor contratado é a soma dos contratos ativos conforme combinado; não representa pagamentos
        recebidos.
      </p>
      <section className="form-stack" aria-label="Histórico de contratos">
        <h3>Histórico de contratos</h3>
        {data.contracts.length ? (
          <MasterTable
            label={'Contratos de ' + name}
            headers={['Número', 'Início', 'Devolução prevista', 'Total', 'Situação']}
          >
            {data.contracts.map((row) => (
              <tr key={row.id}>
                <td className="code-cell">
                  <Link to={'/contratos?id=' + row.id} aria-label={'Abrir contrato ' + row.number}>
                    {row.number}
                  </Link>
                </td>
                <td className="date-cell">{brDate(row.start_date)}</td>
                <td className="date-cell">{brDate(expectedReturn(row))}</td>
                <td className="date-cell">{brMoney(row.total)}</td>
                <td>
                  <ContractBadge status={row.status} />
                </td>
              </tr>
            ))}
          </MasterTable>
        ) : (
          <EmptyState
            initial
            title="Nenhum contrato para este cliente"
            description="Os contratos aparecem aqui assim que forem criados."
          />
        )}
      </section>
      <section className="form-stack" aria-label="Documentos">
        <h3>Documentos</h3>
        <Failure message={error} />
        {data.documents.length ? (
          <MasterTable
            label={'Documentos de ' + name}
            headers={['Contrato', 'Versão', 'Gerado em', 'Situação', 'Ações']}
          >
            {data.documents.map((document) => (
              <tr key={document.id}>
                <td className="code-cell">{document.contract_number}</td>
                <td>v{document.version}</td>
                <td className="date-cell">{brDateTime(document.created_at)}</td>
                <td>
                  <DocumentBadge status={document.status} />
                </td>
                <td>
                  <Button
                    variant="ghost"
                    disabled={downloading !== null}
                    aria-label={
                      'Baixar documento do contrato ' +
                      document.contract_number +
                      ', versão ' +
                      document.version
                    }
                    onClick={() => {
                      setError('')
                      setDownloading(document.id)
                      void downloadDocument({ number: document.contract_number }, document)
                        .catch((e) =>
                          setError(failureMessage(e, 'Não foi possível baixar o documento.')),
                        )
                        .finally(() => setDownloading(null))
                    }}
                  >
                    {downloading === document.id ? 'Baixando…' : 'Baixar PDF'}
                  </Button>
                </td>
              </tr>
            ))}
          </MasterTable>
        ) : (
          <EmptyState
            initial
            title="Nenhum documento gerado"
            description="Os PDFs de contrato gerados para este cliente aparecem aqui."
          />
        )}
      </section>
    </div>
  )
}
