import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/context'
import {
  addressSchema,
  masterSchemas,
  pageSchema,
  states,
  value,
  type Address,
  type MasterKind,
  type MasterRow,
} from '../lib/masters'
import { Button } from '../components/Button'
import { Modal, ConfirmDialog } from '../components/Modal'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, MasterTable, Pager, ProductPicker } from './masters-shared'

type Spec = {
  key: string
  label: string
  required?: boolean
  max: number
  type?: 'email' | 'tel'
  options?: Record<string, string>
}
const yesNo = { true: 'Sim', false: 'Não' }
const fields: Record<MasterKind, Spec[]> = {
  customers: [
    {
      key: 'person_type',
      label: 'Tipo de pessoa',
      max: 2,
      options: { PF: 'Pessoa física', PJ: 'Pessoa jurídica' },
    },
    { key: 'legal_name', label: 'Nome / razão social', required: true, max: 160 },
    { key: 'trade_name', label: 'Nome fantasia', max: 160 },
    { key: 'document', label: 'CPF / CNPJ', required: true, max: 18 },
    { key: 'state_registration', label: 'Inscrição estadual', max: 30 },
    { key: 'phone', label: 'Telefone', max: 30, type: 'tel' },
    { key: 'mobile', label: 'Celular', max: 30, type: 'tel' },
    { key: 'email', label: 'E-mail', max: 254, type: 'email' },
    { key: 'contact', label: 'Contato responsável', max: 120 },
    { key: 'notes', label: 'Observações', max: 2000 },
    { key: 'is_active', label: 'Ativo', max: 5, options: yesNo },
  ],
  products: [
    { key: 'code', label: 'Código', required: true, max: 40 },
    { key: 'name', label: 'Nome do produto', required: true, max: 160 },
    { key: 'description', label: 'Descrição', max: 2000 },
    { key: 'category', label: 'Categoria', max: 80 },
    { key: 'unit', label: 'Unidade de medida', required: true, max: 20 },
    {
      key: 'individual_tracking',
      label: 'Controla equipamento individual',
      max: 5,
      options: yesNo,
    },
    { key: 'is_active', label: 'Ativo', max: 5, options: yesNo },
  ],
  equipment: [
    { key: 'code', label: 'Código interno', required: true, max: 40 },
    { key: 'asset_tag', label: 'Patrimônio', max: 80 },
    { key: 'serial_number', label: 'Número serial', max: 100 },
    { key: 'brand', label: 'Marca', max: 80 },
    { key: 'model', label: 'Modelo', max: 100 },
    { key: 'notes', label: 'Observações', max: 2000 },
  ],
}
const titles = { customers: 'Clientes', products: 'Produtos', equipment: 'Equipamentos' }
const singular = { customers: 'cliente', products: 'produto', equipment: 'equipamento' }
function label(row: MasterRow) {
  return value(row, 'legal_name') || value(row, 'name') || value(row, 'code')
}
function statusLabel(row: MasterRow) {
  return row.status
    ? states[row.status as keyof typeof states]
    : row.is_active
      ? 'Ativo'
      : 'Inativo'
}

