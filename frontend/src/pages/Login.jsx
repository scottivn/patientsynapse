import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Lock, RefreshCw, Eye } from 'lucide-react'
import { adminLogin } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

const ROLE_LANDING = { admin: '/', front_office: '/faxes', dme: '/dme/admin', demo: '/' }

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const doLogin = async (user, pass, setLoadFn) => {
    setLoadFn(true)
    setError('')
    try {
      const result = await adminLogin(user, pass)
      login({ username: result.username, role: result.role, user_id: result.user_id })
      navigate(ROLE_LANDING[result.role] || '/', { replace: true })
    } catch (err) {
      setError(err.message || 'Invalid credentials.')
    } finally {
      setLoadFn(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username and password.')
      return
    }
    await doLogin(username, password, setLoading)
  }

  const handleDemo = () => doLogin('demo', 'demo', setDemoLoading)

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-sm w-full space-y-6">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <div className="p-4 bg-indigo-50 rounded-full">
              <Lock size={28} className="text-indigo-500" />
            </div>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            Patient<span className="text-indigo-500">Synapse</span>
          </h1>
          <p className="text-sm text-gray-500">Sign in to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-6 space-y-4 shadow-sm">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Username</label>
            <input
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin"
              autoComplete="username"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
            <input
              type="password"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || demoLoading}
            className="w-full bg-indigo-500 hover:bg-indigo-600 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading && <RefreshCw size={14} className="animate-spin" />}
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        {/* Demo access for recruiters / portfolio viewers */}
        <div className="text-center">
          <div className="relative">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200" /></div>
            <div className="relative flex justify-center text-xs"><span className="bg-gray-50 px-2 text-gray-400">or</span></div>
          </div>
        </div>
        <button
          onClick={handleDemo}
          disabled={loading || demoLoading}
          className="w-full bg-white hover:bg-gray-50 text-gray-700 font-medium py-2.5 px-4 rounded-xl border border-gray-200 text-sm transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
        >
          {demoLoading ? <RefreshCw size={14} className="animate-spin" /> : <Eye size={14} className="text-amber-500" />}
          {demoLoading ? 'Loading demo...' : 'Try Demo (read-only)'}
        </button>
        <p className="text-center text-[11px] text-gray-400">
          Explore the full app with sample medical practice data
        </p>
      </div>
    </div>
  )
}
