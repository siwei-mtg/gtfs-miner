import { useState, useEffect, useCallback, type ReactNode } from 'react'
import { register as apiRegister, login as apiLogin, getMe } from '../api/client'
import type { UserCreate, UserResponse } from '../types/api'
import { AuthContext } from '../contexts/AuthContext'

// ── Provider ────────────────────────────────────────────────────────────────
// Mount this once at the root so every component shares the same auth state.

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(!!localStorage.getItem('token'))

  const fetchUser = useCallback(async (t: string) => {
    setIsLoading(true)
    try {
      const userData = await getMe(t)
      setUser(userData)
    } catch {
      localStorage.removeItem('token')
      setToken(null)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  // On page load: if a token exists in localStorage, validate it once
  useEffect(() => {
    const stored = localStorage.getItem('token')
    if (stored) fetchUser(stored)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    try {
      const res = await apiLogin(email, password)
      localStorage.setItem('token', res.access_token)
      setToken(res.access_token)
      await fetchUser(res.access_token)
    } catch (e) {
      setIsLoading(false)
      throw e
    }
  }

  const register = async (data: UserCreate) => {
    setIsLoading(true)
    try {
      const res = await apiRegister(data)
      localStorage.setItem('token', res.access_token)
      setToken(res.access_token)
      await fetchUser(res.access_token)
    } catch (e) {
      setIsLoading(false)
      throw e
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// ── Consumer hook ────────────────────────────────────────────────────────────
// Drop-in replacement for the old useAuth() — reads from shared context.
export { useAuthContext as useAuth } from '../contexts/AuthContext'