function Editor({ kind, row, done }: { kind: MasterKind; row?: MasterRow; done: () => void }) {
  const { request } = useAuth()
  const [error, setError] = useState('')
  const [productId, setProductId] = useState(value(row, 'product_id'))
  const [addresses, setAddresses] = useState<Address[]>(
    kind === 'customers' && row ? addressSchema.array().parse(row.addresses) : [],
  )
  const defaults = Object.fromEntries(
    fields[kind].map((f) => [
      f.key,
      row
        ? value(row, f.key)
        : f.key === 'is_active'
          ? 'true'
          : f.key === 'individual_tracking'
            ? 'false'
            : f.key === 'person_type'
              ? 'PF'
              : '',
    ]),
  )
  const form = useForm<Record<string, string>>({ defaultValues: defaults })
  return (
    <form
      className="form-stack"
      onSubmit={form.handleSubmit(async (values) => {
        setError('')
        const body: Record<string, unknown> = { ...values }
        if (kind !== 'equipment') body.is_active = values.is_active === 'true'
        if (kind === 'products') body.individual_tracking = values.individual_tracking === 'true'
        if (kind === 'equipment') {
          body.product_id = Number(productId)
          body.asset_tag = values.asset_tag || null
          body.serial_number = values.serial_number || null
          if (!productId) {
            setError('Selecione um produto.')
            return
          }
        }
        if (kind === 'customers') body.addresses = addresses
        if (row) body.version = row.version
        try {
          await request('/' + kind + (row ? '/' + row.id : ''), row ? 'PUT' : 'POST', body)
          done()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Não foi possível salvar.')
        }
      })}
    >
      {kind === 'equipment' && (
        <ProductPicker selected={productId} onChange={setProductId} individual locked={!!row} />
      )}
      <div className="master-form-grid">
        {fields[kind].map((f) =>
          f.options ? (
            <Select key={f.key} label={f.label} {...form.register(f.key)}>
              {Object.entries(f.options).map(([key, text]) => (
                <option key={key} value={key}>
                  {text}
                </option>
              ))}
            </Select>
          ) : (
            <Field
              key={f.key}
              label={f.label}
              type={f.type || 'text'}
              maxLength={f.max}
              {...form.register(f.key, { required: f.required ? 'Preencha este campo.' : false })}
              error={form.formState.errors[f.key]?.message}
            />
          ),
        )}
      </div>
      {kind === 'customers' && (
        <section aria-label="Endereços">
          <div className="row-actions">
            <h3>Endereços</h3>
            <Button
              variant="secondary"
              disabled={addresses.length >= 10}
              onClick={() =>
                setAddresses([
                  ...addresses,
                  { label: 'Principal', street: '', city: '', state: '', postal_code: '' },
                ])
              }
            >
              Adicionar endereço
            </Button>
          </div>
          {addresses.map((address, index) => (
            <fieldset className="master-address" key={index}>
              <legend>Endereço {index + 1}</legend>
              <div className="master-form-grid">
                {(
                  [
                    ['label', 'Identificação', 60],
                    ['street', 'Endereço completo', 200],
                    ['city', 'Cidade', 100],
                    ['state', 'UF', 2],
                    ['postal_code', 'CEP', 9],
                  ] as const
                ).map(([key, text, max]) => (
                  <Field
                    key={key}
                    label={text + ' ' + (index + 1)}
                    required
                    maxLength={max}
                    pattern={
                      key === 'state'
                        ? '[A-Z]{2}'
                        : key === 'postal_code'
                          ? '[0-9]{5}-?[0-9]{3}'
                          : undefined
                    }
                    value={address[key]}
                    onChange={(e) =>
                      setAddresses(
                        addresses.map((a, i) =>
                          i === index
                            ? {
                                ...a,
                                [key]:
                                  key === 'state' ? e.target.value.toUpperCase() : e.target.value,
                              }
                            : a,
                        ),
                      )
                    }
                  />
                ))}
              </div>
              <Button
                variant="ghost"
                onClick={() => setAddresses(addresses.filter((_, i) => i !== index))}
              >
                Remover endereço {index + 1}
              </Button>
            </fieldset>
          ))}
        </section>
      )}
      <p className="field-hint">
        Alterações reais e auditadas. Campos identificados e códigos permanecem únicos mesmo após
        desativação.
      </p>
      <Failure message={error} />
      <Button type="submit" disabled={form.formState.isSubmitting}>
        {form.formState.isSubmitting ? 'Salvando…' : 'Salvar ' + singular[kind]}
      </Button>
    </form>
  )
}

