import { useState } from 'react'
import { Network } from 'lucide-react'
import { useAuth } from '../auth/context'
import { pairThisComputer } from '../lib/stations'
import { Button } from '../components/Button'
import { Field } from '../components/ui'
import { Failure } from './masters-shared'

/** A computer of the store network without access: it is paired once with the code shown on
 * the main computer (ADR-025). There is no password: the code is temporary and single use. */
export function Pairing() {
  const { refresh } = useAuth()
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [errors, setErrors] = useState<{ name?: string; code?: string }>({})
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <main className="auth-page">
      <section className="login-card" aria-labelledby="pairing-title">
        <div className="login-brand">
          <Network size={30} aria-hidden="true" />
          <strong>LocaControl</strong>
        </div>
        <p className="eyebrow">REDE DA LOJA</p>
        <h1 id="pairing-title">Conectar este computador à loja</h1>
        <p className="page-description">
          Este computador ainda não tem acesso ao LocaControl desta loja. No computador principal,
          abra <strong>Gestão → Estações da rede</strong>, clique em{' '}
          <strong>Gerar código de pareamento</strong> e digite aqui o código mostrado. Isso é feito
          uma única vez por computador.
        </p>
        <form
          className="form-stack"
          noValidate
          aria-label="Parear estação"
          onSubmit={(event) => {
            event.preventDefault()
            const next = {
              name: name.trim() ? undefined : 'Dê um nome a este computador, como "Balcão 1".',
              code:
                code.replace(/[^A-Za-z0-9]/g, '').length === 8
                  ? undefined
                  : 'O código tem 8 letras e números.',
            }
            setErrors(next)
            if (next.name || next.code) return
            setFailure('')
            setBusy(true)
            void pairThisComputer(code, name.trim())
              .then(() => refresh())
              .catch((e) => {
                setFailure(e instanceof Error ? e.message : 'Não foi possível parear.')
                setBusy(false)
              })
          }}
        >
          <Field
            label="Nome desta estação"
            maxLength={60}
            autoComplete="off"
            value={name}
            error={errors.name}
            hint="Aparece na lista de estações e na auditoria, por exemplo Balcão 1 ou Depósito."
            onChange={(e) => setName(e.target.value)}
          />
          <Field
            label="Código de pareamento"
            maxLength={12}
            autoComplete="off"
            spellCheck={false}
            value={code}
            error={errors.code}
            hint="Vale por 10 minutos e para uma única estação."
            onChange={(e) => setCode(e.target.value.toUpperCase())}
          />
          <Failure message={failure} />
          <Button type="submit" disabled={busy}>
            {busy ? 'Conectando…' : 'Conectar à loja'}
          </Button>
        </form>
      </section>
    </main>
  )
}
