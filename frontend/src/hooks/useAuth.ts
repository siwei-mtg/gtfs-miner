import { useState, useEffect, useCallback } from 'react'
import { register as apiRegister, login as apiLogin, getMe } from '../api/client'
import type { UserCreate, UserResponse } from '../types/api'

export function useAuth() {
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

  useEffect(() => {
    if (token && !user) {
      fetchUser(token)
    }
  }, [token, user, fetchUser])

  const login = async (email: string, password: string) => {
    setIsLoading(true)
    try {
      const res = await apiLogin(email, password)
      setToken(res.access_token)
      localStorage.setItem('token', res.access_token)
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
      setToken(res.access_token)
      localStorage.setItem('token', res.access_token)
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

  return { user, token, login, register, logout, isLoading }
}
