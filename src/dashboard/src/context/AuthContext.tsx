import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { authApi, type MeResponse } from '../api/auth'

interface AuthState {
  user: MeResponse | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MeResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('ovd_access_token')
    if (token) {
      authApi.me()
        .then(setUser)
        .catch(() => { localStorage.clear(); setUser(null) })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email: string, password: string) => {
    const data = await authApi.login(email, password)
    localStorage.setItem('ovd_access_token', data.access_token)
    // refresh_token viene en cookie HttpOnly — no se almacena en localStorage (MEDIUM-04)
    const me = await authApi.me()
    setUser(me)
  }

  const logout = () => {
    authApi.logout().catch(() => {})  // cookie HttpOnly enviada automáticamente
    localStorage.removeItem('ovd_access_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
