import { useCallback, useEffect, useRef, useState } from 'react'
import { z } from 'zod'
import { useAuth } from '../auth/context'

/** Automatic drafts (ADR-024): the form as typed, kept on the server apart from the records.
 * A draft never moves stock, confirms a contract or issues a document: only the form that
 * saved it reads it back, and the user decides whether to recover or discard it. */
export type DraftKind = 'quote' | 'contract' | 'withdrawal' | 'return' | 'renewal'

const draftSchema = z.object({
  kind: z.string(),
  scope: z.string(),
  payload: z.record(z.string(), z.unknown()),
  base_version: z.number().nullable(),
  created_at: z.number(),
  updated_at: z.number(),
  expires_at: z.number(),
})
const readSchema = z.object({ draft: draftSchema.nullable() })
export type Draft = z.infer<typeof draftSchema>

/** Saves this long after the last change; a save is a replacement, so repeating it is safe. */
export const DRAFT_DELAY_MS = 1200
/** After a failed save (server down, maintenance) the next attempt waits this long. */
export const DRAFT_RETRY_MS = 10_000

export type DraftState =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'saved'; at: number }
  | { kind: 'error'; message: string }

const path = (kind: DraftKind, scope: string) => '/drafts/' + kind + '/' + scope

export function useDraft<T extends object>({
  kind,
  scope,
  value,
  baseVersion,
  onRestore,
  enabled = true,
}: {
  kind: DraftKind
  /** "new" or the id of the record the form edits or operates on. */
  scope: string
  value: T
  baseVersion?: number
  onRestore: (payload: T) => void
  enabled?: boolean
}) {
  const { request } = useAuth()
  const [offer, setOffer] = useState<Draft | null>(null)
  const [state, setState] = useState<DraftState>({ kind: 'idle' })
  // Nothing is saved until the user changes something and the stored draft, if any, has been
  // recovered or discarded: the empty form never overwrites what was typed before.
  const [decided, setDecided] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const serialized = JSON.stringify(value)
  const [initial, setInitial] = useState(serialized)
  const done = useRef(false)
  const retry = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (!enabled) return
    let active = true
    void Promise.resolve()
      .then(() => request(path(kind, scope)))
      .then((raw) => {
        if (!active) return
        const found = readSchema.safeParse(raw)
        if (found.success && found.data.draft) setOffer(found.data.draft)
        else setDecided(true)
      })
      .catch(() => {
        // No draft service (or offline): the form works as before, without recovery.
        if (active) setDecided(true)
      })
    return () => {
      active = false
    }
  }, [enabled, kind, scope, request])

  useEffect(() => {
    if (!enabled || !decided || done.current || serialized === initial) return
    const timer = setTimeout(() => {
      setState({ kind: 'saving' })
      request(path(kind, scope), 'PUT', {
        payload: JSON.parse(serialized),
        base_version: baseVersion ?? null,
      })
        .then(() => {
          if (!done.current) setState({ kind: 'saved', at: Date.now() })
        })
        .catch((error) => {
          if (done.current) return
          setState({
            kind: 'error',
            message:
              'Rascunho não salvo agora (' +
              (error instanceof Error ? error.message : 'sem conexão') +
              '). O formulário continua aberto; nova tentativa em instantes.',
          })
          clearTimeout(retry.current)
          retry.current = setTimeout(() => setAttempt((n) => n + 1), DRAFT_RETRY_MS)
        })
    }, DRAFT_DELAY_MS)
    return () => clearTimeout(timer)
  }, [enabled, decided, serialized, initial, attempt, baseVersion, kind, scope, request])

  useEffect(() => () => clearTimeout(retry.current), [])

  const restore = useCallback(() => {
    if (!offer) return
    onRestore(offer.payload as T)
    setDecided(true)
    setOffer(null)
    setState({ kind: 'saved', at: offer.updated_at * 1000 })
  }, [offer, onRestore])

  const discard = useCallback(() => {
    setDecided(true)
    setOffer(null)
    setState({ kind: 'idle' })
    setInitial(serialized)
    void Promise.resolve()
      .then(() => request(path(kind, scope), 'DELETE'))
      .catch(() => undefined)
  }, [serialized, kind, scope, request])

  /** After the definitive operation succeeded: stop saving and remove the draft. */
  const finish = useCallback(() => {
    done.current = true
    clearTimeout(retry.current)
    void Promise.resolve()
      .then(() => request(path(kind, scope), 'DELETE'))
      .catch(() => undefined)
  }, [kind, scope, request])

  return {
    offer,
    state,
    restore,
    discard,
    finish,
    /** The record changed after the draft was saved: recovering needs a careful review. */
    outdated: !!offer && baseVersion !== undefined && offer.base_version !== baseVersion,
  }
}
export type DraftControl = ReturnType<typeof useDraft>
