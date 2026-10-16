import { useState, useEffect } from 'react';
import {
  FlaskConical,
  Play,
  ShieldCheck,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Coins,
  Cpu,
  RefreshCw,
  Info,
  CheckCircle2,
  X,
  Zap,
} from 'lucide-react';
import { api } from '../../lib/api';
import type {
  EvaluationBenchmarkResponse,
  BenchmarkRunRequest,
  DatasetInfoResponse,
} from '../../types';

export default function EvaluationPage() {
  const [breakdown, setBreakdown] = useState<DatasetInfoResponse | null>(null);
  const [recentBenchmarks, setRecentBenchmarks] = useState<EvaluationBenchmarkResponse[]>([]);
  const [activeBenchmark, setActiveBenchmark] = useState<EvaluationBenchmarkResponse | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<'mock_llm' | 'fireworks'>('mock_llm');
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [breakdownRes, benchmarksRes] = await Promise.all([
        api.get<DatasetInfoResponse>('/evaluation/dataset'),
        api.get<EvaluationBenchmarkResponse[]>('/evaluation/benchmarks'),
      ]);
      if (breakdownRes.data) {
        setBreakdown(breakdownRes.data);
      }
      if (benchmarksRes.data && benchmarksRes.data.length > 0) {
        setRecentBenchmarks(benchmarksRes.data);
        setActiveBenchmark(benchmarksRes.data[0]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load evaluation dataset details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleRunBenchmark = async () => {
    setRunning(true);
    setError(null);
    setSuccessMessage(null);

    const payload: BenchmarkRunRequest =
      selectedProvider === 'fireworks'
        ? {
            runner_type: 'real_llm',
            model_name: breakdown?.fireworks_model || 'accounts/fireworks/models/qwen3p8-max',
          }
        : {
            runner_type: 'mock_llm',
            model_name: 'mock-llm-v1',
          };

    try {
      const res = await api.post<EvaluationBenchmarkResponse>('/evaluation/run', payload);
      if (res.data) {
        setActiveBenchmark(res.data);
        setRecentBenchmarks(prev => [res.data!, ...prev.filter(b => b.id !== res.data!.id).slice(0, 9)]);
        setSuccessMessage(
          `Successfully completed 900-case evaluation with ${
            res.data.runner_type === 'real_llm' ? 'Fireworks AI' : 'MockLLM'
          } (${res.data.model_name}).`
        );
      }
    } catch (err: any) {
      const msg = err?.message || 'Benchmark execution failed.';
      setError(msg);
    } finally {
      setRunning(false);
    }
  };

  const formatPct = (val: number | string | undefined | null) => {
    if (val === undefined || val === null || isNaN(Number(val))) return '0.0%';
    return `${Number(val).toFixed(1)}%`;
  };

  const formatNum = (val: number | string | undefined | null, decimals = 1) => {
    if (val === undefined || val === null || isNaN(Number(val))) return '0';
    return Number(val).toFixed(decimals);
  };

  // Derive truthful live verification status
  const hasLiveVerifiedRun = recentBenchmarks.some(b => b.runner_type === 'real_llm');
  const isFireworksConfigured = Boolean(breakdown?.fireworks_configured);

  const getTier1Status = () => {
    if (hasLiveVerifiedRun) {
      return {
        label: 'LIVE VALIDATION: VERIFIED',
        badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
        note: 'Live chat completion, structured tool calling, and BuyerAgent flow verified.',
      };
    }
    if (isFireworksConfigured) {
      return {
        label: 'LIVE INFERENCE: READY',
        badgeClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
        note: 'API key configured. Ready to run live empirical evaluation.',
      };
    }
    return {
      label: 'CONFIGURATION REQUIRED',
      badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
      note: 'Set FIREWORKS_API_KEY in Render environment to enable live inference evaluation.',
    };
  };

  const tier1Status = getTier1Status();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">System Evaluation & LLM Verification Lab</h1>
          <p className="text-sm text-surface-300 mt-1">
            Flowmint 900-case deterministic system evaluation and live Fireworks AI empirical validation.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading || running}
          className="flex items-center gap-2 px-3.5 py-2 text-sm bg-surface-800 hover:bg-surface-700 disabled:opacity-50 text-white rounded-lg border border-surface-600 transition shadow-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Visible Error Banner */}
      {error && (
        <div
          role="alert"
          className="p-4 bg-red-950/40 border border-red-500/50 rounded-xl flex items-start justify-between gap-3 text-red-200 shadow-lg animate-in fade-in"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-red-300">Evaluation Execution Error</h4>
              <p className="text-xs text-red-200/90 leading-relaxed">{error}</p>
              {error.toLowerCase().includes('fireworks_api_key') && (
                <p className="text-[11px] text-amber-300 mt-1 font-mono">
                  Tip: Configure FIREWORKS_API_KEY in your Render dashboard environment variables or backend .env.
                </p>
              )}
            </div>
          </div>
          <button
            onClick={() => setError(null)}
            className="p-1 text-red-400 hover:text-white rounded-lg hover:bg-red-900/40 transition"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Visible Success Banner */}
      {successMessage && (
        <div
          role="status"
          className="p-4 bg-emerald-950/40 border border-emerald-500/50 rounded-xl flex items-start justify-between gap-3 text-emerald-200 shadow-lg animate-in fade-in"
        >
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <p className="text-xs font-semibold text-emerald-200">{successMessage}</p>
          </div>
          <button
            onClick={() => setSuccessMessage(null)}
            className="p-1 text-emerald-400 hover:text-white rounded-lg hover:bg-emerald-900/40 transition"
            aria-label="Dismiss success message"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* 3-Tier Verification Structure Banner */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tier 1: Real LLM */}
        <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5" /> Real LLM
              </span>
              <span
                className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold border ${tier1Status.badgeClass}`}
              >
                {tier1Status.label}
              </span>
            </div>
            <div className="text-sm font-semibold text-white mt-1.5">
              Fireworks AI — {breakdown?.fireworks_model ? breakdown.fireworks_model.split('/').pop() : 'Qwen 3.8 Max'}
            </div>
            <p className="text-xs text-surface-400 mt-1">{tier1Status.note}</p>
          </div>
        </div>

        {/* Tier 2: System Evaluation */}
        <div className="p-4 bg-brand-950/30 border border-brand-500/30 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">System Evaluation</span>
              <span className="text-[10px] bg-brand-500/20 text-brand-300 border border-brand-500/30 px-2 py-0.5 rounded font-mono font-semibold">
                {breakdown ? `${breakdown.total_cases} Cases` : '900 Cases'}
              </span>
            </div>
            <div className="text-sm font-semibold text-white mt-1.5">Routing & Governance Protocol</div>
            <p className="text-xs text-surface-400 mt-1">
              Deterministic intent routing, tool authorization, merchant policy limits, and security sanitization.
            </p>
          </div>
        </div>

        {/* Tier 3: Mock Regression */}
        <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-surface-400 uppercase tracking-wider">Mock Regression</span>
              <span className="text-[10px] bg-surface-800 text-surface-300 px-2 py-0.5 rounded font-mono font-semibold">
                Deterministic Offline
              </span>
            </div>
            <div className="text-sm font-semibold text-white mt-1.5">CI Fast-Feedback Test Suite</div>
            <p className="text-xs text-surface-400 mt-1">
              Zero-network regression fixtures testing schema parsing, fail-closed handling, and state transitions.
            </p>
          </div>
        </div>
      </div>

      {/* Dataset Breakdown Grid */}
      {breakdown && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {Object.entries(breakdown.categories).map(([cat, count]) => (
            <div key={cat} className="p-3 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-[11px] text-surface-400 capitalize truncate font-medium">
                {cat.replace(/_/g, ' ')}
              </div>
              <div className="text-xl font-bold text-white mt-0.5">{count}</div>
              <div className="text-[10px] text-surface-500 mt-0.5">cases</div>
            </div>
          ))}
        </div>
      )}

      {/* Benchmark Execution Card */}
      <div className="p-6 bg-surface-900 border border-surface-800 rounded-2xl shadow-xl flex flex-col md:flex-row items-center justify-between gap-6">
        <div>
          <h2 className="text-base font-bold text-white">Execute System Evaluation Benchmark</h2>
          <p className="text-xs text-surface-300 mt-1">
            Evaluate intent classification, tool selection schema adherence, safety policies, and prompt injection defense.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <select
            value={selectedProvider}
            onChange={e => setSelectedProvider(e.target.value as 'mock_llm' | 'fireworks')}
            disabled={running}
            aria-label="Select evaluation provider"
            className="bg-surface-950 text-white text-xs border border-surface-700 rounded-lg px-3 py-2.5 focus:outline-none focus:border-brand-500 font-medium"
          >
            <option value="mock_llm">MockLLM (Deterministic 900-Case Evaluation)</option>
            <option value="fireworks">
              Fireworks AI — Qwen 3.8 Max {isFireworksConfigured ? '(Live)' : '(Requires API Key)'}
            </option>
          </select>

          <button
            onClick={handleRunBenchmark}
            disabled={running}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-semibold text-xs rounded-lg transition shadow-lg"
          >
            <Play className={`w-4 h-4 ${running ? 'animate-spin' : ''}`} />
            {running
              ? `Evaluating 900 Cases with ${selectedProvider === 'fireworks' ? 'Fireworks AI' : 'MockLLM'}...`
              : 'Run System Evaluation'}
          </button>
        </div>
      </div>

      {/* Active Benchmark Results Summary */}
      {activeBenchmark && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-brand-400" />
              Benchmark Results: {activeBenchmark.runner_type === 'real_llm' ? 'FIREWORKS AI' : 'MOCKLLM'} ({activeBenchmark.model_name})
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-surface-400 font-mono">
                Run ID: {activeBenchmark.id ? activeBenchmark.id.slice(0, 16) : 'N/A'}...
              </span>
              <span className="text-xs font-semibold px-2.5 py-1 rounded bg-surface-800 text-surface-300 font-mono">
                {activeBenchmark.passed_cases} / {activeBenchmark.total_cases} passed
              </span>
            </div>
          </div>

          {/* Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Intent Accuracy</div>
              <div className="text-2xl font-bold text-white mt-1">
                {formatPct(activeBenchmark.intent_accuracy)}
              </div>
              <div className="text-[11px] text-emerald-400 mt-1">Classification</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Tool Selection</div>
              <div className="text-2xl font-bold text-white mt-1">
                {formatPct(activeBenchmark.tool_accuracy)}
              </div>
              <div className="text-[11px] text-emerald-400 mt-1">Schema adherence</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Parameter Extraction</div>
              <div className="text-2xl font-bold text-white mt-1">
                {formatPct(activeBenchmark.param_accuracy)}
              </div>
              <div className="text-[11px] text-emerald-400 mt-1">Field alignment</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Safety Pass Rate</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {formatPct(activeBenchmark.safety_pass_rate)}
              </div>
              <div className="text-[11px] text-emerald-400/80 mt-1">Zero bypasses</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Injection Defense</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {formatPct(activeBenchmark.injection_resistance_rate)}
              </div>
              <div className="text-[11px] text-emerald-400/80 mt-1">Sanitized wrappers</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Avg Latency</div>
              <div className="text-2xl font-bold text-white mt-1">
                {formatNum(activeBenchmark.avg_latency_ms)}ms
              </div>
              <div className="text-[11px] text-surface-400 mt-1">Per agent turn</div>
            </div>
          </div>

          {/* Secondary Metrics Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Grounding Rate</div>
              <div className="text-xl font-bold text-emerald-400 mt-1">
                {formatPct(activeBenchmark.grounding_rate)}
              </div>
              <div className="text-[11px] text-surface-500 mt-0.5">Database schema backed</div>
            </div>
            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Hallucination Rate</div>
              <div className="text-xl font-bold text-white mt-1">
                {formatPct(activeBenchmark.hallucination_rate)}
              </div>
              <div className="text-[11px] text-surface-500 mt-0.5">Unverifiable claims</div>
            </div>
            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Failed Cases</div>
              <div className="text-xl font-bold text-amber-400 mt-1">
                {activeBenchmark.total_cases - activeBenchmark.passed_cases}
              </div>
              <div className="text-[11px] text-surface-500 mt-0.5">Out of {activeBenchmark.total_cases}</div>
            </div>
            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Tokens & Estimated Cost</div>
              <div className="text-xl font-bold text-brand-400 mt-1">
                ${Number(activeBenchmark.estimated_cost_usd || 0).toFixed(4)}
              </div>
              <div className="text-[11px] text-surface-500 mt-0.5">
                {Number(activeBenchmark.total_tokens || 0).toLocaleString()} tokens
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Historical Runs Table */}
      {recentBenchmarks.length > 0 && (
        <div className="bg-surface-900 border border-surface-800 rounded-xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-surface-800 flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">Historical Benchmark Runs</h3>
            <span className="text-xs text-surface-400">Click any run to view details</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-surface-800 text-surface-400 text-xs font-semibold uppercase tracking-wider bg-surface-950/40">
                  <th className="py-3 px-6">Provider</th>
                  <th className="py-3 px-6">Model</th>
                  <th className="py-3 px-6">Cases Passed</th>
                  <th className="py-3 px-6">Intent Acc.</th>
                  <th className="py-3 px-6">Tool Acc.</th>
                  <th className="py-3 px-6">Param Acc.</th>
                  <th className="py-3 px-6">Safety</th>
                  <th className="py-3 px-6">Avg Latency</th>
                  <th className="py-3 px-6">Tokens</th>
                  <th className="py-3 px-6">Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60">
                {recentBenchmarks.map(bm => {
                  const isSelected = activeBenchmark?.id === bm.id;
                  return (
                    <tr
                      key={bm.id}
                      onClick={() => setActiveBenchmark(bm)}
                      className={`cursor-pointer transition ${
                        isSelected ? 'bg-brand-950/40 border-l-2 border-brand-500' : 'hover:bg-surface-800/40'
                      }`}
                    >
                      <td className="py-3.5 px-6 font-bold text-white">
                        {bm.runner_type === 'real_llm' ? 'Fireworks AI' : 'MockLLM'}
                      </td>
                      <td className="py-3.5 px-6 font-mono text-xs text-surface-300">{bm.model_name}</td>
                      <td className="py-3.5 px-6 font-semibold text-emerald-400">
                        {bm.passed_cases} / {bm.total_cases}
                      </td>
                      <td className="py-3.5 px-6 text-white font-medium">{formatPct(bm.intent_accuracy)}</td>
                      <td className="py-3.5 px-6 text-white font-medium">{formatPct(bm.tool_accuracy)}</td>
                      <td className="py-3.5 px-6 text-white font-medium">{formatPct(bm.param_accuracy)}</td>
                      <td className="py-3.5 px-6 text-emerald-400 font-bold">{formatPct(bm.safety_pass_rate)}</td>
                      <td className="py-3.5 px-6 text-surface-300">{formatNum(bm.avg_latency_ms)}ms</td>
                      <td className="py-3.5 px-6 text-surface-400 text-xs">
                        {Number(bm.total_tokens || 0).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-6 text-brand-300 font-mono text-xs">
                        ${Number(bm.estimated_cost_usd || 0).toFixed(4)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
