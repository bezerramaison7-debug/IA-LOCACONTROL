import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/context'
import { permissionsSchema, rolesSchema, type Role } from '../auth/api'
import { Button } from '../components/Button'
import { Modal, ConfirmDialog } from '../components/Modal'
import { Card, ErrorState, PageHeader, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'

function RoleEditor({
  role,
  permissions,
  onDone,
}: {
  role: Role
  permissions: { code: string; description: string }[]
  onDone: () => void
}) {
  const { request } = useAuth()
  const [codes, setCodes] = useState(role.permission_codes)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <div className="form-stack">
      <fieldset className="permission-list">
        <legend>Permissões de {role.name}</legend>
        {permissions.map((permission) => (
          <label key={permission.code}>
            <input
              type="checkbox"
              checked={codes.includes(permission.code)}
              onChange={(e) =>
                setCodes(
                  e.target.checked
                    ? [...codes, permission.code]
                    : codes.filter((code) => code !== permission.code),
                )
              }
            />
            <span>
              {permission.description}
              <small>{permission.code}</small>
            </span>
          </label>
        ))}
      </fieldset>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      <ConfirmDialog
        title="Aplicar permissões?"
        description="Todos os usuários deste perfil terão suas sessões encerradas. A alteração será auditada."
        confirmLabel="Aplicar permissões"
        trigger={<Button disabled={busy}>Salvar permissões</Button>}
        onConfirm={() => {
          setBusy(true)
          setError('')
          void request(`/roles/${role.id}/permissions`, 'PUT', { permission_codes: codes })
            .then(onDone)
            .catch((e) => setError(e.message))
            .finally(() => setBusy(false))
        }}
      />
    </div>
  )
}

export function Roles() {
  const { user, request, refresh } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [editing, setEditing] = useState<Role | null>(null)
  const query = useQuery({
    queryKey: ['roles', user?.id],
    retry: false,
    queryFn: async () => {
      const [roles, permissions] = await Promise.all([request('/roles'), request('/permissions')])
      return { roles: rolesSchema.parse(roles), permissions: permissionsSchema.parse(permissions) }
    },
  })
  return (
    <>
      <PageHeader
        title="Perfis e permissões"
        description="Controle quais ações cada perfil pode executar. A API verifica todas as permissões."
      />
      <p className="security-note">
        Administrador mantém acesso completo. Cliente tem acesso apenas à própria conta nesta etapa.
        Permissões comerciais serão acrescentadas junto aos módulos correspondentes.
      </p>
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <Card title="Matriz de acesso">
          <div
            className="table-scroll"
            tabIndex={0}
            role="region"
            aria-label="Matriz de permissões"
          >
            <table className="data-table">
              <thead>
                <tr>
                  <th>Permissão</th>
                  {query.data.roles.map((role) => (
                    <th key={role.id}>{role.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {query.data.permissions.map((permission) => (
                  <tr key={permission.code}>
                    <th scope="row">{permission.description}</th>
                    {query.data.roles.map((role) => (
                      <td key={role.id}>
                        {role.permission_codes.includes(permission.code)
                          ? 'Permitido'
                          : 'Sem acesso'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="padded role-actions">
            {query.data.roles.map((role) => (
              <div key={role.id}>
                <strong>{role.name}</strong>
                {role.protected ? (
                  <span>Perfil protegido</span>
                ) : user?.permissions.includes('roles.write') ? (
                  <Button variant="secondary" onClick={() => setEditing(role)}>
                    Editar {role.name}
                  </Button>
                ) : (
                  <span>Somente consulta</span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
      <Modal
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) setEditing(null)
        }}
        title={`Permissões: ${editing?.name || ''}`}
        description="Revise os acessos antes de confirmar."
      >
        {editing && query.data && (
          <RoleEditor
            key={editing.id}
            role={editing}
            permissions={query.data.permissions}
            onDone={() => {
              setEditing(null)
              toast('Permissões atualizadas.')
              void cache.invalidateQueries({ queryKey: ['roles'] })
              void refresh()
            }}
          />
        )}
      </Modal>
    </>
  )
}
