import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowRight,
  ArrowLeft,
  ChevronRight,
  Play,
  FileCode,
  Layers,
  GitBranch,
  Eye,
  Lock,
  DollarSign,
  TrendingUp,
  Cpu,
  RefreshCw,
  Sparkles,
  Award,
} from 'lucide-react';
import { api } from '../../lib/api';

interface StepDef {
  number: number;
  title: string;
  shortTitle: string;
  badge: string;
  description: string;
}

const STEPS: StepDef[] = [
  {
    number: 1,
    title: 'Revenue Command Center',
    shortTitle: 'Command Center',
    badge: 'Overview',
    description: 'Real-time telemetry of store health, revenue runs, and detection signals.',
  },
  {
    number: 2,
    title: 'Detected Opportunity',
    shortTitle: 'Opportunity',
    badge: 'Revenue Signal',
    description: 'System detects ₹1,42,000 at risk across 37 high-intent abandoned carts.',
  },
  {
    number: 3,
    title: 'Inspectable Evidence',
    shortTitle: 'Evidence',
    badge: 'Zero Black-Box',
    description: 'Underlying data telemetry, timestamps, customer cohorts, and cart details.',
  },
  {
    number: 4,
    title: 'AI Investigation',
    shortTitle: 'AI Reasoning',
    badge: 'Recovery Agent',
    description: 'Autonomous agent investigates cart friction without executing writes.',
  },
  {
    number: 5,
    title: 'What-if Simulation',
    shortTitle: 'Simulation',
    badge: 'Deterministic Math',
    description: 'Pre-flight predictive revenue modeling before committing merchant resources.',
  },
  {
    number: 6,
    title: 'ActionPlan Formulation',
    shortTitle: 'ActionPlan',
    badge: 'Proposal Gate',
    description: 'Structured proposal created with strict bounds, parameters, and rollback plan.',
  },
  {
    number: 7,
    title: 'Policy Engine Check',
    shortTitle: 'Policy Check',
    badge: 'Hard Constraints',
    description: 'Deterministic rule evaluation against merchant policies (e.g. max 15% discount).',
  },
  {
    number: 8,
    title: 'Risk Classification',
    shortTitle: 'Risk Level',
    badge: 'Governance',
    description: 'System automatically classifies action as MEDIUM risk requiring human sign-off.',
  },
  {
    number: 9,
    title: 'Human-in-the-Loop Approval',
    shortTitle: 'HITL Approval',
    badge: 'Permission Gate',
    description: 'Merchant operator reviews bounds, projected impact, and approves execution.',
  },
  {
    number: 10,
    title: 'Controlled Execution',
    shortTitle: 'Execution',
    badge: 'Idempotent Write',
    description: 'Write tool executed via atomic transaction with strict idempotency lock.',
  },
  {
    number: 11,
    title: 'Observed Outcome',
    shortTitle: 'Attribution',
    badge: 'Deterministic Link',
    description: 'Ground-truth orders recorded and labeled OBSERVED vs ESTIMATED.',
  },
  {
    number: 12,
    title: 'Trace & Audit Verification',
    shortTitle: 'Audit / Trace',
    badge: 'Causal DAG',
    description: 'Cryptographically linked causal DAG proving end-to-end provenance.',
  },
];

