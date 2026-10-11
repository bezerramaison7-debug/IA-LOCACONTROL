import { useId, useRef, useState, type ReactNode } from 'react'
import { useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/context'
import { decimalInput, equipmentSchema, localDate, pageSchema, periods } from '../lib/masters'
import {
  actionError,
  conditions,
  contractStatuses,
  customerLine,
  destinations,
  expectedReturn,
  getContract,
  positive,
  priceOptions,
  quantityInput,
  registerReturn,
  registerWithdrawal,
  renewContract,
  useContractPermissions,
  type ActionError,
  type Condition,
  type Contract,
  type ContractItem,
  type Destination,
  type PriceOption,
} from '../lib/contracts'
import {
  brDate,
  brMoney,
  brQuantity,
  centsText,
  estimateCents,
  getPricing,
  scaled,
  type QuotePeriod,
} from '../lib/quotes'
import { Button } from '../components/Button'
import { Modal } from '../components/Modal'
import { Card, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure } from './masters-shared'
import { ActionFailure } from './contracts-shared'
import type { Operation } from './contracts-detail'

type FormProps = {
  contract: Contract
  onDone: (contract: Contract, message: string) => void
  onCancel: () => void
  onReload: () => void
}
type Errors = Record<string, string>
const isDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value)
const unitsText = (count: number) => count + (count === 1 ? ' unidade física' : ' unidades físicas')

function Check({
  checked,
  onChange,
  children,
  type = 'checkbox',
  name,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  children: ReactNode
  type?: 'checkbox' | 'radio'
  name?: string
}) {
  return (
    <label className="quote-check">
      <input
        type={type}
        name={name}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{children}</span>
    </label>
  )
}

function Notes({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        rows={2}
        maxLength={500}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

/**
 * Second step of every operation: what will be sent and what it causes. The request only
 * leaves from here, once, with the request key created when the form was opened.
 */
function Review({
  open,
  title,
  contract,
  lines,
  children,
  confirm,
  busy,
  failure,
  onReload,
  onClose,
  onConfirm,
}: {
  open: boolean
  title: string
  contract: Contract
  lines: string[]
  children: ReactNode
  confirm: string
  busy: boolean
  failure: ActionError | null
  onReload: () => void
  onClose: () => void
  onConfirm: () => void
}) {
  return (
    <Modal
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen && !busy) onClose()
      }}
      title={title}
      description={'Contrato ' + contract.number + ' · ' + contract.customer.legal_name}
    >
      <div className="form-stack">
        <ul className="contract-review">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <div className="quote-notice">{children}</div>
        <ActionFailure failure={failure} onReload={onReload} />
        <div className="modal-actions">
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Voltar e revisar
          </Button>
          <Button disabled={busy} onClick={onConfirm}>
            {busy ? 'Registrando…' : confirm}
          </Button>
        </div>
      </div>
    </Modal>
  )
}

/** One request at a time: the ref blocks a second click before React re-renders. */
function useSubmit(onDone: FormProps['onDone']) {
  const sending = useRef(false)
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<ActionError | null>(null)
  async function submit(task: () => Promise<Contract>, done: (result: Contract) => string) {
    if (sending.current) return
    sending.current = true
    setBusy(true)
    setFailure(null)
    try {
      const result = await task()
      onDone(result, done(result))
    } catch (e) {
      setFailure(actionError(e, 'Não foi possível registrar a operação.'))
    } finally {
      sending.current = false
      setBusy(false)
    }
  }
  return { busy, failure, submit, clear: () => setFailure(null) }
}

function FormActions({ label, onCancel }: { label: string; onCancel: () => void }) {
  return (
    <div className="row-actions">
      <Button type="submit">{label}</Button>
      <Button variant="secondary" onClick={onCancel}>
        Voltar ao contrato
      </Button>
    </div>
  )
}

