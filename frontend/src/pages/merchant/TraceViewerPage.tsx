import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  GitBranch,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowDown,
  ShieldCheck,
  Zap,
  DollarSign,
  AlertTriangle,
  FileCode,
  Layers,
} from 'lucide-react';
import { api } from '../../lib/api';

interface TimelineNode {
  step: number;
  sub_step?: number;
  type: string;
  label: string;
  status: string;
  timestamp: string;
  latency_ms?: number;
  tokens?: number;
  details: Record<string, any>;
}

interface TraceData {
  trace_id: string;
  merchant_id: string;
  total_nodes: number;
  timeline: TimelineNode[];
}

interface TraceSummary {
  trace_id: string;
  event_type: string;
  timestamp: string;
  action_id: string | null;
  agent: string | null;
}

export default function TraceViewerPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialId = searchParams.get('id') || '';
  const [traceIdInput, setTraceIdInput] = useState(initialId);
  const [traceData, setTraceData] = useState<TraceData | null>(null);
  const [recentTraces, setRecentTraces] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Record<number, boolean>>({});

  useEffect(() => {
    // Load recent traces
    api.get<TraceSummary[]>('/traces')
      .then(res => {
        if (res.data) setRecentTraces(res.data);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const id = searchParams.get('id');
    if (id) {
      setTraceIdInput(id);
      loadTrace(id);
    }
  }, [searchParams]);

  const loadTrace = async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<TraceData>(`/traces/${id.trim()}`);
      if (res.data) {
        setTraceData(res.data);
        // Expand first and last nodes by default
        setExpandedNodes({ 0: true, [res.data.timeline.length - 1]: true });
      } else {
        setError(`No trace data found for '${id}'.`);
        setTraceData(null);
      }
    } catch (err) {
      setError(`Failed to retrieve trace '${id}'.`);
      setTraceData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (traceIdInput.trim()) {
      setSearchParams({ id: traceIdInput.trim() });
    }
  };

  const toggleNode = (index: number) => {
    setExpandedNodes(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const getNodeIcon = (type: string, status: string) => {
    if (status === 'failed' || status === 'policy_rejected') {
      return <XCircle className="w-5 h-5 text-red-400" />;
    }
    switch (type) {
      case 'opportunity_detected':
        return <Zap className="w-5 h-5 text-amber-400" />;
      case 'agent_run':
        return <GitBranch className="w-5 h-5 text-blue-400" />;
      case 'tool_call':
        return <FileCode className="w-5 h-5 text-purple-400" />;
      case 'action_plan':
        return <Layers className="w-5 h-5 text-cyan-400" />;
      case 'audit_log':
        return <ShieldCheck className="w-5 h-5 text-indigo-400" />;
      case 'approval':
        return <CheckCircle2 className="w-5 h-5 text-emerald-400" />;
      case 'execution':
        return <Zap className="w-5 h-5 text-emerald-400" />;
      case 'outcome':
        return <DollarSign className="w-5 h-5 text-brand-400" />;
      default:
        return <Clock className="w-5 h-5 text-surface-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">End-to-End Trace Viewer</h1>
          <p className="text-sm text-surface-300 mt-1">
            Complete causal DAG reconstruction from Opportunity Signal to Observed Revenue Outcome.
          </p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="p-4 bg-surface-900 border border-surface-800 rounded-xl">
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-surface-400 absolute left-3 top-3" />
            <input
              type="text"
              placeholder="Enter trace ID (e.g. trc_... or select from recent below)"
              value={traceIdInput}
              onChange={e => setTraceIdInput(e.target.value)}
              className="w-full bg-surface-950 text-white pl-9 pr-4 py-2 rounded-lg border border-surface-700 focus:outline-none focus:border-brand-500 text-sm font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2 bg-brand-600 hover:bg-brand-500 text-white font-medium text-sm rounded-lg transition disabled:opacity-50"
          >
            {loading ? 'Reconstructing...' : 'Inspect Trace'}
          </button>
        </form>

        {/* Quick picks */}
        {recentTraces.length > 0 && (
          <div className="mt-3 flex items-center gap-2 overflow-x-auto text-xs text-surface-400 pt-2 border-t border-surface-800/60">
            <span className="shrink-0 font-medium">Recent Traces:</span>
            {recentTraces.slice(0, 4).map(t => (
              <button
                key={t.trace_id}
                type="button"
                onClick={() => {
                  setTraceIdInput(t.trace_id);
                  setSearchParams({ id: t.trace_id });
                }}
                className="px-2 py-0.5 rounded bg-surface-800 hover:bg-surface-700 text-surface-300 font-mono text-[11px] border border-surface-700 transition shrink-0"
              >
                {t.trace_id.slice(0, 18)}...
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Trace Timeline Canvas */}
      {loading ? (
        <div className="p-16 text-center text-surface-400 animate-pulse bg-surface-900/40 rounded-2xl border border-surface-800">
          Reconstructing full causal DAG timeline...
        </div>
      ) : error ? (
        <div className="p-8 text-center text-red-400 bg-red-950/20 border border-red-900/30 rounded-xl">
          {error}
        </div>
      ) : traceData ? (
        <div className="bg-surface-900 border border-surface-800 rounded-2xl p-6 shadow-2xl">
          <div className="flex items-center justify-between pb-4 border-b border-surface-800 mb-8">
            <div>
              <div className="text-xs uppercase tracking-widest text-brand-400 font-bold">
                Causal Journey Graph
              </div>
              <h2 className="text-lg font-bold text-white font-mono mt-0.5">
                {traceData.trace_id}
              </h2>
            </div>
            <div className="flex items-center gap-3">
              <span className="px-3 py-1 rounded-full bg-surface-800 border border-surface-700 text-xs text-surface-300">
                {traceData.total_nodes} Journey Steps
              </span>
            </div>
          </div>

          {/* Chronological DAG Nodes */}
          <div className="relative pl-6 space-y-6 before:absolute before:left-8 before:top-4 before:bottom-4 before:w-0.5 before:bg-surface-800">
            {traceData.timeline.map((node, idx) => {
              const isExpanded = !!expandedNodes[idx];
              const isLast = idx === traceData.timeline.length - 1;
              return (
                <div key={idx} className="relative flex items-start gap-4">
                  {/* Step Bubble */}
                  <div className="w-10 h-10 rounded-xl bg-surface-950 border border-surface-700 flex items-center justify-center shrink-0 z-10 shadow-lg">
                    {getNodeIcon(node.type, node.status)}
                  </div>

                  {/* Card Content */}
                  <div className="flex-1 bg-surface-950/70 border border-surface-800 rounded-xl p-4 transition hover:border-surface-700">
                    <div className="flex items-center justify-between cursor-pointer" onClick={() => toggleNode(idx)}>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-surface-500">
                          #{node.step}{node.sub_step ? `.${node.sub_step}` : ''}
                        </span>
                        <span className="text-sm font-bold text-white">
                          {node.label}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                          node.status === 'completed' || node.status === 'success' || node.status === 'approved'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : node.status === 'failed' || node.status === 'policy_rejected'
                            ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                            : 'bg-surface-800 text-surface-400 border border-surface-700'
                        }`}>
                          {node.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-surface-400">
                        {node.latency_ms !== undefined && (
                          <span>{node.latency_ms}ms</span>
                        )}
                        <span>{new Date(node.timestamp).toLocaleTimeString()}</span>
                        <button type="button" className="text-brand-400 hover:text-brand-300 font-medium">
                          {isExpanded ? 'Collapse' : 'Details'}
                        </button>
                      </div>
                    </div>

                    {/* Collapsible Details */}
                    {isExpanded && (
                      <div className="mt-3 pt-3 border-t border-surface-800/80 text-xs">
                        <pre className="p-3 bg-surface-900 rounded-lg text-surface-300 font-mono text-[11px] overflow-x-auto border border-surface-800">
                          {JSON.stringify(node.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="p-16 text-center text-surface-500 bg-surface-900/30 rounded-2xl border border-surface-800/60">
          Enter a trace ID above or select from recent traces to visualize the complete execution DAG.
        </div>
      )}
    </div>
  );
}
