import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, send, sessionSchema, type AuthUser } from './api'
import { AuthContext } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const csrf = useRef('')
  const generation = useRef(0)
  const invalidate = useCallback(() => {
    generation.current++
  }, [])
  const cache = useQueryClient()
  const clear = useCallback(() => {
    generation.current++
    csrf.current = ''
    setUser(null)
    cache.clear()
  }, [cache])
  const refresh = useCallback(() => {
    const current = ++generation.current
    return send('/auth/me', '')
      .then((raw) => {
        const data = sessionSchema.parse(raw)
        if (current === generation.current) {
          setError('')
          csrf.current = data.csrf_token
          setUser(data.user)
          setLoading(false)
        }
      })
      .catch((error) => {
        if (current !== generation.current) return
        clear()
        setError(
          error instanceof ApiError && error.status === 401
            ? ''
            : error instanceof Error
              ? error.message
              : 'Erro de conexão.',
        )
        setLoading(false)
      })
  }, [clear])
  useEffect(() => {
    void refresh()
    return invalidate
  }, [refresh, invalidate])
  useEffect(() => {
    const check = () => {
      if (document.visibilityState === 'visible') void refresh()
    }
    window.addEventListener('focus', check)
    return () => window.removeEventListener('focus', check)
  }, [refresh])
  const request = useCallback(
    async (path: string, method = 'GET', body?: unknown) => {
      try {
        return await send(path, csrf.current, method, body)
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) clear()
        throw error
      }
    },
    [clear],
  )
  const login = async (username: string, password: string) => {
    const data = sessionSchema.parse(await send('/auth/login', '', 'POST', { username, password }))
    generation.current++
    cache.clear()
    csrf.current = data.csrf_token
    setUser(data.user)
    setError('')
    return data.user
  }
  const logout = async () => {
    await request('/auth/logout', 'POST')
    clear()
  }
  return (
    <AuthContext.Provider value={{ user, loading, error, refresh, login, logout, request, clear }}>
      {children}
    </AuthContext.Provider>
  )
}
