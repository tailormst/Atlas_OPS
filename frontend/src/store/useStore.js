import { create } from 'zustand'

const PIPELINE_STAGES = [
  { id: 1, name: 'Transaction Submitted' },
  { id: 2, name: 'Validation Started' },
  { id: 3, name: 'Luhn Check' },
  { id: 4, name: 'Idempotency Check' },
  { id: 5, name: 'Fraud Feature Extraction' },
  { id: 6, name: 'ML Fraud Scoring' },
  { id: 7, name: 'Gateway Health Evaluation' },
  { id: 8, name: 'Intelligent Routing Decision' },
  { id: 9, name: 'Circuit Breaker Verification' },
  { id: 10, name: 'Gateway Execution' },
  { id: 11, name: 'Gateway Response' },
  { id: 12, name: 'Failure Analysis' },
  { id: 13, name: 'SHAP Explainability' },
  { id: 14, name: 'RAG/LLM Explanation' },
  { id: 15, name: 'Database Persistence' },
  { id: 16, name: 'Final Transaction Result' },
]

const useStore = create((set, get) => ({
  // ── Auth State ────────────────────────────────────────────────────────
  authToken: localStorage.getItem('atlas_token') || null,
  refreshToken: localStorage.getItem('atlas_refresh') || null,
  user: JSON.parse(localStorage.getItem('atlas_user') || 'null'),
  isAuthenticated: !!localStorage.getItem('atlas_token'),

  login: (tokenData) => {
    localStorage.setItem('atlas_token', tokenData.access_token)
    localStorage.setItem('atlas_refresh', tokenData.refresh_token)
    const user = { email: tokenData.email, role: tokenData.role }
    localStorage.setItem('atlas_user', JSON.stringify(user))
    set({
      authToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token,
      user,
      isAuthenticated: true,
    })
  },

  logout: () => {
    localStorage.removeItem('atlas_token')
    localStorage.removeItem('atlas_refresh')
    localStorage.removeItem('atlas_user')
    set({
      authToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    })
  },

  // ── Pipeline State ───────────────────────────────────────────────────
  pipelineStages: PIPELINE_STAGES.map((s) => ({
    ...s,
    status: 'pending',
    timestamp: null,
    data: {},
  })),
  pipelineRunning: false,
  pipelineLogs: [],
  pipelineResult: null,
  pipelineError: null,

  startPipeline: () =>
    set({
      pipelineRunning: true,
      pipelineError: null,
      pipelineResult: null,
      pipelineLogs: [],
      pipelineStages: PIPELINE_STAGES.map((s) => ({
        ...s,
        status: 'pending',
        timestamp: null,
        data: {},
      })),
    }),

  updateStage: (event) =>
    set((state) => {
      const stages = state.pipelineStages.map((s) =>
        s.id === event.stage
          ? { ...s, status: event.status, timestamp: event.timestamp, data: event.data }
          : s
      )
      const log = {
        stage: event.stage,
        name: event.name,
        status: event.status,
        timestamp: event.timestamp,
        message: event.data?.message || '',
      }
      return {
        pipelineStages: stages,
        pipelineLogs: [...state.pipelineLogs, log],
      }
    }),

  completePipeline: (result) =>
    set({ pipelineRunning: false, pipelineResult: result }),

  failPipeline: (error) =>
    set({ pipelineRunning: false, pipelineError: error }),

  // ── Gateway Health ───────────────────────────────────────────────────
  gateways: [],
  gatewaysLoading: false,
  setGateways: (gateways) => set({ gateways, gatewaysLoading: false }),
  setGatewaysLoading: (v) => set({ gatewaysLoading: v }),

  // ── Dashboard Stats ──────────────────────────────────────────────────
  stats: {
    totalTransactions: 0,
    approvedRate: 0,
    avgFraudScore: 0,
    avgLatency: 0,
  },
  setStats: (stats) => set({ stats }),

  // ── ML Status ────────────────────────────────────────────────────────
  mlStatus: null,
  setMLStatus: (s) => set({ mlStatus: s }),

  // ── Backend Connection ───────────────────────────────────────────────
  backendConnected: false,
  setBackendConnected: (v) => set({ backendConnected: v }),

  // ── Transactions History ─────────────────────────────────────────────
  transactions: [],
  transactionsPage: 1,
  transactionsTotal: 0,
  transactionsLoading: false,
  setTransactions: (data) => set({
    transactions: data.transactions || [],
    transactionsPage: data.page || 1,
    transactionsTotal: data.total || 0,
    transactionsLoading: false,
  }),
  setTransactionsLoading: (v) => set({ transactionsLoading: v }),
}))

export default useStore
