import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api';
import type { Product, Order, RevenueOverviewMetrics, Opportunity } from '../../types';
import {
  TrendingUp,
  Package,
  ShoppingCart,
  DollarSign,
  ArrowUpRight,
  Zap,
  AlertTriangle,
  Lightbulb,
  ArrowRight,
  Percent,
  CreditCard,
} from 'lucide-react';

export default function DashboardPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [metrics, setMetrics] = useState<RevenueOverviewMetrics | null>(null);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<Product[]>('/products?per_page=5'),
      api.get<Order[]>('/orders?per_page=5'),
      api.get<RevenueOverviewMetrics>('/opportunities/metrics/overview').catch(() => ({ data: null })),
      api.get<Opportunity[]>('/opportunities?per_page=4').catch(() => ({ data: [] })),
    ])
      .then(([prodRes, orderRes, metricsRes, oppRes]) => {
        setProducts(prodRes.data || []);
        setOrders(orderRes.data || []);
        if (metricsRes.data) setMetrics(metricsRes.data);
        if (oppRes.data) setOpportunities(oppRes.data);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const totalRevenue = metrics ? metrics.total_revenue : orders.reduce((sum, o) => sum + Number(o.total), 0);
  const totalOrders = metrics ? metrics.completed_orders : orders.length;

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 font-mono">
              DEMO DATASET: TECHMART INDIA
            </span>
            <span className="text-xs text-surface-400">Simulated Commerce Telemetry</span>
          </div>
          <h1 className="text-3xl font-bold text-white mt-1">Revenue Command Center</h1>
          <p className="text-surface-300 mt-0.5">Real-time revenue metrics, detected leakages, and proactive opportunities</p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/simulations"
            className="btn-secondary flex items-center gap-2 text-sm"
          >
            <TrendingUp className="w-4 h-4 text-brand-400" />
            What-If Simulator
          </Link>
          <Link
            to="/opportunities"
            className="btn-primary flex items-center gap-2 text-sm"
          >
            <Zap className="w-4 h-4" />
            View Opportunities ({opportunities.length})
          </Link>
        </div>
      </div>

      {/* Revenue Intelligence Core Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard
          icon={DollarSign}
          label="Total Revenue"
          value={formatCurrency(totalRevenue)}
          trend="30 Days"
          color="brand"
        />
        <StatCard
          icon={AlertTriangle}
          label="Revenue at Risk"
          value={formatCurrency(metrics?.revenue_at_risk ?? 0)}
          trend="Carts & Drops"
          color="danger"
          isDanger={Boolean(metrics?.revenue_at_risk && metrics.revenue_at_risk > 0)}
        />
        <StatCard
          icon={Lightbulb}
          label="Active Opportunities"
          value={String(opportunities.length || metrics?.active_opportunities_count || 0)}
          trend="High Potential"
          color="warning"
        />
        <StatCard
          icon={ShoppingCart}
          label="Cart Abandonment"
          value={`${(metrics?.cart_abandonment_rate ?? 0).toFixed(1)}%`}
          trend="Recovery Potential"
          color="info"
        />
        <StatCard
          icon={CreditCard}
          label="Payment Failure"
          value={`${(metrics?.payment_failure_rate ?? 0).toFixed(1)}%`}
          trend="Transaction Risk"
          color="danger"
        />
        <StatCard
          icon={Percent}
          label="Checkout Conversion"
          value={`${(metrics?.checkout_conversion_rate ?? 0).toFixed(1)}%`}
          trend="Completed"
          color="success"
        />
      </div>

      {/* Detected Opportunities Spotlight */}
      <div className="card p-6 bg-gradient-to-r from-brand-900/40 via-surface-900 to-surface-900 border-brand-500/30">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-brand-600/20 rounded-xl border border-brand-500/30">
              <Zap className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Detected Revenue Opportunities</h2>
              <p className="text-xs text-surface-300">
                AI and deterministic rule detectors identified these actionable profit opportunities.
              </p>
            </div>
          </div>
          <Link
            to="/opportunities"
            className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1 font-medium"
          >
            Explore all <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {opportunities.length === 0 ? (
          <div className="p-6 text-center rounded-xl bg-surface-950/40 border border-surface-800 text-surface-400 text-sm">
            No active revenue opportunities detected yet. As carts, orders, and payments flow through Flowmint, the decision engine evaluates growth and recovery opportunities automatically.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {opportunities.slice(0, 4).map((opp) => (
              <div
                key={opp.id}
                className="p-4 rounded-xl bg-surface-950/60 border border-surface-700/60 hover:border-brand-500/40 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-800 text-brand-400 border border-surface-700">
                      {opp.type.replace('_', ' ')}
                    </span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase ${
                      opp.priority === 'critical' ? 'bg-danger-500/20 text-danger-400' :
                      opp.priority === 'high' ? 'bg-warning-500/20 text-warning-400' :
                      'bg-surface-800 text-surface-300'
                    }`}>
                      {opp.priority}
                    </span>
                  </div>
                  <h4 className="text-sm font-semibold text-white mt-2">{opp.title}</h4>
                  <p className="text-xs text-surface-300 mt-1 line-clamp-2">{opp.description}</p>
                </div>

                <div className="mt-4 pt-3 border-t border-surface-800/80 flex items-center justify-between">
                  <div className="text-xs">
                    <span className="text-surface-400">Est. Value: </span>
                    <span className="text-white font-semibold">{formatCurrency(opp.estimated_value)}</span>
                  </div>
                  <Link
                    to={`/opportunities?id=${opp.id}`}
                    className="text-xs font-medium text-brand-400 hover:text-brand-300 flex items-center gap-1"
                  >
                    Investigate <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Orders */}
      <div className="card">
        <div className="px-6 py-4 border-b border-surface-700/50 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Recent Orders</h2>
          <Link to="/orders" className="text-xs text-brand-400 hover:underline">View all</Link>
        </div>
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-8 text-center text-surface-300">Loading live data...</div>
          ) : orders.length === 0 ? (
            <div className="p-8 text-center text-surface-300">
              No orders yet. Create products and start selling!
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-700/50">
                  <th className="table-header px-6 py-3 text-left">Order</th>
                  <th className="table-header px-6 py-3 text-left">Status</th>
                  <th className="table-header px-6 py-3 text-left">Items</th>
                  <th className="table-header px-6 py-3 text-right">Total</th>
                  <th className="table-header px-6 py-3 text-right">Date</th>
                </tr>
              </thead>
              <tbody>
                {orders.map(order => (
                  <tr key={order.id} className="table-row">
                    <td className="px-6 py-3.5 text-sm font-mono text-brand-400">
                      {order.order_number}
                    </td>
                    <td className="px-6 py-3.5">
                      <StatusBadge status={order.status} />
                    </td>
                    <td className="px-6 py-3.5 text-sm text-surface-300">
                      {order.items.length} items
                    </td>
                    <td className="px-6 py-3.5 text-sm text-right font-medium text-white">
                      {formatCurrency(Number(order.total))}
                    </td>
                    <td className="px-6 py-3.5 text-sm text-right text-surface-300">
                      {new Date(order.created_at).toLocaleDateString('en-IN')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, trend, color, isDanger }: {
  icon: any; label: string; value: string; trend: string; color: string; isDanger?: boolean;
}) {
  const colorMap: Record<string, string> = {
    brand: 'text-brand-400 bg-brand-600/15',
    success: 'text-success-500 bg-success-500/15',
    warning: 'text-warning-500 bg-warning-500/15',
    danger: 'text-danger-400 bg-danger-500/15',
    info: 'text-brand-300 bg-brand-500/10',
  };

  return (
    <div className={`stat-card animate-slide-up ${isDanger ? 'border-danger-500/30' : ''}`}>
      <div className="flex items-center justify-between">
        <div className={`p-2 rounded-lg ${colorMap[color] || colorMap.brand}`}>
          <Icon className="w-4.5 h-4.5" />
        </div>
        <span className={`text-[11px] font-medium flex items-center gap-0.5 ${isDanger ? 'text-danger-400' : 'text-surface-400'}`}>
          {trend}
        </span>
      </div>
      <div className="stat-value text-xl mt-2">{value}</div>
      <div className="stat-label text-xs">{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'badge-warning',
    confirmed: 'badge-success',
    completed: 'badge-success',
    paid: 'badge-success',
    cancelled: 'badge-danger',
    failed: 'badge-danger',
    processing: 'badge-info',
  };
  return <span className={styles[status] || 'badge-info'}>{status}</span>;
}
