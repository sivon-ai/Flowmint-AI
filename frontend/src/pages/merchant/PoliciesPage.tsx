import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import type { MerchantPolicy, PolicyEvaluationResult } from '../../types';
import {
  ShieldCheck,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Sliders,
  Settings2,
  Save,
  HelpCircle,
} from 'lucide-react';

export default function PoliciesPage() {
  const [policy, setPolicy] = useState<MerchantPolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Policy Simulator State
  const [simActionType, setSimActionType] = useState<string>('cross_sell_bundle');
  const [simDiscount, setSimDiscount] = useState<number>(10);
  const [simBudget, setSimBudget] = useState<number>(5000);
  const [simAgent, setSimAgent] = useState<string>('growth_agent');
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState<PolicyEvaluationResult | null>(null);

  useEffect(() => {
    fetchPolicy();
  }, []);

  const fetchPolicy = async () => {
    setLoading(true);
    try {
      const res = await api.get<MerchantPolicy>('/policies');
      if (res.data) setPolicy(res.data);
    } catch (err) {
      console.error('Failed to load merchant policy:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSavePolicy = async () => {
    if (!policy) return;
    setSaving(true);
    setSaveSuccess(false);
    try {
      const res = await api.put<MerchantPolicy>('/policies', {
        max_discount_percentage: Number(policy.max_discount_percentage),
        max_campaign_budget: Number(policy.max_campaign_budget),
        high_value_threshold: Number(policy.high_value_threshold),
        contact_cooldown_hours: Number(policy.contact_cooldown_hours),
        require_approval_all_actions: Boolean(policy.require_approval_all_actions),
      });
      if (res.data) {
        setPolicy(res.data);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      console.error('Failed to save policy updates:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleRunSimulator = async () => {
    setSimulating(true);
    try {
      const payload = {
        action_type: simActionType,
        target: 'test_simulation_target',
        parameters: {
          discount_percentage: Number(simDiscount),
          budget: Number(simBudget),
        },
        agent_name: simAgent,
      };
      const res = await api.post<PolicyEvaluationResult>('/policies/evaluate', payload);
      if (res.data) setSimResult(res.data);
    } catch (err) {
      console.error('Policy simulation failed:', err);
    } finally {
      setSimulating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
            PHASE 3 POLICY ENGINE
          </span>
          <span className="text-xs text-surface-400">Deterministic Guardrails & Autonomy Limits</span>
        </div>
        <h1 className="text-3xl font-bold text-white mt-1">Policy & Guardrails</h1>
        <p className="text-surface-300 mt-0.5">
          Configure merchant autonomy bounds and test why actions are allowed or blocked using the simulator.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Interactive Policy Simulator */}
        <div className="lg:col-span-6 space-y-6">
          <div className="card p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-surface-800">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-brand-400" />
                <h3 className="text-base font-semibold text-white">Policy Simulator</h3>
              </div>
              <span className="text-[11px] text-surface-400 bg-surface-800 px-2 py-0.5 rounded">
                Read-Only Testing
              </span>
            </div>

            <p className="text-xs text-surface-300">
              Test an ActionPlan proposal against all 9 deterministic policy rules. Inspect why an action is allowed or blocked before agents propose it.
            </p>

            <div className="space-y-4">
              <div>
                <label className="text-xs font-medium text-surface-300 block mb-1">Proposing Agent</label>
                <select
                  value={simAgent}
                  onChange={(e) => setSimAgent(e.target.value)}
                  className="input text-xs w-full"
                >
                  <option value="growth_agent">Growth Agent</option>
                  <option value="recovery_agent">Recovery Agent</option>
                  <option value="analytics_agent">Analytics Agent (Read-Only)</option>
                  <option value="buyer_agent">Buyer Agent (Read-Only)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-medium text-surface-300 block mb-1">Action Type</label>
                <select
                  value={simActionType}
                  onChange={(e) => setSimActionType(e.target.value)}
                  className="input text-xs w-full"
                >
                  <option value="cross_sell_bundle">Cross-Sell Bundle Deal</option>
                  <option value="promotional_offer">Promotional Discount Offer</option>
                  <option value="abandoned_cart_recovery">Abandoned Cart Recovery</option>
                  <option value="payment_retry_nudge">Payment Retry Nudge</option>
                </select>
              </div>

              <div>
                <div className="flex justify-between items-center text-xs mb-1">
                  <span className="font-medium text-surface-300">Proposed Discount Percentage</span>
                  <span className="font-bold text-brand-400 text-sm">{simDiscount}%</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="40"
                  value={simDiscount}
                  onChange={(e) => setSimDiscount(Number(e.target.value))}
                  className="w-full accent-brand-500 bg-surface-800 rounded-lg cursor-pointer h-2"
                />
              </div>

              <div>
                <label className="text-xs font-medium text-surface-300 block mb-1">Proposed Campaign Budget (₹)</label>
                <input
                  type="number"
                  min="0"
                  step="1000"
                  value={simBudget}
                  onChange={(e) => setSimBudget(Number(e.target.value))}
                  className="input text-xs w-full"
                />
              </div>

              <button
                type="button"
                onClick={handleRunSimulator}
                disabled={simulating}
                className="btn-primary w-full flex items-center justify-center gap-2 py-2 text-xs"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                {simulating ? 'Evaluating Policy Engine...' : 'Evaluate Against Policy Rules'}
              </button>
            </div>

            {/* Simulator Results */}
            {simResult && (
              <div className="pt-4 border-t border-surface-800 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-surface-400">
                    Evaluation Verdict
                  </span>
                  <span
                    className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase ${
                      simResult.allowed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-danger-500/20 text-danger-400'
                    }`}
                  >
                    {simResult.allowed ? 'ALLOWED' : 'BLOCKED'}
                  </span>
                </div>

                <div className="p-3 rounded-lg bg-surface-950 border border-surface-800 text-xs">
                  <div className="text-surface-300 font-medium">{simResult.reasons.join(' ')}</div>
                  <div className="mt-2 text-[11px] text-surface-400 flex justify-between">
                    <span>Classified Risk: <strong className="text-white uppercase">{simResult.risk_level}</strong></span>
                    <span>Approval Required: <strong className="text-warning-400">{simResult.requires_approval ? 'YES' : 'NO'}</strong></span>
                  </div>
                </div>

                {/* Individual Rule Breakdown */}
                <div className="space-y-1.5">
                  <span className="text-[11px] font-bold uppercase text-surface-400">Individual Rule Checks</span>
                  {simResult.rule_results.map((r) => (
                    <div
                      key={r.rule}
                      className="p-2 rounded bg-surface-950/60 border border-surface-800 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {r.passed ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-danger-400 shrink-0" />
                        )}
                        <span className="capitalize text-white">{r.rule.replace(/_/g, ' ')}</span>
                      </div>
                      <span className="text-[11px] text-surface-400 truncate max-w-[200px]">{r.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Policy Configuration Settings */}
        <div className="lg:col-span-6 space-y-6">
          <div className="card p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-surface-800">
              <div className="flex items-center gap-2">
                <Settings2 className="w-5 h-5 text-brand-400" />
                <h3 className="text-base font-semibold text-white">Merchant Autonomy Bounds</h3>
              </div>
              <span className="text-[11px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Active Enforcing
              </span>
            </div>

            {loading || !policy ? (
              <div className="p-8 text-center text-surface-400 text-xs">Loading policy rules...</div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-surface-300 block mb-1">
                    Maximum Allowed Discount (%)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={policy.max_discount_percentage}
                    onChange={(e) =>
                      setPolicy({ ...policy, max_discount_percentage: Number(e.target.value) })
                    }
                    className="input text-xs w-full"
                  />
                  <p className="text-[11px] text-surface-400 mt-1">
                    Any proposal exceeding this discount will be strictly blocked by the Policy Engine.
                  </p>
                </div>

                <div>
                  <label className="text-xs font-medium text-surface-300 block mb-1">
                    Maximum Campaign Budget Cap (₹)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="5000"
                    value={policy.max_campaign_budget}
                    onChange={(e) =>
                      setPolicy({ ...policy, max_campaign_budget: Number(e.target.value) })
                    }
                    className="input text-xs w-full"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-surface-300 block mb-1">
                    High-Value Action Threshold (₹)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="5000"
                    value={policy.high_value_threshold}
                    onChange={(e) =>
                      setPolicy({ ...policy, high_value_threshold: Number(e.target.value) })
                    }
                    className="input text-xs w-full"
                  />
                  <p className="text-[11px] text-surface-400 mt-1">
                    Proposals involving revenue above this threshold strictly mandate human merchant approval.
                  </p>
                </div>

                <div>
                  <label className="text-xs font-medium text-surface-300 block mb-1">
                    Customer Contact Cooldown Window (Hours)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="168"
                    value={policy.contact_cooldown_hours}
                    onChange={(e) =>
                      setPolicy({ ...policy, contact_cooldown_hours: Number(e.target.value) })
                    }
                    className="input text-xs w-full"
                  />
                </div>

                <div className="p-3.5 rounded-xl bg-surface-950/70 border border-surface-800 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-white">Require Approval For All Actions</div>
                    <div className="text-[11px] text-surface-400">
                      When enabled, zero autonomous executions occur without explicit human approval.
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={policy.require_approval_all_actions}
                    onChange={(e) =>
                      setPolicy({ ...policy, require_approval_all_actions: e.target.checked })
                    }
                    className="w-4 h-4 accent-brand-500 rounded cursor-pointer"
                  />
                </div>

                {saveSuccess && (
                  <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs">
                    Policy constraints updated and saved successfully!
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleSavePolicy}
                  disabled={saving}
                  className="btn-primary w-full flex items-center justify-center gap-2 py-2 text-xs"
                >
                  <Save className="w-3.5 h-3.5" />
                  {saving ? 'Saving...' : 'Save Policy Configuration'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
