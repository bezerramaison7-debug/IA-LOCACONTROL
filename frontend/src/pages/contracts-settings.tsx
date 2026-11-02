import { useId, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useAuth } from '../auth/context'
import {
  actionError,
  getNumbering,
  getTemplates,
  publishTemplate,
  setNumbering,
  type ActionError,
  type Templates,
} from '../lib/contracts'
import { brDateTime } from '../lib/quotes'
import { Button } from '../components/Button'
import { Card, ErrorState, Field, Skeleton } from '../components/ui'
import { useToast } from '../components/toast-context'
import { ActionFailure } from './contracts-shared'

function NumberingForm({ next, highest }: { next: number; highest: number | null }) {
  const { request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const [failure, setFailure] = useState<ActionError | null>(null)
  const reload = () => void cache.invalidateQueries({ queryKey: ['contracts', 'numbering'] })
  const form = useForm<{ next: string }>({ defaultValues: { next: String(next) } })
  return (
    <form
      className="form-stack"
      noValidate
      aria-label="Numeração de contratos"
      onSubmit={form.handleSubmit(async (values) => {
        setFailure(null)
        try {
          const saved = await setNumbering(request, Number(values.next.trim()))
          toast('Próximo contrato sairá com o número ' + saved.next_number + '.')
          reload()
        } catch (e) {
          setFailure(actionError(e, 'Não foi possível salvar a numeração.'))
        }
      })}
    >
      <p>
        Próximo número: <strong>{next}</strong> ·{' '}
        {highest ? 'maior número já usado: ' + highest : 'nenhum contrato numerado ainda'}.
        Renovações mantêm o número e ganham sufixo (9193 → 9193.1).
      </p>
      <div className="master-form-grid">
        <Field
          label="Próximo número de contrato"
          inputMode="numeric"
          maxLength={9}
          autoComplete="off"
          hint="Use para continuar a numeração do sistema anterior. Deve ser maior que o maior número já usado."
          {...form.register('next', {
            validate: (value) => {
              if (!/^[1-9]\d{0,8}$/.test(value.trim())) return 'Informe um número inteiro positivo.'
              return (
                !highest ||
                Number(value.trim()) > highest ||
                'Informe um número maior que ' + highest + ', o maior já usado.'
              )
            },
          })}
          error={form.formState.errors.next?.message}
        />
      </div>
      <ActionFailure failure={failure} onReload={reload} reloadLabel="Recarregar numeração" />
      <div className="row-actions">
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Salvando…' : 'Salvar numeração'}
        </Button>
      </div>
    </form>
  )
}

function TemplateForm({ templates }: { templates: Templates }) {
  const { request } = useAuth()
  const cache = useQueryClient()
  const toast = useToast()
  const bodyId = useId()
  const [failure, setFailure] = useState<ActionError | null>(null)
  const current = templates.items.find((item) => item.is_active)
  const reload = () => void cache.invalidateQueries({ queryKey: ['contracts', 'templates'] })
  const form = useForm<{ name: string; body: string; is_provisional: boolean }>({
    defaultValues: { name: current?.name || '', body: current?.body || '', is_provisional: false },
  })
  const errors = form.formState.errors
  return (
    <form
      className="form-stack"
      noValidate
      aria-label="Modelo de contrato"
      onSubmit={form.handleSubmit(async (values) => {
        setFailure(null)
        try {
          await publishTemplate(request, values)
          toast('Nova versão do modelo publicada. Ela passa a ser o modelo em uso.')
          reload()
        } catch (e) {
          setFailure(actionError(e, 'Não foi possível publicar o modelo.'))
        }
      })}
    >
      {current ? (
        <p className={current.is_provisional ? 'quote-notice' : undefined} role="note">
          <span>
            Modelo em uso: <strong>{current.name}</strong>, versão {current.version}, publicado em{' '}
            {brDateTime(current.created_at)}.
            {current.is_provisional &&
              ' Este modelo é provisório: é um texto de exemplo e os PDFs saem com esse aviso até a locadora publicar o seu contrato oficial.'}
          </span>
        </p>
      ) : (
        <p className="quote-notice quote-notice-danger">
          Não há modelo de contrato ativo. Publique um para gerar documentos.
        </p>
      )}
      <Field
        label="Nome do modelo"
        maxLength={120}
        autoComplete="off"
        {...form.register('name', {
          validate: (value) => value.trim().length >= 3 || 'Informe um nome com 3+ caracteres.',
        })}
        error={errors.name?.message}
      />
      <div className="field">
        <label htmlFor={bodyId}>Texto do modelo</label>
        <textarea
          id={bodyId}
          className="contract-template"
          rows={14}
          maxLength={60000}
          spellCheck={false}
          aria-invalid={!!errors.body}
          aria-describedby={bodyId + '-help'}
          {...form.register('body', {
            validate: (value) =>
              value.trim().length >= 20 || 'Informe o texto do contrato (20+ caracteres).',
          })}
        />
        <p className={errors.body ? 'field-error' : 'field-hint'} id={bodyId + '-help'}>
          {errors.body?.message ||
            'Linhas iniciadas por “# ” viram títulos. Os blocos precisam ficar sozinhos na linha.'}
        </p>
      </div>
      <div className="contract-placeholders">
        <div>
          <h3>Campos disponíveis</h3>
          <ul aria-label="Campos disponíveis">
            {templates.fields.map((field) => (
              <li key={field}>
                <code>{'{{ ' + field + ' }}'}</code>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h3>Blocos (sozinhos na linha)</h3>
          <ul aria-label="Blocos disponíveis">
            {templates.blocks.map((block) => (
              <li key={block}>
                <code>{'{{ ' + block + ' }}'}</code>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <label className="quote-check">
        <input type="checkbox" {...form.register('is_provisional')} />
        <span>
          Publicar como modelo provisório
          <small>
            Marque apenas para textos de exemplo: os PDFs saem com o aviso de modelo provisório.
          </small>
        </span>
      </label>
      <p className="field-hint">
        Publicar cria uma nova versão, que passa a valer para os próximos documentos. Documentos já
        gerados ou assinados não mudam.
      </p>
      <ActionFailure failure={failure} onReload={reload} reloadLabel="Recarregar modelos" />
      <div className="row-actions">
        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Publicando…' : 'Publicar nova versão'}
        </Button>
      </div>
    </form>
  )
}

/** Contract numbering and document model, for profiles with `contracts.configure`. */
export function ContractSettings() {
  const { request } = useAuth()
  const numbering = useQuery({
    queryKey: ['contracts', 'numbering'],
    queryFn: () => getNumbering(request),
    retry: false,
  })
  const templates = useQuery({
    queryKey: ['contracts', 'templates'],
    queryFn: () => getTemplates(request),
    retry: false,
  })
  return (
    <>
      <Card
        title="Numeração de contratos"
        description="Define o número do próximo contrato novo. Números usados nunca são reaproveitados."
      >
        <div className="padded">
          {numbering.isPending ? (
            <Skeleton rows={1} />
          ) : numbering.isError ? (
            <ErrorState
              message={numbering.error.message}
              onRetry={() => void numbering.refetch()}
            />
          ) : (
            <NumberingForm
              key={numbering.data.next_number}
              next={numbering.data.next_number}
              highest={numbering.data.highest_used}
            />
          )}
        </div>
      </Card>
      <Card
        title="Modelo de contrato"
        description="Texto usado para gerar o PDF do contrato. Cada publicação é uma nova versão."
      >
        <div className="padded">
          {templates.isPending ? (
            <Skeleton rows={2} />
          ) : templates.isError ? (
            <ErrorState
              message={templates.error.message}
              onRetry={() => void templates.refetch()}
            />
          ) : (
            <TemplateForm
              key={templates.data.items.find((item) => item.is_active)?.id ?? 0}
              templates={templates.data}
            />
          )}
        </div>
      </Card>
    </>
  )
}
