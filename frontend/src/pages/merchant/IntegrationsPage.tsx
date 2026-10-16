import { useState, useEffect } from 'react';
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
} from 'lucide-react';

export default function IntegrationsPage() {
  const [connections, setConnections] = useState<StoreConnection[]>([]);
  const [paymentConfig, setPaymentConfig] = useState<PaymentConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [disconnectModal, setDisconnectModal] = useState<StoreConnection | null>(null);
  const [statusMsg, setStatusMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

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

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Header */}
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

        <a
          href="/onboarding/connect-store"
          className="btn-primary text-xs flex items-center gap-2 self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Connect Another Store</span>
        </a>
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
                          Automatic Real-Time Synchronization (Webhooks)
                        </span>
                        <span className="text-[10px] text-brand-300 font-mono bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                          Active &lt; 5s
                        </span>
                      </div>
                      <p className="text-surface-400 text-[11px]">
                        Product name, price, SKU, and stock changes in Shopify automatically trigger updates in Flowmint AI.
                        Webhook URL registered in Shopify:
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
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-brand-400" />
              Payment Gateway &amp; Reconciliation
            </h2>
            <p className="text-xs text-surface-300">
              Flowmint connects with Razorpay for test/live checkout and automated transaction reconciliation.
            </p>
          </div>
          <span className="badge-warning text-xs">
            {paymentConfig?.razorpay_mode === 'live' ? 'Live Mode' : 'Test Mode'}
          </span>
        </div>

        <div className="card p-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div className="space-y-1">
              <div className="text-surface-400 font-medium">Payment Mode</div>
              <div className="text-sm font-semibold text-white capitalize">
                {paymentConfig?.payment_mode?.replace('_', ' ') || 'Store Native'}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-surface-400 font-medium">Gateway Status</div>
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${paymentConfig?.razorpay_configured ? 'bg-emerald-400' : 'bg-amber-400'}`} />
                <span className="text-sm font-semibold text-white">
                  {paymentConfig?.razorpay_configured ? 'Configured & Active' : 'Default Sandbox'}
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-surface-400 font-medium">Public Key ID</div>
              <div className="text-sm font-mono text-surface-300">
                {paymentConfig?.razorpay_key_id || 'Platform Default'}
              </div>
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
        </div>
      </section>

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
