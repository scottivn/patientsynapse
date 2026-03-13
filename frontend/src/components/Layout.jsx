import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  FileText,
  CalendarClock,
  DollarSign,
  Settings,
  Activity,
} from 'lucide-react'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/referrals', icon: FileText, label: 'Referrals' },
  { to: '/scheduling', icon: CalendarClock, label: 'Scheduling' },
  { to: '/rcm', icon: DollarSign, label: 'RCM' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-gray-100">
          <div className="flex items-center gap-2">
            <svg viewBox="0 0 28 28" className="w-7 h-7" fill="none">
              <rect x="0" y="11" width="4" height="14" rx="1" fill="#2563eb" />
              <rect x="24" y="11" width="4" height="14" rx="1" fill="#2563eb" />
              <path d="M 2 11 Q 14 1, 26 11" stroke="#0ea5e9" strokeWidth="4" fill="none" strokeLinecap="round" />
              <rect x="12.5" y="2" width="3" height="8" rx="0.5" fill="#10b981" />
              <rect x="10" y="4.5" width="8" height="3" rx="0.5" fill="#10b981" />
            </svg>
            <span className="text-lg font-bold text-gray-900">
              Patient<span className="text-brand-500">Bridge</span>
            </span>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
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
          ))}
        </nav>

        {/* Status footer */}
        <div className="p-4 border-t border-gray-100">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Activity size={12} className="text-emerald-500" />
            <span>System Online</span>
          </div>
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
