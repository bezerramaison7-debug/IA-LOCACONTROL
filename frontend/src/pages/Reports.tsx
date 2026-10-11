import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileDown, FileSpreadsheet } from 'lucide-react'
import { canOpen, useAuth } from '../auth/context'
import {
  REPORT_PAGE,
  downloadReport,
  emptyFilters,
  formatCell,
  getCatalog,
  getReport,
  numericTypes,
  reportFilterKinds,
  type ExportFormat,
  type Report,
  type ReportFilters,
} from '../lib/reports'
import { failureMessage } from '../lib/quotes'
import { Button } from '../components/Button'
import { Card, EmptyState, ErrorState, Field, PageHeader, Select, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { Failure, Pager } from './masters-shared'
import { RecordPicker } from './quotes-editor'

/** Generic table: the server declares the columns and how each value must be shown. */
export function ReportTable({ report, linkContracts }: { report: Report; linkContracts: boolean }) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={'Tabela: ' + report.title}>
      <table className="data-table">
        <caption className="sr-only">{report.title}</caption>
        <thead>
          <tr>
            {report.columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={numericTypes.includes(column.type) ? 'number-cell' : undefined}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {report.rows.map((row, index) => (
            <tr key={index}>
              {report.columns.map((column, position) => {
                const text = formatCell(column.type, row[column.key])
                const contract = row.contract_id
                return (
                  <td
                    key={column.key}
                    className={
                      numericTypes.includes(column.type)
                        ? 'number-cell'
                        : column.type === 'date'
                          ? 'date-cell'
                          : undefined
                    }
                  >
                    {position === 0 && linkContracts && typeof contract === 'number' ? (
                      <Link to={'/contratos?id=' + contract}>{text}</Link>
                    ) : (
                      text
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Reports() {
  const { user, request } = useAuth()
  const toast = useToast()
  const [selected, setSelected] = useState('')
  const [filters, setFilters] = useState<ReportFilters>(emptyFilters)
  const [labels, setLabels] = useState({ customer: '', product: '' })
  const [offset, setOffset] = useState(0)
  const [exporting, setExporting] = useState<ExportFormat | null>(null)
  const [exportError, setExportError] = useState('')
  const catalog = useQuery({
    queryKey: ['reports', 'catalog'],
    queryFn: () => getCatalog(request),
    retry: false,
  })
  const key = selected || catalog.data?.items[0]?.key || ''
  const kinds = reportFilterKinds(key)
  const invalidPeriod =
    kinds.includes('period') &&
    !!filters.date_from &&
    !!filters.date_to &&
    filters.date_to < filters.date_from
  const report = useQuery({
    queryKey: ['reports', 'run', key, filters, offset],
    queryFn: () => getReport(request, key, filters, offset),
    enabled: !!key && !invalidPeriod,
    retry: false,
  })
  const change = (next: Partial<ReportFilters>) => {
    setFilters({ ...filters, ...next })
    setOffset(0)
  }
  const filtered = Object.values(filters).some(Boolean)
  async function exportAs(format: ExportFormat) {
    setExportError('')
    setExporting(format)
    try {
      await downloadReport(key, format, filters)
      toast(format === 'xlsx' ? 'Planilha Excel gerada.' : 'PDF gerado.')
    } catch (e) {
      setExportError(failureMessage(e, 'Não foi possível exportar o relatório.'))
    } finally {
      setExporting(null)
    }
  }
  return (
    <>
      <PageHeader
        title="Relatórios"
        description="Consultas calculadas na hora, a partir dos contratos, do estoque e das movimentações."
      />
      {catalog.isPending ? (
        <Skeleton />
      ) : catalog.isError ? (
        <ErrorState message={catalog.error.message} onRetry={() => void catalog.refetch()} />
      ) : !catalog.data.items.length ? (
        <Card>
          <EmptyState
            initial
            title="Nenhum relatório disponível"
            description="O servidor não informou relatórios para este ambiente."
          />
        </Card>
      ) : (
        <Card
          title={report.data?.title || 'Relatório'}
          description="Escolha o relatório, ajuste os filtros e exporte o resultado completo."
        >
          <div className="master-filters">
            <Select
              label="Relatório"
              value={key}
              onChange={(e) => {
                setSelected(e.target.value)
                setOffset(0)
                setExportError('')
              }}
            >
              {catalog.data.items.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.title}
                </option>
              ))}
            </Select>
            {kinds.includes('period') && (
              <>
                <Field
                  label="Período: de"
                  type="date"
                  value={filters.date_from}
                  onChange={(e) => change({ date_from: e.target.value })}
                />
                <Field
                  label="Período: até"
                  type="date"
                  value={filters.date_to}
                  error={invalidPeriod ? 'A data final é anterior à inicial.' : undefined}
                  onChange={(e) => change({ date_to: e.target.value })}
                />
              </>
            )}
            {kinds.includes('q') && (
              <Field
                label="Buscar no relatório"
                value={filters.q}
                maxLength={160}
                placeholder="Código, nome, patrimônio ou serial"
                onChange={(e) => change({ q: e.target.value })}
              />
            )}
          </div>
          {(kinds.includes('customer') || kinds.includes('product')) && (
            <div className="padded form-stack report-pickers">
              {kinds.includes('customer') && (
                <RecordPicker
                  kind="customers"
                  searchLabel="Buscar cliente para filtrar"
                  label="Cliente do relatório"
                  placeholder="Todos os clientes"
                  value={filters.customer_id}
                  knownLabel={labels.customer}
                  onChange={(id, text) => {
                    setLabels({ ...labels, customer: text })
                    change({ customer_id: id })
                  }}
                />
              )}
              {kinds.includes('product') && (
                <RecordPicker
                  kind="products"
                  searchLabel="Buscar produto para filtrar"
                  label="Produto do relatório"
                  placeholder="Todos os produtos"
                  value={filters.product_id}
                  knownLabel={labels.product}
                  onChange={(id, text) => {
                    setLabels({ ...labels, product: text })
                    change({ product_id: id })
                  }}
                />
              )}
            </div>
          )}
          <div className="padded form-stack">
            <div className="row-actions" role="group" aria-label="Exportar relatório">
              <Button
                variant="secondary"
                disabled={!!exporting || invalidPeriod || !report.isSuccess}
                onClick={() => void exportAs('xlsx')}
              >
                <FileSpreadsheet size={16} aria-hidden="true" />
                {exporting === 'xlsx' ? 'Gerando Excel…' : 'Exportar Excel'}
              </Button>
              <Button
                variant="secondary"
                disabled={!!exporting || invalidPeriod || !report.isSuccess}
                onClick={() => void exportAs('pdf')}
              >
                <FileDown size={16} aria-hidden="true" />
                {exporting === 'pdf' ? 'Gerando PDF…' : 'Exportar PDF'}
              </Button>
              {filtered && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setFilters(emptyFilters)
                    setLabels({ customer: '', product: '' })
                    setOffset(0)
                  }}
                >
                  Limpar filtros
                </Button>
              )}
            </div>
            <p className="field-hint" aria-live="polite">
              {exporting
                ? 'Gerando o arquivo com todas as linhas do relatório. Você pode continuar usando a tela.'
                : 'A exportação traz todas as linhas com os filtros acima, não só a página exibida.'}
            </p>
            <Failure message={exportError} />
            {report.data?.note && (
              <p className="quote-notice" role="note">
                {report.data.note}
              </p>
            )}
          </div>
          {invalidPeriod ? (
            <ErrorState message="Corrija o período: a data final é anterior à inicial." />
          ) : report.isPending ? (
            <Skeleton />
          ) : report.isError ? (
            <ErrorState message={report.error.message} onRetry={() => void report.refetch()} />
          ) : !report.data.rows.length ? (
            <EmptyState
              initial={!filtered}
              title={
                filtered ? 'Nenhuma linha para estes filtros' : 'Nada a mostrar neste relatório'
              }
              description={
                filtered
                  ? 'Ajuste o período ou limpe os filtros.'
                  : 'Quando houver registros, eles aparecem aqui.'
              }
            />
          ) : (
            <>
              <ReportTable report={report.data} linkContracts={canOpen(user, '/contratos')} />
              <Pager
                total={report.data.total}
                offset={offset}
                size={REPORT_PAGE}
                onChange={setOffset}
              />
            </>
          )}
        </Card>
      )}
    </>
  )
}
