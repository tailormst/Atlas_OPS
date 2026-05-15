import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import useStore from '../store/useStore'
import { api } from '../api/client'
import StatsCards from '../components/dashboard/StatsCards'
import GatewayCards from '../components/dashboard/GatewayCards'
import FraudChart from '../components/dashboard/FraudChart'
import RecentTransactions from '../components/dashboard/RecentTransactions'

export default function DashboardPage() {
  const { stats, setStats, gateways, setGateways, setGatewaysLoading, backendConnected } = useStore()
  const [recentTxns, setRecentTxns] = useState([])
  const [lastShap, setLastShap] = useState(null)

  useEffect(() => {
    if (!backendConnected) return

    const fetchData = async () => {
      try {
        setGatewaysLoading(true)
        const healthRes = await api.getGatewayHealth()
        setGateways(healthRes.gateways || [])

        // Derive stats from gateway data
        const gws = healthRes.gateways || []
        const totalReq = gws.reduce((sum, g) => sum + g.total_requests, 0)
        const avgSuccess = gws.length > 0
          ? gws.reduce((sum, g) => sum + g.success_rate, 0) / gws.length
          : 0
        const avgLatency = gws.length > 0
          ? gws.reduce((sum, g) => sum + g.avg_latency_ms, 0) / gws.length
          : 0

        // Fetch real transaction stats
        let avgFraud = '0.00'
        let approvedRate = (avgSuccess * 100).toFixed(1)
        try {
          const txnRes = await api.listTransactions(1, 50)
          const txns = txnRes.transactions || []
          setRecentTxns(txns.slice(0, 5).map(t => ({
            id: t.id,
            amount: t.amount,
            status: t.status,
            gateway: t.selected_gateway || '—',
            fraud_score: t.fraud_score || 0,
            time: t.created_at ? new Date(t.created_at).toLocaleString() : 'just now',
          })))
          if (txns.length > 0) {
            avgFraud = (txns.reduce((s, t) => s + (t.fraud_score || 0), 0) / txns.length * 100).toFixed(1)
            const approved = txns.filter(t => t.status === 'APPROVED' || t.status === 'REROUTED')
            approvedRate = (approved.length / txns.length * 100).toFixed(1)
          }
        } catch {}

        setStats({
          totalTransactions: totalReq,
          approvedRate,
          avgFraudScore: avgFraud + '%',
          avgLatency: avgLatency.toFixed(0),
        })
      } catch {
        // Backend might be down
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000)
    return () => clearInterval(interval)
  }, [backendConnected, setGateways, setGatewaysLoading, setStats])

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">
          Real-time overview of the ATLAS-OPS payment operations platform
        </p>
      </motion.div>

      {!backendConnected && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="glass-card p-4 border border-amber-500/20 bg-amber-500/5">
          <div className="flex items-center gap-3">
            <span className="text-amber-400 text-lg">⚠️</span>
            <div>
              <p className="text-sm font-semibold text-amber-400">Backend Offline</p>
              <p className="text-xs text-slate-400">
                Start the backend with <code className="text-atlas-400">python run_local.py</code> to see live data.
              </p>
            </div>
          </div>
        </motion.div>
      )}

      <StatsCards stats={stats} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-sm font-semibold text-slate-300 mb-3">Gateway Health</h2>
          <GatewayCards gateways={gateways} />
        </div>
        <div>
          <FraudChart shapValues={lastShap} />
        </div>
      </div>

      <RecentTransactions transactions={recentTxns} />
    </div>
  )
}
