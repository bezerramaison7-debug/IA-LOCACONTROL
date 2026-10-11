import { createContext, useContext } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'
export const themeKey = 'locacontrol.theme'
export function isTheme(value: unknown): value is ThemePreference {
  return value === 'system' || value === 'light' || value === 'dark'
}
export const ThemeContext = createContext<{
  preference: ThemePreference
  resolved: 'light' | 'dark'
  setPreference: (preference: ThemePreference) => void
} | null>(null)

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('ThemeProvider ausente')
  return context
}
