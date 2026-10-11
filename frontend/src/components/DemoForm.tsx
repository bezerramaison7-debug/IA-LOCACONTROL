import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import type { ReactNode } from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import { Field, Select } from './ui'
import { useToast } from './toast-context'

const formSchema = z.object({
  name: z.string().trim().min(2, 'Informe pelo menos 2 caracteres.'),
  note: z.string().max(120, 'Use até 120 caracteres.'),
  period: z.enum(['Diária', 'Semanal', 'Quinzenal', 'Mensal']),
})

export function DemoForm({
  trigger,
  title = 'Prévia de orçamento',
}: {
  trigger: ReactNode
  title?: string
}) {
  const [open, setOpen] = useState(false)
  const notify = useToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { name: '', note: '', period: 'Mensal' },
  })
  return (
    <Modal
      open={open}
      onOpenChange={(value) => {
        setOpen(value)
        if (!value) reset()
      }}
      trigger={trigger}
      title={title}
      description="Prévia de formulário da Etapa 1. Use apenas dados fictícios; nada será cadastrado."
    >
      <form
        className="form-stack"
        noValidate
        onSubmit={handleSubmit(() => {
          setOpen(false)
          reset()
          notify('Prévia validada. Nenhum registro foi salvo.')
        })}
      >
        <Field
          label="Nome de exemplo"
          placeholder="Ex.: Obra de demonstração"
          autoComplete="off"
          {...register('name')}
          error={errors.name?.message}
        />
        <Select label="Período de locação" {...register('period')}>
          <option>Diária</option>
          <option>Semanal</option>
          <option>Quinzenal</option>
          <option>Mensal</option>
        </Select>
        <Field
          label="Observação de exemplo"
          hint="Opcional · até 120 caracteres"
          autoComplete="off"
          {...register('note')}
          error={errors.note?.message}
        />
        <div className="modal-actions">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Voltar
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Validando…' : 'Validar prévia'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
