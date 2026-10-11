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

export const catalogData: Record<string, DemoRow[]> = {
  clientes: contracts.map((row, i) => ({
    ...row,
    id: `CLI-DEMO-00${i + 1}`,
    secondary: 'Pessoa jurídica · cadastro fictício',
    detail: i % 2 ? 'Campinas · SP' : 'São Paulo · SP',
    status: 'Ativo',
  })),
  produtos: [
    {
      id: 'PRO-DEMO-01',
      name: 'Betoneira 400 L',
      secondary: 'Mistura e preparo',
      detail: 'Unidade individual',
      date: '2026-09-12',
      status: 'Ativo',
    },
    {
      id: 'PRO-DEMO-02',
      name: 'Andaime tubular',
      secondary: 'Acesso e elevação',
      detail: 'Por quantidade',
      date: '2026-09-12',
      status: 'Ativo',
    },
    {
      id: 'PRO-DEMO-03',
      name: 'Martelete 5 kg',
      secondary: 'Perfuração e demolição',
      detail: 'Unidade individual',
      date: '2026-09-12',
      status: 'Ativo',
    },
    {
      id: 'PRO-DEMO-04',
      name: 'Compactador de solo',
      secondary: 'Compactação',
      detail: 'Unidade individual',
      date: '2026-09-12',
      status: 'Ativo',
    },
  ],
  equipamentos: [
    {
      id: 'BET-DEMO-01',
      name: 'Betoneira 400 L',
      secondary: 'Unidade física · demonstração',
      detail: 'Pátio principal',
      date: '2026-09-12',
      status: 'Disponível',
    },
    {
      id: 'BET-DEMO-02',
      name: 'Betoneira 400 L',
      secondary: 'Unidade física · demonstração',
      detail: 'Oficina',
      date: '2026-09-12',
      status: 'Manutenção',
    },
    {
      id: 'MAR-DEMO-01',
      name: 'Martelete 5 kg',
      secondary: 'Unidade física · demonstração',
      detail: 'Pátio principal',
      date: '2026-09-12',
      status: 'Disponível',
    },
  ],
  orcamentos: contracts.map((row, i) => ({
    ...row,
    id: `ORC-DEMO-00${i + 1}`,
    status: 'Rascunho',
  })),
  contratos: contracts,
}

export function displayDate(iso: string) {
  const [year, month, day] = iso.split('-')
  return `${day}/${month}/${year}`
}
