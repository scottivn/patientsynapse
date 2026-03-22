import { useEffect, useState, useCallback } from 'react'
import { Plus, Trash2, RefreshCw, Shield, Eye, EyeOff, UserX, UserCheck } from 'lucide-react'
import { listUsers, createUser, updateUser, resetUserPassword, deleteUser, getRoles } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import ErrorBanner from '../components/ErrorBanner'

const ROLE_COLORS = {
  admin: 'bg-purple-100 text-purple-700 border-purple-200',
  front_office: 'bg-sky-100 text-sky-700 border-sky-200',
  dme: 'bg-teal-100 text-teal-700 border-teal-200',
}

export default function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [roles, setRoles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState('dme')
  const [showPassword, setShowPassword] = useState(false)
  const [creating, setCreating] = useState(false)

  // Edit state
  const [editingId, setEditingId] = useState(null)
  const [editRole, setEditRole] = useState('')
  const [resetPw, setResetPw] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [u, r] = await Promise.all([listUsers(), getRoles()])
      setUsers(u)
      setRoles(r)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newUsername.trim() || !newPassword.trim()) return
    setCreating(true)
    setError(null)
    try {
      await createUser(newUsername.trim(), newPassword, newRole)
      setNewUsername('')
      setNewPassword('')
      setNewRole('dme')
      setShowCreate(false)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdate = async (userId) => {
    setSaving(true)
    setError(null)
    try {
      // Role update via PUT
      if (editRole) {
        await updateUser(userId, { role: editRole })
      }
      // Password reset via separate endpoint
      if (resetPw) {
        await resetUserPassword(userId, resetPw)
      }
      setEditingId(null)
      setEditRole('')
      setResetPw('')
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleToggleActive = async (userId, currentlyActive) => {
    setError(null)
    try {
      await updateUser(userId, { is_active: !currentlyActive })
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (userId, username) => {
    if (!confirm(`Delete user "${username}"? This cannot be undone.`)) return
    setError(null)
    try {
      await deleteUser(userId)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  const startEdit = (u) => {
    setEditingId(u.id)
    setEditRole(u.role)
    setResetPw('')
  }

  const isSelf = (u) => String(u.id) === currentUser?.user_id

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          <p className="text-xs text-gray-400">Create and manage staff accounts</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowCreate(!showCreate)}
            className="text-sm flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 transition-colors"
          >
            <Plus size={14} /> New User
          </button>
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="text-sm flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Create user form */}
      {showCreate && (
        <form onSubmit={handleCreate} className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
          <h3 className="font-medium text-gray-800 text-sm">Create New User</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Username</label>
              <input
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                placeholder="jsmith"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Password (min 8 chars)</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 pr-9"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Secure password"
                  minLength={8}
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                  {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Role</label>
              <select
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={newRole}
                onChange={(e) => setNewRole(e.target.value)}
              >
                {roles.map(r => (
                  <option key={r.key} value={r.key}>{r.label} — {r.description}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button type="submit" disabled={creating || !newUsername.trim() || newPassword.length < 8}
              className="text-sm px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2">
              {creating && <RefreshCw size={13} className="animate-spin" />}
              Create User
            </button>
            <button type="button" onClick={() => setShowCreate(false)}
              className="text-sm px-4 py-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Users table */}
      {loading ? (
        <p className="text-gray-400 text-center py-12">Loading...</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="text-left px-4 py-3 font-medium text-gray-600">ID</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Username</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Role</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Created</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Last Login</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className={`border-b border-gray-100 last:border-0 hover:bg-gray-50 ${!u.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-4 py-3 text-gray-500">{u.id}</td>
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {u.username}
                    {isSelf(u) && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 font-medium">you</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {editingId === u.id ? (
                      <select value={editRole} onChange={(e) => setEditRole(e.target.value)}
                        className="px-2 py-1 border border-gray-300 rounded text-xs">
                        {roles.map(r => <option key={r.key} value={r.key}>{r.label}</option>)}
                      </select>
                    ) : (
                      <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${ROLE_COLORS[u.role] || 'bg-gray-100 text-gray-700 border-gray-200'}`}>
                        {roles.find(r => r.key === u.role)?.label || u.role}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                      u.is_active ? 'bg-green-100 text-green-700 border-green-200' : 'bg-red-100 text-red-700 border-red-200'
                    }`}>
                      {u.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{u.created_at?.split('T')[0] || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{u.last_login || 'Never'}</td>
                  <td className="px-4 py-3 text-right">
                    {editingId === u.id ? (
                      <div className="flex items-center justify-end gap-2">
                        <input
                          type="password"
                          placeholder="New password (optional, min 8)"
                          value={resetPw}
                          onChange={(e) => setResetPw(e.target.value)}
                          className="px-2 py-1 border border-gray-300 rounded text-xs w-44"
                          minLength={8}
                        />
                        <button onClick={() => handleUpdate(u.id)} disabled={saving}
                          className="text-xs px-2.5 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50">
                          {saving ? '...' : 'Save'}
                        </button>
                        <button onClick={() => setEditingId(null)}
                          className="text-xs px-2.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50">
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => startEdit(u)}
                          className="text-xs px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50">
                          Edit
                        </button>
                        {!isSelf(u) && (
                          <>
                            <button onClick={() => handleToggleActive(u.id, u.is_active)}
                              title={u.is_active ? 'Deactivate' : 'Reactivate'}
                              className={`text-xs px-2 py-1 rounded border ${
                                u.is_active
                                  ? 'border-orange-200 text-orange-600 hover:bg-orange-50'
                                  : 'border-green-200 text-green-600 hover:bg-green-50'
                              }`}>
                              {u.is_active ? <UserX size={12} /> : <UserCheck size={12} />}
                            </button>
                            <button onClick={() => handleDelete(u.id, u.username)}
                              className="text-xs px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50">
                              <Trash2 size={12} />
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Role reference */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-2 flex items-center gap-2">
          <Shield size={14} /> Role Permissions
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          {roles.map(r => (
            <div key={r.key} className="bg-white rounded-lg border border-blue-100 px-3 py-2">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${ROLE_COLORS[r.key] || 'bg-gray-100'}`}>
                {r.label}
              </span>
              <p className="text-xs text-gray-600 mt-1">{r.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
