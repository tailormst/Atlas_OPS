import { useEffect } from 'react'
import useStore from '../../store/useStore'
import api from '../../api/client'

export default function Header() {
  const backendConnected = useStore((s) => s.backendConnected)
  const setBackendConnected = useStore((s) => s.setBackendConnected)
  const user = useStore((s) => s.user)
  const logout = useStore((s) => s.logout)

  useEffect(() => {
    const check = async () => {
      try {
        await api.health()
        setBackendConnected(true)
      } catch {
        setBackendConnected(false)
      }
    }
    check()
    const interval = setInterval(check, 15000)
    return () => clearInterval(interval)
  }, [setBackendConnected])

  return (
    <header className="h-16 border-b border-white/5 bg-surface-800/30 backdrop-blur-xl flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="capitalize">{user.role}</span>
            <span className="text-slate-600">·</span>
            <span>{user.email}</span>
          </div>
        )}
        <div className="flex items-center gap-2 glass-card px-3 py-1.5">
          <div
            className={`w-2 h-2 rounded-full ${
              backendConnected ? 'bg-emerald-400 shadow-lg shadow-emerald-400/50' : 'bg-red-400 shadow-lg shadow-red-400/50'
            }`}
          />
          <span className="text-xs font-medium text-slate-400">
            {backendConnected ? 'API Connected' : 'API Offline'}
          </span>
        </div>
      </div>
    </header>
  )
}
