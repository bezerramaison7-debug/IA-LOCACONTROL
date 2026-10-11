import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, DatabaseBackup, ShieldAlert, TriangleAlert } from 'lucide-react'
import { useAuth } from '../auth/context'
import {
  absolutePath,
  backupKinds,
  createBackup,
  downloadBackup,
  fileSize,
  getBackups,
  restoreBackup,
  restorePhrase,
  saveBackupConfig,
  verifyBackup,
  type BackupConfig,
  type BackupItem,
  type Backups as BackupsData,
  type Verification,
} from '../lib/backups'
import { brDateTime, failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Skeleton, Tag } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable } from './masters-shared'

function ConfigForm({
  data,
  onSaved,
}: {
  data: BackupsData
  onSaved: (data: BackupsData) => void
}) {
  const { request } = useAuth()
  const [config, setConfig] = useState<BackupConfig>(data.config)
  const [keep, setKeep] = useState(String(data.config.keep))
  const [errors, setErrors] = useState<{ time?: string; keep?: string; directory?: string }>({})
  const [failure, setFailure] = useState('')
  const [saving, setSaving] = useState(false)
  return (
    <form
      className="form-stack"
      noValidate
      aria-label="Backup automático"
      onSubmit={(event) => {
        event.preventDefault()
        const next = {
          time: /^([01]\d|2[0-3]):[0-5]\d$/.test(config.time)
            ? undefined
            : 'Informe a hora (HH:MM).',
          keep:
            /^[1-9]\d{0,2}$/.test(keep.trim()) && Number(keep) <= 365
              ? undefined
              : 'Informe de 1 a 365 backups.',
          directory: absolutePath(config.directory)
            ? undefined
            : 'Informe o caminho completo da pasta, por exemplo D:\\Backups\\LocaControl.',
        }
        setErrors(next)
        if (next.time || next.keep || next.directory) return
        setFailure('')
        setSaving(true)
        void saveBackupConfig(request, {
          ...config,
          keep: Number(keep),
          directory: config.directory.trim(),
        })
          .then(onSaved)
          .catch((e) => setFailure(failureMessage(e, 'Não foi possível salvar a configuração.')))
          .finally(() => setSaving(false))
      }}
    >
      <label className="quote-check">
        <input
          type="checkbox"
          checked={config.enabled}
          onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
        />
        <span>
          Fazer backup automático todos os dias
          <small>
            Roda no horário abaixo enquanto o LocaControl estiver ligado neste computador.
          </small>
        </span>
      </label>
      <div className="master-form-grid">
        <Field
          label="Horário do backup diário"
          type="time"
          value={config.time}
          error={errors.time}
          onChange={(e) => setConfig({ ...config, time: e.target.value })}
        />
        <Field
          label="Quantos backups manter"
          inputMode="numeric"
          maxLength={3}
          value={keep}
          error={errors.keep}
          hint="Os mais antigos são apagados automaticamente. Cópias de segurança de restauração são mantidas."
          onChange={(e) => setKeep(e.target.value)}
        />
      </div>
      <Field
        label="Pasta dos backups"
        maxLength={260}
        autoComplete="off"
        value={config.directory}
        error={errors.directory}
        hint={
          'Deixe em branco para usar a pasta padrão. Pasta em uso: ' +
          data.directory +
          '. Prefira um disco diferente do computador do sistema.'
        }
        onChange={(e) => setConfig({ ...config, directory: e.target.value })}
      />
      <Failure message={failure} />
      <div className="row-actions">
        <Button type="submit" disabled={saving}>
          {saving ? 'Salvando…' : 'Salvar configuração'}
        </Button>
      </div>
    </form>
  )
}

