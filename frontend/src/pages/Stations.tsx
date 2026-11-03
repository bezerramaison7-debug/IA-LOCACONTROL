import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, KeyRound, Network, ShieldOff } from 'lucide-react'
import { useAuth } from '../auth/context'
import {
  cancelPairing,
  eventLabels,
  getStations,
  recentReuse,
  resetRegistry,
  RESET_PHRASE,
  revokeStation,
  startPairing,
  type PairingCode,
  type Station,
} from '../lib/stations'
import { brDateTime, failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Skeleton, Tag } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable } from './masters-shared'

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [active])
  return now
}

/** The code is shown once, here, on the main computer; it is typed on the station. */
function CodePanel({ code, onCancel }: { code: PairingCode; onCancel: () => void }) {
  const now = useNow(true)
  const left = Math.max(0, Math.round(code.expires_at - now / 1000))
  return (
    <div className="quote-notice" role="status" aria-label="Código de pareamento">
      {left > 0 ? (
        <>
          <span>
            Na estação, rode o instalador do LocaControl, escolha <strong>Conectar à loja</strong> e
            informe o endereço deste computador e este código. Ele também comprova à estação que o
            certificado de segurança é deste computador.
          </span>
          <strong className="pairing-code">{code.code}</strong>
          <span>
            Vale por mais {Math.floor(left / 60)} min {String(left % 60).padStart(2, '0')} s, para
            uma única estação; {code.attempts_left} tentativas erradas o cancelam.
          </span>
          <Button variant="secondary" onClick={onCancel}>
            Cancelar código
          </Button>
        </>
      ) : (
        <strong>O código expirou. Gere outro para parear uma estação.</strong>
      )}
    </div>
  )
}