function WithdrawalForm({ contract, onDone, onCancel, onReload }: FormProps) {
  const { request } = useAuth()
  const can = useContractPermissions()
  const items = contract.items.filter((item) => positive(item.to_withdraw))
  const [key] = useState(() => crypto.randomUUID())
  const [date, setDate] = useState(localDate)
  const [notes, setNotes] = useState('')
  const [quantities, setQuantities] = useState<Record<number, string>>(() =>
    Object.fromEntries(items.map((item) => [item.id, quantityInput(item.to_withdraw)])),
  )
  const [chosen, setChosen] = useState<Record<number, number[]>>({})
  const [errors, setErrors] = useState<Errors>({})
  const [review, setReview] = useState<string[] | null>(null)
  const { busy, failure, submit, clear } = useSubmit(onDone)
  const canUnits = can.has('equipment.read')
  const candidates = useQueries({
    queries: items.map((item) => ({
      queryKey: ['contracts', 'candidates', item.product_id],
      queryFn: async () =>
        pageSchema(equipmentSchema).parse(
          await request(
            '/equipment?product_id=' + item.product_id + '&status=DISPONIVEL&limit=100&offset=0',
          ),
        ),
      enabled: item.individual_tracking && canUnits,
      retry: false,
    })),
  })
  const lines = () =>
    items.flatMap((item) => {
      const text = (quantities[item.id] || '').trim()
      const milli = text ? scaled(text, 3) : 0n
      return milli === 0n ? [] : [{ item, text, milli, units: chosen[item.id] || [] }]
    })
  function validate() {
    const found: Errors = {}
    if (!isDate(date)) found.date = 'Informe a data da retirada.'
    const active = lines()
    for (const { item, milli, units } of active) {
      if (milli === null) found[item.id] = 'Use um número com até três casas decimais.'
      else if (milli > scaled(item.to_withdraw, 3)!)
        found[item.id] =
          'A quantidade supera o saldo a retirar (' +
          brQuantity(item.to_withdraw) +
          ' ' +
          item.unit +
          ').'
      else if (item.individual_tracking && milli % 1000n !== 0n)
        found[item.id] = 'Item com unidade física exige quantidade inteira.'
      else if (item.individual_tracking && BigInt(units.length) !== milli / 1000n)
        found[item.id] =
          'Selecione exatamente ' +
          unitsText(Number(milli / 1000n)) +
          ' de ' +
          item.product_name +
          '.'
    }
    if (!active.length) found.form = 'Informe a quantidade de pelo menos um item.'
    setErrors(found)
    if (Object.keys(found).length) return
    clear()
    setReview(
      active.map(({ item, text, units }, index) => {
        const codes = candidates[items.indexOf(item)]?.data?.items
          .filter((unit) => units.includes(unit.id))
          .map((unit) => unit.code)
        return (
          index +
          1 +
          '. ' +
          brQuantity(decimalInput(text)) +
          ' ' +
          item.unit +
          ' de ' +
          item.product_name +
          (codes?.length ? ' · ' + codes.join(', ') : '')
        )
      }),
    )
  }
  return (
    <form
      className="form-stack"
      noValidate
      aria-label={'Registrar retirada do contrato ' + contract.number}
      onSubmit={(e) => {
        e.preventDefault()
        validate()
      }}
    >
      <Card title="Dados da retirada" description="A retirada baixa o estoque disponível.">
        <div className="padded form-stack">
          <div className="master-form-grid">
            <Field
              label="Data da retirada"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              error={errors.date}
            />
          </div>
          <Notes label="Observação da retirada (opcional)" value={notes} onChange={setNotes} />
        </div>
      </Card>
      <Card
        title="Itens a retirar"
        description="Deixe a quantidade em branco ou zero para não retirar o item agora."
      >
        <div className="padded form-stack">
          {items.map((item, index) => {
            const query = candidates[index]
            const picked = chosen[item.id] || []
            return (
              <fieldset className="master-address quote-item" key={item.id}>
                <legend>
                  {item.product_name} ({item.product_code})
                </legend>
                <div className="form-stack">
                  <div className="master-form-grid">
                    <Field
                      label={'Quantidade a retirar de ' + item.product_name}
                      inputMode="decimal"
                      maxLength={10}
                      autoComplete="off"
                      value={quantities[item.id] ?? ''}
                      onChange={(e) =>
                        setQuantities((known) => ({ ...known, [item.id]: e.target.value }))
                      }
                      hint={
                        'A retirar: ' +
                        brQuantity(item.to_withdraw) +
                        ' ' +
                        item.unit +
                        (item.individual_tracking ? ' · quantidade inteira.' : '.')
                      }
                      error={errors[item.id]}
                    />
                  </div>
                  {item.individual_tracking &&
                    (!canUnits ? (
                      <ErrorState message="Seu perfil não consulta equipamentos, e este item exige a escolha das unidades físicas. Peça a permissão de consulta de equipamentos." />
                    ) : query.isPending ? (
                      <Skeleton rows={1} />
                    ) : query.isError ? (
                      <ErrorState
                        message={query.error.message}
                        onRetry={() => void query.refetch()}
                      />
                    ) : !query.data.items.length ? (
                      <p className="quote-notice quote-notice-danger">
                        Nenhuma unidade física disponível deste produto. Libere uma unidade da
                        manutenção ou cadastre um equipamento antes de registrar a retirada.
                      </p>
                    ) : (
                      <fieldset className="contract-choices">
                        <legend>Unidades físicas de {item.product_name}</legend>
                        <p className="field-hint">
                          Uma unidade por quantidade retirada · {picked.length} selecionada(s).
                        </p>
                        {query.data.items.map((unit) => (
                          <Check
                            key={unit.id}
                            checked={picked.includes(unit.id)}
                            onChange={(checked) =>
                              setChosen((known) => ({
                                ...known,
                                [item.id]: checked
                                  ? [...picked, unit.id]
                                  : picked.filter((id) => id !== unit.id),
                              }))
                            }
                          >
                            {unit.code}
                            {(unit.asset_tag || unit.serial_number) && (
                              <small>
                                {[
                                  unit.asset_tag && 'Patrimônio ' + unit.asset_tag,
                                  unit.serial_number && 'Série ' + unit.serial_number,
                                ]
                                  .filter(Boolean)
                                  .join(' · ')}
                              </small>
                            )}
                          </Check>
                        ))}
                      </fieldset>
                    ))}
                </div>
              </fieldset>
            )
          })}
          <Failure message={errors.form || ''} />
          <FormActions label="Revisar retirada" onCancel={onCancel} />
        </div>
      </Card>
      <Review
        open={review !== null}
        title="Confirmar retirada"
        contract={contract}
        lines={review || []}
        confirm="Confirmar retirada"
        busy={busy}
        failure={failure}
        onReload={onReload}
        onClose={() => setReview(null)}
        onConfirm={() =>
          void submit(
            () =>
              registerWithdrawal(request, contract.id, {
                occurred_on: date,
                notes: notes.trim(),
                request_key: key,
                items: lines().map(({ item, text, units }) => ({
                  contract_item_id: item.id,
                  quantity: decimalInput(text),
                  equipment_ids: item.individual_tracking ? units : [],
                })),
              }),
            () => 'Retirada registrada no contrato ' + contract.number + '.',
          )
        }
      >
        <p>
          Ao confirmar, estes itens saem do estoque disponível e passam a constar como locados, com
          o cliente, a partir de {isDate(date) ? brDate(date) : 'hoje'}.
          {contract.stored_status !== 'ATIVO' &&
            ' O contrato passa a Ativo e não pode mais ser cancelado.'}{' '}
          Para desfazer, será preciso registrar uma devolução.
        </p>
      </Review>
    </form>
  )
}

