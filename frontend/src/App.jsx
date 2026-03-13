import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Referrals from './pages/Referrals'
import ReferralDetail from './pages/ReferralDetail'
import Scheduling from './pages/Scheduling'
import RCM from './pages/RCM'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/referrals" element={<Referrals />} />
        <Route path="/referrals/:id" element={<ReferralDetail />} />
        <Route path="/scheduling" element={<Scheduling />} />
        <Route path="/rcm" element={<RCM />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
