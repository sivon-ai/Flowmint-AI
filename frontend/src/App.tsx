import { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { api } from './lib/api';
import LoginPage from './pages/LoginPage';
import DashboardLayout from './components/layout/DashboardLayout';
import DashboardPage from './pages/merchant/DashboardPage';
import ProductsPage from './pages/merchant/ProductsPage';
import OrdersPage from './pages/merchant/OrdersPage';
import InventoryPage from './pages/merchant/InventoryPage';
import AICopilotPage from './pages/merchant/AICopilotPage';
import OpportunitiesPage from './pages/merchant/OpportunitiesPage';
import SimulationsPage from './pages/merchant/SimulationsPage';
import ApprovalsPage from './pages/merchant/ApprovalsPage';
import PoliciesPage from './pages/merchant/PoliciesPage';
import AuditPage from './pages/merchant/AuditPage';
import AttributionPage from './pages/merchant/AttributionPage';
import TraceViewerPage from './pages/merchant/TraceViewerPage';
import EvaluationPage from './pages/merchant/EvaluationPage';
import JudgePage from './pages/merchant/JudgePage';
import StorefrontPage from './pages/buyer/StorefrontPage';
import type { User } from './types';

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (api.isAuthenticated()) {
      api.get<User>('/auth/me')
        .then(res => { if (res.data) setUser(res.data); })
        .catch(() => { api.clearTokens(); })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogin = (userData: User, accessToken: string, refreshToken: string) => {
    api.setToken(accessToken);
    api.setRefreshToken(refreshToken);
    setUser(userData);
  };

  const handleLogout = () => {
    api.clearTokens();
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-brand-400 text-xl font-semibold">
          Loading Flowmint AI...
        </div>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={
        user ? <Navigate to="/dashboard" /> : <LoginPage onLogin={handleLogin} />
      } />
      <Route path="/store" element={<StorefrontPage />} />
      {!user && (
        <Route path="/judge" element={
          <div className="min-h-screen bg-surface-950 p-6 md:p-10 text-white">
            <JudgePage />
          </div>
        } />
      )}

      {/* Protected merchant routes */}
      {user ? (
        <Route element={<DashboardLayout user={user} onLogout={handleLogout} />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/judge" element={<JudgePage />} />
          <Route path="/dashboard/judge" element={<Navigate to="/judge" replace />} />
          <Route path="/copilot" element={<AICopilotPage />} />
          <Route path="/opportunities" element={<OpportunitiesPage />} />
          <Route path="/simulations" element={<SimulationsPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/policies" element={<PoliciesPage />} />
          <Route path="/attribution" element={<AttributionPage />} />
          <Route path="/traces" element={<TraceViewerPage />} />
          <Route path="/evaluation" element={<EvaluationPage />} />
          <Route path="/audit" element={<AuditPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/orders" element={<OrdersPage />} />
        </Route>
      ) : null}

      {/* Redirect */}
      <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} />} />
    </Routes>
  );
}