type ReturnLine = {
  key: string
  item: ContractItem
  equipmentId: number | null
  name: string
  selected: boolean
  quantity: string
  condition: Condition
  destination: Destination
  notes: string
}

function ReturnForm({ contract, onDone, onCancel, onReload }: FormProps) {
  const { request } = useAuth()
  const [key] = useState(() => crypto.randomUUID())
  const [date, setDate] = useState(localDate)
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<ReturnLine[]>(() =>
    contract.items
      .filter((item) => positive(item.outstanding))
      .flatMap((item): ReturnLine[] => {
        const base = {
          item,
          selected: true,
          condition: 'BOM' as const,
          destination: 'DISPONIVEL' as const,
          notes: '',
        }
        return item.individual_tracking
          ? item.units
              .filter((unit) => unit.state === 'EM_POSSE')
              .map((unit) => ({
                ...base,
                key: 'u' + unit.equipment_id,
                equipmentId: unit.equipment_id,
                name: item.product_name + ' ' + unit.code,
                quantity: '1',
              }))
          : [
              {
                ...base,
                key: 'i' + item.id,
                equipmentId: null,
                name: item.product_name,
                quantity: quantityInput(item.outstanding),
              },
            ]
      }),
  )
  const [errors, setErrors] = useState<Errors>({})
  const [review, setReview] = useState<string[] | null>(null)
  const { busy, failure, submit, clear } = useSubmit(onDone)
  const change = (lineKey: string, patch: Partial<ReturnLine>) =>
    setLines((known) => known.map((line) => (line.key === lineKey ? { ...line, ...patch } : line)))
  const active = lines.filter((line) => line.selected)
  // Nothing stays with the customer when every pending line is returned in full.
  const everything =
    active.length === lines.length &&
    active.every(
      (line) =>
        line.equipmentId !== null || scaled(line.quantity, 3) === scaled(line.item.outstanding, 3),
    )
  const leftToWithdraw = contract.items.some((item) => positive(item.to_withdraw))
  function validate() {
    const found: Errors = {}
    if (!isDate(date)) found.date = 'Informe a data da devolução.'
    for (const line of active) {
      if (line.equipmentId !== null) continue
      const milli = scaled(line.quantity, 3)
      if (milli === null || milli === 0n)
        found[line.key] = 'Informe uma quantidade maior que zero, com até três casas decimais.'
      else if (milli > scaled(line.item.outstanding, 3)!)
        found[line.key] =
          'A quantidade devolvida supera a quantidade com o cliente (' +
          brQuantity(line.item.outstanding) +
          ' ' +
          line.item.unit +
          ').'
    }
    if (!active.length) found.form = 'Selecione pelo menos um item para devolver.'
    setErrors(found)
    if (Object.keys(found).length) return
    clear()
    setReview(
      active.map(
        (line, index) =>
          index +
          1 +
          '. ' +
          (line.equipmentId === null
            ? brQuantity(decimalInput(line.quantity)) + ' ' + line.item.unit + ' de '
            : '') +
          line.name +
          ' · ' +
          conditions[line.condition] +
          ' → ' +
          destinations[line.destination],
      ),
    )
  }
  return (
    <form
      className="form-stack"
      noValidate
      aria-label={'Registrar devolução do contrato ' + contract.number}
      onSubmit={(e) => {
        e.preventDefault()
        validate()
      }}
    >
      <Card
        title="Dados da devolução"
        description="A devolução devolve os itens ao estoque, conforme a condição informada."
      >
        <div className="padded form-stack">
          <div className="master-form-grid">
            <Field
              label="Data da devolução"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              error={errors.date}
            />
          </div>
          <Notes label="Observação da devolução (opcional)" value={notes} onChange={setNotes} />
        </div>
      </Card>
      <Card
        title="Itens com o cliente"
        description="Desmarque o que continua com o cliente. Item avariado segue obrigatoriamente para manutenção."
      >
        <div className="padded form-stack">
          {lines.map((line) => (
            <fieldset className="master-address quote-item" key={line.key}>
              <legend>{line.name}</legend>
              <div className="form-stack">
                <Check
                  checked={line.selected}
                  onChange={(selected) => change(line.key, { selected })}
                >
                  Devolver {line.name}
                  <small>
                    {line.equipmentId === null
                      ? 'Com o cliente: ' +
                        brQuantity(line.item.outstanding) +
                        ' ' +
                        line.item.unit +
                        '. Para devolver parte em bom estado e parte avariada, registre duas devoluções.'
                      : 'Unidade física ' + line.item.product_code + ' com o cliente.'}
                  </small>
                </Check>
                {line.selected && (
                  <div className="quote-item-grid">
                    {line.equipmentId === null && (
                      <Field
                        label={'Quantidade devolvida de ' + line.name}
                        inputMode="decimal"
                        maxLength={10}
                        autoComplete="off"
                        value={line.quantity}
                        onChange={(e) => change(line.key, { quantity: e.target.value })}
                        error={errors[line.key]}
                      />
                    )}
                    <Select
                      label={'Condição de ' + line.name}
                      value={line.condition}
                      onChange={(e) => {
                        const condition = e.target.value as Condition
                        change(line.key, {
                          condition,
                          destination: condition === 'AVARIADO' ? 'MANUTENCAO' : 'DISPONIVEL',
                        })
                      }}
                    >
                      {Object.entries(conditions).map(([value, text]) => (
                        <option key={value} value={value}>
                          {text}
                        </option>
                      ))}
                    </Select>
                    <div>
                      <Select
                        label={'Destino de ' + line.name}
                        value={line.destination}
                        disabled={line.condition === 'AVARIADO'}
                        onChange={(e) =>
                          change(line.key, { destination: e.target.value as Destination })
                        }
                      >
                        {Object.entries(destinations).map(([value, text]) => (
                          <option key={value} value={value}>
                            {text}
                          </option>
                        ))}
                      </Select>
                      {line.condition === 'AVARIADO' && (
                        <p className="field-hint">Avariado segue para manutenção.</p>
                      )}
                    </div>
                    <Field
                      label={'Observação de ' + line.name}
                      maxLength={500}
                      autoComplete="off"
                      value={line.notes}
                      onChange={(e) => change(line.key, { notes: e.target.value })}
                    />
                  </div>
                )}
              </div>
            </fieldset>
          ))}
          <Failure message={errors.form || ''} />
          <FormActions label="Revisar devolução" onCancel={onCancel} />
        </div>
      </Card>
      <Review
        open={review !== null}
        title="Confirmar devolução"
        contract={contract}
        lines={review || []}
        confirm="Confirmar devolução"
        busy={busy}
        failure={failure}
        onReload={onReload}
        onClose={() => setReview(null)}
        onConfirm={() =>
          void submit(
            () =>
              registerReturn(request, contract.id, {
                occurred_on: date,
                notes: notes.trim(),
                request_key: key,
                items: active.map((line) => ({
                  contract_item_id: line.item.id,
                  quantity: line.equipmentId === null ? decimalInput(line.quantity) : '1.000',
                  equipment_id: line.equipmentId,
                  condition: line.condition,
                  destination: line.condition === 'AVARIADO' ? 'MANUTENCAO' : line.destination,
                  notes: line.notes.trim(),
                })),
              }),
            (result) =>
              result.stored_status === 'ENCERRADO'
                ? 'Devolução total registrada. Contrato ' + contract.number + ' encerrado.'
                : 'Devolução registrada no contrato ' + contract.number + '.',
          )
        }
      >
        <p>
          Ao confirmar, estes itens voltam ao estoque no destino indicado e deixam de constar com o
          cliente. A devolução não pode ser desfeita.
        </p>
        <p>
          <strong>
            {!everything
              ? 'Devolução parcial: o restante continua com o cliente e o contrato segue ativo.'
              : leftToWithdraw
                ? 'Nada ficará com o cliente. Como ainda há saldo a retirar, o contrato continua ativo até nova retirada ou encerramento manual.'
                : 'Devolução total: o contrato será encerrado automaticamente.'}
          </strong>
        </p>
      </Review>
    </form>
  )
}

