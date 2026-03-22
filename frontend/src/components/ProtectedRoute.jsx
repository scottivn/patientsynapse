import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const ROLE_LANDING = {
  admin: '/',
  front_office: '/faxes',
  dme: '/dme/admin',
}

/**
 * ProtectedRoute — gate for authenticated routes.
 *
 * Props:
 *   allowedRoles — optional array of role strings. If omitted, any authenticated user can access.
 *                  If provided, the user's role must be in the array.
 */
export default function ProtectedRoute({ children, allowedRoles }) {
  const { user, isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  // Role check — if allowedRoles specified, verify user's role
  if (allowedRoles && !allowedRoles.includes(user?.role)) {
    // Redirect to their role's landing page instead of showing an error
    const landing = ROLE_LANDING[user?.role] || '/'
    return <Navigate to={landing} replace />
  }

  return children
}