export default function JudgePage() {
  const [currentStep, setCurrentStep] = useState(1);
  const [failureDemoMode, setFailureDemoMode] = useState(false);
  const [approvedState, setApprovedState] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const [executedState, setExecutedState] = useState(false);

  const step = STEPS[currentStep - 1];

  const handleNext = () => {
    if (currentStep < 12) setCurrentStep(currentStep + 1);
  };

  const handlePrev = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Judge Mode Hero Banner */}
      <div className="p-6 bg-gradient-to-r from-brand-950 via-surface-900 to-surface-900 border border-brand-500/40 rounded-2xl shadow-2xl relative overflow-hidden">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-0.5 text-[11px] font-extrabold uppercase tracking-widest rounded-full bg-brand-500/20 text-brand-300 border border-brand-500/40">
                Official Competition Evaluation
              </span>
              <span className="px-2.5 py-0.5 text-[11px] font-bold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                Live Interactive Mode
              </span>
            </div>
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
              <Award className="w-6 h-6 text-brand-400" />
              Flowmint AI — Guided Judge Walkthrough
            </h1>
            <p className="text-xs text-surface-300 max-w-2xl">
              12-step autonomous revenue operating system demonstration: from commerce telemetry signal
              through AI reasoning, safety policies, human approval, to verifiable financial outcome.
            </p>
          </div>

          <div className="flex items-center gap-2 bg-surface-950/70 p-2 rounded-xl border border-surface-800">
            <button
              onClick={() => {
                setFailureDemoMode(false);
                setCurrentStep(1);
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
                !failureDemoMode
                  ? 'bg-brand-600 text-white shadow-md'
                  : 'text-surface-400 hover:text-white'
              }`}
            >
              Canonical Success Demo
            </button>
            <button
              onClick={() => {
                setFailureDemoMode(true);
                setCurrentStep(7); // Jump straight to policy check
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition ${
                failureDemoMode
                  ? 'bg-red-600 text-white shadow-md'
                  : 'text-surface-400 hover:text-white'
              }`}
            >
              Blocked Failure Demo (25% Discount)
            </button>
          </div>
        </div>

        {/* Stepper Progress Bar */}
        <div className="mt-6 pt-6 border-t border-surface-800/80">
          <div className="grid grid-cols-6 md:grid-cols-12 gap-1.5">
            {STEPS.map((s) => {
              const isCurrent = s.number === currentStep;
              const isPast = s.number < currentStep;
              return (
                <button
                  key={s.number}
                  onClick={() => setCurrentStep(s.number)}
                  className={`p-2 rounded-lg text-left transition flex flex-col items-center text-center group border ${
                    isCurrent
                      ? 'bg-brand-500/20 border-brand-500 text-white ring-1 ring-brand-500'
                      : isPast
                      ? 'bg-surface-950/80 border-surface-700/60 text-emerald-400 hover:border-surface-600'
                      : 'bg-surface-950/40 border-surface-800 text-surface-500 hover:border-surface-700'
                  }`}
                >
                  <div className="text-[10px] font-bold">
                    {isPast ? '✓' : `0${s.number}`.slice(-2)}
                  </div>
                  <div className="text-[10px] font-medium truncate w-full mt-0.5 hidden md:block">
                    {s.shortTitle}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Step Display Header */}
      <div className="flex items-center justify-between bg-surface-900 border border-surface-800 px-6 py-4 rounded-xl">
        <div className="flex items-center gap-3">
          <span className="w-8 h-8 rounded-lg bg-brand-500/20 text-brand-400 flex items-center justify-center font-bold text-sm border border-brand-500/30">
            {currentStep}
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white">{step.title}</h2>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded bg-surface-800 text-surface-300">
                {step.badge}
              </span>
            </div>
            <p className="text-xs text-surface-400 mt-0.5">{step.description}</p>
          </div>
        </div>

        {/* Step Navigation Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrev}
            disabled={currentStep === 1}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-surface-800 hover:bg-surface-700 disabled:opacity-30 text-white rounded-lg border border-surface-700 transition"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Prev
          </button>
          <span className="text-xs text-surface-400 font-mono px-2">
            Step {currentStep} of 12
          </span>
          <button
            onClick={handleNext}
            disabled={currentStep === 12}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs bg-brand-600 hover:bg-brand-500 disabled:opacity-30 text-white font-semibold rounded-lg transition shadow-md"
          >
            Next <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Step Content View */}
      <div className="bg-surface-900 border border-surface-800 rounded-2xl p-6 shadow-xl">
        {/* STEP 1: Revenue Command Center */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Total Monthly GMV</div>
                <div className="text-2xl font-bold text-white mt-1">₹18,45,200</div>
                <div className="text-[11px] text-emerald-400 mt-1">+14.2% vs previous period</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Revenue at Risk</div>
                <div className="text-2xl font-bold text-red-400 mt-1">₹1,42,000</div>
                <div className="text-[11px] text-surface-400 mt-1">37 abandoned checkouts</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Autonomous Policy Mode</div>
                <div className="text-2xl font-bold text-emerald-400 mt-1">Active</div>
                <div className="text-[11px] text-surface-400 mt-1">Max 15% discount cap enforced</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Active System Agents</div>
                <div className="text-2xl font-bold text-brand-400 mt-1">4 Agents</div>
                <div className="text-[11px] text-surface-400 mt-1">Buyer, Analytics, Growth, Recovery</div>
              </div>
            </div>

            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl space-y-2">
              <h3 className="text-sm font-semibold text-white">Merchant Profile Telemetry</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 text-xs text-surface-300 gap-4">
                <div><span className="text-surface-500">Merchant:</span> TechMart India</div>
                <div><span className="text-surface-500">Store Domain:</span> techmart-india.flowmint.in</div>
                <div><span className="text-surface-500">Currency:</span> INR (₹)</div>
                <div><span className="text-surface-500">Payment Gateway:</span> Razorpay (TEST MODE)</div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Detected Opportunity */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div className="p-5 bg-surface-950 border border-brand-500/30 rounded-xl">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-red-500/20 text-red-300 text-xs font-bold border border-red-500/30">
                    HIGH PRIORITY SIGNAL
                  </span>
                  <span className="text-xs font-mono text-surface-400">opp_ab_cart_2026_01</span>
                </div>
                <span className="text-sm font-bold text-emerald-400">92% Confidence</span>
              </div>
              <h3 className="text-xl font-bold text-white mt-2">
                High Checkout Abandonment Spike (₹1,42,000 at risk)
              </h3>
              <p className="text-xs text-surface-300 mt-1">
                37 high-intent buyer carts were abandoned during final payment step over the last 24 hours.
                Mean cart value: ₹3,837.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400 font-medium">Estimated Recoverable Revenue</div>
                <div className="text-2xl font-bold text-white mt-1">₹35,500 – ₹51,120</div>
                <div className="text-[11px] text-surface-400 mt-1">Based on historical 25-36% recovery</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400 font-medium">Targeted Cohort</div>
                <div className="text-2xl font-bold text-white mt-1">37 Carts</div>
                <div className="text-[11px] text-surface-400 mt-1">Abandoned 2h–24h ago</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400 font-medium">Recommended Action</div>
                <div className="text-2xl font-bold text-brand-400 mt-1">10% Time-Bounded Offer</div>
                <div className="text-[11px] text-surface-400 mt-1">Well within 15% policy ceiling</div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Inspectable Evidence */}
        {currentStep === 3 && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-white">Underlying Telemetry & Audit Evidence</h3>
            <p className="text-xs text-surface-400">
              Unlike black-box systems, every Flowmint opportunity provides deterministic data evidence
              accessible to operators and auditors.
            </p>
            <div className="bg-surface-950 p-4 rounded-xl border border-surface-800 font-mono text-xs text-surface-300 overflow-x-auto">
              <pre>{JSON.stringify({
                opportunity_id: "opp_ab_cart_2026_01",
                detection_timestamp: "2026-10-02T12:00:00Z",
                metric: "checkout_abandonment_spike",
                baseline_abandonment_rate: 0.22,
                observed_abandonment_rate: 0.40,
                statistical_delta: "+18.0% over 7-day rolling window",
                eligible_entities_count: 37,
                at_risk_amount_inr: 142000.0,
                target_skus: ["LAP-001", "PHN-001", "ACC-001"],
                cooldown_policy_check: "All 37 customers outside 24h contact cooldown window",
                provenance: "EventBus -> Outbox -> OpportunityEngine"
              }, null, 2)}</pre>
            </div>
          </div>
        )}

        {/* STEP 4: AI Investigation */}
        {currentStep === 4 && (
          <div className="space-y-4">
            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl space-y-2">
              <div className="flex items-center gap-2">
                <Cpu className="w-5 h-5 text-brand-400" />
                <span className="text-sm font-bold text-white">Autonomous Agent: Recovery Agent</span>
              </div>
              <p className="text-xs text-surface-300">
                The Recovery Agent autonomously invoked structured read tools: <code className="text-brand-300 bg-surface-900 px-1 py-0.5 rounded">get_abandoned_carts</code> and <code className="text-brand-300 bg-surface-900 px-1 py-0.5 rounded">get_recovery_candidates</code>.
              </p>
            </div>

            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl space-y-2">
              <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider">Agent Internal Reasoning Chain</h4>
              <div className="space-y-2 text-xs text-surface-300 font-mono bg-surface-900/60 p-3 rounded-lg border border-surface-800">
                <div>[1] Ingested 37 abandoned carts from EventBus telemetry.</div>
                <div>[2] Checked customer contact history: 0 customers contacted in last 24h.</div>
                <div>[3] Verified inventory stock for all 37 carts: All items in stock (0 stockouts).</div>
                <div>[4] Calculated price sensitivity: 10% discount recovers an estimated 25% of carts.</div>
                <div>[5] Formulation: Prepared ActionPlan proposal with bounded coupon recovery offer.</div>
                <div>[6] Write status: STOPPED AT READ-ONLY BOUNDARY. Proposal dispatched to Governance Gate.</div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: What-if Simulation */}
        {currentStep === 5 && (
          <div className="space-y-6">
            <div className="p-4 bg-purple-950/20 border border-purple-500/30 rounded-xl flex items-center justify-between">
              <div>
                <span className="text-xs font-bold text-purple-300 uppercase tracking-widest">
                  Simulation Engine Projection (SIMULATED)
                </span>
                <h3 className="text-lg font-bold text-white mt-0.5">Monte Carlo & Arithmetic Model</h3>
              </div>
              <span className="px-2.5 py-1 text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 rounded-full">
                SIMULATED
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Offer Discount</div>
                <div className="text-2xl font-bold text-white mt-1">10.0%</div>
                <div className="text-[11px] text-emerald-400 mt-1">Within 15% limit</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Projected Conversions</div>
                <div className="text-2xl font-bold text-white mt-1">9 to 11 carts</div>
                <div className="text-[11px] text-surface-400 mt-1">25% expected recovery rate</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Projected Gross Lift</div>
                <div className="text-2xl font-bold text-white mt-1">₹38,370</div>
                <div className="text-[11px] text-surface-400 mt-1">Estimated discount cost: -₹3,837</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Projected Net Impact</div>
                <div className="text-2xl font-bold text-purple-400 mt-1">₹34,533</div>
                <div className="text-[11px] text-purple-300 mt-1">Not actual revenue (SIMULATED)</div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 6: ActionPlan Formulation */}
        {currentStep === 6 && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">Generated ActionPlan (Status: PROPOSED)</h3>
              <span className="text-xs px-2.5 py-1 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-bold">
                PROPOSED — AWAITING GOVERNANCE
              </span>
            </div>

            <div className="bg-surface-950 p-4 rounded-xl border border-surface-800 text-xs font-mono text-surface-300">
              <pre>{JSON.stringify({
                action_id: "plan_rec_cart_019",
                action_type: "abandoned_cart_recovery",
                status: "PROPOSED",
                tool_to_execute: "apply_cart_recovery_offer",
                bounds: {
                  discount_percentage: 10.0,
                  max_recipients: 37,
                  expiry_hours: 48,
                  total_budget_limit_inr: 15000.0,
                  idempotency_key: "idem_cart_recovery_20261002_001"
                },
                rollback_strategy: "expire_discount_codes_immediately"
              }, null, 2)}</pre>
            </div>
          </div>
        )}

        {/* STEP 7: Policy Check */}
        {currentStep === 7 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">Deterministic Merchant Policy Evaluation</h3>
              <button
                onClick={() => setFailureDemoMode(!failureDemoMode)}
                className={`text-xs px-3 py-1.5 rounded-lg border font-semibold transition ${
                  failureDemoMode
                    ? 'bg-red-500/20 text-red-300 border-red-500/40'
                    : 'bg-surface-800 text-surface-300 border-surface-700'
                }`}
              >
                {failureDemoMode ? 'Testing 25% Exceeding Discount' : 'Switch to 25% Disallowed Discount Test'}
              </button>
            </div>

            {failureDemoMode ? (
              <div className="p-5 bg-red-950/30 border border-red-500/40 rounded-xl space-y-4">
                <div className="flex items-center gap-2">
                  <XCircle className="w-6 h-6 text-red-400" />
                  <h4 className="text-base font-bold text-red-400">
                    POLICY REJECTED — DISALLOWED DISCOUNT (25% &gt; 15% Maximum)
                  </h4>
                </div>
                <p className="text-xs text-red-200">
                  The merchant policy strictly caps discounts at 15.0%. The proposed 25.0% discount was
                  evaluated by PolicyEngine and rejected before approval or execution could ever occur.
                </p>
                <div className="bg-surface-950 p-3 rounded-lg border border-red-900/50 text-xs font-mono text-red-300">
                  <div>Rule: rule_max_discount_cap</div>
                  <div>Policy Limit: 15.00%</div>
                  <div>Proposed: 25.00%</div>
                  <div>Verdict: REJECTED (Fail-Closed)</div>
                  <div>Action Status: BLOCKED</div>
                  <div>Audit Event: audit_pol_violation_091 logged</div>
                </div>
              </div>
            ) : (
              <div className="p-5 bg-emerald-950/20 border border-emerald-500/30 rounded-xl space-y-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                  <h4 className="text-base font-bold text-emerald-400">
                    ALL 9 POLICY RULES PASSED
                  </h4>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="p-3 bg-surface-950 rounded-lg border border-surface-800">
                    <span className="text-surface-400">Discount Cap:</span>
                    <div className="text-emerald-400 font-bold mt-0.5">10% &le; 15% Limit (PASS)</div>
                  </div>
                  <div className="p-3 bg-surface-950 rounded-lg border border-surface-800">
                    <span className="text-surface-400">Campaign Budget:</span>
                    <div className="text-emerald-400 font-bold mt-0.5">₹3,837 &le; ₹50,000 (PASS)</div>
                  </div>
                  <div className="p-3 bg-surface-950 rounded-lg border border-surface-800">
                    <span className="text-surface-400">Cooldown Window:</span>
                    <div className="text-emerald-400 font-bold mt-0.5">24h elapsed (PASS)</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* STEP 8: Risk Classification */}
        {currentStep === 8 && (
          <div className="space-y-4">
            <div className="p-5 bg-surface-950 border border-amber-500/30 rounded-xl space-y-3">
              <div className="flex items-center justify-between">
                <span className="px-3 py-1 text-xs font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  MEDIUM RISK CLASSIFICATION
                </span>
                <span className="text-xs text-surface-400">Auto-Approval: FORBIDDEN</span>
              </div>
              <h3 className="text-lg font-bold text-white">
                Human-in-the-Loop Approval Required
              </h3>
              <p className="text-xs text-surface-300">
                Because this action mutates pricing and messages external buyers, Flowmint governance
                rules forbid autonomous auto-approval. An explicit human sign-off is required.
              </p>
            </div>
          </div>
        )}

        {/* STEP 9: Approval */}
        {currentStep === 9 && (
          <div className="space-y-6">
            <div className="p-6 bg-surface-950 border border-surface-800 rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-white">Merchant Operator Approval Gate</h3>
                <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                  approvedState === 'approved'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                }`}>
                  {approvedState === 'approved' ? 'APPROVED' : 'AWAITING OPERATOR REVIEW'}
                </span>
              </div>

              <div className="text-xs text-surface-300 space-y-1">
                <div><span className="text-surface-500">Approver Role:</span> Merchant Store Owner</div>
                <div><span className="text-surface-500">Action Plan:</span> 10% Discount Offer for 37 Abandoned Checkouts</div>
                <div><span className="text-surface-500">Max Exposure Limit:</span> ₹15,000 INR</div>
              </div>

              {approvedState !== 'approved' ? (
                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={() => setApprovedState('approved')}
                    className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-lg transition shadow-lg flex items-center gap-2"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Approve Execution
                  </button>
                  <button
                    onClick={() => setApprovedState('rejected')}
                    className="px-4 py-2.5 bg-surface-800 hover:bg-surface-700 text-surface-300 font-semibold text-xs rounded-lg transition border border-surface-700"
                  >
                    Reject Proposal
                  </button>
                </div>
              ) : (
                <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded-lg text-xs text-emerald-300 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  Approved by admin@techmart.in at 2026-10-02T12:04:18Z with reason: &quot;Approved 10% checkout recovery&quot;
                </div>
              )}
            </div>
          </div>
        )}

        {/* STEP 10: Execution */}
        {currentStep === 10 && (
          <div className="space-y-6">
            <div className="p-6 bg-surface-950 border border-surface-800 rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-base font-bold text-white">Idempotent Execution Engine</h3>
                <span className="text-xs font-mono text-surface-400">
                  Tool: apply_cart_recovery_offer
                </span>
              </div>

              <p className="text-xs text-surface-300">
                Action execution is guaranteed idempotent. Replay attacks and duplicate runs are blocked
                via database unique locks.
              </p>

              {!executedState ? (
                <button
                  onClick={() => setExecutedState(true)}
                  className="px-5 py-2.5 bg-brand-600 hover:bg-brand-500 text-white font-bold text-xs rounded-lg transition shadow-lg flex items-center gap-2"
                >
                  <Play className="w-4 h-4" /> Trigger Controlled Execution
                </button>
              ) : (
                <div className="space-y-3">
                  <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded-lg text-xs text-emerald-300 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    Successfully executed! Idempotency key locked: idem_cart_recovery_20261002_001
                  </div>
                  <div className="bg-surface-900 p-3 rounded-lg text-xs font-mono text-surface-300 space-y-1">
                    <div>Status: COMPLETED (Duration: 84ms)</div>
                    <div>Targeted Carts: 37 vouchers generated</div>
                    <div>Outbox Events Published: 37 &apos;cart.recovery_voucher_applied&apos;</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* STEP 11: Outcome */}
        {currentStep === 11 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-surface-800 pb-3">
              <div>
                <span className="text-xs font-bold text-emerald-400 uppercase tracking-wider">
                  Post-Action Telemetry Ledger
                </span>
                <h3 className="text-lg font-bold text-white mt-0.5">
                  Ground-Truth Measured Financial Outcome
                </h3>
              </div>
              <span className="px-3 py-1 text-xs font-bold rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                OBSERVED
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Actual Recovered Orders</div>
                <div className="text-2xl font-bold text-emerald-400 mt-1">3 Completed</div>
                <div className="text-[11px] text-surface-400 mt-1">Deterministic cart linkage</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Gross Recovered GMV</div>
                <div className="text-2xl font-bold text-white mt-1">₹9,850</div>
                <div className="text-[11px] text-surface-400 mt-1">Actual captured payments</div>
              </div>
              <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
                <div className="text-xs text-surface-400">Discount Concession</div>
                <div className="text-2xl font-bold text-red-400 mt-1">-₹985</div>
                <div className="text-[11px] text-surface-400 mt-1">10% voucher code impact</div>
              </div>
              <div className="p-4 bg-surface-950 border border-brand-500/40 rounded-xl bg-brand-950/20">
                <div className="text-xs text-brand-300 font-semibold uppercase">Net Bankable Lift</div>
                <div className="text-2xl font-black text-brand-400 mt-1">+₹8,865</div>
                <div className="text-[11px] text-brand-300/80 mt-1">DETERMINISTIC EVENT LINK</div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 12: Trace / Audit */}
        {currentStep === 12 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between border-b border-surface-800 pb-3">
              <div>
                <span className="text-xs font-bold text-brand-400 uppercase tracking-wider">
                  End-to-End Cryptographic Provenance
                </span>
                <h3 className="text-lg font-bold text-white mt-0.5">
                  Trace Graph & Immutable Audit Log
                </h3>
              </div>
              <Link
                to="/traces?id=tr_canon_cart_recovery_01"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-brand-600 hover:bg-brand-500 text-white font-semibold rounded-lg transition"
              >
                <GitBranch className="w-3.5 h-3.5" /> Open Full Trace DAG
              </Link>
            </div>

            <div className="p-4 bg-surface-950 border border-surface-800 rounded-xl">
              <h4 className="text-xs font-bold text-surface-400 uppercase tracking-wider mb-3">
                Causal Reconstruction Chain (12 Verified Nodes)
              </h4>
              <div className="space-y-2 text-xs font-mono">
                <div className="flex items-center gap-2 text-surface-300">
                  <span className="text-emerald-400 font-bold">[01]</span> Commerce Event: Checkout Abandonment Spike (37 carts)
                </div>
                <div className="flex items-center gap-2 text-surface-300">
                  <span className="text-emerald-400 font-bold">[02]</span> Opportunity Engine: opp_ab_cart_2026_01 detected
                </div>
                <div className="flex items-center gap-2 text-surface-300">
                  <span className="text-emerald-400 font-bold">[03]</span> Recovery Agent Run: Tool calls get_abandoned_carts, check_inventory
                </div>
                <div className="flex items-center gap-2 text-surface-300">
                  <span className="text-emerald-400 font-bold">[04]</span> What-if Simulation: 10% discount test projected ₹34,533 net lift
                </div>
                <div className="flex items-center gap-2 text-surface-300">
                  <span className="text-emerald-400 font-bold">[05]</span> ActionPlan Created: plan_rec_cart_019 (Status: PROPOSED)
                </div>
                <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <span>[06]</span> Policy Engine: 9 rules verified & passed (10% &le; 15% max limit)
                </div>
                <div className="flex items-center gap-2 text-amber-300 font-semibold">
                  <span>[07]</span> Risk Engine: Classified as MEDIUM risk &rarr; HITL Approval Required
                </div>
                <div className="flex items-center gap-2 text-blue-300 font-semibold">
                  <span>[08]</span> Approval: Signed off by admin@techmart.in
                </div>
                <div className="flex items-center gap-2 text-emerald-400 font-semibold">
                  <span>[09]</span> Execution: apply_cart_recovery_offer tool executed atomically
                </div>
                <div className="flex items-center gap-2 text-emerald-400 font-bold">
                  <span>[10]</span> Outcome: 3 recovered orders, +₹8,865 net impact (OBSERVED)
                </div>
                <div className="flex items-center gap-2 text-purple-400 font-bold">
                  <span>[11]</span> Attribution: DETERMINISTIC EVENT LINK verified
                </div>
                <div className="flex items-center gap-2 text-brand-300 font-bold">
                  <span>[12]</span> Audit Log: Immutable cryptographic ledger entry written
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
