import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import { useAuth } from '../auth/context'
import { Button } from '../components/Button'
import { Card, PageHeader } from '../components/ui'
import { MasterTable, Pager } from './masters-shared'

const rowSchema = z.object({
  row: z.number(),
  status: z.string(),
  message: z.string(),
  warnings: z.array(z.string()),
})
const reportSchema = z.object({
  total: z.number(),
  successful: z.number(),
  ignored: z.number(),
  warnings: z.number(),
  errors: z.number(),
  rows: z.array(rowSchema),
  digest: z.string(),
  notice: z.string(),
  pending_sheets: z.array(z.string()),
  unmapped_columns: z.array(z.string()),
})
const mappingSchema = z.object({
  sheet: z.string(),
  header_row: z.number(),
  entity: z.string(),
  columns: z.record(z.string(), z.number()),
  decimal_separator: z.string(),
  date_format: z.string(),
})
const batchSchema = z.object({
  mapping: mappingSchema.nullable(),
  id: z.string(),
  filename: z.string(),
  status: z.string(),
  report: reportSchema.nullable(),
})
const uploadSchema = z.object({
  batch: batchSchema,
  sheets: z.array(
    z.object({
      name: z.string(),
      rows: z.number(),
      columns: z.number(),
      visibility: z.string(),
      formula_count: z.number(),
      merged_ranges: z.array(z.string()),
      sample: z.array(z.array(z.unknown())),
      warnings: z.array(z.tuple([z.string(), z.string()])),
    }),
  ),
})
const fieldsSchema = z.record(
  z.string(),
  z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      required: z.boolean(),
    }),
  ),
)
type Mapping = {
  sheet: string
  header_row: number
  entity: string
  columns: Record<string, number>
  decimal_separator: string
  date_format: string
}
const entities: Record<string, string> = {
  customers: 'Clientes',
  products: 'Produtos',
  equipment: 'Equipamentos',
  prices: 'Preços',
  stock: 'Entradas de estoque disponível',
}
function columnName(index: number) {
  let name = ''
  for (let n = index; n > 0; n = Math.floor((n - 1) / 26))
    name = String.fromCharCode(65 + ((n - 1) % 26)) + name
  return name
}
function download(report: unknown, id: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json;charset=utf-8',
    }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = 'importacao-' + id + '.json'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function Imports() {
  const { request, user, station } = useAuth()
  const cache = useQueryClient()
  const [upload, setUpload] = useState<z.infer<typeof uploadSchema> | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [mapping, setMapping] = useState<Mapping>({
    sheet: '',
    header_row: 1,
    entity: 'customers',
    columns: {},
    decimal_separator: ',',
    date_format: 'DMY',
  })
  const [report, setReport] = useState<z.infer<typeof reportSchema> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [acknowledged, setAcknowledged] = useState(false)
  const [offset, setOffset] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  // Sending, previewing and confirming happen on the main computer only (2026-11-03).
  const canWrite = !!user?.permissions.includes('imports.write') && !station
  const fields = useQuery({
    queryKey: ['import-fields'],
    queryFn: async () => fieldsSchema.parse(await request('/imports/fields')),
  })
  const history = useQuery({
    queryKey: ['import-history', historyOffset],
    queryFn: async () =>
      z.array(batchSchema).parse(await request('/imports?offset=' + historyOffset)),
  })
  function change(next: Partial<Mapping>) {
    setMapping((m) => ({ ...m, ...next }))
    setReport(null)
    setAcknowledged(false)
    setError('')
    setOffset(0)
  }
  async function perform(work: () => Promise<void>) {
    setBusy(true)
    setError('')
    try {
      await work()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Não foi possível concluir.')
    } finally {
      setBusy(false)
    }
  }
  const sheet = upload?.sheets.find((s) => s.name === mapping.sheet)
  const confirmed = upload?.batch.status === 'IMPORTED'
  const targetFields = fields.data?.[mapping.entity] || []
  const ready =
    targetFields.length > 0 && targetFields.every((f) => !f.required || mapping.columns[f.key])
  return (
    <>
      <PageHeader
        title="Importar Excel"
        description="Envie a planilha que sua empresa já utiliza. Revise a conversão antes de salvar."
      />
      <Card title="1. Enviar arquivo">
        <div className="import-body">
          <p>
            O original é preservado. Formatos .xlsx e .xlsm, até 10 MB; até 10.000 linhas por aba,
            200 colunas e 200.000 células no arquivo. Macros e fórmulas não são executadas.
          </p>
          <p>
            Converta uma aba e um módulo por operação. Importe produtos antes de equipamentos,
            estoque e preços. O histórico de contratos e renovações da planilha ainda não é
            convertido e fica preservado no arquivo original.
          </p>
          {station && (
            <div className="quote-notice" role="note">
              <strong>Enviar e confirmar importações só no computador principal.</strong>
              <span>Desta estação dá para consultar os lotes e os relatórios de importação.</span>
            </div>
          )}
          {canWrite && (
            <form
              className="form-stack"
              onSubmit={(event) => {
                event.preventDefault()
                if (!file) return
                void perform(async () => {
                  const body = new FormData()
                  body.append('file', file)
                  const data = uploadSchema.parse(await request('/imports/upload', 'POST', body))
                  setUpload(data)
                  change({ sheet: data.sheets[0]?.name || '', columns: {}, header_row: 1 })
                  await cache.invalidateQueries({ queryKey: ['import-history'] })
                })
              }}
            >
              <label>
                Arquivo Excel
                <input
                  type="file"
                  accept=".xlsx,.xlsm"
                  required
                  disabled={busy}
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
              </label>
              <Button type="submit" disabled={!file || busy}>
                Enviar e analisar Excel
              </Button>
            </form>
          )}
          {error && (
            <p role="alert" className="field-error">
              {error}
            </p>
          )}
        </div>
      </Card>
      {upload && (
        <Card title="2. Analisar e mapear">
          <div className="import-body">
            <p>
              <strong>{upload.batch.filename}</strong> · Importação {upload.batch.id}
            </p>
            <p>
              <a href={'/api/imports/' + upload.batch.id + '/original'} download>
                Baixar original preservado
              </a>
            </p>
            <div className="master-form-grid">
              <label>
                Aba do Excel
                <select
                  value={mapping.sheet}
                  disabled={busy || confirmed}
                  onChange={(e) => change({ sheet: e.target.value, columns: {} })}
                >
                  {upload.sheets.map((s) => (
                    <option key={s.name}>{s.name}</option>
                  ))}
                </select>
              </label>
              <label>
                Linha do cabeçalho
                <input
                  type="number"
                  min="1"
                  max={sheet?.rows || 1}
                  value={mapping.header_row}
                  disabled={busy || confirmed}
                  onChange={(e) => change({ header_row: Number(e.target.value), columns: {} })}
                />
              </label>
              <label>
                Converter para
                <select
                  value={mapping.entity}
                  disabled={busy || confirmed}
                  onChange={(e) => change({ entity: e.target.value, columns: {} })}
                >
                  {Object.entries(entities).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Separador decimal nos textos
                <select
                  value={mapping.decimal_separator}
                  disabled={busy || confirmed}
                  onChange={(e) => change({ decimal_separator: e.target.value })}
                >
                  <option value=",">Vírgula (123,45)</option>
                  <option value=".">Ponto (123.45)</option>
                </select>
              </label>
              <label>
                Formato das datas nos textos
                <select
                  value={mapping.date_format}
                  disabled={busy || confirmed}
                  onChange={(e) => change({ date_format: e.target.value })}
                >
                  <option value="DMY">Dia/mês/ano</option>
                  <option value="ISO">Ano-mês-dia</option>
                </select>
              </label>
            </div>
            {sheet && (
              <>
                <p>
                  {sheet.rows} linhas · {sheet.columns} colunas · {sheet.formula_count} fórmulas ·{' '}
                  {sheet.merged_ranges.length} áreas mescladas · visibilidade: {sheet.visibility}
                </p>
                {sheet.merged_ranges.length > 0 && (
                  <p>
                    Mesclas: {sheet.merged_ranges.join(', ')}. Células vazias não são preenchidas
                    automaticamente.
                  </p>
                )}
                {sheet.warnings.length > 0 && (
                  <details>
                    <summary>Avisos das células</summary>
                    <ul>
                      {sheet.warnings.map(([cell, message]) => (
                        <li key={cell}>
                          {cell}: {message}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <details>
                  <summary>Ver primeiras 20 linhas do arquivo</summary>
                  <MasterTable
                    label="Amostra do Excel"
                    headers={[
                      'Linha',
                      ...Array.from({ length: sheet.columns }, (_, i) => columnName(i + 1)),
                    ]}
                  >
                    {sheet.sample.map((row, i) => (
                      <tr key={i}>
                        <th>{i + 1}</th>
                        {row.map((v, j) => (
                          <td key={j}>{String(v ?? '')}</td>
                        ))}
                      </tr>
                    ))}
                  </MasterTable>
                </details>
                <p>
                  Escolha qual coluna alimenta cada campo. Campos com * são obrigatórios. Colunas
                  sem destino serão identificadas no relatório.
                </p>
                {fields.isError && (
                  <p role="alert">
                    Falha ao carregar campos.{' '}
                    <Button onClick={() => void fields.refetch()}>Tentar novamente</Button>
                  </p>
                )}
                <div className="master-form-grid">
                  {targetFields.map((field) => (
                    <label key={field.key}>
                      {field.label}
                      {field.required ? ' *' : ''}
                      <select
                        value={mapping.columns[field.key] || ''}
                        disabled={busy || confirmed}
                        onChange={(e) => {
                          const columns = { ...mapping.columns }
                          if (e.target.value) columns[field.key] = Number(e.target.value)
                          else delete columns[field.key]
                          change({ columns })
                        }}
                      >
                        <option value="">Não mapear</option>
                        {Array.from({ length: sheet.columns }, (_, i) => (
                          <option key={i} value={i + 1}>
                            {columnName(i + 1)} —{' '}
                            {String(sheet.sample[mapping.header_row - 1]?.[i] ?? 'Sem cabeçalho')}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
              </>
            )}
            {canWrite && !confirmed && (
              <Button
                disabled={busy || !ready}
                onClick={() =>
                  void perform(async () => {
                    setReport(
                      reportSchema.parse(
                        await request('/imports/' + upload.batch.id + '/preview', 'POST', mapping),
                      ),
                    )
                    setAcknowledged(false)
                    setOffset(0)
                  })
                }
              >
                Validar e gerar prévia (DRY RUN)
              </Button>
            )}
          </div>
        </Card>
      )}
      {report && (
        <Card title={confirmed ? 'Resultado da importação' : '3. Revisar prévia e confirmar'}>
          <div className="import-body">
            <p role="status">
              Total: {report.total} · {confirmed ? 'Importados' : 'Válidos'}: {report.successful} ·
              Ignorados: {report.ignored} · Avisos: {report.warnings} · Erros: {report.errors}
            </p>
            <p>{report.notice}</p>
            {confirmed && canWrite && upload && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    const data = uploadSchema.parse(
                      await request('/imports/' + upload.batch.id + '/new-conversion', 'POST'),
                    )
                    setUpload(data)
                    change({ sheet: data.sheets[0]?.name || '', header_row: 1, columns: {} })
                    await cache.invalidateQueries({ queryKey: ['import-history'] })
                  })
                }
              >
                Converter outra aba ou módulo deste arquivo
              </Button>
            )}
            <p>
              Colunas sem destino: {report.unmapped_columns.join(', ') || 'nenhuma'}. Outras abas
              pendentes: {report.pending_sheets.join(', ') || 'nenhuma'}.
            </p>
            <MasterTable label="Resultado por linha" headers={['Linha', 'Situação', 'Detalhes']}>
              {report.rows.slice(offset, offset + 20).map((row) => (
                <tr key={row.row}>
                  <td>{row.row}</td>
                  <td>{row.status}</td>
                  <td>
                    {row.message} {row.warnings.join(' ')}
                  </td>
                </tr>
              ))}
            </MasterTable>
            <Pager total={report.rows.length} offset={offset} onChange={setOffset} />
            <Button
              variant="secondary"
              onClick={() => download(report, upload?.batch.id || 'previa')}
            >
              Baixar relatório JSON
            </Button>
            {canWrite && !confirmed && upload && (
              <>
                <p>
                  O DRY RUN não gravou dados comerciais. A confirmação importa somente linhas
                  válidas e preserva os erros no relatório. Registros existentes não serão
                  sobrescritos.
                </p>
                <label className="checkbox-field">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    disabled={busy}
                    onChange={(e) => setAcknowledged(e.target.checked)}
                  />
                  Revisei os avisos, os erros e as informações que ficaram sem destino.
                </label>
                <Button
                  disabled={busy || !acknowledged || report.successful === 0}
                  onClick={() =>
                    void perform(async () => {
                      const batch = batchSchema.parse(
                        await request('/imports/' + upload.batch.id + '/confirm', 'POST', {
                          mapping,
                          preview_digest: report.digest,
                          confirm: true,
                        }),
                      )
                      setUpload({ ...upload, batch })
                      setReport(batch.report)
                      setAcknowledged(false)
                      await cache.invalidateQueries()
                    })
                  }
                >
                  Confirmar importação das linhas válidas
                </Button>
              </>
            )}
          </div>
        </Card>
      )}
      <Card title="Histórico de arquivos enviados">
        <div className="import-body">
          {history.isPending && <p role="status">Carregando histórico…</p>}
          {history.isError && (
            <p role="alert">
              Falha ao carregar histórico.{' '}
              <Button onClick={() => void history.refetch()}>Tentar novamente</Button>
            </p>
          )}
          {history.data?.length === 0 && <p>Nenhum arquivo enviado.</p>}
          {history.data?.map((batch) => (
            <p key={batch.id}>
              {batch.filename} ·{' '}
              {batch.status === 'IMPORTED' ? 'Confirmado' : 'Aguardando conversão'}{' '}
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    const data = uploadSchema.parse(await request('/imports/' + batch.id))
                    setUpload(data)
                    setReport(data.batch.report)
                    setAcknowledged(false)
                    setOffset(0)
                    if (data.batch.mapping) {
                      setMapping(data.batch.mapping)
                    } else if (data.batch.report) {
                      // Read-only reports can be reopened without requesting another conversion.
                      setMapping((m) => ({ ...m, sheet: data.sheets[0]?.name || '' }))
                    } else change({ sheet: data.sheets[0]?.name || '', header_row: 1, columns: {} })
                  })
                }
              >
                Abrir arquivo e relatório
              </Button>
            </p>
          ))}
          <div className="button-row">
            <Button
              variant="secondary"
              disabled={busy || historyOffset === 0}
              onClick={() => setHistoryOffset(Math.max(0, historyOffset - 20))}
            >
              Arquivos anteriores
            </Button>
            <Button
              variant="secondary"
              disabled={busy || (history.data?.length || 0) < 20}
              onClick={() => setHistoryOffset(historyOffset + 20)}
            >
              Próximos arquivos
            </Button>
          </div>
        </div>
      </Card>
    </>
  )
}
