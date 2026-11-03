import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { ApiError, send, sessionSchema, type AuthUser } from './api'
import { AuthContext } from './context'

export const SESSION_RENEWED =
  'A sessão deste computador foi renovada automaticamente. Nada foi gravado: confira os dados ' +
  'e envie novamente.'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [local, setLocal] = useState(false)
  const localRef = useRef(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const csrf = useRef('')
  const generation = useRef(0)
  const invalidate = useCallback(() => {
    generation.current++
  }, [])
  const cache = useQueryClient()
  const reset = useCallback(() => {
    generation.current++
    csrf.current = ''
    signedIn.current = false
    setUser(null)
    cache.clear()
  }, [cache])
  const markLocal = useCallback((value: boolean) => {
    localRef.current = value
    setLocal(value)
  }, [])
  const signedIn = useRef(false)
  const refresh = useCallback(
    (background = false) => {
      const current = ++generation.current
      return send('/auth/me', '')
        .then((raw) => {
          const data = sessionSchema.parse(raw)
          if (current === generation.current) {
            markLocal(data.edition === 'local')
            setError('')
            csrf.current = data.csrf_token
            signedIn.current = true
            setUser(data.user)
            setLoading(false)
          }
        })
        .catch((error) => {
          if (current !== generation.current) return
          // A check on focus that cannot reach the server (it restarted, the network dropped)
          // keeps the screen and whatever is being typed; only a real "no access" ends it.
          if (
            background &&
            signedIn.current &&
            error instanceof ApiError &&
            (error.status === 0 || error.status >= 500)
          )
            return
          if (error instanceof ApiError && error.local) markLocal(true)
          reset()
          setError(
            error instanceof ApiError && error.status === 401 && !error.local
              ? ''
              : error instanceof Error
                ? error.message
                : 'Erro de conexão.',
          )
          setLoading(false)
        })
    },
    [reset, markLocal],
  )
  /** Local edition: an ended session is reopened at once; there is no login screen. */
  const clear = useCallback(() => {
    reset()
    if (localRef.current) {
      setLoading(true)
      void refresh()
    }
  }, [reset, refresh])
  useEffect(() => {
    void refresh()
    return invalidate
  }, [refresh, invalidate])
  useEffect(() => {
    const check = () => {
      if (document.visibilityState === 'visible') void refresh(true)
    }
    window.addEventListener('focus', check)
    return () => window.removeEventListener('focus', check)
  }, [refresh])
  /** Local edition: a new session for this computer, without leaving the screen. One renewal
   * serves every request that found the session expired at the same time. */
  const renewing = useRef<Promise<boolean> | null>(null)
  const renew = useCallback(() => {
    renewing.current ??= send('/auth/me', '')
      .then((raw) => {
        const data = sessionSchema.parse(raw)
        generation.current++
        csrf.current = data.csrf_token
        signedIn.current = true
        setUser(data.user)
        return true
      })
      .catch(() => false)
      .finally(() => {
        renewing.current = null
      })
    return renewing.current
  }, [])
  const request = useCallback(
    async (path: string, method = 'GET', body?: unknown) => {
      try {
        return await send(path, csrf.current, method, body)
      } catch (error) {
        const stale = error instanceof ApiError && (error.status === 401 || error.retry === 'csrf')
        if (stale && localRef.current && (await renew())) {
          // A read is repeated once. A write is never repeated on its own (it may lack an
          // operation key): the form stays as typed and the user sends it again.
          if (method === 'GET') return await send(path, csrf.current, method, body)
          throw new ApiError(401, SESSION_RENEWED, true, 'renewed')
        }
        if (error instanceof ApiError && error.status === 401) clear()
        throw error
      }
    },
    [clear, renew],
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
    <AuthContext.Provider
      value={{ user, local, loading, error, refresh, login, logout, request, clear }}
    >
      {children}
    </AuthContext.Provider>
  )
}