type RenewalLine = {
  item: ContractItem
  selected: boolean
  quantity: string
  units: number[]
  period: QuotePeriod
  periodCount: string
  unitPrice: string
}

const optionHelp: Record<PriceOption, string> = {
  ANTERIORES: 'Mesmo período e mesmo preço de cada item do contrato atual.',
  ATUAIS: 'Preço da tabela vigente na data de início da renovação.',
  NEGOCIADOS: 'Você informa o preço de cada item. Valor diferente da tabela exige permissão.',
}

function RenewalForm({ contract, onDone, onCancel, onReload }: FormProps) {
  const { request } = useAuth()
  const can = useContractPermissions()
  const canPrice = can.has('quotes.read')
  const [startDate, setStartDate] = useState(() => expectedReturn(contract))
  const [option, setOption] = useState<PriceOption | ''>('')
  const [notes, setNotes] = useState('')
  const [lines, setLines] = useState<RenewalLine[]>(() =>
    contract.items
      .filter((item) => positive(item.outstanding))
      .map((item) => ({
        item,
        selected: true,
        quantity: quantityInput(item.outstanding),
        units: item.units
          .filter((unit) => unit.state === 'EM_POSSE')
          .map((unit) => unit.equipment_id),
        period: item.period,
        periodCount: String(item.period_count),
        unitPrice: '',
      })),
  )
  const [errors, setErrors] = useState<Errors>({})
  const [review, setReview] = useState<string[] | null>(null)
  const { busy, failure, submit, clear } = useSubmit(onDone)
  const change = (id: number, patch: Partial<RenewalLine>) =>
    setLines((known) => known.map((line) => (line.item.id === id ? { ...line, ...patch } : line)))
  const periodOf = (line: RenewalLine) => (option === 'ANTERIORES' ? line.item.period : line.period)
  const quantityOf = (line: RenewalLine) =>
    line.item.individual_tracking ? String(line.units.length) : line.quantity
  const pricing = useQueries({
    queries: lines.map((line) => ({
      queryKey: ['quotes', 'pricing', String(line.item.product_id), periodOf(line), startDate],
      queryFn: () => getPricing(request, String(line.item.product_id), periodOf(line), startDate),
      enabled:
        canPrice &&
        line.selected &&
        isDate(startDate) &&
        (option === 'ATUAIS' || option === 'NEGOCIADOS'),
      retry: false,
    })),
  })
  const active = lines.filter((line) => line.selected)
  const everything =
    active.length === lines.length &&
    active.every((line) =>
      line.item.individual_tracking
        ? line.units.length === line.item.units.filter((unit) => unit.state === 'EM_POSSE').length
        : scaled(line.quantity, 3) === scaled(line.item.outstanding, 3),
    )
  const leftToWithdraw = contract.items.some((item) => positive(item.to_withdraw))
  /** Price used only for the preview; the server applies the official one. */
  const previewPrice = (line: RenewalLine, index: number) =>
    option === 'ANTERIORES'
      ? line.item.unit_price
      : option === 'NEGOCIADOS'
        ? line.unitPrice.trim() || null
        : option === 'ATUAIS'
          ? (pricing[index]?.data?.table_price ?? null)
          : null
  function validate() {
    const found: Errors = {}
    if (!option) found.option = 'Escolha a opção de preço da renovação.'
    if (!isDate(startDate)) found.date = 'Informe o início da renovação.'
    for (const line of active) {
      const id = line.item.id
      if (line.item.individual_tracking) {
        if (!line.units.length) found[id] = 'Selecione ao menos uma unidade física para renovar.'
      } else {
        const milli = scaled(line.quantity, 3)
        if (milli === null || milli === 0n)
          found[id] = 'Informe uma quantidade maior que zero, com até três casas decimais.'
        else if (milli > scaled(line.item.outstanding, 3)!)
          found[id] =
            'A quantidade renovada supera a quantidade com o cliente (' +
            brQuantity(line.item.outstanding) +
            ' ' +
            line.item.unit +
            ').'
      }
      if (!/^[1-9]\d{0,2}$/.test(line.periodCount.trim()))
        found['count' + id] = 'Informe um número inteiro de 1 a 999.'
      if (option === 'NEGOCIADOS' && !/^\d{1,9}([.,]\d{1,2})?$/.test(line.unitPrice.trim()))
        found['price' + id] = 'Informe o preço negociado com até duas casas decimais.'
    }
    if (!active.length) found.form = 'Selecione pelo menos um item para renovar.'
    setErrors(found)
    if (Object.keys(found).length || !option) return
    clear()
    setReview(
      active.map((line, index) => {
        const price = previewPrice(line, lines.indexOf(line))
        return (
          index +
          1 +
          '. ' +
          brQuantity(decimalInput(quantityOf(line))) +
          ' ' +
          line.item.unit +
          ' de ' +
          line.item.product_name +
          ' · ' +
          line.periodCount.trim() +
          ' × ' +
          periods[periodOf(line)] +
          (price ? ' · ' + brMoney(centsText(scaled(price, 2) ?? 0n)) + ' por período' : '')
        )
      }),
    )
  }
  return (
    <form
      className="form-stack"
      noValidate
      aria-label={'Renovar contrato ' + contract.number}
      onSubmit={(e) => {
        e.preventDefault()
        validate()
      }}
    >
      <Card
        title="Dados da renovação"
        description="A renovação cria um novo contrato na mesma cadeia e não movimenta estoque."
      >
        <div className="padded form-stack">
          <div className="master-form-grid">
            <Field
              label="Início da renovação"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              hint="Sugestão: a devolução prevista do contrato atual."
              error={errors.date}
            />
          </div>
          <fieldset
            className="contract-choices"
            aria-describedby={errors.option ? 'renewal-option-error' : undefined}
          >
            <legend>Opção de preço (obrigatória)</legend>
            <p className="field-hint">A opção escolhida fica registrada no contrato renovado.</p>
            {(Object.keys(priceOptions) as PriceOption[]).map((value) => (
              <Check
                key={value}
                type="radio"
                name="price_option"
                checked={option === value}
                onChange={() => setOption(value)}
              >
                {priceOptions[value]}
                <small>{optionHelp[value]}</small>
              </Check>
            ))}
            {errors.option && (
              <p className="field-error" id="renewal-option-error" role="alert">
                {errors.option}
              </p>
            )}
          </fieldset>
          <Notes label="Observações da renovação (opcional)" value={notes} onChange={setNotes} />
        </div>
      </Card>
      <Card
        title="Itens com o cliente"
        description="Desmarque o que não será renovado: esses itens continuam pendentes no contrato atual."
      >
        <div className="padded form-stack">
          {lines.map((line, index) => {
            const item = line.item
            const query = pricing[index]
            const price = previewPrice(line, index)
            const estimate = price ? estimateCents(quantityOf(line), price, line.periodCount) : null
            return (
              <fieldset className="master-address quote-item" key={item.id}>
                <legend>
                  {item.product_name} ({item.product_code})
                </legend>
                <div className="form-stack">
                  <Check
                    checked={line.selected}
                    onChange={(selected) => change(item.id, { selected })}
                  >
                    Renovar {item.product_name}
                    <small>
                      Com o cliente: {brQuantity(item.outstanding)} {item.unit} · contrato atual:{' '}
                      {item.period_count} × {periods[item.period]} a {brMoney(item.unit_price)}
                    </small>
                  </Check>
                  {line.selected && (
                    <>
                      {item.individual_tracking && (
                        <fieldset className="contract-choices">
                          <legend>Unidades de {item.product_name} a renovar</legend>
                          {item.units
                            .filter((unit) => unit.state === 'EM_POSSE')
                            .map((unit) => (
                              <Check
                                key={unit.equipment_id}
                                checked={line.units.includes(unit.equipment_id)}
                                onChange={(checked) =>
                                  change(item.id, {
                                    units: checked
                                      ? [...line.units, unit.equipment_id]
                                      : line.units.filter((id) => id !== unit.equipment_id),
                                  })
                                }
                              >
                                {unit.code}
                              </Check>
                            ))}
                          <Failure message={errors[item.id] || ''} />
                        </fieldset>
                      )}
                      <div className="quote-item-grid">
                        {!item.individual_tracking && (
                          <Field
                            label={'Quantidade renovada de ' + item.product_name}
                            inputMode="decimal"
                            maxLength={10}
                            autoComplete="off"
                            value={line.quantity}
                            onChange={(e) => change(item.id, { quantity: e.target.value })}
                            error={errors[item.id]}
                          />
                        )}
                        <div>
                          <Select
                            label={'Período de ' + item.product_name}
                            value={periodOf(line)}
                            disabled={option === 'ANTERIORES'}
                            onChange={(e) =>
                              change(item.id, { period: e.target.value as QuotePeriod })
                            }
                          >
                            {Object.entries(periods).map(([value, text]) => (
                              <option key={value} value={value}>
                                {text}
                              </option>
                            ))}
                          </Select>
                          {option === 'ANTERIORES' && (
                            <p className="field-hint">Preços anteriores mantêm o mesmo período.</p>
                          )}
                        </div>
                        <Field
                          label={'Número de períodos de ' + item.product_name}
                          inputMode="numeric"
                          maxLength={3}
                          autoComplete="off"
                          value={line.periodCount}
                          onChange={(e) => change(item.id, { periodCount: e.target.value })}
                          error={errors['count' + item.id]}
                        />
                        {option === 'NEGOCIADOS' && (
                          <Field
                            label={'Preço negociado de ' + item.product_name + ' (R$)'}
                            inputMode="decimal"
                            maxLength={12}
                            autoComplete="off"
                            value={line.unitPrice}
                            onChange={(e) => change(item.id, { unitPrice: e.target.value })}
                            hint={
                              can.negotiate
                                ? 'Preço por período.'
                                : 'Seu perfil só pode informar o preço de tabela.'
                            }
                            error={errors['price' + item.id]}
                          />
                        )}
                      </div>
                      <div className="quote-line-info">
                        {(option === 'ATUAIS' || option === 'NEGOCIADOS') &&
                          (!canPrice ? (
                            <p className="field-hint">
                              O preço de tabela vigente será conferido pelo servidor ao salvar.
                            </p>
                          ) : query?.isPending ? (
                            <p className="field-hint" role="status">
                              Consultando preço de tabela…
                            </p>
                          ) : query?.isError ? (
                            <p className="field-hint">
                              Não foi possível consultar a tabela ({query.error.message}). O
                              servidor confere o preço ao salvar.
                            </p>
                          ) : query?.data?.table_price ? (
                            <p>
                              Preço de tabela em {brDate(startDate)}:{' '}
                              <strong>{brMoney(query.data.table_price)}</strong> por período (
                              {periods[periodOf(line)]})
                            </p>
                          ) : (
                            query?.data && (
                              <p className="quote-notice quote-notice-danger" role="alert">
                                Não há preço {periods[periodOf(line)]} vigente para este produto em{' '}
                                {brDate(startDate)}. Cadastre o preço, mude o período ou mantenha os
                                preços anteriores.
                              </p>
                            )
                          ))}
                        {estimate !== null && <p>Prévia do item: {brMoney(centsText(estimate))}</p>}
                      </div>
                    </>
                  )}
                </div>
              </fieldset>
            )
          })}
          <p className="field-hint">
            A prévia é uma estimativa. O valor oficial é calculado pelo servidor ao renovar.
          </p>
          <Failure message={errors.form || ''} />
          <FormActions label="Revisar renovação" onCancel={onCancel} />
        </div>
      </Card>
      <Review
        open={review !== null}
        title="Confirmar renovação"
        contract={contract}
        lines={review || []}
        confirm="Confirmar renovação"
        busy={busy}
        failure={failure}
        onReload={onReload}
        onClose={() => setReview(null)}
        onConfirm={() => {
          if (!option) return
          void submit(
            () =>
              renewContract(request, contract.id, {
                version: contract.version,
                start_date: startDate,
                price_option: option,
                notes: notes.trim(),
                items: active.map((line) => ({
                  source_item_id: line.item.id,
                  quantity: decimalInput(quantityOf(line)),
                  period: periodOf(line),
                  period_count: Number(line.periodCount.trim()),
                  unit_price: option === 'NEGOCIADOS' ? decimalInput(line.unitPrice) : null,
                  equipment_ids: line.item.individual_tracking ? line.units : [],
                })),
              }),
            (result) => 'Contrato ' + result.number + ' criado por renovação.',
          )
        }}
      >
        <p>
          Opção de preço: <strong>{option ? priceOptions[option] : ''}</strong>. Será criado um novo
          contrato na cadeia {contract.base_number}, já ativo, com início em{' '}
          {isDate(startDate) ? brDate(startDate) : ''}. Renovar não movimenta estoque e não pode ser
          desfeito.
        </p>
        <p>
          <strong>
            {!everything
              ? 'Renovação parcial: os itens não renovados continuam pendentes no contrato ' +
                contract.number +
                '.'
              : leftToWithdraw
                ? 'Todos os itens com o cliente passam para o novo contrato. O contrato ' +
                  contract.number +
                  ' continua ativo porque ainda tem saldo a retirar.'
                : 'Todos os itens com o cliente passam para o novo contrato e o contrato ' +
                  contract.number +
                  ' será encerrado automaticamente.'}
          </strong>
        </p>
      </Review>
    </form>
  )
}

