import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, DatabaseBackup, ShieldAlert, TriangleAlert, Upload } from 'lucide-react'
import { useAuth } from '../auth/context'
import {
  absolutePath,
  backupKinds,
  brIso,
  frequencies,
  importBackup,
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
import {
  Card,
  EmptyState,
  ErrorState,
  Field,
  PageHeader,
  Select,
  Skeleton,
  Tag,
} from '../components/ui'
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
  const [limits, setLimits] = useState({
    max_total_gb: String(data.config.max_total_gb),
    min_free_gb: String(data.config.min_free_gb),
    min_free_percent: String(data.config.min_free_percent),
  })
  const [errors, setErrors] = useState<{
    time?: string
    keep?: string
    directory?: string
    mirror?: string
    max_total_gb?: string
    min_free_gb?: string
    min_free_percent?: string
  }>({})
  const [failure, setFailure] = useState('')
  const [saving, setSaving] = useState(false)
  const daily = config.frequency === 'daily'
  return (
    <form
      className="form-stack"
      noValidate
      aria-label="Backup automático"
      onSubmit={(event) => {
        event.preventDefault()
        const next = {
          time:
            !daily || /^([01]\d|2[0-3]):[0-5]\d$/.test(config.time)
              ? undefined
              : 'Informe a hora (HH:MM).',
          keep:
            /^[1-9]\d{0,2}$/.test(keep.trim()) && Number(keep) <= 365
              ? undefined
              : 'Informe de 1 a 365 dias.',
          directory: absolutePath(config.directory)
            ? undefined
            : 'Informe o caminho completo da pasta, por exemplo D:\\Backups\\LocaControl.',
          max_total_gb:
            /^\d{1,6}$/.test(limits.max_total_gb.trim()) && Number(limits.max_total_gb) >= 1
              ? undefined
              : 'Informe o limite em GB (1 ou mais).',
          min_free_gb: /^\d{1,6}$/.test(limits.min_free_gb.trim())
            ? undefined
            : 'Informe quantos GB manter livres (0 ou mais).',
          min_free_percent:
            /^\d{1,2}$/.test(limits.min_free_percent.trim()) &&
            Number(limits.min_free_percent) <= 90
              ? undefined
              : 'Informe de 0 a 90%.',
          mirror: absolutePath(config.mirror_directory)
            ? undefined
            : 'Informe o caminho completo da pasta, por exemplo E:\\Copia\\LocaControl.',
        }
        setErrors(next)
        if (Object.values(next).some(Boolean)) return
        setFailure('')
        setSaving(true)
        void saveBackupConfig(request, {
          ...config,
          keep: Number(keep),
          directory: config.directory.trim(),
          mirror_directory: config.mirror_directory.trim(),
          max_total_gb: Number(limits.max_total_gb),
          min_free_gb: Number(limits.min_free_gb),
          min_free_percent: Number(limits.min_free_percent),
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
          Fazer backup automático
          <small>{data.status.requires_running}</small>
        </span>
      </label>
      <div className="master-form-grid">
        <Select
          label="Frequência"
          value={config.frequency}
          onChange={(e) =>
            setConfig({ ...config, frequency: e.target.value as BackupConfig['frequency'] })
          }
        >
          {Object.entries(frequencies).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
        {daily && (
          <Field
            label="Horário do backup diário"
            type="time"
            value={config.time}
            error={errors.time}
            onChange={(e) => setConfig({ ...config, time: e.target.value })}
          />
        )}
        <Field
          label="Dias com cópia guardada"
          inputMode="numeric"
          maxLength={3}
          value={keep}
          error={errors.keep}
          hint="Todas as cópias das últimas 24 horas ficam guardadas; dos dias anteriores, a última de cada dia. Cópias anteriores a restaurações e backups importados nunca são apagados."
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
          '. Pode ficar em outro disco: a restauração funciona do mesmo jeito.'
        }
        onChange={(e) => setConfig({ ...config, directory: e.target.value })}
      />
      <Field
        label="Segunda cópia (opcional)"
        maxLength={260}
        autoComplete="off"
        value={config.mirror_directory}
        error={errors.mirror}
        hint="Cada backup concluído é copiado e conferido também nesta pasta, de preferência em outro disco ou pendrive que fique conectado. Deixe em branco para não fazer."
        onChange={(e) => setConfig({ ...config, mirror_directory: e.target.value })}
      />
      <div className="master-form-grid">
        <Field
          label="Limite para backups (GB)"
          inputMode="numeric"
          maxLength={6}
          value={limits.max_total_gb}
          error={errors.max_total_gb}
          hint="Espaço máximo da pasta de backups. Para abrir espaço, saem primeiro as cópias intermediárias mais antigas; a mais recente, as anteriores a restaurações e as importadas nunca."
          onChange={(e) => setLimits({ ...limits, max_total_gb: e.target.value })}
        />
        <Field
          label="Manter livres no disco (GB)"
          inputMode="numeric"
          maxLength={6}
          value={limits.min_free_gb}
          error={errors.min_free_gb}
          hint="O backup não é feito se o disco ficaria com menos que isso."
          onChange={(e) => setLimits({ ...limits, min_free_gb: e.target.value })}
        />
        <Field
          label="Manter livres no disco (%)"
          inputMode="numeric"
          maxLength={2}
          value={limits.min_free_percent}
          error={errors.min_free_percent}
          hint="Vale o maior dos dois: em GB ou em porcentagem do disco."
          onChange={(e) => setLimits({ ...limits, min_free_percent: e.target.value })}
        />
      </div>
      <Failure message={failure} />
      <div className="row-actions">
        <Button type="submit" disabled={saving}>
          {saving ? 'Salvando…' : 'Salvar configuração'}
        </Button>
      </div>
    </form>
  )
}

const runKinds: Record<string, string> = {
  auto: 'Automático',
  manual: 'Manual',
  'pre-restore': 'Antes de restauração',
}

/** Last completed copy, the warning to act on and the record of recent runs. */
function ProtectionStatus({ data }: { data: BackupsData }) {
  const { status } = data
  return (
    <div className="padded form-stack">
      {status.alert ? (
        <div
          className={
            'quote-notice' + (status.alert.level === 'danger' ? ' quote-notice-danger' : '')
          }
          role="alert"
        >
          <strong>{status.alert.message}</strong>
        </div>
      ) : (
        <div className="quote-notice" role="status">
          <strong>Proteção automática em dia.</strong>
        </div>
      )}
      <p className="draft-status">
        Última cópia concluída:{' '}
        <strong>
          {status.last_success
            ? brIso(status.last_success.finished_at) + ' (' + status.last_success.name + ')'
            : 'nenhuma ainda'}
        </strong>
        {status.unchanged_at &&
          ' · Última verificação sem alterações nos dados: ' + brIso(status.unchanged_at)}
        {' · Espaço ocupado pelos backups: ' + fileSize(data.total_size)}
      </p>
      {status.storage?.available && (
        <p className="draft-status" aria-label="Espaço dos backups">
          Limite: {fileSize(status.storage.managed_bytes)} de {fileSize(status.storage.cap_bytes)} ·
          Disco: {fileSize(status.storage.free_bytes)} livres, mínimo de{' '}
          {fileSize(status.storage.reserve_bytes)} · Próximo backup: cerca de{' '}
          {fileSize(status.storage.estimate_bytes)}
          {status.storage.fits
            ? status.storage.removes
              ? ' (vai remover ' + status.storage.removes + ' cópia(s) antiga(s) para caber)'
              : ' (cabe)'
            : ' (não cabe)'}
        </p>
      )}
      <p className="draft-status">
        <TriangleAlert size={14} aria-hidden="true" /> {status.requires_running}
      </p>
      {status.runs.length > 0 && (
        <MasterTable
          label="Execuções recentes de backup"
          headers={['Quando', 'Tipo', 'Resultado', 'Detalhe']}
        >
          {status.runs.slice(0, 10).map((run) => (
            <tr key={run.started_at + run.kind + run.status}>
              <td className="date-cell">{brIso(run.finished_at)}</td>
              <td>{runKinds[run.kind] || run.kind}</td>
              <td>
                {run.status === 'ok' ? (
                  <Tag tone="success" icon={CircleCheck}>
                    Concluído
                  </Tag>
                ) : (
                  <Tag tone="danger" icon={ShieldAlert}>
                    Falhou
                  </Tag>
                )}
              </td>
              <td>
                {run.status === 'ok'
                  ? run.name +
                    (run.mirror?.status === 'ok'
                      ? ' · segunda cópia conferida'
                      : run.mirror?.status === 'failed'
                        ? ' · segunda cópia falhou: ' + (run.mirror.error || '')
                        : '')
                  : run.error}
              </td>
            </tr>
          ))}
        </MasterTable>
      )}
    </div>
  )
}

/** A set kept on another disk or a USB drive comes into the backup folder, verified first. */
function ImportForm({ onImported }: { onImported: (name: string) => void }) {
  const { request } = useAuth()
  const [file, setFile] = useState<File | null>(null)
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <form
      className="form-stack"
      noValidate
      aria-label="Importar backup"
      onSubmit={(event) => {
        event.preventDefault()
        if (!file) {
          setFailure('Escolha o arquivo .zip do backup.')
          return
        }
        setFailure('')
        setBusy(true)
        void importBackup(request, file)
          .then((result) => onImported(result.name))
          .catch((e) => setFailure(failureMessage(e, 'Não foi possível importar o backup.')))
          .finally(() => setBusy(false))
      }}
    >
      <div className="field">
        <label htmlFor="backup-import-file">Arquivo do backup (.zip)</label>
        <input
          id="backup-import-file"
          type="file"
          accept=".zip,application/zip"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <small>
          Use para recuperar um backup guardado em outro disco, pendrive ou outro computador. O
          arquivo é conferido antes de ser aceito e nada nos dados atuais muda: depois, restaure-o
          pela lista abaixo.
        </small>
      </div>
      <Failure message={failure} />
      <div className="row-actions">
        <Button type="submit" variant="secondary" disabled={busy}>
          <Upload size={16} aria-hidden="true" />
          {busy ? 'Importando e conferindo…' : 'Importar backup'}
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

/** Restore replaces the data: it needs a visible verification, the exact phrase and, in the
 * login-based edition, the password. The local edition has no password (ADR-023). */
export function RestoreDialog({
  item,
  onClose,
  onRestored,
}: {
  item: BackupItem
  onClose: () => void
  onRestored: (message: string) => void
}) {
  const { request, local } = useAuth()
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
  const ready = check.data?.ok === true && phrase === expected && (local || password.length > 0)
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
          void restoreBackup(request, item.name, phrase, local ? undefined : password)
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
            {!local && <li>Todos os usuários, inclusive você, terão de entrar novamente.</li>}
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
        {!local && (
          <Field
            label="Sua senha"
            type="password"
            autoComplete="current-password"
            maxLength={200}
            value={password}
            disabled={check.data?.ok !== true}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
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
  const { request, clear, station } = useAuth()
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
            title="Proteção automática"
            description="Última cópia concluída, avisos e as execuções mais recentes."
          >
            <ProtectionStatus data={query.data} />
          </Card>
          {station ? (
            <div className="quote-notice" role="note">
              <strong>
                Configurar, baixar, importar e restaurar backups só no computador principal.
              </strong>
              <span>
                Desta estação ({station.name}) dá para acompanhar a proteção, fazer um backup agora
                e verificar os conjuntos.
              </span>
            </div>
          ) : (
            <>
              <Card
                title="Backup automático"
                description="Frequência, retenção, pasta de destino e segunda cópia. A alteração é auditada."
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
                title="Recuperar backup de outro disco"
                description="Traz para a pasta de backups um conjunto guardado fora dela."
              >
                <div className="padded">
                  <ImportForm
                    onImported={(name) => {
                      toast('Backup conferido e importado: ' + name + '. Ele já aparece na lista.')
                      void cache.invalidateQueries({ queryKey: ['backups', 'overview'] })
                    }}
                  />
                </div>
              </Card>
            </>
          )}
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
                      ) : item.kind === 'imported' ? (
                        <Tag tone="info" icon={Upload}>
                          {backupKinds.imported}
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
                        {!station && (
                          <>
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
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </MasterTable>
            ) : (
              <EmptyState
                initial
                title="Nenhum backup ainda"
                description="Use “Fazer backup agora” ou ative o backup automático."
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
