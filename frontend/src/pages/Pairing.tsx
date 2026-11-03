import { useState } from 'react'
import { Network } from 'lucide-react'
import { useAuth } from '../auth/context'
import { codeFromAddress, codeLength, pairThisComputer } from '../lib/stations'
import { Button } from '../components/Button'
import { Field } from '../components/ui'
import { Failure } from './masters-shared'

/** A computer of the store network without access: it is paired once with the code shown on
 * the main computer (ADR-025). There is no password: the code is temporary and single use. */
export function Pairing() {
  const { refresh } = useAuth()
  const [name, setName] = useState('')
  const [code, setCode] = useState(codeFromAddress)
  const plain = window.location.protocol !== 'https:'
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
        {plain && (
          <div className="quote-notice quote-notice-danger" role="alert">
            <strong>Esta conexão não é segura.</strong>
            <span>As estações só se conectam por HTTPS. Use o instalador "Conectar à loja".</span>
          </div>
        )}
        <p className="page-description">
          Este computador ainda não tem acesso ao LocaControl desta loja. No computador principal,
          abra <strong>Gestão → Estações da rede</strong>, clique em{' '}
          <strong>Gerar código de pareamento</strong> e digite aqui o código mostrado. Isso é feito
          uma única vez por computador.
        </p>
        <p className="draft-status">
          O caminho seguro é o instalador do LocaControl nesta estação, opção{' '}
          <strong>Conectar à loja</strong>: ele confere a identidade do computador principal com o
          código antes de confiar no certificado e já abre esta tela com o código preenchido. Não
          ignore avisos de certificado do navegador.
        </p>
        <form
          className="form-stack"
          noValidate
          aria-label="Parear estação"
          onSubmit={(event) => {
            event.preventDefault()
            const next = {
              name: !name.trim()
                ? 'Dê um nome a este computador, como "Balcão 1".'
                : /^[\p{L}\p{N}_ .-]{1,40}$/u.test(name.trim())
                  ? undefined
                  : 'Use até 40 letras, números, espaços, ponto, hífen ou sublinhado.',
              code:
                codeLength(code) >= 13 && codeLength(code) <= 40
                  ? undefined
                  : 'Digite o código inteiro mostrado no computador principal (26 letras e números).',
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
            maxLength={40}
            autoComplete="off"
            value={name}
            error={errors.name}
            hint="Aparece na lista de estações e na auditoria, por exemplo Balcão 1 ou Depósito. Até 40 caracteres; não pode repetir o nome de outra estação ativa."
            onChange={(e) => setName(e.target.value)}
          />
          <Field
            label="Código de pareamento"
            maxLength={60}
            autoComplete="off"
            spellCheck={false}
            value={code}
            error={errors.code}
            hint="26 letras e números em grupos de 4. Vale por 10 minutos e para uma única estação."
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
