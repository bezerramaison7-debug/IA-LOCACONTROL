import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useAuth } from '../auth/context'
import { usersSchema, type AuthUser } from '../auth/api'
import { Button } from '../components/Button'
import { Modal, ConfirmDialog } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'

const roleOptions = ['ADMINISTRADOR', 'COMERCIAL', 'OPERACAO', 'FINANCEIRO', 'CLIENTE']
type Values = { username: string; name: string; password: string; role: string }

function UserEditor({ account, onDone }: { account?: AuthUser; onDone: () => void }) {
  const { request } = useAuth()
  const [error, setError] = useState('')
  const form = useForm<Values>({
    defaultValues: {
      name: account?.name || '',
      username: account?.username || '',
      role: account?.role_codes[0] || 'COMERCIAL',
      password: '',
    },
  })
  return (
    <form
      className="form-stack"
      onSubmit={form.handleSubmit(async (values) => {
        setError('')
        try {
          if (account)
            await request(`/users/${account.id}`, 'PATCH', {
              name: values.name,
              is_active: account.is_active,
              role_codes: [values.role],
            })
          else
            await request('/users', 'POST', {
              name: values.name,
              username: values.username,
              password: values.password,
              role_codes: [values.role],
            })
          form.reset()
          onDone()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Erro ao salvar usuário.')
        }
      })}
    >
      {!account && (
        <Field
          label="Usuário"
          autoComplete="off"
          maxLength={80}
          hint="3 a 80 letras minúsculas, números, ponto, _ ou -."
          {...form.register('username', {
            required: 'Informe o usuário.',
            pattern: { value: /^[a-z0-9][a-z0-9._-]{2,79}$/, message: 'Use o formato informado.' },
          })}
          error={form.formState.errors.username?.message}
        />
      )}
      <Field
        label="Nome completo"
        maxLength={120}
        {...form.register('name', {
          required: 'Informe o nome.',
          minLength: { value: 2, message: 'Use ao menos 2 caracteres.' },
        })}
        error={form.formState.errors.name?.message}
      />
      <Select label="Perfil" {...form.register('role')}>
        {roleOptions.map((role) => (
          <option key={role} value={role}>
            {role === 'OPERACAO' ? 'OPERAÇÃO' : role}
          </option>
        ))}
      </Select>
      {account && account.role_codes.length > 1 && (
        <p>
          Este usuário possui múltiplos perfis. Ao salvar, eles serão substituídos pelo perfil
          selecionado.
        </p>
      )}
      {!account && (
        <Field
          label="Senha temporária"
          type="password"
          autoComplete="new-password"
          maxLength={128}
          hint="12 a 128 caracteres. A troca será obrigatória no primeiro acesso."
          {...form.register('password', {
            required: 'Informe a senha temporária.',
            minLength: { value: 12, message: 'Use ao menos 12 caracteres.' },
          })}
          error={form.formState.errors.password?.message}
        />
      )}
      {account && (
        <p>Alterar o perfil encerra as sessões desse usuário. A alteração será auditada.</p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <Button type="submit" disabled={form.formState.isSubmitting}>
        {form.formState.isSubmitting ? 'Salvando…' : 'Salvar usuário'}
      </Button>
    </form>
  )
}

function ResetPassword({ account, onDone }: { account: AuthUser; onDone: () => void }) {
  const { request } = useAuth()
  const [error, setError] = useState('')
  const form = useForm<{ password: string }>()
  return (
    <form
      className="form-stack"
      onSubmit={form.handleSubmit(async ({ password }) => {
        setError('')
        try {
          await request(`/users/${account.id}/reset-password`, 'POST', { new_password: password })
          form.reset()
          onDone()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Erro ao redefinir senha.')
        }
      })}
    >
      <Field
        label="Nova senha temporária"
        type="password"
        autoComplete="new-password"
        maxLength={128}
        {...form.register('password', {
          required: 'Informe a senha.',
          minLength: { value: 12, message: 'Use ao menos 12 caracteres.' },
        })}
        error={form.formState.errors.password?.message}
      />
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <Button type="submit" variant="danger" disabled={form.formState.isSubmitting}>
        Confirmar redefinição
      </Button>
    </form>
  )
}

export function Users() {
  const { user, request, refresh } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [editor, setEditor] = useState<AuthUser | 'new' | null>(null)
  const [reset, setReset] = useState<AuthUser | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const canWrite = user?.permissions.includes('users.write')
  const query = useQuery({
    queryKey: ['users', user?.id, q, offset],
    queryFn: async () =>
      usersSchema.parse(
        await request(`/users?q=${encodeURIComponent(q)}&offset=${offset}&limit=20`),
      ),
    retry: false,
  })
  const done = async (message: string) => {
    setEditor(null)
    setReset(null)
    toast(message)
    await cache.invalidateQueries({ queryKey: ['users'] })
    await refresh()
  }
  return (
    <>
      <PageHeader
        title="Usuários"
        description="Contas reais, perfis de acesso e situação de cada usuário."
        actions={canWrite && <Button onClick={() => setEditor('new')}>Novo usuário</Button>}
      />
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <Card title="Contas do ambiente">
        <div className="padded">
          <Field
            label="Buscar usuários"
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setOffset(0)
            }}
            maxLength={80}
            placeholder="Nome ou usuário"
          />
        </div>
        {query.isPending ? (
          <Skeleton />
        ) : query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : query.data.items.length === 0 ? (
          <EmptyState title="Nenhum usuário encontrado" />
        ) : (
          <>
            <div className="table-scroll" tabIndex={0} role="region" aria-label="Lista de usuários">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Nome / usuário</th>
                    <th>Perfis</th>
                    <th>Situação</th>
                    <th>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((account) => (
                    <tr key={account.id}>
                      <td>
                        <strong>{account.name}</strong>
                        <span className="cell-description">{account.username}</span>
                      </td>
                      <td>{account.role_codes.join(', ')}</td>
                      <td>
                        {account.is_active ? 'Ativo' : 'Desativado'}
                        {account.must_change_password && (
                          <span className="cell-description">Troca de senha pendente</span>
                        )}
                      </td>
                      <td>
                        <div className="row-actions">
                          {canWrite ? (
                            <>
                              <Button
                                variant="ghost"
                                onClick={() => setEditor(account)}
                                aria-label={`Editar ${account.username}`}
                              >
                                Editar
                              </Button>
                              <Button
                                variant="ghost"
                                onClick={() => setReset(account)}
                                aria-label={`Redefinir senha de ${account.username}`}
                              >
                                Redefinir senha
                              </Button>
                              <ConfirmDialog
                                title={
                                  account.is_active ? 'Desativar usuário?' : 'Reativar usuário?'
                                }
                                description={`${account.name}: a ação será auditada e as sessões existentes serão encerradas.`}
                                confirmLabel={account.is_active ? 'Desativar' : 'Reativar'}
                                trigger={
                                  <Button
                                    variant="secondary"
                                    disabled={busy}
                                    aria-label={`${account.is_active ? 'Desativar' : 'Reativar'} ${account.username}`}
                                  >
                                    {account.is_active ? 'Desativar' : 'Reativar'}
                                  </Button>
                                }
                                onConfirm={() => {
                                  setError('')
                                  setBusy(true)
                                  void request(`/users/${account.id}`, 'PATCH', {
                                    name: account.name,
                                    is_active: !account.is_active,
                                    role_codes: account.role_codes,
                                  })
                                    .then(() => done('Situação do usuário atualizada.'))
                                    .catch((e) => setError(e.message))
                                    .finally(() => setBusy(false))
                                }}
                              />
                            </>
                          ) : (
                            <span>Somente consulta</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <span>{query.data.total} usuários</span>
              <div className="pagination">
                <Button
                  variant="secondary"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 20))}
                >
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  disabled={offset + 20 >= query.data.total}
                  onClick={() => setOffset(offset + 20)}
                >
                  Próxima
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
      <Modal
        open={editor !== null}
        onOpenChange={(open) => {
          if (!open) setEditor(null)
        }}
        title={editor === 'new' ? 'Criar usuário' : 'Editar usuário'}
        description="Alterações reais e auditadas no ambiente."
      >
        {editor && (
          <UserEditor
            key={editor === 'new' ? 'new' : editor.id}
            account={editor === 'new' ? undefined : editor}
            onDone={() => void done('Usuário salvo.')}
          />
        )}
      </Modal>
      <Modal
        open={reset !== null}
        onOpenChange={(open) => {
          if (!open) setReset(null)
        }}
        title="Redefinir senha"
        description={`A senha de ${reset?.username || ''} será substituída. Todas as sessões serão encerradas e a troca será obrigatória no próximo acesso.`}
      >
        {reset && (
          <ResetPassword
            key={reset.id}
            account={reset}
            onDone={() =>
              void done('Senha redefinida. Oriente o usuário a alterá-la no primeiro acesso.')
            }
          />
        )}
      </Modal>
    </>
  )
}
