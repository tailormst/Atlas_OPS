/**
 * ATLAS-OPS API Client
 * Central fetch wrapper for all backend API calls.
 * Includes auth header injection and idempotency key generation.
 */

const API_BASE = '/v1'

function getAuthToken() {
  return localStorage.getItem('atlas_token')
}

function generateIdempotencyKey() {
  return crypto.randomUUID ? crypto.randomUUID() : 
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
    })
}

async function request(endpoint, options = {}) {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  // Inject auth token
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Auto-add idempotency key for POST requests
  if (options.method === 'POST' && !headers['Idempotency-Key']) {
    headers['Idempotency-Key'] = generateIdempotencyKey()
  }

  const config = { ...options, headers }

  try {
    const response = await fetch(url, config)
    
    if (response.status === 401) {
      // Token expired — clear auth
      localStorage.removeItem('atlas_token')
      localStorage.removeItem('atlas_refresh')
      localStorage.removeItem('atlas_user')
      window.location.href = '/login'
      throw new Error('Session expired. Please login again.')
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return await response.json()
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      throw new Error('Backend unavailable. Ensure the API is running on port 8000.')
    }
    throw err
  }
}

export const api = {
  // Auth
  login: (email, password, adminKey) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, admin_key: adminKey || undefined }),
    }),

  refreshToken: (refreshToken) =>
    request('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  getMe: () => request('/auth/me'),

  // Health
  health: () => request('/health'),

  // Transactions
  processTransaction: (data) =>
    request('/transaction/process', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listTransactions: (page = 1, perPage = 20, status = null) => {
    let url = `/transactions?page=${page}&per_page=${perPage}`
    if (status) url += `&status=${status}`
    return request(url)
  },

  // Gateway Health
  getGatewayHealth: () => request('/gateways/health'),

  // ML Status
  getMLStatus: () => request('/ml/status'),

  // Explain
  explainTransaction: (txnId) => request(`/transaction/${txnId}/explain`),

  // Simulate Outage
  simulateOutage: (data, adminKey) =>
    request('/simulate/outage', {
      method: 'POST',
      body: JSON.stringify(data),
      headers: { 'X-Admin-Key': adminKey },
    }),

  clearOutage: (gateway, adminKey) =>
    request(`/simulate/outage/${gateway}`, {
      method: 'DELETE',
      headers: { 'X-Admin-Key': adminKey },
    }),
}

/**
 * Start an SSE connection for the live pipeline.
 * Returns a function to abort the connection.
 */
export function connectPipelineSSE(transactionData, onEvent, onError, onComplete) {
  const controller = new AbortController()

  const headers = {
    'Content-Type': 'application/json',
    'Idempotency-Key': generateIdempotencyKey(),
  }
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  fetch(`${API_BASE}/transaction/process-live`, {
    method: 'POST',
    headers,
    body: JSON.stringify(transactionData),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Pipeline request failed' }))
        onError(new Error(err.detail || `HTTP ${response.status}`))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6))
              onEvent(event)
            } catch {
              // skip malformed events
            }
          }
        }
      }

      onComplete?.()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(err)
      }
    })

  return () => controller.abort()
}

export default api
