import { useEffect, useState, type ReactNode } from 'react'
import { readPreference, writePreference } from '../lib/preferences'
import { isTheme, themeKey, ThemeContext, type ThemePreference } from './context'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setTheme] = useState<ThemePreference>(() => {
    const saved = readPreference(themeKey)
    return isTheme(saved) ? saved : 'system'
  })
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  const resolved = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const changed = () => setSystemDark(query.matches)
    query.addEventListener('change', changed)
    changed()
    return () => query.removeEventListener('change', changed)
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = resolved
    document.documentElement.style.colorScheme = resolved
  }, [resolved])

  useEffect(() => {
    const changed = (event: StorageEvent) => {
      if (event.key === themeKey || event.key === null) {
        setTheme(isTheme(event.newValue) ? event.newValue : 'system')
      }
    }
    window.addEventListener('storage', changed)
    return () => window.removeEventListener('storage', changed)
  }, [])

  function setPreference(value: ThemePreference) {
    setTheme(value)
    writePreference(themeKey, value)
  }

  return (
    <ThemeContext.Provider value={{ preference, resolved, setPreference }}>
      {children}
    </ThemeContext.Provider>
  )
}
