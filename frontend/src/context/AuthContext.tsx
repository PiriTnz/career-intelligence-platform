import { createContext, useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { login as apiLogin, register as apiRegister } from '@/api/auth'
import type { User } from '@/types'

interface AuthContextValue {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, name: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'))
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')
    if (stored && storedUser) {
      setToken(stored)
      setUser(JSON.parse(storedUser))
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password)
    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const register = useCallback(async (email: string, password: string, name: string) => {
    await apiRegister(email, password, name)
    await login(email, password)
  }, [login])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
