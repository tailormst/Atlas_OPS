import { useState } from 'react'
import { motion } from 'framer-motion'
import { api } from '../api/client'
import ExplainPanel from '../components/explain/ExplainPanel'

export default function ExplainabilityPage() {
  const [txnId, setTxnId] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleLookup = async () => {
    if (!txnId.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.explainTransaction(txnId.trim())
      setResult(res)
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <span>🧠</span> AI Explainability
        </h1>
        <p className="text-sm text-slate-400 mt-1">SHAP analysis and RAG explanations for transaction decisions</p>
      </motion.div>

      <div className="glass-card p-6">
        <div className="flex gap-3">
          <input type="text" value={txnId} onChange={(e) => setTxnId(e.target.value)}
            placeholder="Enter Transaction ID (UUID)" className="input-field flex-1" id="explain-txn-id"
            onKeyDown={(e) => e.key === 'Enter' && handleLookup()} />
          <button onClick={handleLookup} disabled={loading || !txnId.trim()}
            className="btn-primary disabled:opacity-50" id="explain-lookup-btn">
            {loading ? 'Loading...' : '🔍 Explain'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">{error}</div>
      )}

      {result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="glass-card p-6">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="text-[10px] text-slate-500 uppercase">Status</p>
                <p className={`text-sm font-bold ${result.status === 'APPROVED' ? 'text-emerald-400' : result.status === 'REJECTED' ? 'text-red-400' : 'text-orange-400'}`}>{result.status}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 uppercase">Amount</p>
                <p className="text-sm font-bold text-white">${result.amount?.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 uppercase">Fraud Score</p>
                <p className={`text-sm font-mono font-bold ${result.fraud_score > 0.65 ? 'text-red-400' : 'text-emerald-400'}`}>
                  {result.fraud_score != null ? (result.fraud_score * 100).toFixed(1) + '%' : '—'}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 uppercase">Gateway</p>
                <p className="text-sm text-slate-300 capitalize">{result.selected_gateway || '—'}</p>
              </div>
            </div>
          </div>
          <ExplainPanel transactionId={result.transaction_id}
            shapValues={result.fraud_shap_values || result.failure_shap_values}
            explanation={result.llm_explanation} />
        </motion.div>
      )}
    </div>
  )
}