const operations = {
  retirada: {
    title: 'Registrar retirada',
    permission: 'operations.write',
    denied: 'Seu perfil não tem permissão para registrar retiradas.',
    allowed: (contract: Contract) =>
      ['AGUARDANDO_RETIRADA', 'ATIVO'].includes(contract.stored_status) &&
      contract.items.some((item) => positive(item.to_withdraw)),
    blocked: 'não tem saldo a retirar ou não permite retirada',
    Form: WithdrawalForm,
  },
  devolucao: {
    title: 'Registrar devolução',
    permission: 'operations.write',
    denied: 'Seu perfil não tem permissão para registrar devoluções.',
    allowed: (contract: Contract) =>
      contract.stored_status === 'ATIVO' &&
      contract.items.some((item) => positive(item.outstanding)),
    blocked: 'não tem itens com o cliente para devolver',
    Form: ReturnForm,
  },
  renovar: {
    title: 'Renovar contrato',
    permission: 'contracts.write',
    denied: 'Seu perfil não tem permissão para renovar contratos.',
    allowed: (contract: Contract) =>
      contract.stored_status === 'ATIVO' &&
      contract.items.some((item) => positive(item.outstanding)),
    blocked: 'não tem itens com o cliente para renovar',
    Form: RenewalForm,
  },
}

