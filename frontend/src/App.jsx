import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import FaxInbox from './pages/FaxInbox'
import Referrals from './pages/Referrals'
import ReferralDetail from './pages/ReferralDetail'
import ReferralAuths from './pages/ReferralAuths'
import Scheduling from './pages/Scheduling'
import RCM from './pages/RCM'
import DMEOrder from './pages/DMEOrder'
import DMEConfirm from './pages/DMEConfirm'
import DMEAdmin from './pages/DMEAdmin'
import Settings from './pages/Settings'
import AllowableRates from './pages/AllowableRates'
import UserManagement from './pages/UserManagement'

const ROLE_LANDING = {
  admin: '/',
  front_office: '/faxes',
  dme: '/dme/admin',
}

function RoleLanding() {
  const { user } = useAuth()
  const role = user?.role || 'admin'
  if (role === 'admin') return <Dashboard />
  return <Navigate to={ROLE_LANDING[role] || '/'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/dme" element={<DMEOrder />} />
        <Route path="/dme/confirm/:token" element={<DMEConfirm />} />

        {/* Protected routes (require login) */}
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          {/* Landing — role-based redirect */}
          <Route path="/" element={<RoleLanding />} />

          {/* Admin-only routes */}
          <Route path="/faxes" element={<ProtectedRoute allowedRoles={['admin', 'front_office']}><FaxInbox /></ProtectedRoute>} />
          <Route path="/faxes/:id" element={<ProtectedRoute allowedRoles={['admin', 'front_office']}><ReferralDetail /></ProtectedRoute>} />
          <Route path="/referrals" element={<ProtectedRoute allowedRoles={['admin', 'front_office']}><Referrals /></ProtectedRoute>} />
          <Route path="/referrals/:id" element={<ProtectedRoute allowedRoles={['admin', 'front_office']}><ReferralDetail /></ProtectedRoute>} />
          <Route path="/referral-auths" element={<ProtectedRoute allowedRoles={['admin', 'front_office']}><ReferralAuths /></ProtectedRoute>} />
          <Route path="/scheduling" element={<ProtectedRoute allowedRoles={['admin', 'front_office']}><Scheduling /></ProtectedRoute>} />
          <Route path="/rcm" element={<ProtectedRoute allowedRoles={['admin']}><RCM /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute allowedRoles={['admin']}><Settings /></ProtectedRoute>} />
          <Route path="/admin/users" element={<ProtectedRoute allowedRoles={['admin']}><UserManagement /></ProtectedRoute>} />

          {/* DME routes (admin + dme) */}
          <Route path="/dme/admin" element={<ProtectedRoute allowedRoles={['admin', 'dme']}><DMEAdmin /></ProtectedRoute>} />
          <Route path="/allowable-rates" element={<ProtectedRoute allowedRoles={['admin', 'dme']}><AllowableRates /></ProtectedRoute>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
