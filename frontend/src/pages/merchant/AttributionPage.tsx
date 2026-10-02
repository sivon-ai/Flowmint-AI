import { useState, useEffect } from 'react';
import {
  TrendingUp,
  DollarSign,
  ArrowRight,
  ShieldAlert,
  Percent,
  RefreshCw,
  GitBranch,
} from 'lucide-react';
import { api } from '../../lib/api';
import { Link } from 'react-router-dom';

interface ActionOutcome {
  id: string;
  action_id: string;
  execution_id: string | null;
  campaign_id: string | null;
  trace_id: string | null;
  label: 'SIMULATED' | 'ESTIMATED' | 'OBSERVED' | 'ATTRIBUTED';
  attribution_method: string;
  confidence: number;
  baseline_period: Record<string, unknown>;
  observation_period: Record<string, unknown>;
  affected_entities: Record<string, unknown>;
  orders_attributed: number;
  gross_revenue: number;
  discount_cost: number;
  operational_cost: number;
  net_revenue_impact: number;
  created_at: string;
}

interface BeforeVsAfterReport {
  campaign_name: string;
  action_id: string;
  trace_id: string | null;
  baseline_window: string;
  observation_window: string;
  eligible_entities_count: number;
  actual_conversions_count: number;
  conversion_rate: number;
  observed_gross_revenue: number;
  discount_cost: number;
  operational_cost: number;
  observed_net_revenue_impact: number;
  label: string;
  attribution_method: string;
  confidence: number;
}