function StatusEditor({ row, done }: { row: MasterRow; done: () => void }) {
  const { request } = useAuth()
  const [error, setError] = useState('')
  const form = useForm<{ status: string; reason: string }>({
    defaultValues: { status: value(row, 'status'), reason: '' },
  })
  return (
    <form
      className="form-stack"
      onSubmit={form.handleSubmit(async (payload) => {
        setError('')
        try {
          await request('/equipment/' + row.id + '/status', 'POST', {
            ...payload,
            version: row.version,
          })
          done()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Não foi possível movimentar.')
        }
      })}
    >
      <Select label="Nova situação" {...form.register('status')}>
        {Object.entries(states).map(([k, v]) => (
          <option key={k} value={k}>
            {v}
          </option>
        ))}
      </Select>
      <Field
        label="Motivo da alteração"
        required
        minLength={5}
        maxLength={500}
        {...form.register('reason', { required: true, minLength: 5 })}
      />
      <p>
        Baixado é definitivo. Unidades reservadas ou locadas precisam ser liberadas antes da baixa.
        A movimentação preservará o histórico.
      </p>
      <Failure message={error} />
      <Button type="submit" disabled={form.formState.isSubmitting}>
        Confirmar alteração
      </Button>
    </form>
  )
}

export function Masters({ kind }: { kind: MasterKind }) {
  const { request, user } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const [editor, setEditor] = useState<MasterRow | 'new' | null>(null)
  const [detail, setDetail] = useState<MasterRow | null>(null)
  const [status, setStatus] = useState<MasterRow | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const canWrite = user?.permissions.includes(kind + '.write')
  const canMove = user?.permissions.includes('stock.write')
  const productFilter =
    kind === 'equipment' && params.get('product')
      ? '&product_id=' + encodeURIComponent(params.get('product')!)
      : ''
  const query = useQuery({
    queryKey: ['masters', kind, q, filter, offset, productFilter],
    queryFn: async () =>
      pageSchema(masterSchemas[kind]).parse(
        await request(
          '/' +
            kind +
            '?limit=20&offset=' +
            offset +
            '&q=' +
            encodeURIComponent(q) +
            productFilter +
            (filter ? '&' + (kind === 'equipment' ? 'status' : 'active') + '=' + filter : ''),
        ),
      ),
    retry: false,
  })
  async function done() {
    setEditor(null)
    setStatus(null)
    setError('')
    toast('Registro salvo.')
    await cache.invalidateQueries({ queryKey: ['masters'] })
  }
  return (
    <>
      <PageHeader
        title={titles[kind]}
        description="Cadastros reais, com histórico e controle de acesso."
        actions={
          canWrite && <Button onClick={() => setEditor('new')}>Novo {singular[kind]}</Button>
        }
      />
      <Failure message={error} />
      <Card title={'Lista de ' + titles[kind].toLocaleLowerCase('pt-BR')}>
        <div className="master-filters">
          <Field
            label={'Buscar em ' + titles[kind].toLocaleLowerCase('pt-BR')}
            value={q}
            maxLength={160}
            onChange={(e) => {
              setQ(e.target.value)
              setOffset(0)
            }}
            placeholder="Nome, código ou documento"
          />
          <Select
            label="Filtrar situação"
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value)
              setOffset(0)
            }}
          >
            <option value="">Todas</option>
            {Object.entries(
              kind === 'equipment' ? states : { true: 'Ativos', false: 'Inativos' },
            ).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </Select>
        </div>
        {query.isPending ? (
          <Skeleton />
        ) : query.isError ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : (
          <>
            {!query.data.items.length ? (
              <EmptyState
                title="Nenhum registro encontrado"
                description="Cadastre o primeiro registro ou ajuste os filtros."
              />
            ) : (
              <MasterTable
                label={titles[kind]}
                headers={[
                  'Identificação',
                  kind === 'customers'
                    ? 'Documento / contato'
                    : kind === 'products'
                      ? 'Categoria / unidade'
                      : 'Produto / patrimônio',
                  'Situação',
                  'Ações',
                ]}
              >
                {query.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <strong>{label(row)}</strong>
                      <span className="cell-description">
                        {value(
                          row,
                          kind === 'customers'
                            ? 'trade_name'
                            : kind === 'products'
                              ? 'code'
                              : 'serial_number',
                        )}
                      </span>
                    </td>
                    <td>
                      {value(
                        row,
                        kind === 'customers'
                          ? 'document'
                          : kind === 'products'
                            ? 'category'
                            : 'product_name',
                      )}
                      <span className="cell-description">
                        {value(
                          row,
                          kind === 'customers'
                            ? 'email'
                            : kind === 'products'
                              ? 'unit'
                              : 'asset_tag',
                        )}
                      </span>
                    </td>
                    <td>{statusLabel(row)}</td>
                    <td>
                      <div className="row-actions">
                        <Button
                          variant="ghost"
                          onClick={() => setDetail(row)}
                          aria-label={'Detalhes de ' + label(row)}
                        >
                          Detalhes
                        </Button>
                        {canWrite && (
                          <Button
                            variant="ghost"
                            onClick={() => setEditor(row)}
                            aria-label={'Editar ' + label(row)}
                          >
                            Editar
                          </Button>
                        )}
                        {kind === 'equipment'
                          ? canMove &&
                            value(row, 'status') !== 'BAIXADO' && (
                              <Button variant="secondary" onClick={() => setStatus(row)}>
                                Alterar situação
                              </Button>
                            )
                          : canWrite &&
                            value(row, 'is_active') === 'true' && (
                              <ConfirmDialog
                                title={'Desativar ' + singular[kind] + '?'}
                                description={
                                  label(row) + ': o registro e seu histórico serão preservados.'
                                }
                                confirmLabel="Desativar"
                                trigger={
                                  <Button variant="secondary" disabled={busy}>
                                    Desativar
                                  </Button>
                                }
                                onConfirm={() => {
                                  setBusy(true)
                                  setError('')
                                  void request(
                                    '/' + kind + '/' + row.id + '?version=' + row.version,
                                    'DELETE',
                                  )
                                    .then(done)
                                    .catch((e) => setError(e.message))
                                    .finally(() => setBusy(false))
                                }}
                              />
                            )}
                      </div>
                    </td>
                  </tr>
                ))}
              </MasterTable>
            )}
            <Pager total={query.data.total} offset={offset} onChange={setOffset} />
          </>
        )}
      </Card>
      <Modal
        open={editor !== null}
        onOpenChange={(open) => {
          if (!open) setEditor(null)
        }}
        title={(editor === 'new' ? 'Novo ' : 'Editar ') + singular[kind]}
        description="Preencha os dados. O salvamento será auditado."
        className="master-modal"
      >
        {editor && (
          <Editor
            key={editor === 'new' ? 'new' : editor.id}
            kind={kind}
            row={editor === 'new' ? undefined : editor}
            done={() => void done()}
          />
        )}
      </Modal>
      <Modal
        open={detail !== null}
        onOpenChange={(open) => {
          if (!open) setDetail(null)
        }}
        title="Detalhes do cadastro"
        description={detail ? label(detail) : ''}
      >
        {detail && (
          <>
            <dl className="master-details">
              {fields[kind].map((f) => (
                <div key={f.key}>
                  <dt>{f.label}</dt>
                  <dd>
                    {f.options
                      ? f.options[value(detail, f.key)]
                      : value(detail, f.key) || 'Não informado'}
                  </dd>
                </div>
              ))}
            </dl>
            {kind === 'equipment' && (
              <p>
                Produto: {value(detail, 'product_name')} · {statusLabel(detail)}
              </p>
            )}
            {kind === 'customers' &&
              addressSchema
                .array()
                .parse(detail.addresses)
                .map((a, i) => (
                  <p key={i}>
                    {a.label}: {a.street}, {a.city} / {a.state} · CEP {a.postal_code}
                  </p>
                ))}
            <p>
              Atualizado em {new Date(Number(detail.updated_at) * 1000).toLocaleString('pt-BR')}
            </p>
          </>
        )}
      </Modal>
      <Modal
        open={status !== null}
        onOpenChange={(open) => {
          if (!open) setStatus(null)
        }}
        title="Alterar situação do equipamento"
        description={status ? label(status) : ''}
      >
        {status && <StatusEditor key={status.id} row={status} done={() => void done()} />}
      </Modal>
    </>
  )
}
