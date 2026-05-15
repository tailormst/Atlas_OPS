import { Routes, Route, Navigate } from 'react-router-dom'
import useStore from './store/useStore'
import Layout from './components/layout/Layout'
import ErrorBoundary from './components/ui/ErrorBoundary'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import LiveDemoPage from './pages/LiveDemoPage'
import AdminPage from './pages/AdminPage'
import TransactionsPage from './pages/TransactionsPage'
import GatewayHealthPage from './pages/GatewayHealthPage'
import FraudAnalyticsPage from './pages/FraudAnalyticsPage'
import ExplainabilityPage from './pages/ExplainabilityPage'
import SettingsPage from './pages/SettingsPage'

function ProtectedRoute({ children }) {
  const isAuthenticated = useStore((s) => s.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        {/* Public route */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <Layout>
                <Routes>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/live" element={<LiveDemoPage />} />
                  <Route path="/transactions" element={<TransactionsPage />} />
                  <Route path="/gateways" element={<GatewayHealthPage />} />
                  <Route path="/analytics" element={<FraudAnalyticsPage />} />
                  <Route path="/explainability" element={<ExplainabilityPage />} />
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </ErrorBoundary>
  )
}
