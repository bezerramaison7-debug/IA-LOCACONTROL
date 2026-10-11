import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../lib/api'
import { Button } from './Button'
import { Card } from './ui'
import { CircleCheck, TriangleAlert } from 'lucide-react'

export function HealthPanel() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => getHealth(signal),
    retry: false,
    staleTime: 30_000,
  })
  return (
    <Card
      title="Conexão do ambiente"
      description="Diagnóstico real da aplicação, separado dos exemplos visuais."
    >
      <div className="health-body" aria-busy={health.isFetching}>
        <div aria-live="polite" aria-atomic="true">
          {health.isPending ? (
            <p>Conectando ao servidor…</p>
          ) : health.isError ? (
            <div role="alert" className="health-error">
              <TriangleAlert size={20} aria-hidden="true" />
              <div>
                <strong>Conexão indisponível</strong>
                <p>{health.error.message}</p>
              </div>
            </div>
          ) : (
            <>
              <p className="health-success">
                <CircleCheck size={20} aria-hidden="true" />
                Ambiente conectado
              </p>
              <dl className="health-grid">
                <div>
                  <dt>Servidor</dt>
                  <dd>Disponível</dd>
                </div>
                <div>
                  <dt>Banco de dados</dt>
                  <dd>Conectado</dd>
                </div>
                <div>
                  <dt>Migrations</dt>
                  <dd>Atualizadas</dd>
                </div>
                <div>
                  <dt>Versão</dt>
                  <dd>{health.data.version}</dd>
                </div>
              </dl>
            </>
          )}
        </div>
        <div className="health-footer">
          <p>Esta tela não contém dados comerciais.</p>
          <Button
            variant="secondary"
            disabled={health.isFetching}
            onClick={() => void health.refetch()}
          >
            {health.isFetching ? 'Verificando…' : 'Verificar novamente'}
          </Button>
        </div>
      </div>
    </Card>
  )
}
