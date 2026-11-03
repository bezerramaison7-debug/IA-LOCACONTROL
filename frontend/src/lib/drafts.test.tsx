import { useState } from 'react'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { DraftNotice } from '../components/DraftNotice'
import { mockRequest, renderPage, type Handler } from '../test/render'
import { ApiError } from '../auth/api'
import { useDraft } from './drafts'

/** A long form reduced to one field; the hook and the notice are the real ones. */
function Form({ onSent }: { onSent?: () => void }) {
  const [notes, setNotes] = useState('')
  const draft = useDraft({
    kind: 'quote',
    scope: 'new',
    value: { notes },
    baseVersion: 3,
    onRestore: (saved) => setNotes(saved.notes),
  })
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        draft.finish()
        onSent?.()
      }}
    >
      <DraftNotice draft={draft} />
      <label>
        Observações
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button type="submit">Enviar</button>
    </form>
  )
}
const stored = {
  kind: 'quote',
  scope: 'new',
  payload: { notes: 'Ligar antes de entregar' },
  base_version: 2,
  created_at: 1789254000,
  updated_at: 1789254000,
  expires_at: 1789858800,
}
const draftWrites = (request: ReturnType<typeof mockRequest>) =>
  request.mock.calls.filter(
    ([path, method]) => path === '/drafts/quote/new' && !!method && method !== 'GET',
  )

function setup(handler: Handler) {
  const request = mockRequest(handler)
  renderPage(<Form />, request)
  return request
}

it('offers the stored draft and saves nothing until it is recovered or discarded', async () => {
  const user = userEvent.setup()
  const request = setup((_path, method) =>
    method === 'GET' ? { draft: stored } : { draft: { ...stored, payload: {} } },
  )
  const offer = await screen.findByRole('region', { name: 'Rascunho encontrado' })
  expect(offer).toHaveTextContent('Nada dele foi gravado nos registros')
  expect(offer).toHaveTextContent('o registro foi alterado depois deste rascunho')
  expect(offer).toHaveTextContent('expiram 7 dias')
  await user.type(screen.getByLabelText('Observações'), 'x')
  await new Promise((resolve) => setTimeout(resolve, 1400))
  expect(draftWrites(request)).toEqual([]) // o rascunho guardado não é sobrescrito
  await user.click(screen.getByRole('button', { name: 'Recuperar rascunho' }))
  expect(screen.getByLabelText('Observações')).toHaveValue('Ligar antes de entregar')
  expect(screen.queryByRole('region', { name: 'Rascunho encontrado' })).toBeNull()
})

it('saves after a pause, keeps the form on failure and stops after the real send', async () => {
  const user = userEvent.setup()
  let fail = true
  const request = setup((_path, method) => {
    if (method === 'GET') return { draft: null }
    if (method === 'PUT' && fail) {
      fail = false
      throw new Error('Não foi possível conectar.')
    }
    return method === 'PUT' ? { draft: stored } : undefined
  })
  await user.type(screen.getByLabelText('Observações'), 'Entregar às 8h')
  expect(
    await screen.findByText(/Rascunho não salvo agora/, {}, { timeout: 3000 }),
  ).toBeInTheDocument()
  expect(screen.getByLabelText('Observações')).toHaveValue('Entregar às 8h')
  await user.type(screen.getByLabelText('Observações'), '!')
  expect(
    await screen.findByText(/Rascunho salvo automaticamente às/, {}, { timeout: 3000 }),
  ).toBeInTheDocument()
  const saved = draftWrites(request).filter(([, method]) => method === 'PUT')
  expect(saved.at(-1)![2]).toEqual({ payload: { notes: 'Entregar às 8h!' }, base_version: 3 })
  await user.click(screen.getByRole('button', { name: 'Enviar' }))
  await waitFor(() => expect(draftWrites(request).at(-1)).toEqual(['/drafts/quote/new', 'DELETE']))
  const count = draftWrites(request).length
  await user.type(screen.getByLabelText('Observações'), ' depois')
  await new Promise((resolve) => setTimeout(resolve, 1400))
  expect(draftWrites(request)).toHaveLength(count)
})

it('discarding removes the stored draft and starts a clean form', async () => {
  const user = userEvent.setup()
  const request = setup((_path, method) => (method === 'GET' ? { draft: stored } : undefined))
  await user.click(await screen.findByRole('button', { name: 'Descartar rascunho' }))
  expect(draftWrites(request)).toEqual([['/drafts/quote/new', 'DELETE']])
  expect(screen.getByLabelText('Observações')).toHaveValue('')
})

it('after a session renewal the draft is saved again at once (a draft save is repeatable)', async () => {
  const user = userEvent.setup()
  let renewed = false
  const request = setup((_path, method) => {
    if (method === 'GET') return { draft: null }
    if (method === 'PUT' && !renewed) {
      renewed = true
      throw new ApiError(401, 'Sessão renovada.', true, 'renewed')
    }
    return { draft: stored }
  })
  await user.type(screen.getByLabelText('Observações'), 'Depois da sessão')
  expect(
    await screen.findByText(/Rascunho salvo automaticamente às/, {}, { timeout: 4000 }),
  ).toBeInTheDocument()
  expect(screen.queryByText(/Rascunho não salvo agora/)).toBeNull()
  expect(draftWrites(request).filter(([, method]) => method === 'PUT')).toHaveLength(2)
})
