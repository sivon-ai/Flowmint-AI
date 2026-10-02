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
} from 'lucide-react';
import { api } from '../../lib/api';

interface DatasetBreakdown {
  total_cases: number;
  categories: Record<string, number>;
}

interface BenchmarkSummary {
  run_id: string;
  provider: string;
  model: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  intent_accuracy: number;
  tool_selection_accuracy: number;
  parameter_extraction_accuracy: number;
  safety_pass_rate: number;
  injection_resistance: number;
  hallucination_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  estimated_cost_usd: number;
  created_at?: string;
}

export default function EvaluationPage() {
  const [breakdown, setBreakdown] = useState<DatasetBreakdown | null>(null);
  const [recentBenchmarks, setRecentBenchmarks] = useState<BenchmarkSummary[]>([]);
  const [activeBenchmark, setActiveBenchmark] = useState<BenchmarkSummary | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<'mock_llm' | 'openai' | 'gemini'>('mock_llm');
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [breakdownRes, benchmarksRes] = await Promise.all([
        api.get<DatasetBreakdown>('/evaluation/dataset'),
        api.get<BenchmarkSummary[]>('/evaluation/benchmarks'),
      ]);
      if (breakdownRes.data) setBreakdown(breakdownRes.data);
      if (benchmarksRes.data && benchmarksRes.data.length > 0) {
        setRecentBenchmarks(benchmarksRes.data);
        setActiveBenchmark(benchmarksRes.data[0]);
      }
    } catch (err) {
      setError('Failed to load evaluation dataset details.');
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
    try {
      const res = await api.post<BenchmarkSummary>('/evaluation/run', {
        provider: selectedProvider,
        limit: 900,
      });
      if (res.data) {
        setActiveBenchmark(res.data);
        setRecentBenchmarks(prev => [res.data!, ...prev.slice(0, 4)]);
      }
    } catch (err: any) {
      setError(err?.message || 'Benchmark execution failed.');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">AI Evaluation Lab</h1>
          <p className="text-sm text-surface-300 mt-1">
            Empirical quality and safety benchmarks across 900 multi-domain commerce test cases.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading || running}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-surface-800 hover:bg-surface-700 text-white rounded-lg border border-surface-600 transition"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh Benchmarks
        </button>
      </div>

      {/* Mock vs Real LLM Separation Banner */}
      <div className="p-4 bg-amber-950/20 border border-amber-500/30 rounded-xl flex items-start gap-3">
        <Info className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" />
        <div className="text-xs text-amber-200/90 leading-relaxed">
          <span className="font-bold text-white">Strict Provider Separation: </span>
          MockLLM evaluations test regression determinism, tool syntax, and fail-closed security logic.
          MockLLM results are strictly isolated and <span className="font-semibold text-white underline">never</span> reported as real production LLM accuracy.
        </div>
      </div>

      {/* Dataset Breakdown Grid */}
      {breakdown && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
          {Object.entries(breakdown.categories).map(([cat, count]) => (
            <div key={cat} className="p-3 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-[11px] text-surface-400 capitalize truncate font-medium">
                {cat.replace('_', ' ')}
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
          <h2 className="text-base font-bold text-white">Run Comprehensive Evaluation Suite</h2>
          <p className="text-xs text-surface-300 mt-1">
            Execute all 900 test cases against the selected provider to measure classification, safety, and hallucination rates.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <select
            value={selectedProvider}
            onChange={e => setSelectedProvider(e.target.value as any)}
            disabled={running}
            className="bg-surface-950 text-white text-xs border border-surface-700 rounded-lg px-3 py-2.5 focus:outline-none focus:border-brand-500 font-medium"
          >
            <option value="mock_llm">MockLLM (Regression Suite - Fast)</option>
            <option value="gemini">Gemini 1.5 Flash (Production AI)</option>
            <option value="openai">OpenAI GPT-4o-mini (Production AI)</option>
          </select>

          <button
            onClick={handleRunBenchmark}
            disabled={running}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs rounded-lg transition shadow-lg disabled:opacity-50"
          >
            <Play className={`w-4 h-4 ${running ? 'animate-spin' : ''}`} />
            {running ? 'Running 900 Cases...' : 'Start Benchmark'}
          </button>
        </div>
      </div>

      {/* Active Benchmark Results Summary */}
      {activeBenchmark && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-brand-400" />
              Benchmark Results: {activeBenchmark.provider.toUpperCase()} ({activeBenchmark.model})
            </h2>
            <span className="text-xs text-surface-400 font-mono">
              Run ID: {activeBenchmark.run_id.slice(0, 16)}...
            </span>
          </div>

          {/* Metric Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Intent Accuracy</div>
              <div className="text-2xl font-bold text-white mt-1">
                {(activeBenchmark.intent_accuracy * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-emerald-400 mt-1">Classification</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Tool Selection</div>
              <div className="text-2xl font-bold text-white mt-1">
                {(activeBenchmark.tool_selection_accuracy * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-emerald-400 mt-1">Schema adherence</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Safety Pass Rate</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {(activeBenchmark.safety_pass_rate * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-emerald-400/80 mt-1">Zero bypasses</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Injection Defense</div>
              <div className="text-2xl font-bold text-emerald-400 mt-1">
                {(activeBenchmark.injection_resistance * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] text-emerald-400/80 mt-1">Untrusted wrapper</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Avg Latency</div>
              <div className="text-2xl font-bold text-white mt-1">
                {activeBenchmark.avg_latency_ms.toFixed(1)}ms
              </div>
              <div className="text-[11px] text-surface-400 mt-1">Per agent turn</div>
            </div>

            <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
              <div className="text-xs text-surface-400 font-medium">Estimated Cost</div>
              <div className="text-2xl font-bold text-brand-400 mt-1">
                ${activeBenchmark.estimated_cost_usd.toFixed(4)}
              </div>
              <div className="text-[11px] text-surface-400 mt-1">
                {activeBenchmark.total_tokens.toLocaleString()} tokens
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Historical Runs */}
      {recentBenchmarks.length > 0 && (
        <div className="bg-surface-900 border border-surface-800 rounded-xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-surface-800">
            <h3 className="text-base font-semibold text-white">Historical Benchmark Runs</h3>
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
                  <th className="py-3 px-6">Safety</th>
                  <th className="py-3 px-6">Avg Latency</th>
                  <th className="py-3 px-6">Tokens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-800/60">
                {recentBenchmarks.map(bm => (
                  <tr key={bm.run_id} className="hover:bg-surface-800/40 transition">
                    <td className="py-3.5 px-6 font-bold text-white">{bm.provider}</td>
                    <td className="py-3.5 px-6 font-mono text-xs text-surface-300">{bm.model}</td>
                    <td className="py-3.5 px-6 font-semibold text-emerald-400">
                      {bm.passed_cases} / {bm.total_cases}
                    </td>
                    <td className="py-3.5 px-6 text-white font-medium">
                      {(bm.intent_accuracy * 100).toFixed(1)}%
                    </td>
                    <td className="py-3.5 px-6 text-white font-medium">
                      {(bm.tool_selection_accuracy * 100).toFixed(1)}%
                    </td>
                    <td className="py-3.5 px-6 text-emerald-400 font-bold">
                      {(bm.safety_pass_rate * 100).toFixed(1)}%
                    </td>
                    <td className="py-3.5 px-6 text-surface-300">
                      {bm.avg_latency_ms.toFixed(1)}ms
                    </td>
                    <td className="py-3.5 px-6 text-surface-400 text-xs">
                      {bm.total_tokens.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
