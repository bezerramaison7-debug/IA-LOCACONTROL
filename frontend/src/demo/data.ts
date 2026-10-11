import type { Status } from '../components/ui'

// Fixtures EXCLUSIVAMENTE visuais da Etapa 1. Nunca enviadas para a API ou persistidas.
export type DemoRow = {
  id: string
  name: string
  secondary: string
  detail: string
  date: string
  status: Status
}
export const contracts: DemoRow[] = [
  {
    id: 'DEMO-1042',
    name: 'Construtora Horizonte (exemplo)',
    secondary: 'Betoneira 400 L · 2 unidades',
    detail: 'Mensal',
    date: '2026-09-14',
    status: 'Vencendo',
  },
  {
    id: 'DEMO-1041',
    name: 'Obras Almeida (exemplo)',
    secondary: 'Andaime tubular · 12 unidades',
    detail: 'Quinzenal',
    date: '2026-09-13',
    status: 'Vencendo',
  },
  {
    id: 'DEMO-1040',
    name: 'Reforma Ideal (exemplo)',
    secondary: 'Martelete 5 kg · 1 unidade',
    detail: 'Semanal',
    date: '2026-09-10',
    status: 'Vencido',
  },
  {
    id: 'DEMO-1039',
    name: 'Engenharia Norte (exemplo)',
    secondary: 'Compactador de solo · 1 unidade',
    detail: 'Mensal',
    date: '2026-09-26',
    status: 'Ativo',
  },
  {
    id: 'DEMO-1038',
    name: 'Construções Vale (exemplo)',
    secondary: 'Escora metálica · 20 unidades',
    detail: 'Mensal',
    date: '2026-09-28',
    status: 'Ativo',
  },
  {
    id: 'DEMO-1037',
    name: 'Projeto Casa (exemplo)',
    secondary: 'Serra circular · 1 unidade',
    detail: 'Diária',
    date: '2026-09-09',
    status: 'Encerrado',
  },
  {
    id: 'DEMO-1036',
    name: 'Obra Jardim (exemplo)',
    secondary: 'Lixadeira · 2 unidades',
    detail: 'Semanal',
    date: '2026-09-08',
    status: 'Cancelado',
  },
]

export function displayDate(iso: string) {
  const [year, month, day] = iso.split('-')
  return `${day}/${month}/${year}`
}
