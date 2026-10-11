import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useAuth } from '../auth/context'
import { useToast } from '../components/toast-context'
import { Button } from '../components/Button'
import { Card, Field, PageHeader } from '../components/ui'

export function Profile() {
  const { user, request, refresh, clear } = useAuth()
  const toast = useToast()
  const [error, setError] = useState('')
  const profile = useForm<{ name: string }>({ defaultValues: { name: user?.name } })
  const passwords = useForm<{ current: string; password: string; confirmation: string }>()
  if (!user) return null
  return (
    <>
      <PageHeader title="Meu perfil" description="Seus dados e a segurança da sua conta." />
      {user.must_change_password && (
        <div className="error-state" role="alert">
          Para continuar, substitua a senha temporária por uma senha pessoal.
        </div>
      )}
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <div className="security-grid">
        <Card title="Dados da conta" description={`Usuário: ${user.username}`}>
          <form
            className="form-stack padded"
            onSubmit={profile.handleSubmit(async ({ name }) => {
              setError('')
              try {
                await request('/auth/me', 'PATCH', { name })
                await refresh()
                toast('Perfil atualizado.')
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Erro ao salvar.')
              }
            })}
          >
            <Field
              label="Nome completo"
              maxLength={120}
              {...profile.register('name', {
                required: 'Informe seu nome.',
                minLength: { value: 2, message: 'Informe pelo menos 2 caracteres.' },
              })}
              error={profile.formState.errors.name?.message}
            />
            <p>Perfis: {user.role_codes.join(', ')}</p>
            <Button type="submit" disabled={profile.formState.isSubmitting}>
              Salvar perfil
            </Button>
          </form>
        </Card>
        <Card
          title="Alterar senha"
          description="Use de 12 a 128 caracteres. Todas as sessões serão encerradas."
        >
          <form
            className="form-stack padded"
            onSubmit={passwords.handleSubmit(async ({ current, password }) => {
              setError('')
              try {
                await request('/auth/password', 'POST', {
                  current_password: current,
                  new_password: password,
                })
                passwords.reset()
                clear()
                toast('Senha alterada. Entre novamente.')
              } catch (e) {
                setError(e instanceof Error ? e.message : 'Erro ao alterar senha.')
              }
            })}
          >
            <Field
              label="Senha atual"
              type="password"
              autoComplete="current-password"
              maxLength={128}
              {...passwords.register('current', { required: 'Informe a senha atual.' })}
              error={passwords.formState.errors.current?.message}
            />
            <Field
              label="Nova senha"
              type="password"
              autoComplete="new-password"
              maxLength={128}
              {...passwords.register('password', {
                required: 'Informe a nova senha.',
                minLength: { value: 12, message: 'Use pelo menos 12 caracteres.' },
              })}
              error={passwords.formState.errors.password?.message}
            />
            <Field
              label="Confirmar nova senha"
              type="password"
              autoComplete="new-password"
              maxLength={128}
              {...passwords.register('confirmation', {
                validate: (value) =>
                  value === passwords.getValues('password') || 'As senhas não conferem.',
              })}
              error={passwords.formState.errors.confirmation?.message}
            />
            <Button type="submit" disabled={passwords.formState.isSubmitting}>
              Alterar senha
            </Button>
          </form>
        </Card>
      </div>
    </>
  )
}
