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
