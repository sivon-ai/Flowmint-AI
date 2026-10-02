import { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { api } from '../../lib/api';
import type { Opportunity, ActionPlan } from '../../types';
import {
  Zap,
  Filter,
  CheckCircle2,
  Clock,
  TrendingUp,
  AlertCircle,
  HelpCircle,
  Sparkles,
  ArrowRight,
  ShieldAlert,
  Info,
  Layers,
} from 'lucide-react';

export default function OpportunitiesPage() {
  const [searchParams] = useSearchParams();
  const selectedIdFromUrl = searchParams.get('id');

  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selectedOpp, setSelectedOpp] = useState<Opportunity | null>(null);
  const [actionPlan, setActionPlan] = useState<ActionPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    fetchOpportunities();
  }, []);

  const fetchOpportunities = async () => {
    setLoading(true);
    try {
      const res = await api.get<Opportunity[]>('/opportunities');
      const list = res.data || [];
      setOpportunities(list);

      if (selectedIdFromUrl) {
        const found = list.find((o) => o.id === selectedIdFromUrl);
        if (found) setSelectedOpp(found);
      } else if (list.length > 0 && !selectedOpp) {
        setSelectedOpp(list[0]);
      }
    } catch (err) {
      console.error('Failed to load opportunities:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedOpp) {
      // Fetch associated action plan if any
      api.get<ActionPlan[]>(`/action-plans?opportunity_id=${selectedOpp.id}`)
        .then((res) => {
          if (res.data && res.data.length > 0) {
            setActionPlan(res.data[0]);
          } else {
            setActionPlan(null);
          }
        })
        .catch(() => setActionPlan(null));
    }
  }, [selectedOpp]);

  const handleInvestigate = async (oppId: string) => {
    setInvestigating(true);
    try {
      const res = await api.post<{ opportunity: Opportunity; action_plan?: ActionPlan }>(
        `/opportunities/${oppId}/investigate`
      );
      if (res.data) {
        setSelectedOpp(res.data.opportunity);
        if (res.data.action_plan) {
          setActionPlan(res.data.action_plan);
        }
        // Update list
        setOpportunities((prev) =>
          prev.map((o) => (o.id === oppId ? res.data!.opportunity : o))
        );
      }
    } catch (err) {
      console.error('Investigation failed:', err);
    } finally {
      setInvestigating(false);
    }
  };

  const filteredOpportunities = opportunities.filter((o) => {
    if (typeFilter !== 'all' && o.type !== typeFilter) return false;
    if (statusFilter !== 'all' && o.status !== statusFilter) return false;
    return true;
  });

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
              PHASE 2B DECISION LAYER
            </span>
            <span className="text-xs text-surface-400">Recommendation-Only Engine</span>
          </div>
          <h1 className="text-3xl font-bold text-white mt-1">Revenue Opportunities</h1>
          <p className="text-surface-300 mt-0.5">
            Real-time revenue leakages and proactive growth possibilities detected by Flowmint AI.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link to="/simulations" className="btn-secondary text-sm flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4 text-brand-400" />
            What-If Simulator
          </Link>
        </div>
      </div>

      {/* Safety Notice */}
      <div className="p-4 rounded-xl bg-surface-900/60 border border-surface-700/60 flex items-start gap-3 text-xs text-surface-300">
        <ShieldAlert className="w-5 h-5 text-brand-400 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-white">Bounded Autonomy Safety Guarantee: </span>
          All recommendations and action plans in Phase 2B are strictly non-mutating proposals. No discounts, prices, customer communications, or inventory changes are executed autonomously.
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-surface-900/40 p-3 rounded-xl border border-surface-800">
        <div className="flex items-center gap-2 text-xs text-surface-400 mr-2">
          <Filter className="w-3.5 h-3.5" /> Filters:
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="bg-surface-800 text-white text-xs rounded-lg px-3 py-1.5 border border-surface-700 focus:outline-none focus:border-brand-500"
        >
          <option value="all">All Opportunity Types</option>
          <option value="abandoned_cart">Abandoned Cart</option>
          <option value="payment_failure">Payment Failure</option>
          <option value="conversion_drop">Conversion Drop</option>
          <option value="cross_sell">Cross-Sell & Bundle</option>
          <option value="low_inventory">Low Inventory</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-surface-800 text-white text-xs rounded-lg px-3 py-1.5 border border-surface-700 focus:outline-none focus:border-brand-500"
        >
          <option value="all">All Statuses</option>
          <option value="detected">Detected</option>
          <option value="investigating">Investigating</option>
          <option value="proposed">Proposed</option>
          <option value="ready_for_review">Ready For Review</option>
          <option value="resolved">Resolved</option>
        </select>

        <div className="ml-auto text-xs text-surface-400">
          Showing {filteredOpportunities.length} of {opportunities.length} opportunities
        </div>
      </div>

      {/* Main Content: Split Master-Detail Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Opportunity List */}
        <div className="lg:col-span-5 space-y-3">
          {loading ? (
            <div className="card p-8 text-center text-surface-300">Scanning commerce data...</div>
          ) : filteredOpportunities.length === 0 ? (
            <div className="card p-8 text-center text-surface-300">
              No opportunities match the selected criteria.
            </div>
          ) : (
            filteredOpportunities.map((opp) => {
              const isSelected = selectedOpp?.id === opp.id;
              return (
                <div
                  key={opp.id}
                  onClick={() => setSelectedOpp(opp)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-surface-900 border-brand-500 shadow-lg shadow-brand-500/10'
                      : 'bg-surface-900/60 border-surface-800 hover:border-surface-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-800 text-brand-400 border border-surface-700">
                      {opp.type.replace('_', ' ')}
                    </span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase ${
                        opp.priority === 'critical'
                          ? 'bg-danger-500/20 text-danger-400'
                          : opp.priority === 'high'
                          ? 'bg-warning-500/20 text-warning-400'
                          : 'bg-surface-800 text-surface-300'
                      }`}
                    >
                      {opp.priority}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-white mt-2">{opp.title}</h3>
                  <p className="text-xs text-surface-300 mt-1 line-clamp-2">{opp.description}</p>

                  <div className="mt-3 pt-2.5 border-t border-surface-800 flex items-center justify-between text-xs">
                    <div>
                      <span className="text-surface-400">Potential: </span>
                      <span className="text-white font-semibold">{formatCurrency(opp.estimated_value)}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-surface-400 text-[11px]">
                      <Clock className="w-3 h-3" />
                      <span>{new Date(opp.detected_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Opportunity Detail Inspector */}
        <div className="lg:col-span-7">
          {selectedOpp ? (
            <div className="card p-6 space-y-6 sticky top-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-800">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-brand-500/20 text-brand-400 border border-brand-500/30">
                      {selectedOpp.type.replace('_', ' ')}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-surface-800 text-surface-300 border border-surface-700">
                      Status: {selectedOpp.status}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-white mt-2">{selectedOpp.title}</h2>
                  <p className="text-xs text-surface-300 mt-1">{selectedOpp.description}</p>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-xs text-surface-400">Estimated Value</div>
                  <div className="text-2xl font-bold text-white">
                    {formatCurrency(selectedOpp.estimated_value)}
                  </div>
                  <div className="text-[11px] text-brand-400 font-medium">
                    Confidence: {(selectedOpp.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* WHY DETECTED */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                  <HelpCircle className="w-3.5 h-3.5 text-brand-400" />
                  Why Was This Detected?
                </h4>
                <div className="p-3.5 rounded-xl bg-surface-950/60 border border-surface-800 text-xs text-surface-200 leading-relaxed">
                  {selectedOpp.evidence_json?.metric
                    ? `Detector flagged metric "${selectedOpp.evidence_json.metric}" with value ${
                        typeof selectedOpp.evidence_json.value === 'number'
                          ? formatCurrency(selectedOpp.evidence_json.value)
                          : selectedOpp.evidence_json.value
                      } over the ${selectedOpp.evidence_json.period || 'current'} period.`
                    : 'Deterministic engine detected anomalies against store baseline metrics.'}
                </div>
              </div>

              {/* REVENUE EVIDENCE (Inspectable) */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                  <Info className="w-3.5 h-3.5 text-brand-400" />
                  Inspectable Evidence
                </h4>
                <div className="p-3 rounded-xl bg-surface-950/80 border border-surface-800 font-mono text-[11px] text-surface-300 overflow-x-auto">
                  <pre>{JSON.stringify(selectedOpp.evidence_json, null, 2)}</pre>
                </div>
              </div>

              {/* AFFECTED ENTITIES */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider flex items-center gap-1.5 mb-2">
                  <Layers className="w-3.5 h-3.5 text-brand-400" />
                  Affected Entities ({selectedOpp.affected_entity_type})
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {selectedOpp.affected_entity_ids.map((id) => (
                    <span
                      key={id}
                      className="px-2 py-1 rounded bg-surface-950 border border-surface-800 text-[11px] font-mono text-surface-300"
                    >
                      {id.substring(0, 8)}...
                    </span>
                  ))}
                </div>
              </div>

              {/* RECOMMENDED ACTION */}
              <div className="p-4 rounded-xl bg-gradient-to-r from-brand-950/50 via-surface-900 to-surface-900 border border-brand-500/30">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-brand-500/20 rounded-lg shrink-0 mt-0.5">
                    <Sparkles className="w-4 h-4 text-brand-400" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-brand-400 uppercase tracking-wider">
                      Recommended Revenue Strategy
                    </h4>
                    <p className="text-sm font-medium text-white mt-1">
                      {selectedOpp.recommended_action}
                    </p>
                  </div>
                </div>
              </div>

              {/* ACTION PLAN DISPLAY (if investigated/proposed) */}
              {actionPlan ? (
                <div className="p-4 rounded-xl bg-surface-950 border border-brand-500/40 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-brand-400" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        Formulated Action Plan
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
                      STATUS: {actionPlan.status.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-surface-400">Action ID: </span>
                      <span className="font-mono text-white">{actionPlan.action_id}</span>
                    </div>
                    <div>
                      <span className="text-surface-400">Type: </span>
                      <span className="font-semibold text-white">{actionPlan.action_type}</span>
                    </div>
                    <div>
                      <span className="text-surface-400">Requires Approval: </span>
                      <span className="text-warning-400 font-semibold">
                        {actionPlan.requires_approval ? 'YES (Phase 3)' : 'NO'}
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-400">Risk Level: </span>
                      <span className="text-surface-200 capitalize">{actionPlan.risk_level}</span>
                    </div>
                  </div>

                  <div className="text-xs text-surface-300 bg-surface-900 p-2.5 rounded-lg border border-surface-800">
                    <span className="font-semibold text-white">Rationale: </span>
                    {actionPlan.recommendation_reason}
                  </div>
                </div>
              ) : null}

              {/* ACTION BUTTONS */}
              <div className="pt-2 flex flex-wrap items-center gap-3">
                <button
                  onClick={() => handleInvestigate(selectedOpp.id)}
                  disabled={investigating}
                  className="btn-primary flex items-center gap-2 text-xs py-2 px-4"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  {investigating ? 'Investigating with AI...' : 'Investigate with AI'}
                </button>

                <Link
                  to={`/simulations?type=${
                    selectedOpp.type === 'abandoned_cart' ? 'recovery' : 'offer'
                  }&threshold=${selectedOpp.estimated_value}`}
                  className="btn-secondary flex items-center gap-1.5 text-xs py-2 px-4"
                >
                  <TrendingUp className="w-3.5 h-3.5 text-brand-400" />
                  Simulate Strategy
                  <ArrowRight className="w-3 h-3 ml-1" />
                </Link>
              </div>
            </div>
          ) : (
            <div className="card p-12 text-center text-surface-400">
              Select an opportunity from the list to inspect its evidence and formulated action plan.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
