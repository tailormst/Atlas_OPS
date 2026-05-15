import { useState } from 'react'
import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import useStore from '../store/useStore'
import { api } from '../api/client'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [adminKey, setAdminKey] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [showAdminKey, setShowAdminKey] = useState(false)
  const login = useStore((s) => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const res = await api.login(email, password, adminKey || undefined)
      login(res)
      navigate('/')
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }

  const fillAdmin = () => {
    setEmail('admin@atlas-ops.ai')
    setPassword('atlas_admin_2024')
    setShowAdminKey(true)
  }

  const fillCompany = () => {
    setEmail('demo@company.com')
    setPassword('demo_company_2024')
    setShowAdminKey(false)
    setAdminKey('')
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: 'var(--color-bg)' }}>
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-atlas-500 to-atlas-700 flex items-center justify-center mx-auto mb-4 shadow-lg shadow-atlas-500/30">
            <span className="text-white font-bold text-2xl">A</span>
          </div>
          <h1 className="text-3xl font-bold gradient-text">ATLAS-OPS</h1>
          <p className="text-sm text-slate-500 mt-2">Autonomous AI Payment Operations Platform</p>
        </div>

        {/* Login Card */}
        <div className="glass-card p-8">
          <h2 className="text-xl font-bold text-white mb-6">Sign In</h2>

          {/* Quick Fill Buttons */}
          <div className="flex gap-2 mb-6">
            <button
              type="button"
              onClick={fillAdmin}
              className="flex-1 text-xs px-3 py-2 rounded-lg bg-surface-900 border border-white/5 hover:border-atlas-500/30 text-slate-400 hover:text-white transition-all"
            >
              🔑 Admin Demo
            </button>
            <button
              type="button"
              onClick={fillCompany}
              className="flex-1 text-xs px-3 py-2 rounded-lg bg-surface-900 border border-white/5 hover:border-emerald-500/30 text-slate-400 hover:text-white transition-all"
            >
              🏢 Company Demo
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@atlas-ops.ai"
                required
                className="input-field w-full"
                id="login-email"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="input-field w-full"
                id="login-password"
              />
            </div>

            {showAdminKey && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}>
                <label className="text-[10px] text-slate-500 uppercase tracking-wider block mb-1.5">Admin Key (optional)</label>
                <input
                  type="password"
                  value={adminKey}
                  onChange={(e) => setAdminKey(e.target.value)}
                  placeholder="Optional admin key"
                  className="input-field w-full"
                  id="login-admin-key"
                />
              </motion.div>
            )}

            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400"
              >
                {error}
              </motion.div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2"
              id="login-submit"
            >
              {loading ? (
                <>
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full"
                  />
                  Signing in...
                </>
              ) : (
                <>🔐 Sign In</>
              )}
            </button>
          </form>

          <p className="text-[10px] text-slate-600 text-center mt-6">
            No public registration. Accounts are created by the admin.
          </p>
        </div>
      </motion.div>
    </div>
  )
}
