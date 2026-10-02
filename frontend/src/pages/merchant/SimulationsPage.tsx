import { useState } from 'react';
import { api } from '../../lib/api';
import type { SimulationResult } from '../../types';
import {
  TrendingUp,
  Percent,
  DollarSign,
  AlertCircle,
  HelpCircle,
  Play,
  RotateCcw,
  Sparkles,
  ShieldCheck,
  CheckCircle,
} from 'lucide-react';

export default function SimulationsPage() {
  const [simulationType, setSimulationType] = useState<'recovery' | 'offer'>('recovery');
  const [discountPercent, setDiscountPercent] = useState<number>(10);
  const [minCartValue, setMinCartValue] = useState<number>(3000);
  const [maxAgeDays, setMaxAgeDays] = useState<number>(7);
  const [assumedConversionRate, setAssumedConversionRate] = useState<number>(20);

  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runSimulation = async () => {
    setLoading(true);
    setError(null);
    try {
      if (simulationType === 'recovery') {
        const payload = {
          discount_percentage: Number(discountPercent),
          min_cart_value: Number(minCartValue),
          max_age_days: Number(maxAgeDays),
          assumed_conversion_rate: assumedConversionRate ? Number(assumedConversionRate) / 100 : undefined,
        };
        const res = await api.post<SimulationResult>('/simulations/recovery', payload);
        if (res.data) setResult(res.data);
      } else {
        const payload = {
          discount_percentage: Number(discountPercent),
          min_order_value: Number(minCartValue),
          estimated_traffic: 500,
          assumed_conversion_rate: assumedConversionRate ? Number(assumedConversionRate) / 100 : undefined,
        };
        const res = await api.post<SimulationResult>('/simulations/offer', payload);
        if (res.data) setResult(res.data);
      }
    } catch (err: any) {
      setError(err?.message || 'Simulation run failed.');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
            PHASE 2B WHAT-IF SIMULATOR
          </span>
          <span className="text-xs text-surface-400">Deterministic Financial Modelling</span>
        </div>
        <h1 className="text-3xl font-bold text-white mt-1">What-If Revenue Simulator</h1>
        <p className="text-surface-300 mt-0.5">
          Model discount sensitivity, recovery thresholds, and projected margin impact prior to action plan approval.
        </p>
      </div>

      {/* Prominent Disclaimer Banner */}
      <div className="p-4 rounded-xl bg-surface-900/80 border border-brand-500/30 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-brand-400 shrink-0 mt-0.5" />
        <div className="text-xs text-surface-200">
          <span className="font-bold text-brand-400 uppercase tracking-wider mr-1">
            SIMULATION / ESTIMATE ONLY:
          </span>
          Projections are calculated deterministically using store telemetry, standard margin ratios, and declared assumptions. Flowmint will NOT execute discounts or campaigns without Phase 3 merchant policy authorization.
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive Scenario Controls */}
        <div className="lg:col-span-5 space-y-5">
          <div className="card p-6 space-y-5">
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-400" />
              Scenario Configuration
            </h3>

            {/* Type selector */}
            <div>
              <label className="text-xs font-medium text-surface-300 mb-1.5 block">
                Simulation Model
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => { setSimulationType('recovery'); setResult(null); }}
                  className={`py-2 px-3 rounded-lg text-xs font-medium border text-center transition-all ${
                    simulationType === 'recovery'
                      ? 'bg-brand-600/20 border-brand-500 text-brand-400'
                      : 'bg-surface-800/60 border-surface-700 text-surface-300 hover:text-white'
                  }`}
                >
                  Cart Recovery Nudge
                </button>
                <button
                  type="button"
                  onClick={() => { setSimulationType('offer'); setResult(null); }}
                  className={`py-2 px-3 rounded-lg text-xs font-medium border text-center transition-all ${
                    simulationType === 'offer'
                      ? 'bg-brand-600/20 border-brand-500 text-brand-400'
                      : 'bg-surface-800/60 border-surface-700 text-surface-300 hover:text-white'
                  }`}
                >
                  Storewide Promo Offer
                </button>
              </div>
            </div>

            {/* Discount Slider */}
            <div>
              <div className="flex justify-between items-center text-xs mb-1">
                <span className="font-medium text-surface-300">Discount Percentage</span>
                <span className="font-bold text-brand-400 text-sm">{discountPercent}%</span>
              </div>
              <input
                type="range"
                min="1"
                max="50"
                step="1"
                value={discountPercent}
                onChange={(e) => setDiscountPercent(Number(e.target.value))}
                className="w-full accent-brand-500 bg-surface-800 rounded-lg cursor-pointer h-2"
              />
              <div className="flex justify-between text-[10px] text-surface-400 mt-1">
                <span>1% (Conservative)</span>
                <span>25%</span>
                <span>50% (Aggressive)</span>
              </div>
            </div>

            {/* Minimum Cart / Order Threshold */}
            <div>
              <label className="text-xs font-medium text-surface-300 mb-1 block">
                Minimum Cart Value Threshold (₹)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-2.5 text-xs text-surface-400">₹</span>
                <input
                  type="number"
                  min="0"
                  step="500"
                  value={minCartValue}
                  onChange={(e) => setMinCartValue(Number(e.target.value))}
                  className="input pl-7 text-sm w-full"
                  placeholder="3000"
                />
              </div>
              <p className="text-[11px] text-surface-400 mt-1">
                Only carts with value greater than or equal to this amount qualify.
              </p>
            </div>

            {/* Max Cart Age in Days */}
            {simulationType === 'recovery' && (
              <div>
                <label className="text-xs font-medium text-surface-300 mb-1 block">
                  Eligible Cart Window (Days)
                </label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={maxAgeDays}
                  onChange={(e) => setMaxAgeDays(Number(e.target.value))}
                  className="input text-sm w-full"
                />
                <p className="text-[11px] text-surface-400 mt-1">
                  Lookback limit for recently abandoned checkout sessions.
                </p>
              </div>
            )}

            {/* Assumed Conversion Rate */}
            <div>
              <div className="flex justify-between items-center text-xs mb-1">
                <span className="font-medium text-surface-300">Assumed Conversion Rate</span>
                <span className="font-bold text-white text-sm">{assumedConversionRate}%</span>
              </div>
              <input
                type="range"
                min="5"
                max="50"
                step="1"
                value={assumedConversionRate}
                onChange={(e) => setAssumedConversionRate(Number(e.target.value))}
                className="w-full accent-brand-500 bg-surface-800 rounded-lg cursor-pointer h-2"
              />
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs">
                {error}
              </div>
            )}

            {/* Run Button */}
            <button
              onClick={runSimulation}
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-2.5 text-sm"
            >
              <Play className="w-4 h-4 fill-current" />
              {loading ? 'Computing Deterministic Model...' : 'Simulate Revenue Impact'}
            </button>
          </div>
        </div>

        {/* Right Column: Financial Impact Dashboard */}
        <div className="lg:col-span-7">
          {result ? (
            <div className="card p-6 space-y-6 animate-fade-in">
              <div className="flex items-center justify-between pb-4 border-b border-surface-800">
                <div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-brand-400 bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                    OUTPUT: {result.simulation_type.toUpperCase()}
                  </span>
                  <h3 className="text-xl font-bold text-white mt-1.5">Projected Financial Impact</h3>
                </div>
                <div className="text-right">
                  <span className="text-[11px] text-surface-400">Model Confidence</span>
                  <div className="text-sm font-bold text-brand-400">
                    {(result.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              {/* Primary Projected KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                <div className="p-3.5 rounded-xl bg-surface-950/60 border border-surface-800">
                  <div className="text-xs text-surface-400">Eligible Carts</div>
                  <div className="text-2xl font-bold text-white mt-1">
                    {result.eligible_count}
                  </div>
                  <div className="text-[11px] text-surface-400 mt-0.5">
                    Pool: {formatCurrency(result.current_value)}
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-950/60 border border-surface-800">
                  <div className="text-xs text-surface-400">Projected Recovered</div>
                  <div className="text-2xl font-bold text-brand-400 mt-1">
                    {formatCurrency(result.projected_revenue)}
                  </div>
                  <div className="text-[11px] text-surface-400 mt-0.5">
                    ~{result.projected_conversions} orders converted
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-surface-950/60 border border-surface-800">
                  <div className="text-xs text-surface-400">Discount Cost</div>
                  <div className="text-2xl font-bold text-warning-400 mt-1">
                    {formatCurrency(result.discount_cost)}
                  </div>
                  <div className="text-[11px] text-surface-400 mt-0.5">
                    {discountPercent}% incentive deduction
                  </div>
                </div>
              </div>

              {/* Net Margin Impact Highlight */}
              <div className="p-4 rounded-xl bg-gradient-to-r from-success-500/10 via-surface-900 to-surface-900 border border-success-500/30">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wider text-success-400">
                      Net Projected Margin Impact
                    </div>
                    <div className="text-xs text-surface-300 mt-0.5">
                      Incremental contribution margin after deduction of discount incentive cost.
                    </div>
                  </div>
                  <div className="text-2xl font-bold text-success-400">
                    {formatCurrency(result.projected_margin_impact)}
                  </div>
                </div>
              </div>

              {/* Assumptions Table */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5 text-brand-400" />
                  Model Assumptions & Parameters
                </h4>
                <div className="p-3 rounded-xl bg-surface-950/80 border border-surface-800">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(result.assumptions).map(([key, val]) => (
                      <div key={key} className="flex justify-between border-b border-surface-800/60 pb-1">
                        <span className="text-surface-400 capitalize">{key.replace(/_/g, ' ')}:</span>
                        <span className="font-mono text-white">
                          {typeof val === 'number' ? (val < 1 ? `${(val * 100).toFixed(0)}%` : val) : String(val)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Explicit Disclaimer */}
              <div className="p-3 rounded-lg bg-surface-950 border border-surface-800 text-[11px] text-surface-400 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-warning-400 shrink-0 mt-0.5" />
                <span>{result.disclaimer}</span>
              </div>
            </div>
          ) : (
            <div className="card p-12 text-center text-surface-300 space-y-4">
              <div className="w-12 h-12 rounded-xl bg-brand-500/10 text-brand-400 flex items-center justify-center mx-auto border border-brand-500/20">
                <TrendingUp className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-white">No Active Simulation</h3>
              <p className="text-xs text-surface-400 max-w-md mx-auto">
                Configure scenario parameters on the left and click "Simulate Revenue Impact" to run a deterministic financial projection.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
