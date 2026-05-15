import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts'
import useStore from '../store/useStore'
import { api } from '../api/client'
import StatusBadge from '../components/ui/StatusBadge'

export default function FraudAnalyticsPage() {
  const { backendConnected } = useStore()
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!backendConnected) return
    const fetch = async () => {
      setLoading(true)
      try {
        const res = await api.listTransactions(1, 100)
        setTransactions(res.transactions || [])
      } catch {}
      setLoading(false)
    }
    fetch()
  }, [backendConnected])

  // Compute analytics
  const total = transactions.length
  const rejected = transactions.filter(t => t.status === 'REJECTED')
  const approved = transactions.filter(t => t.status === 'APPROVED')
  const failed = transactions.filter(t => ['FAILED', 'TIMEOUT'].includes(t.status))
  const rerouted = transactions.filter(t => t.status === 'REROUTED')

  const avgFraud = total > 0
    ? transactions.reduce((s, t) => s + (t.fraud_score || 0), 0) / total
    : 0

  const pieData = [
    { name: 'Approved', value: approved.length, color: '#10b981' },
    { name: 'Rejected', value: rejected.length, color: '#ef4444' },
    { name: 'Failed', value: failed.length, color: '#f59e0b' },
    { name: 'Rerouted', value: rerouted.length, color: '#6366f1' },
  ].filter(d => d.value > 0)

  // Fraud score distribution buckets
  const buckets = [
    { range: '0-10%', min: 0, max: 0.1 },
    { range: '10-20%', min: 0.1, max: 0.2 },
    { range: '20-40%', min: 0.2, max: 0.4 },
    { range: '40-65%', min: 0.4, max: 0.65 },
    { range: '65-80%', min: 0.65, max: 0.8 },
    { range: '80-100%', min: 0.8, max: 1.01 },
  ]
  const distData = buckets.map(b => ({
    range: b.range,
    count: transactions.filter(t => (t.fraud_score || 0) >= b.min && (t.fraud_score || 0) < b.max).length,
    risky: b.min >= 0.65,
  }))

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <span>📈</span> Fraud Analytics
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Fraud detection performance and transaction outcome analysis
        </p>
      </motion.div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Transactions', value: total, icon: '💳', color: 'text-atlas-400' },
          { label: 'Rejection Rate', value: total > 0 ? `${(rejected.length / total * 100).toFixed(1)}%` : '—', icon: '🚫', color: 'text-red-400' },
          { label: 'Avg Fraud Score', value: `${(avgFraud * 100).toFixed(1)}%`, icon: '🛡️', color: avgFraud > 0.4 ? 'text-amber-400' : 'text-emerald-400' },
          { label: 'Reroute Rate', value: total > 0 ? `${(rerouted.length / total * 100).toFixed(1)}%` : '—', icon: '🔄', color: 'text-atlas-400' },
        ].map((card, i) => (
          <motion.div key={card.label} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
            className="glass-card-hover p-5">
            <span className="text-2xl">{card.icon}</span>
            <p className={`text-2xl font-bold mt-2 ${card.color}`}>{card.value}</p>
            <p className="text-xs text-slate-400 mt-1">{card.label}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pie Chart */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Outcome Distribution</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  innerRadius={50} outerRadius={90} paddingAngle={4} label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} fillOpacity={0.85} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#141627', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                  itemStyle={{ color: '#e2e8f0', fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-slate-500 text-sm">
              {loading ? 'Loading...' : 'No transaction data yet'}
            </div>
          )}
        </div>

        {/* Fraud Score Distribution */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Fraud Score Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={distData}>
              <XAxis dataKey="range" tick={{ fill: '#64748b', fontSize: 10 }} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#141627', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                itemStyle={{ color: '#e2e8f0', fontSize: 12 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]} maxBarSize={40}>
                {distData.map((entry, i) => (
                  <Cell key={i} fill={entry.risky ? '#ef4444' : '#10b981'} fillOpacity={0.75} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Rejected */}
      {rejected.length > 0 && (
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">Recent Rejected Transactions</h3>
          <div className="space-y-2">
            {rejected.slice(0, 10).map((txn, i) => (
              <motion.div key={txn.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.04 }}
                className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/[0.02]">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-slate-500">{txn.id.slice(0, 8)}</span>
                  <span className="text-sm text-white">${txn.amount?.toFixed(2)}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-red-400">{((txn.fraud_score || 0) * 100).toFixed(1)}%</span>
                  <StatusBadge status="REJECTED">REJECTED</StatusBadge>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
