import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  Inbox,
  CalendarClock,
  DollarSign,
  Settings,
  Activity,
  Package,
  ShieldCheck,
  ClipboardCheck,
  LogOut,
  User,
  Users,
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

// Each nav item includes `roles` — which roles can see it.
// If omitted, all authenticated users can see it.
const NAV_MAIN = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', roles: ['admin'] },
  { to: '/faxes', icon: Inbox, label: 'Fax Inbox', roles: ['admin', 'front_office'] },
  { to: '/referrals', icon: FileText, label: 'Referrals', roles: ['admin', 'front_office'] },
  { to: '/referral-auths', icon: ClipboardCheck, label: 'Referral Auths', roles: ['admin', 'front_office'] },
  { to: '/scheduling', icon: CalendarClock, label: 'Scheduling', roles: ['admin', 'front_office'] },
  { to: '/rcm', icon: DollarSign, label: 'RCM', roles: ['admin'] },
]

const NAV_DME = [
  { to: '/dme/admin', icon: ShieldCheck, label: 'DME Admin', roles: ['admin', 'dme'] },
  { to: '/allowable-rates', icon: DollarSign, label: 'Allowable Rates', roles: ['admin', 'dme'] },
]

const NAV_SYSTEM = [
  { to: '/admin/users', icon: Users, label: 'User Management', roles: ['admin'] },
  { to: '/settings', icon: Settings, label: 'Settings', roles: ['admin'] },
]

const ROLE_LABELS = {
  admin: 'Admin',
  front_office: 'Front Office',
  dme: 'DME',
}

function NavSection({ items, userRole }) {
  const visible = items.filter(item => !item.roles || item.roles.includes(userRole))
  if (visible.length === 0) return null
  return visible.map(({ to, icon: Icon, label }) => (
    <NavLink
      key={to}
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
          isActive
            ? 'bg-brand-50 text-brand-600'
            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        }`
      }
    >
      <Icon size={18} />
      {label}
    </NavLink>
  ))
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const userRole = user?.role || 'admin'

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  // Check if sections have any visible items for this role
  const hasDME = NAV_DME.some(item => !item.roles || item.roles.includes(userRole))
  const hasSystem = NAV_SYSTEM.some(item => !item.roles || item.roles.includes(userRole))

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 40 28" className="w-8 h-7" fill="none">
              {/* Left neuron */}
              <circle cx="6" cy="14" r="5" fill="#6366f1" opacity="0.9"/>
              <circle cx="6" cy="14" r="3" fill="#818cf8"/>
              {/* Dendrites left */}
              <line x1="3" y1="8" x2="1" y2="4" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
              <line x1="6" y1="9" x2="6" y2="4" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
              <line x1="9" y1="10" x2="12" y2="5" stroke="#6366f1" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
              {/* Axon left */}
              <path d="M 11 14 C 15 14, 15 7, 18 7" stroke="#10b981" strokeWidth="2" fill="none" strokeLinecap="round"/>
              {/* Gap */}
              <circle cx="20" cy="7" r="1.5" fill="#10b981" opacity="0.5"/>
              {/* Axon right */}
              <path d="M 22 7 C 25 7, 25 14, 29 14" stroke="#10b981" strokeWidth="2" fill="none" strokeLinecap="round"/>
              {/* Right neuron */}
              <circle cx="34" cy="14" r="5" fill="#06b6d4" opacity="0.9"/>
              <circle cx="34" cy="14" r="3" fill="#22d3ee"/>
              {/* Dendrites right */}
              <line x1="37" y1="10" x2="39" y2="5" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
              <line x1="34" y1="9" x2="34" y2="4" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" opacity="0.6"/>
              <line x1="31" y1="8" x2="28" y2="4" stroke="#06b6d4" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
              {/* Medical cross */}
              <rect x="19" y="15" width="2" height="6" rx="0.5" fill="#10b981"/>
              <rect x="17.5" y="16.5" width="5" height="2" rx="0.5" fill="#10b981"/>
            </svg>
            <span className="text-lg font-bold text-gray-900">
              Patient<span className="text-indigo-500">Synapse</span>
            </span>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          <NavSection items={NAV_MAIN} userRole={userRole} />

          {/* DME separator */}
          {hasDME && (
            <>
              <div className="pt-3 pb-1">
                <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400">DME Portal</p>
              </div>
              <NavSection items={NAV_DME} userRole={userRole} />
            </>
          )}

          {/* System separator */}
          {hasSystem && (
            <>
              <div className="pt-3 pb-1">
                <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-gray-400">System</p>
              </div>
              <NavSection items={NAV_SYSTEM} userRole={userRole} />
            </>
          )}
        </nav>

        {/* User + logout footer */}
        <div className="p-4 border-t border-gray-100 space-y-2">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Activity size={12} className="text-emerald-500" />
            <span>System Online</span>
          </div>
          {user && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <User size={12} />
                <span>{user.username}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 font-medium">
                  {ROLE_LABELS[user.role] || user.role}
                </span>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-xs text-gray-400 hover:text-red-500 transition-colors"
                title="Sign out"
              >
                <LogOut size={12} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
