import { motion } from 'framer-motion'
import useStore from '../store/useStore'

export default function SettingsPage() {
  const { backendConnected, mlStatus, user } = useStore()

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <span>⚙️</span> Settings
        </h1>
        <p className="text-sm text-slate-400 mt-1">System configuration and connection status</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Connection</h3>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-xs text-slate-500">API Status</span>
              <span className={`text-xs font-semibold ${backendConnected ? 'text-emerald-400' : 'text-red-400'}`}>
                {backendConnected ? '● Connected' : '● Offline'}
              </span>
            </div>
            <div className="flex justify-between"><span className="text-xs text-slate-500">API URL</span>
              <span className="text-xs text-slate-400 font-mono">localhost:8000</span>
            </div>
            <div className="flex justify-between"><span className="text-xs text-slate-500">Frontend URL</span>
              <span className="text-xs text-slate-400 font-mono">localhost:5173</span>
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">User</h3>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-xs text-slate-500">Email</span>
              <span className="text-xs text-slate-400">{user?.email || '—'}</span>
            </div>
            <div className="flex justify-between"><span className="text-xs text-slate-500">Role</span>
              <span className="text-xs text-atlas-400 capitalize">{user?.role || '—'}</span>
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">ML Configuration</h3>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-xs text-slate-500">Fraud Threshold</span>
              <span className="text-xs text-slate-400 font-mono">0.65 (65%)</span>
            </div>
            <div className="flex justify-between"><span className="text-xs text-slate-500">Models Dir</span>
              <span className="text-xs text-slate-400 font-mono">app/ml_models/</span>
            </div>
          </div>
        </div>

        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Credentials</h3>
          <div className="space-y-3 text-xs text-slate-500">
            <p>Admin: admin@atlas-ops.ai / atlas_admin_2024</p>
            <p>Company: demo@company.com / demo_company_2024</p>
          </div>
        </div>
      </div>
    </div>
  )
}
