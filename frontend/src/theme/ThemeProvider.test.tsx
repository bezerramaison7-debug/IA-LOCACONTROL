import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { ThemeProvider } from './ThemeProvider'
import { ThemeSelect } from '../components/ThemeSelect'
import { themeKey } from './context'

it('defaults to system and follows operating system changes', () => {
  let changed = () => {}
  const media = {
    matches: false,
    addEventListener: vi.fn((_event, listener) => {
      changed = listener
    }),
    removeEventListener: vi.fn(),
  }
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => media),
  )
  const { unmount } = render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  )
  expect(screen.getByLabelText('Tema')).toHaveValue('system')
  expect(document.documentElement.dataset.theme).toBe('light')
  act(() => {
    media.matches = true
    changed()
  })
  expect(document.documentElement.dataset.theme).toBe('dark')
  unmount()
  expect(media.removeEventListener).toHaveBeenCalled()
})

it('persists a choice and restores it when mounted again', async () => {
  const user = userEvent.setup()
  const { unmount } = render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  )
  await user.selectOptions(screen.getByLabelText('Tema'), 'dark')
  expect(localStorage.getItem(themeKey)).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
  unmount()
  render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  )
  expect(screen.getByLabelText('Tema')).toHaveValue('dark')
})

it('handles invalid preferences and blocked localStorage without crashing', async () => {
  localStorage.setItem(themeKey, 'invalid')
  render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  )
  expect(screen.getByLabelText('Tema')).toHaveValue('system')
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new DOMException('Blocked')
  })
  await userEvent.setup().selectOptions(screen.getByLabelText('Tema'), 'dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
})

it('applies preference changes from another tab', () => {
  render(
    <ThemeProvider>
      <ThemeSelect />
    </ThemeProvider>,
  )
  act(() => window.dispatchEvent(new StorageEvent('storage', { key: themeKey, newValue: 'dark' })))
  expect(screen.getByLabelText('Tema')).toHaveValue('dark')
  act(() => window.dispatchEvent(new StorageEvent('storage', { key: themeKey, newValue: null })))
  expect(screen.getByLabelText('Tema')).toHaveValue('system')
})
