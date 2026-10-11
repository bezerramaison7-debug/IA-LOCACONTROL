import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { Card, EmptyState, PageHeader } from '../components/ui'
import { Button } from '../components/Button'

export function Placeholder({ title }: { title?: string }) {
  return (
    <>
      <PageHeader
        title={title || 'Página não encontrada'}
        description={
          title
            ? 'Esta área faz parte do plano de evolução do LocaControl.'
            : 'O endereço informado não corresponde a uma página disponível.'
        }
      />
      <Card>
        <EmptyState
          initial
          title={title ? 'Disponível em uma próxima etapa' : 'Vamos voltar ao início?'}
          description={
            title
              ? 'A navegação está preparada. As funcionalidades desta área serão implementadas na etapa correspondente.'
              : 'Use o menu para encontrar uma área ou retorne ao dashboard.'
          }
          action={
            <Button asChild variant="secondary">
              <Link to="/">
                <ArrowLeft size={17} aria-hidden="true" />
                Voltar ao dashboard
              </Link>
            </Button>
          }
        />
      </Card>
    </>
  )
}
