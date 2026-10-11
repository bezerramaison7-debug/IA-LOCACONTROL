import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme, type ThemePreference } from '../theme/context'
import { useId } from 'react'

export function ThemeSelect({ compact = false }: { compact?: boolean }) {
  const { preference, setPreference } = useTheme()
  const id = useId()
  const Icon = preference === 'system' ? Monitor : preference === 'dark' ? Moon : Sun
  return (
    <div className={`theme-select ${compact ? 'theme-compact' : ''}`}>
      <Icon size={18} aria-hidden="true" />
      <label className="sr-only" htmlFor={id}>
        Tema
      </label>
      <select
        id={id}
        value={preference}
        onChange={(e) => setPreference(e.target.value as ThemePreference)}
        title="Tema: Sistema / Claro / Escuro"
      >
        <option value="system">Sistema</option>
        <option value="light">Claro</option>
        <option value="dark">Escuro</option>
      </select>
    </div>
  )
}