/** Dedicated view for an operation: long forms read better as a page than as a modal on mobile. */
export function ContractOperation({
  id,
  operation,
  onBack,
  onOpen,
}: {
  id: number
  operation: Operation
  onBack: () => void
  onOpen: (id: number) => void
}) {
  const { request } = useAuth()
  const can = useContractPermissions()
  const cache = useQueryClient()
  const toast = useToast()
  const config = operations[operation]
  const query = useQuery({
    queryKey: ['contracts', 'detail', id],
    queryFn: () => getContract(request, id),
    retry: false,
  })
  const back = (
    <Button variant="secondary" onClick={onBack}>
      Voltar ao contrato
    </Button>
  )
  if (!can.has(config.permission))
    return (
      <>
        <PageHeader title={config.title} description="Operação do contrato." actions={back} />
        <ErrorState message={config.denied} />
      </>
    )
  if (query.isPending)
    return (
      <>
        <PageHeader title={config.title} description="Carregando o contrato." actions={back} />
        <Skeleton rows={4} />
      </>
    )
  if (query.isError)
    return (
      <>
        <PageHeader title={config.title} description="Não foi possível abrir." actions={back} />
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      </>
    )
  const contract = query.data
  const Form = config.Form
  return (
    <>
      <PageHeader
        title={config.title + ' · contrato ' + contract.number}
        description={customerLine(contract)}
        actions={back}
      />
      {!config.allowed(contract) ? (
        <ErrorState
          message={
            'O contrato ' +
            contract.number +
            ' (' +
            contractStatuses[contract.status] +
            ') ' +
            config.blocked +
            '.'
          }
        />
      ) : (
        <Form
          key={contract.id + ':' + contract.version}
          contract={contract}
          onCancel={onBack}
          onReload={() => void cache.invalidateQueries({ queryKey: ['contracts'] })}
          onDone={(result, message) => {
            toast(message)
            void cache.invalidateQueries({ queryKey: ['contracts'] })
            void cache.invalidateQueries({ queryKey: ['masters'] })
            onOpen(result.id)
          }}
        />
      )}
    </>
  )
}
