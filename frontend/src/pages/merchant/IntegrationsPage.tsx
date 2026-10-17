import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api';
import type { StoreConnection, StoreSyncStatus, PaymentConfig } from '../../types';
import {
  Link2,
  RefreshCw,
  Unlink,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  CreditCard,
  Plus,
  Package,
  Users,
  ShoppingCart,
  Clock,
  Lock,
  Store,
  Sparkles,
  Info,
  Sliders,
  Settings,
} from 'lucide-react';

export default function IntegrationsPage() {
  const [connections, setConnections] = useState<StoreConnection[]>([]);
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [disconnectModal, setDisconnectModal] = useState<StoreConnection | null>(null);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Payment configuration modal state
  const [paymentModalOpen, setPaymentModalOpen] = useState(false);
  const [selectedPaymentMode, setSelectedPaymentMode] = useState<string>('later');
  const [selectedRazorpayMode, setSelectedRazorpayMode] = useState<'test' | 'live'>('test');
  const [editKeyId, setEditKeyId] = useState('');
  const [editKeySecret, setEditKeySecret] = useState('');
  const [savingPayment, setSavingPayment] = useState(false);
  const [paymentSaveError, setPaymentSaveError] = useState<string | null>(null);

  // Load connections and payment config
  const loadData = async () => {
    setLoading(true);
    try {
      const [connRes, payRes] = await Promise.all([
        api.get<StoreConnection[]>('/stores'),
        api.get<PaymentConfig>('/payments/config'),
      ]);
      setConnections(connRes.data || []);
      setPaymentConfig(payRes.data || null);
    } catch (e: any) {
      console.error('Failed to load integrations', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const openPaymentModal = () => {
    setSelectedPaymentMode(paymentConfig?.payment_mode || 'later');
    setSelectedRazorpayMode(paymentConfig?.razorpay_mode === 'live' ? 'live' : 'test');
    setEditKeyId('');
    setEditKeySecret('');
    setPaymentSaveError(null);
    setPaymentModalOpen(true);
  };

  const formatPaymentMode = (mode?: string) => {
    switch (mode) {
      case 'store_native':
        return 'Store Native (Shopify/WooCommerce)';
      case 'razorpay_reconciliation':
        return 'Razorpay Reconciliation';
      case 'razorpay_hosted':
        return 'Flowmint-Hosted Razorpay';
      case 'later':
        return 'Configure Later (Preview Only)';
      default:
        return mode ? mode.replace('_', ' ') : 'Store Native';
    }
  };

  const handleSavePaymentConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingPayment(true);
    setPaymentSaveError(null);

    try {
      const payload: {
        payment_mode: string;
        razorpay_mode: 'test' | 'live';
        razorpay_key_id?: string;
        razorpay_key_secret?: string;
      } = {
        payment_mode: selectedPaymentMode,
        razorpay_mode: selectedRazorpayMode,
      };

      if (editKeyId.trim()) {
        payload.razorpay_key_id = editKeyId.trim();
      }
      if (editKeySecret.trim()) {
        payload.razorpay_key_secret = editKeySecret.trim();
      }

      const res = await api.post<PaymentConfig>('/payments/config', payload);
      if (!res.data) {
        throw new Error('Failed to update payment configuration');
      }

      // Refresh payment config from GET /payments/config to guarantee synchronization with backend
      const freshRes = await api.get<PaymentConfig>('/payments/config');
      if (freshRes.data) {
        setPaymentConfig(freshRes.data);
      } else {
        setPaymentConfig(res.data);
      }

      setStatusMsg({
        type: 'success',
        text: `Payment configuration updated successfully to ${formatPaymentMode(selectedPaymentMode)}!`,
      });
      setPaymentModalOpen(false);
    } catch (err: any) {
      setPaymentSaveError(err.message || 'Failed to save payment configuration');
    } finally {
      setSavingPayment(false);
    }
  };

  const handleSyncNow = async (connectionId: string) => {
    if (syncingId === connectionId) return;
    setSyncingId(connectionId);
    setStatusMsg(null);
    try {
      const res = await api.post<StoreSyncStatus>(`/stores/${connectionId}/sync`);
      if (res.data) {
        setStatusMsg({
          type: 'success',
          text: `Synchronization complete: processed ${res.data.records_processed} records.`,
        });
        await loadData();
      }
    } catch (err: any) {
      setStatusMsg({
        type: 'error',
        text: err.message || 'Synchronization failed.',
      });
    } finally {
      setSyncingId(null);
    }
  };

  const handleDisconnect = async () => {
    if (!disconnectModal) return;
    setStatusMsg(null);
    try {
      await api.post(`/stores/${disconnectModal.id}/disconnect`);
      setStatusMsg({
        type: 'success',
        text: `Disconnected ${disconnectModal.store_name || disconnectModal.provider}. Historical records have been preserved.`,
      });
      setDisconnectModal(null);
      await loadData();
    } catch (err: any) {
      setStatusMsg({
        type: 'error',
        text: err.message || 'Failed to disconnect store.',
      });
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    });
  };

  const isStoreNative = paymentConfig?.payment_mode === 'store_native';
  const isPaymentLater = paymentConfig?.payment_mode === 'later' || !paymentConfig?.payment_mode;
  const isRazorpayHosted = paymentConfig?.payment_mode === 'razorpay_hosted' || paymentConfig?.payment_mode === 'razorpay';
  const isRazorpayReconciliation = paymentConfig?.payment_mode === 'razorpay_reconciliation';

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header with Clear Action Hierarchy */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <Link2 className="w-6 h-6 text-brand-400" />
            Integrations &amp; Store Connections
          </h1>
          <p className="text-surface-300 text-sm mt-1">
            Manage your connected e-commerce storefronts, payment gateways, and data synchronization.
          </p>
        </div>

        <div className="flex items-center gap-3 self-start sm:self-auto">
          {/* Secondary Action: Preview Customer-Facing Storefront */}
          <Link
            to="/store"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary text-xs flex items-center gap-2 py-2 px-3.5 border-surface-700 hover:border-brand-500/50 hover:bg-surface-800 text-surface-200 transition"
            title="Preview customer-facing Flowmint storefront in a new tab"
          >
            <Store className="w-4 h-4 text-brand-400" />
            <span>Preview Storefront</span>
            <ExternalLink className="w-3.5 h-3.5 text-surface-400" />
          </Link>

          {/* Primary Action: Connect Another External Store */}
          <a
            href="/onboarding/connect-store"
            className="btn-primary text-xs flex items-center gap-2 py-2 px-3.5 shadow-md"
          >
            <Plus className="w-4 h-4" />
            <span>Connect Another Store</span>
          </a>
        </div>
      </div>

      {statusMsg && (
        <div
          className={`p-4 rounded-xl flex items-center gap-3 text-sm animate-fade-in ${
            statusMsg.type === 'success'
              ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-300'
              : 'bg-danger-500/10 border border-danger-500/30 text-danger-300'
          }`}
        >
          {statusMsg.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
          )}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Customer-Facing Storefront Channel Overview */}
      <section className="card p-5 bg-gradient-to-r from-surface-900 via-surface-900 to-surface-950 border-surface-700/80 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 border border-brand-400/30 flex items-center justify-center text-brand-400">
              <Store className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">Flowmint Customer Storefront</h3>
                <span
                  className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                    isPaymentLater
                      ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                      : isRazorpayHosted
                      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                      : isRazorpayReconciliation
                      ? 'bg-blue-500/10 text-blue-300 border-blue-500/30'
                      : 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                  }`}
                >
                  {isPaymentLater
                    ? 'PREVIEW ONLY (CHECKOUT PENDING)'
                    : isRazorpayHosted
                    ? 'HOSTED COMMERCE ACTIVE'
                    : isRazorpayReconciliation
                    ? 'RECONCILIATION ACTIVE'
                    : 'EXTERNAL CHECKOUT ACTIVE'}
                </span>
              </div>
              <p className="text-xs text-surface-400 mt-0.5">
                {isRazorpayHosted
                  ? 'Flowmint-hosted storefront with direct Razorpay checkout enabled.'
                  : isRazorpayReconciliation
                  ? 'Razorpay configured for transaction reconciliation. Customer checkout is handled on your connected storefront.'
                  : isStoreNative
                  ? 'Your connected external store remains your primary storefront and checkout. The Flowmint storefront provides an AI product discovery preview.'
                  : 'Payment gateway setup was deferred. The customer storefront can be previewed, but checkout is disabled until payment credentials are configured.'}
              </p>
            </div>
          </div>

          <Link
            to="/store"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-brand-300 hover:text-white font-medium bg-surface-800/80 hover:bg-surface-800 px-3 py-1.5 rounded-lg border border-surface-700 transition self-start sm:self-auto shrink-0"
          >
            <span>Open Preview</span>
            <ExternalLink className="w-3.5 h-3.5 text-brand-400" />
          </Link>
        </div>
      </section>

      {/* Connected Stores Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Connected Platforms</h2>
          <span className="text-xs text-surface-400">
            {connections.length} {connections.length === 1 ? 'connection' : 'connections'}
          </span>
        </div>

        {loading ? (
          <div className="card p-12 text-center text-surface-400 animate-pulse">
            Loading store connections...
          </div>
        ) : connections.length === 0 ? (
          <div className="card p-10 text-center space-y-4 border-dashed border-surface-700">
            <div className="w-12 h-12 mx-auto rounded-xl bg-surface-800 flex items-center justify-center text-surface-400">
              <Link2 className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">No External Store Connected</h3>
              <p className="text-xs text-surface-400 max-w-md mx-auto mt-1">
                You are currently managing products and customers manually. Connect your Shopify,
                WooCommerce, or custom storefront to unlock real-time revenue actions.
              </p>
            </div>
            <a href="/onboarding/connect-store" className="btn-primary inline-flex items-center gap-2 text-xs">
              <Plus className="w-4 h-4" />
              <span>Connect Store Now</span>
            </a>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-5">
            {connections.map(conn => {
              const summary = conn.sync_summary || {};
              const isSyncing = syncingId === conn.id;

              return (
                <div key={conn.id} className="card p-6 space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-700/60">
                    <div className="flex items-center gap-3.5">
                      <div className="w-11 h-11 rounded-xl bg-surface-900 border border-surface-700 flex items-center justify-center text-brand-400 font-bold text-lg uppercase">
                        {conn.provider.charAt(0)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-base font-semibold text-white">
                            {conn.store_name || conn.provider}
                          </h3>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                              conn.status === 'connected' || conn.status === 'synced'
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                            }`}
                          >
                            {conn.status}
                          </span>
                        </div>
                        <a
                          href={conn.store_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-surface-400 hover:text-brand-400 flex items-center gap-1 mt-0.5 font-mono"
                        >
                          <span>{conn.store_url}</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-start sm:self-auto">
                      <button
                        onClick={() => handleSyncNow(conn.id)}
                        disabled={isSyncing}
                        className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
                        <span>{isSyncing ? 'Syncing...' : 'Sync Now'}</span>
                      </button>

                      <button
                        onClick={() => setDisconnectModal(conn)}
                        className="p-1.5 rounded-lg text-surface-400 hover:text-danger-400 hover:bg-danger-500/10 transition-colors"
                        title="Disconnect store"
                      >
                        <Unlink className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Sync Metrics Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
                    <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-700/50 space-y-1">
                      <div className="flex items-center gap-1.5 text-surface-400">
                        <Package className="w-3.5 h-3.5" />
                        <span>Products Synced</span>
                      </div>
                      <div className="text-base font-bold text-white">
                        {summary.products ?? 0}
                      </div>
                    </div>

                    <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-700/50 space-y-1">
                      <div className="flex items-center gap-1.5 text-surface-400">
                        <Users className="w-3.5 h-3.5" />
                        <span>Customers Synced</span>
                      </div>
                      <div className="text-base font-bold text-white">
                        {summary.customers ?? 0}
                      </div>
                    </div>

                    <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-700/50 space-y-1">
                      <div className="flex items-center gap-1.5 text-surface-400">
                        <ShoppingCart className="w-3.5 h-3.5" />
                        <span>Orders Reconciled</span>
                      </div>
                      <div className="text-base font-bold text-white">
                        {summary.orders ?? 0}
                      </div>
                    </div>

                    <div className="p-3 bg-surface-900/60 rounded-xl border border-surface-700/50 space-y-1">
                      <div className="flex items-center gap-1.5 text-surface-400">
                        <Clock className="w-3.5 h-3.5" />
                        <span>Last Successful Sync</span>
                      </div>
                      <div className="text-xs font-semibold text-surface-200">
                        {formatDate(conn.last_sync_at)}
                      </div>
                    </div>
                  </div>

                  {/* Permissions & Scopes note */}
                  <div className="text-[11px] text-surface-400 flex flex-wrap items-center justify-between gap-2 pt-1">
                    <span className="flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                      Scopes: <span className="font-mono text-surface-300">{conn.scopes || 'read-only'}</span>
                    </span>
                    <span>Provider ID: <span className="font-mono">{conn.id.slice(0, 8)}</span></span>
                  </div>

                  {/* Shopify Webhook Endpoint Notice */}
                  {conn.provider === 'shopify' && (
                    <div className="bg-surface-900/80 rounded-xl p-3 border border-surface-700/60 text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white flex items-center gap-1.5">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          Automatic Real-Time Webhook Pipeline
                        </span>
                        <span className="text-[10px] text-brand-300 font-mono bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                          Active Webhooks
                        </span>
                      </div>
                      <p className="text-surface-400 text-[11px]">
                        Product, price, inventory, and order changes in Shopify automatically synchronize with Flowmint AI.
                        Webhook receiver registered:
                      </p>
                      <div className="bg-surface-950 px-2.5 py-1.5 rounded font-mono text-[11px] text-brand-300 border border-surface-800 break-all select-all">
                        {window.location.origin.replace(':5173', ':8000')}/api/v1/stores/shopify/webhook
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Payment Gateway Configuration Section */}
      <section className="space-y-4 pt-4 border-t border-surface-700/60">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-brand-400" />
              <span>Payment Gateway &amp; Reconciliation</span>
            </h2>
            <p className="text-xs text-surface-300">
              Flowmint connects with Razorpay for test/live checkout and automated transaction reconciliation.
            </p>
          </div>
          <div className="flex items-center gap-2.5 self-start sm:self-auto">
            <span className={paymentConfig?.razorpay_mode === 'live' ? 'badge-danger text-xs' : 'badge-warning text-xs'}>
              {paymentConfig?.razorpay_mode === 'live' ? 'Live Mode' : 'Test Mode'}
            </span>
            <button
              type="button"
              onClick={openPaymentModal}
              className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3 border-surface-700 hover:border-brand-500/50 hover:bg-surface-800 text-surface-200 transition"
              title="Configure payment modes, Razorpay gateway credentials, and checkout behavior"
            >
              <Sliders className="w-3.5 h-3.5 text-brand-400" />
              <span>Configure Payments</span>
            </button>
          </div>
        </div>

        <div className="card p-6 space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div className="space-y-1">
              <div className="text-surface-400 font-medium">Payment Mode</div>
              <div className="text-sm font-semibold text-white">
                {formatPaymentMode(paymentConfig?.payment_mode)}
              </div>
              <p className="text-[11px] text-surface-400">
                {paymentConfig?.payment_mode === 'razorpay_hosted'
                  ? 'Autonomous buyer checkout enabled on Flowmint storefront.'
                  : paymentConfig?.payment_mode === 'razorpay_reconciliation'
                  ? 'Reconciliation of external store payments.'
                  : paymentConfig?.payment_mode === 'later'
                  ? 'Checkout deferred; storefront in preview mode.'
                  : 'Native store checkout.'}
              </p>
            </div>

            <div className="space-y-1">
              <div className="text-surface-400 font-medium">Gateway Status</div>
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${paymentConfig?.razorpay_configured ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className="text-sm font-semibold text-white">
                  {paymentConfig?.razorpay_configured ? 'Configured & Active' : 'Default Sandbox'}
                </span>
              </div>
              <p className="text-[11px] text-surface-400">
                {paymentConfig?.razorpay_configured ? 'Credentials validated on backend.' : 'Using fallback test sandbox.'}
              </p>
            </div>

            <div className="space-y-1">
              <div className="text-surface-400 font-medium">Public Key ID</div>
              <div className="text-sm font-mono text-surface-300">
                {paymentConfig?.razorpay_key_id || 'Platform Default'}
              </div>
              <p className="text-[11px] text-surface-400">
                Environment: {paymentConfig?.razorpay_mode === 'live' ? 'Live Production' : 'Test Mode'}
              </p>
            </div>
          </div>

          <div className="p-3 bg-surface-900 rounded-lg border border-surface-700/60 text-xs text-surface-400 space-y-1">
            <div className="font-semibold text-surface-300 flex items-center gap-1">
              <Lock className="w-3.5 h-3.5 text-brand-400" />
              Webhook Receiver Endpoint:
            </div>
            <code className="text-[11px] font-mono text-emerald-300 select-all block">
              {paymentConfig?.webhook_url || `${window.location.origin}/api/v1/payments/webhook`}
            </code>
          </div>

          <div className="pt-2 border-t border-surface-800 flex items-center justify-between">
            <span className="text-xs text-surface-400">
              Need to adjust credentials or switch checkout modes?
            </span>
            <button
              type="button"
              onClick={openPaymentModal}
              className="text-xs text-brand-400 hover:text-brand-300 font-medium flex items-center gap-1 transition"
            >
              <span>Edit Payment Settings</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        </div>
      </section>

      {/* Payment Configuration Modal */}
      {paymentModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="card p-6 sm:p-7 max-w-xl w-full space-y-5 animate-scale-up border-brand-500/40 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-surface-700/60">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-brand-500/15 rounded-lg border border-brand-400/25">
                  <CreditCard className="w-5 h-5 text-brand-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">Configure Payment Processing</h3>
                  <p className="text-xs text-surface-400">
                    Choose how checkouts and payments are handled across Flowmint.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setPaymentModalOpen(false)}
                className="text-surface-400 hover:text-white p-1 text-sm rounded-lg"
              >
                ✕
              </button>
            </div>

            {paymentSaveError && (
              <div className="p-3 bg-danger-500/10 border border-danger-500/30 rounded-lg text-xs text-danger-300 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{paymentSaveError}</span>
              </div>
            )}

            <form onSubmit={handleSavePaymentConfig} className="space-y-4">
              {/* Payment Mode Selection */}
              <div className="space-y-2">
                <label className="block text-xs font-semibold text-surface-300 uppercase tracking-wider">
                  Payment Mode
                </label>
                <div className="grid grid-cols-1 gap-2.5">
                  {/* Mode 1: store_native */}
                  <label
                    className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                      selectedPaymentMode === 'store_native'
                        ? 'border-brand-500 bg-brand-950/25 ring-1 ring-brand-500/30'
                        : 'border-surface-700/80 bg-surface-900/60 hover:border-surface-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="payment_mode"
                      value="store_native"
                      checked={selectedPaymentMode === 'store_native'}
                      onChange={e => setSelectedPaymentMode(e.target.value)}
                      className="mt-0.5 text-brand-500 focus:ring-brand-500"
                    />
                    <div className="space-y-0.5">
                      <div className="text-xs font-semibold text-white">
                        Existing Store Checkout (Store Native)
                      </div>
                      <p className="text-[11px] text-surface-400 leading-relaxed">
                        Customers checkout on your connected Shopify or WooCommerce store. Flowmint imports orders and reconciles financial data.
                      </p>
                    </div>
                  </label>

                  {/* Mode 2: razorpay_reconciliation */}
                  <label
                    className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                      selectedPaymentMode === 'razorpay_reconciliation'
                        ? 'border-brand-500 bg-brand-950/25 ring-1 ring-brand-500/30'
                        : 'border-surface-700/80 bg-surface-900/60 hover:border-surface-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="payment_mode"
                      value="razorpay_reconciliation"
                      checked={selectedPaymentMode === 'razorpay_reconciliation'}
                      onChange={e => setSelectedPaymentMode(e.target.value)}
                      className="mt-0.5 text-brand-500 focus:ring-brand-500"
                    />
                    <div className="space-y-0.5">
                      <div className="text-xs font-semibold text-white">
                        Razorpay Payment Reconciliation
                      </div>
                      <p className="text-[11px] text-surface-400 leading-relaxed">
                        Connect Razorpay for automated settlement monitoring, dispute tracking, and payment failure recovery across external channels.
                      </p>
                    </div>
                  </label>

                  {/* Mode 3: razorpay_hosted */}
                  <label
                    className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                      selectedPaymentMode === 'razorpay_hosted'
                        ? 'border-brand-500 bg-brand-950/25 ring-1 ring-brand-500/30'
                        : 'border-surface-700/80 bg-surface-900/60 hover:border-surface-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="payment_mode"
                      value="razorpay_hosted"
                      checked={selectedPaymentMode === 'razorpay_hosted'}
                      onChange={e => setSelectedPaymentMode(e.target.value)}
                      className="mt-0.5 text-brand-500 focus:ring-brand-500"
                    />
                    <div className="space-y-0.5">
                      <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                        <span>Flowmint-Hosted Razorpay Checkout</span>
                        <span className="badge-success text-[10px] px-1.5 py-0.2">Storefront</span>
                      </div>
                      <p className="text-[11px] text-surface-400 leading-relaxed">
                        Enable direct buyer purchasing on your Flowmint storefront (`/store`). Buyers can complete checkout directly using Razorpay.
                      </p>
                    </div>
                  </label>

                  {/* Mode 4: later */}
                  <label
                    className={`p-3.5 rounded-xl border cursor-pointer flex items-start gap-3 transition ${
                      selectedPaymentMode === 'later'
                        ? 'border-brand-500 bg-brand-950/25 ring-1 ring-brand-500/30'
                        : 'border-surface-700/80 bg-surface-900/60 hover:border-surface-600'
                    }`}
                  >
                    <input
                      type="radio"
                      name="payment_mode"
                      value="later"
                      checked={selectedPaymentMode === 'later'}
                      onChange={e => setSelectedPaymentMode(e.target.value)}
                      className="mt-0.5 text-brand-500 focus:ring-brand-500"
                    />
                    <div className="space-y-0.5">
                      <div className="text-xs font-semibold text-white">
                        Configure Later (Preview Only)
                      </div>
                      <p className="text-[11px] text-surface-400 leading-relaxed">
                        Defer payment gateway setup. The customer storefront can be previewed, but checkout will be disabled.
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              {/* Gateway Mode Selector: Test Mode vs Live Mode */}
              <div className="space-y-2 pt-2 border-t border-surface-800">
                <label className="block text-xs font-semibold text-surface-300 uppercase tracking-wider">
                  Gateway Environment
                </label>
                <div className="grid grid-cols-2 gap-2.5">
                  <button
                    type="button"
                    onClick={() => setSelectedRazorpayMode('test')}
                    className={`py-2 px-3 rounded-lg border text-xs font-medium transition flex items-center justify-center gap-1.5 ${
                      selectedRazorpayMode === 'test'
                        ? 'bg-brand-500/20 border-brand-400 text-brand-300 ring-1 ring-brand-400/40'
                        : 'bg-surface-900 border-surface-700 text-surface-300 hover:text-white'
                    }`}
                  >
                    <CheckCircle2 className={`w-3.5 h-3.5 ${selectedRazorpayMode === 'test' ? 'text-brand-400' : 'text-surface-500'}`} />
                    <span>Test Mode (Default)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedRazorpayMode('live')}
                    className={`py-2 px-3 rounded-lg border text-xs font-medium transition flex items-center justify-center gap-1.5 ${
                      selectedRazorpayMode === 'live'
                        ? 'bg-danger-500/20 border-danger-400 text-danger-300 ring-1 ring-danger-400/40'
                        : 'bg-surface-900 border-surface-700 text-surface-300 hover:text-white'
                    }`}
                  >
                    <CheckCircle2 className={`w-3.5 h-3.5 ${selectedRazorpayMode === 'live' ? 'text-danger-400' : 'text-surface-500'}`} />
                    <span>Live Production Mode</span>
                  </button>
                </div>
                {selectedRazorpayMode === 'live' && (
                  <p className="text-[11px] text-danger-300 bg-danger-500/10 p-2 rounded border border-danger-500/20">
                    Caution: Live Mode processes real customer charges. Ensure your Live Key ID &amp; Secret are configured.
                  </p>
                )}
              </div>

              {/* Credential Editing (shown when razorpay mode selected) */}
              {(selectedPaymentMode === 'razorpay_hosted' || selectedPaymentMode === 'razorpay_reconciliation') && (
                <div className="space-y-3 pt-2 border-t border-surface-800 bg-surface-900/40 p-3.5 rounded-xl border border-surface-800">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-brand-400" />
                      Razorpay API Credentials
                    </span>
                    {paymentConfig?.razorpay_configured && (
                      <span className="text-[10px] text-emerald-400 font-mono">
                        Configured: {paymentConfig.razorpay_key_id}
                      </span>
                    )}
                  </div>

                  {paymentConfig?.razorpay_configured && (
                    <p className="text-[11px] text-surface-400">
                      Credentials are already saved. Leave these fields blank to retain your existing configured keys.
                    </p>
                  )}

                  <div className="space-y-2">
                    <div>
                      <label className="block text-[11px] text-surface-400 mb-1">
                        Key ID
                      </label>
                      <input
                        type="text"
                        value={editKeyId}
                        onChange={e => setEditKeyId(e.target.value)}
                        placeholder={paymentConfig?.razorpay_key_id ? `Keep current key (${paymentConfig.razorpay_key_id})` : 'rzp_test_...'}
                        className="input-field w-full text-xs font-mono"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] text-surface-400 mb-1">
                        Key Secret
                      </label>
                      <input
                        type="password"
                        value={editKeySecret}
                        onChange={e => setEditKeySecret(e.target.value)}
                        placeholder={paymentConfig?.razorpay_configured ? '•••••••••••••••• (Leave blank to keep existing)' : 'Enter Razorpay Key Secret'}
                        className="input-field w-full text-xs font-mono"
                      />
                    </div>
                  </div>

                  <p className="text-[10px] text-surface-500 leading-tight">
                    Secrets are encrypted with AES-256 GCM on the server and are never returned to the frontend.
                  </p>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-800">
                <button
                  type="button"
                  onClick={() => setPaymentModalOpen(false)}
                  disabled={savingPayment}
                  className="btn-secondary text-xs px-4 py-2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingPayment}
                  className="btn-primary text-xs px-5 py-2 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {savingPayment ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Save Payment Configuration</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Disconnect Confirmation Modal */}
      {disconnectModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="card p-6 max-w-md w-full space-y-5 animate-scale-up border-danger-500/30">
            <div className="flex items-center gap-3 text-danger-400">
              <AlertCircle className="w-6 h-6 flex-shrink-0" />
              <h3 className="text-lg font-bold text-white">Disconnect Store?</h3>
            </div>

            <p className="text-xs text-surface-300 leading-relaxed">
              Are you sure you want to disconnect{' '}
              <span className="font-semibold text-white">
                {disconnectModal.store_name || disconnectModal.provider}
              </span>
              ? Flowmint AI will pause ongoing background synchronization.
            </p>

            <div className="p-3 bg-surface-900 rounded-lg border border-surface-700 text-xs text-surface-400 space-y-1">
              <span className="font-semibold text-surface-200">Data Preservation Policy:</span>
              <p>
                Previously imported products, customers, and order records will NOT be deleted.
                You can reconnect this store at any time.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDisconnectModal(null)}
                className="btn-secondary text-xs px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDisconnect}
                className="bg-danger-600 hover:bg-danger-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors"
              >
                Confirm Disconnect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
