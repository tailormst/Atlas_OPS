import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import useStore from '../store/useStore'
import { api } from '../api/client'
import StatusBadge from '../components/ui/StatusBadge'

export default function TransactionsPage() {
  const { transactions, transactionsPage, transactionsTotal, transactionsLoading, setTransactions, setTransactionsLoading, backendConnected } = useStore()
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)

  const fetchTransactions = async (p = 1) => {
    if (!backendConnected) return
    setTransactionsLoading(true)
    try {
      const res = await api.listTransactions(p, 20, statusFilter || null)
      setTransactions(res)
      setPage(p)
    } catch {
      setTransactionsLoading(false)
    }
  }

  useEffect(() => {
    fetchTransactions(1)
  }, [backendConnected, statusFilter])

  const statuses = ['', 'APPROVED', 'REJECTED', 'FAILED', 'REROUTED', 'TIMEOUT']
  const totalPages = Math.ceil(transactionsTotal / 20) || 1

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <span>📋</span> Transactions
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          View all processed transactions with fraud scores and outcomes
        </p>
      </motion.div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        {statuses.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${
              statusFilter === s
                ? 'border-atlas-500/40 bg-atlas-500/10 text-atlas-300'
                : 'border-white/5 bg-surface-900 text-slate-400 hover:text-white'
            }`}
          >
            {s || 'All'}
          </button>
        ))}
        <span className="text-xs text-slate-600 ml-auto">
          {transactionsTotal} total
        </span>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/5">
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">ID</th>
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">Amount</th>
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">Status</th>
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">Fraud Score</th>
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">Gateway</th>
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">Email</th>
                <th className="text-left text-[10px] text-slate-500 uppercase tracking-wider px-4 py-3">Time</th>
              </tr>
            </thead>
            <tbody>
              {transactions.length === 0 && (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-500 text-sm">
                    {transactionsLoading ? 'Loading...' : 'No transactions yet. Run a pipeline to create records.'}
                  </td>
                </tr>
              )}
              {transactions.map((txn, i) => (
                <motion.tr
                  key={txn.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                >
                  <td className="px-4 py-3 text-xs font-mono text-slate-400">{txn.id.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-sm font-medium text-white">${typeof txn.amount === 'number' ? txn.amount.toFixed(2) : txn.amount}</td>
                  <td className="px-4 py-3"><StatusBadge status={txn.status}>{txn.status}</StatusBadge></td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-mono ${txn.fraud_score > 0.65 ? 'text-red-400' : txn.fraud_score > 0.3 ? 'text-amber-400' : 'text-emerald-400'}`}>
                      {txn.fraud_score != null ? (txn.fraud_score * 100).toFixed(1) + '%' : '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-400 capitalize">
                    {txn.selected_gateway || '—'}
                    {txn.rerouted_from && <span className="text-amber-400 ml-1">(↻ {txn.rerouted_from})</span>}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{txn.email_domain}</td>
                  <td className="px-4 py-3 text-[10px] text-slate-600 font-mono">
                    {txn.created_at ? new Date(txn.created_at).toLocaleString() : '—'}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => fetchTransactions(page - 1)}
            disabled={page <= 1}
            className="btn-secondary text-xs disabled:opacity-30"
          >
            ← Previous
          </button>
          <span className="text-xs text-slate-500">Page {page} of {totalPages}</span>
          <button
            onClick={() => fetchTransactions(page + 1)}
            disabled={page >= totalPages}
            className="btn-secondary text-xs disabled:opacity-30"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
