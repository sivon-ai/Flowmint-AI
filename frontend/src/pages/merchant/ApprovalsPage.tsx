import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import type { Approval } from '../../types';
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  ShieldCheck,
  Filter,
  Check,
  X,
  Sparkles,
  ArrowRight,
  Info,
} from 'lucide-react';

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);

  // Decision Modal State
  const [decisionModal, setDecisionModal] = useState<{
    isOpen: boolean;
    type: 'approve' | 'reject';
    approvalId: string;
  }>({ isOpen: false, type: 'approve', approvalId: '' });
  const [decisionReason, setDecisionReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchApprovals();
  }, [statusFilter]);

  const fetchApprovals = async () => {
    setLoading(true);
    try {
      const url = statusFilter === 'all' ? '/approvals' : `/approvals?status=${statusFilter}`;
      const res = await api.get<Approval[]>(url);
      const list = res.data || [];
      setApprovals(list);
      if (list.length > 0 && !selectedApproval) {
        setSelectedApproval(list[0]);
      } else if (list.length === 0) {
        setSelectedApproval(null);
      }
    } catch (err) {
      console.error('Failed to fetch approvals:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenDecisionModal = (id: string, type: 'approve' | 'reject') => {
    setDecisionModal({ isOpen: true, type, approvalId: id });
    setDecisionReason(
      type === 'approve'
        ? 'Verified projected margins and customer eligibility.'
        : 'Discount allocation exceeds current operating targets.'
    );
  };

  const handleSubmitDecision = async () => {
    if (!decisionReason.trim()) return;
    setSubmitting(true);
    try {
      const endpoint = `/approvals/${decisionModal.approvalId}/${decisionModal.type}`;
      await api.post(endpoint, { decision_reason: decisionReason });
      setDecisionModal({ isOpen: false, type: 'approve', approvalId: '' });
      await fetchApprovals();
    } catch (err) {
      console.error('Failed to record approval decision:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const formatCurrency = (val: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
              PHASE 3 GOVERNANCE
            </span>
            <span className="text-xs text-surface-400">Human-in-the-Loop Approval Queue</span>
          </div>
          <h1 className="text-3xl font-bold text-white mt-1">Approval Center</h1>
          <p className="text-surface-300 mt-0.5">
            Review, evaluate, and authorize bounded AI revenue actions before execution.
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-wrap items-center gap-3 bg-surface-900/40 p-3 rounded-xl border border-surface-800">
        <div className="flex items-center gap-2 text-xs text-surface-400 mr-2">
          <Filter className="w-3.5 h-3.5" /> Status Filter:
        </div>
        {(['pending', 'approved', 'rejected', 'all'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize border transition-all ${
              statusFilter === s
                ? 'bg-brand-600/20 border-brand-500 text-brand-400'
                : 'bg-surface-800/60 border-surface-700 text-surface-300 hover:text-white'
            }`}
          >
            {s}
          </button>
        ))}

        <div className="ml-auto text-xs text-surface-400">
          Showing {approvals.length} requests
        </div>
      </div>

      {/* Main Split Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Approvals List */}
        <div className="lg:col-span-5 space-y-3">
          {loading ? (
            <div className="card p-8 text-center text-surface-300">Loading approvals...</div>
          ) : approvals.length === 0 ? (
            <div className="card p-12 text-center text-surface-400 space-y-2">
              <ShieldCheck className="w-10 h-10 text-emerald-400/80 mx-auto" />
              <h3 className="text-base font-semibold text-white">No Approvals Found</h3>
              <p className="text-xs text-surface-400">
                {statusFilter === 'pending'
                  ? 'All autonomous actions have been reviewed or no pending proposals exist.'
                  : `No records found with status '${statusFilter}'.`}
              </p>
            </div>
          ) : (
            approvals.map((a) => {
              const isSelected = selectedApproval?.id === a.id;
              return (
                <div
                  key={a.id}
                  onClick={() => setSelectedApproval(a)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-surface-900 border-brand-500 shadow-lg shadow-brand-500/10'
                      : 'bg-surface-900/60 border-surface-800 hover:border-surface-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-surface-800 text-brand-400 border border-surface-700">
                      {a.requested_by.replace('_', ' ')}
                    </span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded font-semibold uppercase ${
                        a.risk_level === 'high' || a.risk_level === 'critical'
                          ? 'bg-danger-500/20 text-danger-400'
                          : a.risk_level === 'medium'
                          ? 'bg-warning-500/20 text-warning-400'
                          : 'bg-emerald-500/20 text-emerald-400'
                      }`}
                    >
                      RISK: {a.risk_level}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-white mt-2 line-clamp-1">
                    {a.action_plan?.action_type.replace(/_/g, ' ').toUpperCase() || 'PROPOSED REVENUE ACTION'}
                  </h3>
                  <p className="text-xs text-surface-300 mt-1 line-clamp-2">{a.reason}</p>

                  <div className="mt-3 pt-2.5 border-t border-surface-800 flex items-center justify-between text-xs">
                    <span className="text-[11px] text-surface-400">
                      Status: <strong className="text-white uppercase">{a.status}</strong>
                    </span>
                    <span className="text-[11px] text-surface-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      Expires: {new Date(a.expires_at).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right: Detailed Approval Inspector */}
        <div className="lg:col-span-7">
          {selectedApproval ? (
            <div className="card p-6 space-y-6 sticky top-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-800">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-brand-500/20 text-brand-400 border border-brand-500/30">
                      ACTION: {selectedApproval.action_plan?.action_type.replace(/_/g, ' ').toUpperCase()}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                      selectedApproval.status === 'pending'
                        ? 'bg-warning-500/20 text-warning-400'
                        : selectedApproval.status === 'approved'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-danger-500/20 text-danger-400'
                    }`}>
                      {selectedApproval.status}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-white mt-2">
                    Approval Request #{selectedApproval.id.substring(0, 8)}
                  </h2>
                </div>

                <div className="text-right shrink-0">
                  <div className="text-xs text-surface-400">Classified Risk</div>
                  <div className={`text-base font-bold uppercase ${
                    selectedApproval.risk_level === 'high' ? 'text-danger-400' :
                    selectedApproval.risk_level === 'medium' ? 'text-warning-400' : 'text-emerald-400'
                  }`}>
                    {selectedApproval.risk_level} Risk
                  </div>
                </div>
              </div>

              {/* WHAT WILL HAPPEN */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-brand-400" />
                  What Will Happen
                </h4>
                <div className="p-3.5 rounded-xl bg-surface-950/70 border border-surface-800 text-xs text-white leading-relaxed">
                  Upon authorization, Flowmint's central executor will trigger the controlled write tool to formulate and activate{' '}
                  <strong className="text-brand-400">{selectedApproval.action_plan?.action_type.replace(/_/g, ' ')}</strong>{' '}
                  targeting <span className="font-mono text-surface-200">{selectedApproval.action_plan?.target}</span>.
                </div>
              </div>

              {/* WHY */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Info className="w-3.5 h-3.5 text-brand-400" />
                  Why (Reason & Grounding)
                </h4>
                <div className="p-3.5 rounded-xl bg-surface-950/70 border border-surface-800 text-xs text-surface-300">
                  {selectedApproval.reason}
                </div>
              </div>

              {/* WHO/WHAT IS AFFECTED & PARAMETERS */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-2">
                  Parameters & Affected Entities
                </h4>
                <div className="p-3.5 rounded-xl bg-surface-950 border border-surface-800 text-xs font-mono text-surface-300 overflow-x-auto">
                  <pre>{JSON.stringify(selectedApproval.action_plan?.parameters || {}, null, 2)}</pre>
                </div>
              </div>

              {/* POLICY CHECKS (Snapshot) */}
              <div>
                <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  Deterministic Policy Checks
                </h4>
                <div className="space-y-2">
                  {Object.entries(selectedApproval.policy_snapshot).map(([ruleName, ruleData]: [string, any]) => (
                    <div
                      key={ruleName}
                      className="p-2.5 rounded-lg bg-surface-950/60 border border-surface-800 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        {ruleData.passed ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-warning-400 shrink-0" />
                        )}
                        <span className="font-medium text-white capitalize">{ruleName.replace(/_/g, ' ')}</span>
                      </div>
                      <span className="text-surface-400 text-[11px] truncate max-w-xs">{ruleData.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* EXPIRES AT & ACTIONS */}
              <div className="pt-4 border-t border-surface-800 flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="text-xs text-surface-400 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-warning-400" />
                  <span>Expires at: {new Date(selectedApproval.expires_at).toLocaleString()}</span>
                </div>

                {selectedApproval.status === 'pending' ? (
                  <div className="flex items-center gap-3 w-full sm:w-auto">
                    <button
                      onClick={() => handleOpenDecisionModal(selectedApproval.id, 'reject')}
                      className="btn-secondary text-xs flex items-center gap-1 px-4 py-2 border-danger-500/30 text-danger-400 hover:bg-danger-500/10"
                    >
                      <X className="w-3.5 h-3.5" />
                      Reject
                    </button>
                    <button
                      onClick={() => handleOpenDecisionModal(selectedApproval.id, 'approve')}
                      className="btn-primary text-xs flex items-center gap-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white"
                    >
                      <Check className="w-3.5 h-3.5" />
                      Approve Action
                    </button>
                  </div>
                ) : (
                  <div className="text-xs text-surface-400 font-medium">
                    Decided on {new Date(selectedApproval.decided_at || selectedApproval.updated_at).toLocaleDateString()} ({selectedApproval.decision_reason})
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="card p-12 text-center text-surface-400">
              Select an approval request to inspect policy results and authorize action execution.
            </div>
          )}
        </div>
      </div>

      {/* Decision Modal */}
      {decisionModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="card max-w-md w-full p-6 space-y-4 animate-scale-up">
            <h3 className="text-lg font-bold text-white">
              {decisionModal.type === 'approve' ? 'Authorize Action Execution' : 'Reject Proposed Action'}
            </h3>
            <p className="text-xs text-surface-300">
              {decisionModal.type === 'approve'
                ? 'Confirming approval authorizes Flowmint to proceed with controlled execution. All actions remain idempotent and fully audited.'
                : 'Rejecting this proposal prevents any write tools from executing. The action plan status will update to REJECTED.'}
            </p>

            <div>
              <label className="text-xs font-medium text-surface-300 block mb-1">
                Decision Audit Rationale
              </label>
              <textarea
                rows={3}
                value={decisionReason}
                onChange={(e) => setDecisionReason(e.target.value)}
                className="input text-xs w-full"
                placeholder="State reason for audit log..."
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDecisionModal({ isOpen: false, type: 'approve', approvalId: '' })}
                className="btn-secondary text-xs px-3 py-1.5"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmitDecision}
                disabled={submitting || !decisionReason.trim()}
                className={`text-xs px-4 py-1.5 rounded-lg font-medium text-white transition-all ${
                  decisionModal.type === 'approve' ? 'bg-emerald-600 hover:bg-emerald-500' : 'bg-danger-600 hover:bg-danger-500'
                }`}
              >
                {submitting ? 'Recording...' : decisionModal.type === 'approve' ? 'Confirm Approval' : 'Confirm Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
