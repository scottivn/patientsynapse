import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { adminMe, adminLogout } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Check existing session on mount
  useEffect(() => {
    adminMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback((userData) => {
    setUser(userData)
  }, [])

  const logout = useCallback(async () => {
    try { await adminLogout() } catch {}
    setUser(null)
  }, [])

  // Listen for 401s from the API layer (session expired)
  useEffect(() => {
    const handler = () => setUser(null)
    window.addEventListener('auth:session-expired', handler)
    return () => window.removeEventListener('auth:session-expired', handler)
  }, [])

  const hasRole = useCallback((...roles) => {
    return user && roles.includes(user.role)
  }, [user])

  const isDemo = user?.role === 'demo'

  return (
    <AuthContext.Provider value={{ user, loading, isAuthenticated: !!user, isDemo, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