function VerificationResult({ result }: { result: Verification }) {
  return (
    <div
      className={'quote-notice' + (result.ok ? '' : ' quote-notice-danger')}
      role="status"
      aria-label={'Verificação de ' + result.name}
    >
      <strong>
        {result.ok ? 'Backup íntegro: pode ser restaurado.' : 'Backup reprovado na verificação.'}
      </strong>
      {result.ok ? (
        <span>
          {result.files} arquivos conferidos · {result.users ?? 0} usuários no banco · criado em{' '}
          {result.created_at ? new Date(result.created_at).toLocaleString('pt-BR') : '—'} · versão
          do sistema {result.app_version || '—'} · estrutura do banco {result.revision || '—'}.
        </span>
      ) : (
        <ul>
          {result.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** Restore replaces the data: it needs a visible verification, the exact phrase and the password. */
export function RestoreDialog({
  item,
  onClose,
  onRestored,
}: {
  item: BackupItem
  onClose: () => void
  onRestored: (message: string) => void
}) {
  const { request } = useAuth()
  const [phrase, setPhrase] = useState('')
  const [password, setPassword] = useState('')
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  const check = useQuery({
    queryKey: ['backups', 'verify', item.name],
    queryFn: () => verifyBackup(request, item.name),
    retry: false,
    gcTime: 0,
  })
  const expected = restorePhrase(item.name)
  const ready = check.data?.ok === true && phrase === expected && password.length > 0
  return (
    <Modal
      open
      onOpenChange={(open) => !open && !busy && onClose()}
      title="Restaurar backup"
      description={'Substitui os dados atuais pelo conteúdo de ' + item.name + '.'}
      className="master-modal"
    >
      <form
        className="form-stack"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          if (!ready) return
          setFailure('')
          setBusy(true)
          void restoreBackup(request, item.name, phrase, password)
            .then((result) =>
              onRestored(
                result.message +
                  ' Cópia de segurança do estado anterior: ' +
                  result.safety_backup +
                  '.',
              ),
            )
            .catch((e) => {
              setFailure(e instanceof Error ? e.message : 'Não foi possível restaurar o backup.')
              setBusy(false)
            })
        }}
      >
        {check.isPending ? (
          <p role="status">Verificando a integridade do backup…</p>
        ) : check.isError ? (
          <ErrorState message={check.error.message} onRetry={() => void check.refetch()} />
        ) : (
          <VerificationResult result={check.data} />
        )}
        <div className="quote-notice quote-notice-danger" role="note">
          <strong>O que acontece ao restaurar</strong>
          <ul>
            <li>
              Tudo o que foi registrado depois deste backup ({brDateTime(item.created_at)}) deixa de
              aparecer: contratos, movimentações, cadastros e documentos.
            </li>
            <li>
              Antes de substituir, o sistema faz uma cópia de segurança do estado atual, que fica na
              lista de backups.
            </li>
            <li>Todos os usuários, inclusive você, terão de entrar novamente.</li>
          </ul>
        </div>
        <Field
          label={'Digite exatamente: ' + expected}
          autoComplete="off"
          spellCheck={false}
          value={phrase}
          disabled={check.data?.ok !== true}
          hint="Diferencia maiúsculas de minúsculas."
          onChange={(e) => setPhrase(e.target.value)}
        />
        <Field
          label="Sua senha"
          type="password"
          autoComplete="current-password"
          maxLength={200}
          value={password}
          disabled={check.data?.ok !== true}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Failure message={failure} />
        <div className="modal-actions">
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Voltar sem restaurar
          </Button>
          <Button type="submit" variant="danger" disabled={!ready || busy}>
            {busy ? 'Restaurando…' : 'Restaurar este backup'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export function Backups() {
  const { request, clear } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [checked, setChecked] = useState<Verification | null>(null)
  const [restoring, setRestoring] = useState<BackupItem | null>(null)
  const query = useQuery({
    queryKey: ['backups', 'overview'],
    queryFn: () => getBackups(request),
    retry: false,
  })
  const run = (key: string, task: () => Promise<unknown>, fallback: string) => {
    setFailure('')
    setBusy(key)
    void task()
      .catch((e) => setFailure(failureMessage(e, fallback)))
      .finally(() => setBusy(null))
  }
  return (
    <>
      <PageHeader
        title="Backups"
        description="Cópias completas do banco de dados e dos arquivos, com verificação e restauração assistida."
        actions={
          <Button
            disabled={busy !== null}
            onClick={() =>
              run(
                'create',
                async () => {
                  const created = await createBackup(request)
                  toast('Backup criado: ' + created.name + ' (' + fileSize(created.size) + ').')
                  await cache.invalidateQueries({ queryKey: ['backups', 'overview'] })
                },
                'Não foi possível criar o backup.',
              )
            }
          >
            <DatabaseBackup size={18} aria-hidden="true" />
            {busy === 'create' ? 'Criando backup…' : 'Fazer backup agora'}
          </Button>
        }
      />
      <Failure message={failure} />
      {query.isPending ? (
        <Skeleton rows={4} />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <>
          <Card
            title="Backup automático"
            description="Horário, retenção e pasta de destino. A alteração é auditada."
          >
            <div className="padded">
              <ConfigForm
                key={JSON.stringify(query.data.config)}
                data={query.data}
                onSaved={(next) => {
                  cache.setQueryData(['backups', 'overview'], next)
                  toast('Configuração de backup salva.')
                }}
              />
            </div>
          </Card>
          <Card
            title="Backups disponíveis"
            description={
              'Arquivos na pasta ' + query.data.directory + ', do mais recente ao mais antigo.'
            }
          >
            {checked && (
              <div className="padded">
                <VerificationResult result={checked} />
              </div>
            )}
            {query.data.items.length ? (
              <MasterTable
                label="Lista de backups"
                headers={['Arquivo', 'Criado em', 'Tamanho', 'Tipo', 'Ações']}
              >
                {query.data.items.map((item) => (
                  <tr key={item.name}>
                    <td className="code-cell">{item.name}</td>
                    <td className="date-cell">{brDateTime(item.created_at)}</td>
                    <td className="date-cell">{fileSize(item.size)}</td>
                    <td>
                      {item.kind === 'backup' ? (
                        <Tag tone="info" icon={CircleCheck}>
                          {backupKinds.backup}
                        </Tag>
                      ) : (
                        <Tag tone="warning" icon={ShieldAlert}>
                          Anterior a uma restauração
                        </Tag>
                      )}
                    </td>
                    <td>
                      <div className="row-actions">
                        <Button
                          variant="ghost"
                          disabled={busy !== null}
                          aria-label={'Verificar ' + item.name}
                          onClick={() =>
                            run(
                              'verify' + item.name,
                              async () => setChecked(await verifyBackup(request, item.name)),
                              'Não foi possível verificar o backup.',
                            )
                          }
                        >
                          {busy === 'verify' + item.name ? 'Verificando…' : 'Verificar'}
                        </Button>
                        <Button
                          variant="ghost"
                          disabled={busy !== null}
                          aria-label={'Baixar ' + item.name}
                          onClick={() =>
                            run(
                              'download' + item.name,
                              () => downloadBackup(item.name),
                              'Não foi possível baixar o backup.',
                            )
                          }
                        >
                          {busy === 'download' + item.name ? 'Baixando…' : 'Baixar'}
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={busy !== null}
                          aria-label={'Restaurar ' + item.name}
                          onClick={() => setRestoring(item)}
                        >
                          <TriangleAlert size={16} aria-hidden="true" />
                          Restaurar
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </MasterTable>
            ) : (
              <EmptyState
                initial
                title="Nenhum backup ainda"
                description="Use “Fazer backup agora” ou ative o backup automático diário."
              />
            )}
          </Card>
        </>
      )}
      {restoring && (
        <RestoreDialog
          key={restoring.name}
          item={restoring}
          onClose={() => setRestoring(null)}
          onRestored={(message) => {
            toast(message)
            // The session may still exist in the restored data: end it so the login is explicit.
            void request('/auth/logout', 'POST')
              .catch(() => undefined)
              .finally(clear)
          }}
        />
      )}
    </>
  )
}
