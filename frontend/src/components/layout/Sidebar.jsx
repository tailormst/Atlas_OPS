import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import useStore from '../../store/useStore'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '📊' },
  { to: '/live', label: 'Live Pipeline', icon: '⚡' },
  { to: '/transactions', label: 'Transactions', icon: '📋' },
  { to: '/gateways', label: 'Gateway Health', icon: '🏦' },
  { to: '/analytics', label: 'Fraud Analytics', icon: '📈' },
  { to: '/explainability', label: 'Explainability', icon: '🧠' },
  { to: '/admin', label: 'Admin Panel', icon: '⚙️' },
  { to: '/settings', label: 'Settings', icon: '🔧' },
]

export default function Sidebar() {
  const logout = useStore((s) => s.logout)
  const user = useStore((s) => s.user)

  return (
    <aside className="w-64 bg-surface-800/40 backdrop-blur-xl border-r border-white/5 flex flex-col min-h-screen">
      {/* Logo */}
      <div className="p-6 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-atlas-500 to-atlas-700 flex items-center justify-center">
            <span className="text-white font-bold text-lg">A</span>
          </div>
          <div>
            <h1 className="text-lg font-bold gradient-text">ATLAS-OPS</h1>
            <p className="text-[10px] text-slate-500 font-medium tracking-wider uppercase">
              AI Payment Platform
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 ${
                isActive
                  ? 'bg-atlas-500/15 text-atlas-300 border border-atlas-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className="text-lg">{item.icon}</span>
                <span>{item.label}</span>
                {isActive && (
                  <motion.div
                    layoutId="nav-indicator"
                    className="ml-auto w-1.5 h-1.5 rounded-full bg-atlas-400"
                  />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User + Logout */}
      <div className="p-4 border-t border-white/5 space-y-3">
        {user && (
          <div className="glass-card p-3">
            <p className="text-xs text-slate-400 truncate">{user.email}</p>
            <p className="text-[10px] text-atlas-400 capitalize">{user.role}</p>
          </div>
        )}
        <button
          onClick={logout}
          className="w-full text-xs px-4 py-2.5 rounded-lg bg-surface-900 border border-white/5 text-slate-400 hover:text-red-400 hover:border-red-500/20 transition-all"
        >
          🚪 Sign Out
        </button>
        <div className="glass-card p-3 text-center">
          <p className="text-[10px] text-slate-500 font-mono">ATLAS-OPS v1.0.0</p>
          <p className="text-[10px] text-slate-600">Autonomous AI Pipeline</p>
        </div>
      </div>
    </aside>
  )
}
