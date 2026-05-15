import { useEffect } from 'react'
import { motion } from 'framer-motion'
import useStore from '../store/useStore'
import { api } from '../api/client'
import GatewayCards from '../components/dashboard/GatewayCards'

export default function GatewayHealthPage() {
  const { gateways, setGateways, setGatewaysLoading, backendConnected } = useStore()

  useEffect(() => {
    if (!backendConnected) return
    const fetchData = async () => {
      setGatewaysLoading(true)
      try {
        const res = await api.getGatewayHealth()
        setGateways(res.gateways || [])
      } catch {}
    }
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [backendConnected])

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <span>🏦</span> Gateway Health
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Real-time health metrics for all payment gateways. Auto-refreshes every 5 seconds.
        </p>
      </motion.div>

      {!backendConnected && (
        <div className="glass-card p-4 border border-amber-500/20 bg-amber-500/5">
          <p className="text-sm text-amber-400">⚠️ Backend offline — start the API to see live gateway metrics.</p>
        </div>
      )}

      <GatewayCards gateways={gateways} />

      {/* Circuit Breaker States */}
      {gateways.length > 0 && (
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Circuit Breaker Summary</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {gateways.map((gw) => (
              <motion.div
                key={gw.gateway_name}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="glass-card p-4 text-center"
              >
                <p className="text-xs text-slate-500 mb-2 capitalize">{gw.gateway_name}</p>
                <div className={`text-lg font-bold ${
                  gw.circuit_state === 'closed' ? 'text-emerald-400' :
                  gw.circuit_state === 'open' ? 'text-red-400' : 'text-amber-400'
                }`}>
                  {gw.circuit_state === 'closed' ? '🟢' :
                   gw.circuit_state === 'open' ? '🔴' : '🟡'}
                </div>
                <p className="text-[10px] text-slate-600 mt-1 uppercase">{gw.circuit_state || 'unknown'}</p>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
