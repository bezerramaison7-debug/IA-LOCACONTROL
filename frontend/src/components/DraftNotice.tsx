import { Button } from './Button'
import type { DraftControl } from '../lib/drafts'
import { brDateTime } from '../lib/quotes'

/** Recovery offer for a stored draft, then a quiet line saying whether the draft is saved. */
export function DraftNotice({ draft }: { draft: DraftControl }) {
  if (draft.offer)
    return (
      <div className="quote-notice draft-offer" role="region" aria-label="Rascunho encontrado">
        <strong>
          Há um rascunho salvo automaticamente em {brDateTime(draft.offer.updated_at)}.
        </strong>
        <span>
          Ele guarda o que foi digitado e ainda não foi enviado. Nada dele foi gravado nos
          registros: recupere para continuar de onde parou ou descarte para começar de novo.
          {draft.outdated &&
            ' Atenção: o registro foi alterado depois deste rascunho; confira tudo antes de enviar.'}{' '}
          Rascunhos expiram 7 dias depois da última alteração.
        </span>
        <div className="row-actions">
          <Button type="button" onClick={draft.restore}>
            Recuperar rascunho
          </Button>
          <Button type="button" variant="secondary" onClick={draft.discard}>
            Descartar rascunho
          </Button>
        </div>
      </div>
    )
  const { state } = draft
  if (state.kind === 'idle') return null
  return (
    <p
      className={'draft-status' + (state.kind === 'error' ? ' draft-status-error' : '')}
      role="status"
    >
      {state.kind === 'saving'
        ? 'Salvando rascunho…'
        : state.kind === 'saved'
          ? 'Rascunho salvo automaticamente às ' +
            new Date(state.at).toLocaleTimeString('pt-BR', { timeStyle: 'short' }) +
            '. Ele não é um registro: envie o formulário para concluir.'
          : state.message}
    </p>
  )
}