function RevokeDialog({
  station,
  onClose,
  onRevoked,
}: {
  station: Station
  onClose: () => void
  onRevoked: () => void
}) {
  const { request } = useAuth()
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)
  return (
    <Modal
      open
      onOpenChange={(open) => !open && !busy && onClose()}
      title={'Revogar a estação ' + station.name}
      description="O acesso deste computador termina na hora. Para voltar a usá-lo, pareie de novo."
    >
      <div className="form-stack">
        <Failure message={failure} />
        <div className="modal-actions">
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Voltar
          </Button>
          <Button
            variant="danger"
            disabled={busy}
            onClick={() => {
              setBusy(true)
              void revokeStation(request, station.id)
                .then(onRevoked)
                .catch((e) => {
                  setFailure(failureMessage(e, 'Não foi possível revogar.'))
                  setBusy(false)
                })
            }}
          >
            {busy ? 'Revogando…' : 'Revogar estação'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

/** A2: the station list is unreadable; the main computer works, stations are blocked. */
function RegistryRepair({ onDone }: { onDone: () => void }) {
  const { request } = useAuth()
  const [phrase, setPhrase] = useState('')
  const [failure, setFailure] = useState('')
  return (
    <div className="quote-notice quote-notice-danger" role="alert">
      <strong>A lista de estações está ilegível: todas as estações estão bloqueadas.</strong>
      <span>
        Este computador e os dados da loja não foram afetados. Se houver uma cópia da pasta de
        dados, recoloque o arquivo stations.json e reinicie o LocaControl. Sem cópia, recomece a
        lista: os arquivos atuais ficam guardados e todas as estações precisam ser pareadas de novo.
      </span>
      <form
        className="form-stack"
        noValidate
        onSubmit={(event) => {
          event.preventDefault()
          setFailure('')
          void resetRegistry(request, phrase)
            .then(onDone)
            .catch((e) => setFailure(failureMessage(e, 'Não foi possível recomeçar a lista.')))
        }}
      >
        <Field
          label={'Digite exatamente: ' + RESET_PHRASE}
          autoComplete="off"
          spellCheck={false}
          value={phrase}
          onChange={(e) => setPhrase(e.target.value)}
        />
        <Failure message={failure} />
        <Button type="submit" variant="danger" disabled={phrase !== RESET_PHRASE}>
          Recomeçar a lista de estações
        </Button>
      </form>
    </div>
  )
}

export function Stations() {
  const { request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [code, setCode] = useState<PairingCode | null>(null)
  const [failure, setFailure] = useState('')
  const [revoking, setRevoking] = useState<Station | null>(null)
  const query = useQuery({
    queryKey: ['stations'],
    queryFn: () => getStations(request),
    retry: false,
  })
  const reload = () => void cache.invalidateQueries({ queryKey: ['stations'] })
  return (
    <>
      <PageHeader
        title="Estações da rede"
        description="Outros computadores da loja que usam a mesma base por este computador principal."
        actions={
          query.data?.network && (
            <Button
              onClick={() => {
                setFailure('')
                void startPairing(request)
                  .then((next) => {
                    setCode(next)
                    reload()
                  })
                  .catch((e) => setFailure(failureMessage(e, 'Não foi possível gerar o código.')))
              }}
            >
              <KeyRound size={18} aria-hidden="true" />
              Gerar código de pareamento
            </Button>
          )
        }
      />
      <Failure message={failure} />
      {query.isPending ? (
        <Skeleton rows={4} />
      ) : query.isError ? (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      ) : (
        <>
          {query.data.registry.unavailable && <RegistryRepair onDone={reload} />}
          {query.data.registry.recovered_from_backup && (
            <div className="quote-notice" role="status">
              <strong>A lista de estações foi recuperada da cópia de segurança.</strong>
              <span>
                O arquivo principal estava ilegível e foi guardado para análise. Confira se as
                revogações recentes continuam valendo.
              </span>
            </div>
          )}
          {recentReuse(query.data).map((event) => (
            <div
              className="quote-notice quote-notice-danger"
              role="alert"
              key={'reuse' + event.at + event.station_id}
            >
              <strong>
                Credencial da estação {event.station_name} usada por mais de um computador em{' '}
                {brDateTime(event.at)}: a estação foi revogada.
              </strong>
              <span>
                Indícios: endereço {event.peer || '—'} (o último conhecido era{' '}
                {event.last_address || '—'}). Verifique os computadores da loja e pareie de novo a
                estação legítima. A credencial foi copiada de algum modo: o navegador da estação, um
                programa nela ou a rede.
              </span>
            </div>
          ))}
          {query.data.network && query.data.tls && (
            <Card
              title="Conexão segura (HTTPS)"
              description="As estações só falam com este computador por HTTPS, com o certificado da autoridade local desta loja."
            >
              {query.data.tls.available ? (
                <dl className="padded definition-list">
                  <dt>Autoridade local (impressão digital)</dt>
                  <dd className="code-cell">{query.data.tls.ca_fingerprint}</dd>
                  <dt>Certificado deste computador vale até</dt>
                  <dd>{new Date(query.data.tls.server_expires).toLocaleDateString('pt-BR')}</dd>
                  <dt>Nomes e endereços</dt>
                  <dd>
                    {[...query.data.tls.server_names, ...query.data.tls.server_addresses].join(
                      ', ',
                    )}
                  </dd>
                  <dt>Proteção das chaves</dt>
                  <dd>{query.data.tls.protection}</dd>
                </dl>
              ) : (
                <div className="padded">
                  <div className="quote-notice quote-notice-danger" role="alert">
                    <strong>HTTPS indisponível: a rede da loja está fechada.</strong>
                    <span>{query.data.tls.error}</span>
                  </div>
                </div>
              )}
              {query.data.tls.available && query.data.tls.renamed_outside_ca.length > 0 && (
                <div className="padded">
                  <div className="quote-notice" role="status">
                    <strong>
                      O nome atual deste computador ({query.data.tls.renamed_outside_ca.join(', ')})
                      não está no certificado da loja.
                    </strong>
                    <span>As estações devem usar o endereço IP, ou conectar-se de novo.</span>
                  </div>
                </div>
              )}
            </Card>
          )}
          {!query.data.network && (
            <div className="quote-notice" role="note">
              <strong>A rede da loja está desativada neste computador.</strong>
              <span>
                Só este computador usa o LocaControl. O modo rede é escolhido na instalação do
                computador principal; com ele, as estações pareadas acessam a mesma base.
              </span>
            </div>
          )}
          {code && (
            <CodePanel
              code={code}
              onCancel={() => {
                void cancelPairing(request).finally(() => {
                  setCode(null)
                  reload()
                })
              }}
            />
          )}
          <Card
            title="Estações pareadas"
            description="Cada estação tem a sua própria credencial. Revogar encerra o acesso na hora."
          >
            {query.data.stations.length ? (
              <MasterTable
                label="Lista de estações"
                headers={['Estação', 'Pareada em', 'Último acesso', 'Situação', 'Ações']}
              >
                {query.data.stations.map((station) => (
                  <tr key={station.id}>
                    <td>
                      <strong>{station.name}</strong>
                      <small className="draft-status"> {station.id.slice(0, 8)}</small>
                    </td>
                    <td className="date-cell">{brDateTime(station.paired_at)}</td>
                    <td className="date-cell">
                      {brDateTime(station.last_seen_at)}
                      {station.last_address ? ' · ' + station.last_address : ''}
                    </td>
                    <td>
                      {station.revoked_at ? (
                        <Tag tone="danger" icon={ShieldOff}>
                          Revogada em {brDateTime(station.revoked_at)}
                          {station.revoked_reason ? ' · ' + station.revoked_reason : ''}
                        </Tag>
                      ) : (
                        <Tag tone="success" icon={CircleCheck}>
                          Ativa
                        </Tag>
                      )}
                    </td>
                    <td>
                      {!station.revoked_at && (
                        <Button
                          variant="secondary"
                          aria-label={'Revogar ' + station.name}
                          onClick={() => setRevoking(station)}
                        >
                          Revogar
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </MasterTable>
            ) : (
              <EmptyState
                initial
                title="Nenhuma estação pareada"
                description="Gere um código e digite-o no outro computador da loja."
              />
            )}
          </Card>
          <Card
            title="Identificação"
            description="Três identidades diferentes, para não confundir a base, o servidor e as estações."
          >
            <dl className="padded definition-list">
              <dt>Base de dados da loja</dt>
              <dd className="code-cell">{query.data.installation_id}</dd>
              <dt>Este servidor (computador principal)</dt>
              <dd className="code-cell">
                {query.data.server?.id || '— (lista de estações ilegível)'}
              </dd>
              <dt>Estações</dt>
              <dd>Cada uma tem o seu código, mostrado na lista acima.</dd>
            </dl>
          </Card>
          {query.data.events.length > 0 && (
            <Card
              title="Histórico da rede"
              description="Pareamentos, tentativas recusadas e revogações. Não muda com restaurações de backup."
            >
              <MasterTable label="Histórico da rede" headers={['Quando', 'Evento', 'Detalhe']}>
                {query.data.events.map((event, index) => (
                  <tr key={event.at + event.action + index}>
                    <td className="date-cell">{brDateTime(event.at)}</td>
                    <td>{eventLabels[event.action] || event.action}</td>
                    <td>
                      {[event.station_name, event.peer, event.reason].filter(Boolean).join(' · ')}
                    </td>
                  </tr>
                ))}
              </MasterTable>
            </Card>
          )}
        </>
      )}
      {revoking && (
        <RevokeDialog
          station={revoking}
          onClose={() => setRevoking(null)}
          onRevoked={() => {
            toast('Estação ' + revoking.name + ' revogada.')
            setRevoking(null)
            reload()
          }}
        />
      )}
      <p className="draft-status">
        <Network size={14} aria-hidden="true" /> As estações usam este computador como servidor: com
        ele desligado, elas ficam sem acesso até ele voltar.
      </p>
    </>
  )
}
