import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import type { AuditLog } from '../../types';
import {
  ShieldCheck,
  Filter,
  Clock,
  Layers,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Search,
  FileText,
} from 'lucide-react';

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState<string>('all');
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);
  const [copiedTrace, setCopiedTrace] = useState<string | null>(null);

  useEffect(() => {
    fetchLogs();
  }, [eventFilter]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const url = eventFilter === 'all' ? '/audit' : `/audit?event_type=${eventFilter}`;
      const res = await api.get<AuditLog[]>(url);
      const list = res.data || [];
      setLogs(list);
      if (list.length > 0 && !selectedLog) {
        setSelectedLog(list[0]);
      } else if (list.length === 0) {
        setSelectedLog(null);
      }
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTrace(text);
    setTimeout(() => setCopiedTrace(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
            PHASE 3 AUDITABILITY
          </span>
          <span className="text-xs text-surface-400">Append-Only Immutable Event Trail</span>
        </div>
        <h1 className="text-3xl font-bold text-white mt-1">Audit Trail & Governance Log</h1>
        <p className="text-surface-300 mt-0.5">
          Tamper-evident verification of all AI proposals, policy checks, approvals, and controlled executions.
        </p>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-surface-900/40 p-3 rounded-xl border border-surface-800">
        <div className="flex items-center gap-2 text-xs text-surface-400 mr-2">
          <Filter className="w-3.5 h-3.5" /> Event Type:
        </div>
        <select
          value={eventFilter}
          onChange={(e) => setEventFilter(e.target.value)}
          className="bg-surface-800 text-white text-xs rounded-lg px-3 py-1.5 border border-surface-700 focus:outline-none focus:border-brand-500"
        >
          <option value="all">All Governance Events</option>
          <option value="policy.rejected">policy.rejected</option>
          <option value="approval.requested">approval.requested</option>
          <option value="approval.approved">approval.approved</option>
          <option value="approval.rejected">approval.rejected</option>
          <option value="action.executed">action.executed</option>
          <option value="action.blocked">action.blocked</option>
        </select>

        <div className="ml-auto text-xs text-surface-400">
          Total Logged Events: {logs.length}
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Event Stream */}
        <div className="lg:col-span-5 space-y-2.5">
          {loading ? (
            <div className="card p-8 text-center text-surface-300">Loading audit trail...</div>
          ) : logs.length === 0 ? (
            <div className="card p-12 text-center text-surface-400">
              No audit records found matching the filter.
            </div>
          ) : (
            logs.map((log) => {
              const isSelected = selectedLog?.id === log.id;
              return (
                <div
                  key={log.id}
                  onClick={() => setSelectedLog(log)}
                  className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-surface-900 border-brand-500 shadow-md shadow-brand-500/10'
                      : 'bg-surface-900/60 border-surface-800 hover:border-surface-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] text-surface-400">{log.event_id}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold uppercase ${
                        log.event_type.includes('rejected') || log.event_type.includes('blocked')
                          ? 'bg-danger-500/20 text-danger-400'
                          : log.event_type.includes('executed') || log.event_type.includes('approved')
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-warning-500/20 text-warning-400'
                      }`}
                    >
                      {log.event_type}
                    </span>
                  </div>

                  <div className="text-xs font-semibold text-white mt-1.5 line-clamp-1">{log.reason}</div>

                  <div className="mt-2.5 pt-2 border-t border-surface-800 flex items-center justify-between text-[11px] text-surface-400">
                    <span>
                      Actor: <strong className="text-surface-200 capitalize">{log.actor_type}</strong> ({log.actor_id.substring(0, 12)})
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right: Detailed Audit Inspector */}
        <div className="lg:col-span-7">
          {selectedLog ? (
            <div className="card p-6 space-y-5 sticky top-6">
              <div className="flex items-center justify-between pb-3 border-b border-surface-800">
                <div>
                  <span className="text-[10px] font-mono text-brand-400 uppercase tracking-wider bg-brand-500/10 px-2 py-0.5 rounded border border-brand-500/20">
                    EVENT: {selectedLog.event_type}
                  </span>
                  <h3 className="text-lg font-bold text-white mt-1.5 font-mono">{selectedLog.event_id}</h3>
                </div>
                <div className="text-right text-xs text-surface-400">
                  <div>Timestamp</div>
                  <div className="font-mono text-white">{new Date(selectedLog.created_at).toISOString()}</div>
                </div>
              </div>

              {/* Event Reason */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-1.5">
                  Audit Reason & Narrative
                </h4>
                <div className="p-3.5 rounded-xl bg-surface-950/70 border border-surface-800 text-xs text-white">
                  {selectedLog.reason}
                </div>
              </div>

              {/* Status Transition & Actors */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-surface-950/60 border border-surface-800 space-y-1">
                  <span className="text-surface-400">Actor Context</span>
                  <div className="text-white font-medium capitalize">{selectedLog.actor_type}: {selectedLog.actor_id}</div>
                  {selectedLog.agent && (
                    <div className="text-[11px] text-brand-400">Agent: {selectedLog.agent}</div>
                  )}
                </div>

                <div className="p-3 rounded-xl bg-surface-950/60 border border-surface-800 space-y-1">
                  <span className="text-surface-400">Status Transition</span>
                  <div className="text-white font-mono">
                    <span className="text-surface-400">{selectedLog.previous_status || 'NONE'}</span>
                    {' → '}
                    <span className="text-brand-400">{selectedLog.new_status || 'CURRENT'}</span>
                  </div>
                </div>
              </div>

              {/* Policy Evaluation Snapshot */}
              {selectedLog.policy_results && Object.keys(selectedLog.policy_results).length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-1.5">
                    Policy Evaluation Results
                  </h4>
                  <div className="p-3 rounded-xl bg-surface-950 border border-surface-800 font-mono text-[11px] text-surface-300 overflow-x-auto max-h-48">
                    <pre>{JSON.stringify(selectedLog.policy_results, null, 2)}</pre>
                  </div>
                </div>
              )}

              {/* Execution / Tool Result Snapshot */}
              {selectedLog.execution_result && Object.keys(selectedLog.execution_result).length > 0 && (
                <div>
                  <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-1.5">
                    Controlled Tool Execution Output
                  </h4>
                  <div className="p-3 rounded-xl bg-surface-950 border border-surface-800 font-mono text-[11px] text-surface-300 overflow-x-auto max-h-48">
                    <pre>{JSON.stringify(selectedLog.execution_result, null, 2)}</pre>
                  </div>
                </div>
              )}

              {/* Trace ID Bar */}
              {selectedLog.trace_id && (
                <div className="pt-3 border-t border-surface-800 flex items-center justify-between text-xs text-surface-400">
                  <span>Distributed Trace: <strong className="font-mono text-white">{selectedLog.trace_id}</strong></span>
                  <button
                    onClick={() => handleCopy(selectedLog.trace_id!)}
                    className="btn-secondary text-[11px] py-1 px-2.5 flex items-center gap-1"
                  >
                    {copiedTrace === selectedLog.trace_id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedTrace === selectedLog.trace_id ? 'Copied' : 'Copy Trace'}</span>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="card p-12 text-center text-surface-400">
              Select an audit event from the stream to inspect the verifiable record.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