export default function AttributionPage() {
  const [outcomes, setOutcomes] = useState<ActionOutcome[]>([]);
  const [report, setReport] = useState<BeforeVsAfterReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [outcomesRes, reportRes] = await Promise.all([
        api.get<ActionOutcome[]>('/attribution/outcomes'),
        api.get<BeforeVsAfterReport>('/attribution/before-vs-after'),
      ]);
      if (outcomesRes.data) setOutcomes(outcomesRes.data);
      if (reportRes.data) setReport(reportRes.data);
    } catch (err) {
      setError('Failed to load revenue attribution data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getLabelBadge = (label: string) => {
    switch (label) {
      case 'OBSERVED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
            OBSERVED
          </span>
        );
      case 'ATTRIBUTED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
            ATTRIBUTED
          </span>
        );
      case 'ESTIMATED':
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
            ESTIMATED
          </span>
        );
      case 'SIMULATED':
      default:
        return (
          <span className="px-2.5 py-1 text-xs font-bold rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
            SIMULATED
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Revenue Attribution</h1>
          <p className="text-sm text-surface-300 mt-1">
            Deterministic accounting separating pre-action estimates from actual recovered revenue.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-800 hover:bg-surface-700 text-white rounded-lg border border-surface-600 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Metrics
        </button>
      </div>

      {/* Label Hierarchy Notice */}
      <div className="p-4 bg-surface-900/60 border border-surface-700/60 rounded-xl flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 text-brand-400 mt-0.5 shrink-0" />
        <div className="text-xs text-surface-300 space-y-1">
          <span className="font-semibold text-white">Strict Label Hierarchy: </span>
          <span className="text-emerald-400 font-bold">OBSERVED</span> represents real post-execution customer transactions.
          {' '}<span className="text-purple-400 font-bold">SIMULATED</span> and <span className="text-amber-400 font-bold">ESTIMATED</span> represent projected ranges and are never labeled as actual bankable revenue.
        </div>
      </div>

      {/* Before vs After Canonical Card */}
      {report && (
        <div className="p-6 bg-surface-900 border border-brand-500/30 rounded-2xl relative overflow-hidden shadow-2xl">
          <div className="flex items-center justify-between border-b border-surface-800 pb-4 mb-6">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-bold tracking-widest uppercase text-brand-400">
                  Canonical Benchmark Report
                </span>
                {getLabelBadge(report.label)}
              </div>
              <h2 className="text-xl font-bold text-white mt-1">{report.campaign_name}</h2>
            </div>
            {report.trace_id && (
              <Link
                to={`/traces?id=${report.trace_id}`}
                className="flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-lg bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 border border-brand-500/30 transition"
              >
                <GitBranch className="w-4 h-4" />
                View Full Trace
              </Link>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="p-4 rounded-xl bg-surface-950/60 border border-surface-800">
              <div className="text-xs text-surface-400 font-medium">Eligible Carts</div>
              <div className="text-2xl font-bold text-white mt-1">
                {report.eligible_entities_count}
              </div>
              <div className="text-[11px] text-surface-400 mt-1 flex items-center gap-1">
                Baseline: Abandoned checkouts
              </div>
            </div>

            <div className="p-4 rounded-xl bg-surface-950/60 border border-surface-800">
              <div className="text-xs text-surface-400 font-medium">Actual Recoveries</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {report.actual_conversions_count}
              </div>
              <div className="text-[11px] text-emerald-400/80 mt-1">
                {(report.conversion_rate * 100).toFixed(1)}% recovery rate
              </div>
            </div>

            <div className="p-4 rounded-xl bg-surface-950/60 border border-surface-800">
              <div className="text-xs text-surface-400 font-medium">Gross Recovered</div>
              <div className="text-2xl font-bold text-white mt-1">
                ₹{report.observed_gross_revenue.toLocaleString('en-IN')}
              </div>
              <div className="text-[11px] text-surface-400 mt-1">
                Discount cost: -₹{report.discount_cost.toLocaleString('en-IN')}
              </div>
            </div>

            <div className="p-4 rounded-xl bg-brand-950/40 border border-brand-500/40">
              <div className="text-xs text-brand-300 font-semibold uppercase tracking-wider">
                Net Revenue Impact
              </div>
              <div className="text-2xl font-extrabold text-brand-400 mt-1">
                ₹{report.observed_net_revenue_impact.toLocaleString('en-IN')}
              </div>
              <div className="text-[11px] text-brand-300/80 mt-1">
                Method: {report.attribution_method} ({(report.confidence * 100).toFixed(0)}% conf)
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Historical Outcomes List */}
      <div className="bg-surface-900 border border-surface-800 rounded-xl overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-surface-800 flex items-center justify-between">
          <h3 className="text-base font-semibold text-white">Attributed Action Outcomes</h3>
          <span className="text-xs text-surface-400">{outcomes.length} recorded events</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-surface-400 animate-pulse">
            Loading attribution ledger...
          </div>
        ) : error ? (
          <div className="p-12 text-center text-red-400">{error}</div>
        ) : outcomes.length === 0 ? (
          <div className="p-12 text-center text-surface-400">
            No executed actions with recorded outcomes yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-surface-800 text-surface-400 text-xs font-semibold uppercase tracking-wider bg-surface-950/40">
                  <th className="py-3.5 px-6">Classification</th>
                  <th className="py-3.5 px-6">Action / Trace</th>
                  <th className="py-3.5 px-6">Conversions</th>
                  <th className="py-3.5 px-6">Gross Revenue</th>
                  <th className="py-3.5 px-6">Discounts</th>
                  <th className="py-3.5 px-6">Net Impact</th>
                  <th className="py-3.5 px-6">Method</th>
                  <th className="py-3.5 px-6 text-right">Trace</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60">
                {outcomes.map(item => (
                  <tr key={item.id} className="hover:bg-surface-800/40 transition">
                    <td className="py-4 px-6">{getLabelBadge(item.label)}</td>
                    <td className="py-4 px-6 font-mono text-xs text-surface-300">
                      <div>{item.action_id.slice(0, 12)}...</div>
                      {item.trace_id && (
                        <div className="text-[11px] text-surface-500">{item.trace_id.slice(0, 16)}...</div>
                      )}
                    </td>
                    <td className="py-4 px-6 font-semibold text-white">
                      {item.orders_attributed} orders
                    </td>
                    <td className="py-4 px-6 text-white font-medium">
                      ₹{item.gross_revenue.toLocaleString('en-IN')}
                    </td>
                    <td className="py-4 px-6 text-red-400 font-medium">
                      -₹{item.discount_cost.toLocaleString('en-IN')}
                    </td>
                    <td className="py-4 px-6 font-bold text-emerald-400">
                      +₹{item.net_revenue_impact.toLocaleString('en-IN')}
                    </td>
                    <td className="py-4 px-6 text-xs text-surface-400">
                      {item.attribution_method}
                    </td>
                    <td className="py-4 px-6 text-right">
                      {item.trace_id ? (
                        <Link
                          to={`/traces?id=${item.trace_id}`}
                          className="inline-flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 font-medium"
                        >
                          View <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      ) : (
                        <span className="text-xs text-surface-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
