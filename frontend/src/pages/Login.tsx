import { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { Boxes, LockKeyhole } from 'lucide-react'
import { canOpen, homePath, useAuth } from '../auth/context'
import { Button } from '../components/Button'
import { Field } from '../components/ui'
import { ThemeSelect } from '../components/ThemeSelect'

export function Login() {
  const { user, local, login, loading } = useAuth()
  const location = useLocation()
  const [error, setError] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<{ username: string; password: string }>()
  const requested: unknown = location.state?.from
  const target =
    typeof requested === 'string' &&
    requested.startsWith('/') &&
    !requested.startsWith('//') &&
    requested !== '/login'
      ? requested
      : '/'
  // Local edition: no login screen; the app enters by itself or shows the connection error.
  if (local) return <Navigate to="/" replace />
  if (user) {
    const home = homePath(user)
    return (
      <Navigate
        to={
          user.must_change_password
            ? '/perfil'
            : target !== '/' && target !== '/perfil' && canOpen(user, target)
              ? target
              : canOpen(user, home)
                ? home
                : '/perfil'
        }
        replace
      />
    )
  }
  return (
    <main className="auth-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="login-brand">
          <Boxes size={30} aria-hidden="true" />
          <strong>LocaControl</strong>
        </div>
        <p className="eyebrow">SEU AMBIENTE DE TRABALHO</p>
        <h1 id="login-title">Entrar na sua conta</h1>
        <p className="page-description">Use o usuário criado pelo administrador do ambiente.</p>
        <form
          className="form-stack"
          onSubmit={handleSubmit(async ({ username, password }) => {
            setError('')
            try {
              await login(username, password)
            } catch (error) {
              setError(error instanceof Error ? error.message : 'Não foi possível entrar.')
            }
          })}
        >
          <Field
            label="Usuário"
            autoComplete="username"
            maxLength={80}
            {...register('username', { required: 'Informe seu usuário.' })}
            error={errors.username?.message}
          />
          <Field
            label="Senha"
            type="password"
            autoComplete="current-password"
            maxLength={128}
            {...register('password', { required: 'Informe sua senha.' })}
            error={errors.password?.message}
          />
          {error && (
            <p role="alert" className="field-error">
              {error}
            </p>
          )}
          <Button disabled={isSubmitting || loading} type="submit">
            <LockKeyhole size={18} aria-hidden="true" />
            {isSubmitting ? 'Entrando…' : 'Entrar'}
          </Button>
        </form>
        <details className="login-help">
          <summary>Primeiro acesso ou esqueceu a senha?</summary>
          <p>
            O responsável por este computador deve abrir o terminal na pasta do LocaControl e
            executar o comando de criação ou recuperação. A senha é informada de forma oculta no
            terminal.
          </p>
          <p>Primeiro administrador:</p>
          <code>powershell -ExecutionPolicy Bypass -File scripts/admin.ps1</code>
          <p>Recuperação local:</p>
          <code>powershell -ExecutionPolicy Bypass -File scripts/admin.ps1 -Action recover</code>
        </details>
        <ThemeSelect />
      </section>
    </main>
  )
}
