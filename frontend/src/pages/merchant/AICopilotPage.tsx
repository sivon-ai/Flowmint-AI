import { useState, useEffect, useRef } from 'react';
import { api } from '../../lib/api';
import type { AgentChatResponse, AgentSessionItem, ToolCallInfo } from '../../types';
import {
  Bot,
  Send,
  Sparkles,
  TrendingUp,
  Package,
  Clock,
  Layers,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  PlusCircle,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  agentName?: string;
  traceId?: string;
  toolCalls?: ToolCallInfo[];
  structuredData?: any;
  latencyMs?: number;
  timestamp: string;
}

const SAMPLE_PROMPTS = [
  { label: 'Revenue Overview', query: 'What is our total revenue and order summary?' },
  { label: 'Cross-Sell Bundles', query: 'Recommend frequently bought together bundles for our catalog' },
  { label: 'Recover Carts', query: 'Propose a recovery strategy for abandoned checkouts' },
  { label: 'Payment Failures', query: 'How many failed payment attempts occurred this month?' },
  { label: 'Top Products', query: 'Which are our top selling items by revenue?' },
  { label: 'Find Inventory', query: 'Search for active laptop products in catalog' },
];

export default function AICopilotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<AgentSessionItem[]>([]);
  const [agentMode, setAgentMode] = useState<'chat' | 'growth' | 'recovery' | 'analytics' | 'buyer'>('chat');
  const [copiedTrace, setCopiedTrace] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load past sessions
  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const loadSessions = async () => {
    try {
      const res = await api.get<AgentSessionItem[]>('/agents/sessions?limit=10');
      if (res.data) {
        setSessions(res.data);
      }
    } catch (e) {
      console.error('Failed to load agent sessions', e);
    }
  };

  const handleStartNewSession = () => {
    setSessionId(null);
    setMessages([]);
    setErrorMsg(null);
  };

  const handleCopyTrace = (traceId: string) => {
    navigator.clipboard.writeText(traceId);
    setCopiedTrace(traceId);
    setTimeout(() => setCopiedTrace(null), 2000);
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputValue).trim();
    if (!text || loading) return;

    setErrorMsg(null);
    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    if (!textToSend) setInputValue('');
    setLoading(true);

    try {
      const endpoint =
        agentMode === 'growth'
          ? '/agents/growth'
          : agentMode === 'recovery'
          ? '/agents/recovery'
          : agentMode === 'analytics'
          ? '/agents/analytics'
          : agentMode === 'buyer'
          ? '/agents/buyer'
          : '/agents/chat';

      const res = await api.post<AgentChatResponse>(endpoint, {
        message: text,
        session_id: sessionId,
      });

      if (res.data) {
        setSessionId(res.data.session_id);
        const botMsg: ChatMessage = {
          id: `bot_${Date.now()}`,
          role: 'assistant',
          content: res.data.response,
          agentName: res.data.agent_name,
          traceId: res.data.trace_id,
          toolCalls: res.data.tool_calls || [],
          structuredData: res.data.structured_data,
          latencyMs: res.data.latency_ms,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setMessages(prev => [...prev, botMsg]);
        loadSessions();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to process AI agent request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold text-white">AI Copilot</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-500/10 text-brand-400 border border-brand-500/20">
              Multi-Agent Revenue Intelligence
            </span>
          </div>
          <p className="text-surface-300 mt-1">
            Authoritative, read-only conversational intelligence and decision engine for revenue growth & recovery
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {/* Agent Mode Selector */}
          <div className="flex flex-wrap bg-surface-900 border border-surface-700/60 rounded-lg p-1 text-xs">
            <button
              onClick={() => setAgentMode('chat')}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                agentMode === 'chat'
                  ? 'bg-brand-600 text-white font-medium'
                  : 'text-surface-300 hover:text-white'
              }`}
            >
              Auto Router
            </button>
            <button
              onClick={() => setAgentMode('growth')}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                agentMode === 'growth'
                  ? 'bg-brand-600 text-white font-medium'
                  : 'text-surface-300 hover:text-white'
              }`}
            >
              Growth Agent
            </button>
            <button
              onClick={() => setAgentMode('recovery')}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                agentMode === 'recovery'
                  ? 'bg-brand-600 text-white font-medium'
                  : 'text-surface-300 hover:text-white'
              }`}
            >
              Recovery Agent
            </button>
            <button
              onClick={() => setAgentMode('analytics')}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                agentMode === 'analytics'
                  ? 'bg-brand-600 text-white font-medium'
                  : 'text-surface-300 hover:text-white'
              }`}
            >
              Analytics
            </button>
            <button
              onClick={() => setAgentMode('buyer')}
              className={`px-2.5 py-1 rounded-md transition-colors ${
                agentMode === 'buyer'
                  ? 'bg-brand-600 text-white font-medium'
                  : 'text-surface-300 hover:text-white'
              }`}
            >
              Buyer
            </button>
          </div>

          <button
            onClick={handleStartNewSession}
            className="btn-secondary flex items-center gap-1.5 text-xs py-1.5"
            title="Start new conversation"
          >
            <PlusCircle className="w-4 h-4" />
            New Chat
          </button>
        </div>
      </div>

      {/* Main Chat Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Chat Stream (3 Cols) */}
        <div className="lg:col-span-3 card flex flex-col h-[650px] p-0 overflow-hidden">
          {/* Messages Scroll Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-4">
                <div className="w-14 h-14 rounded-2xl bg-brand-600/10 border border-brand-500/20 flex items-center justify-center text-brand-400">
                  <Sparkles className="w-7 h-7" />
                </div>
                <div className="max-w-md">
                  <h3 className="text-lg font-semibold text-white">Ask Flowmint AI</h3>
                  <p className="text-surface-300 text-sm mt-1">
                    Ask questions about revenue, customer conversion, product performance, or catalog
                    availability. Answers are grounded in real-time SQL data.
                  </p>
                </div>

                {/* Sample Prompt Chips */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg mt-4">
                  {SAMPLE_PROMPTS.map(p => (
                    <button
                      key={p.label}
                      onClick={() => handleSendMessage(p.query)}
                      className="p-3 text-left bg-surface-800/60 hover:bg-surface-800 border border-surface-700/60 rounded-xl transition-all group"
                    >
                      <div className="text-xs font-semibold text-brand-400 group-hover:text-brand-300 flex items-center justify-between">
                        {p.label}
                        <ArrowRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                      <div className="text-xs text-surface-300 mt-1 line-clamp-1">{p.query}</div>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map(m => (
                <div
                  key={m.id}
                  className={`flex flex-col ${
                    m.role === 'user' ? 'items-end' : 'items-start'
                  } space-y-2`}
                >
                  {/* Message Bubble */}
                  <div
                    className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-brand-600 text-white rounded-br-none shadow-lg'
                        : 'bg-surface-800/90 border border-surface-700/60 text-surface-100 rounded-bl-none shadow-md'
                    }`}
                  >
                    {/* Metadata Header for Assistant */}
                    {m.role === 'assistant' && (
                      <div className="flex items-center justify-between gap-3 pb-2.5 mb-2.5 border-b border-surface-700/50 text-xs">
                        <div className="flex items-center gap-2">
                          <Bot className="w-4 h-4 text-brand-400" />
                          <span className="font-semibold text-white capitalize">
                            {m.agentName?.replace('_', ' ') || 'AI Agent'}
                          </span>
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-700 text-[10px] text-emerald-400 font-mono">
                            <ShieldCheck className="w-3 h-3" />
                            Read-Only
                          </span>
                        </div>
                        {m.latencyMs !== undefined && (
                          <div className="flex items-center gap-1 text-surface-400 text-[11px]">
                            <Clock className="w-3 h-3" />
                            {m.latencyMs}ms
                          </div>
                        )}
                      </div>
                    )}

                    {/* Content */}
                    <div className="whitespace-pre-wrap">{m.content}</div>

                    {/* Tool Activity Indicator */}
                    {m.toolCalls && m.toolCalls.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-surface-700/50">
                        <div className="text-[11px] font-semibold text-surface-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                          <Layers className="w-3 h-3 text-brand-400" />
                          Grounded Tool Execution
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {m.toolCalls.map((tc, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-900 border border-surface-700 text-xs text-surface-200"
                            >
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                              <span className="font-mono text-brand-300">{tc.tool}</span>
                              <span className="text-surface-400 text-[10px]">
                                ({tc.latency_ms}ms)
                              </span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Plan Card (Phase 2B Recommendation Only) */}
                    {m.structuredData?.action_plan && (
                      <div className="mt-3 p-3.5 rounded-xl bg-surface-950 border border-brand-500/40 text-xs space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-brand-400 uppercase tracking-wider flex items-center gap-1.5">
                            <Sparkles className="w-3.5 h-3.5" />
                            Proposed Action Plan (Recommendation Only)
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-brand-500/20 text-brand-400 border border-brand-500/30">
                            {m.structuredData.action_plan.status?.toUpperCase() || 'PROPOSED'}
                          </span>
                        </div>
                        <div className="text-white font-medium">
                          {m.structuredData.action_plan.action_type?.replace(/_/g, ' ').toUpperCase()}
                        </div>
                        <div className="text-surface-300">
                          {m.structuredData.action_plan.recommendation_reason}
                        </div>
                        <div className="pt-2 border-t border-surface-800 flex justify-between text-[11px] text-surface-400">
                          <span>Target: <strong className="text-white">{m.structuredData.action_plan.target}</strong></span>
                          <span>Requires Approval: <strong className="text-warning-400">YES (Policy-Gated)</strong></span>
                        </div>
                      </div>
                    )}

                    {/* Structured Result Renderers */}
                    {m.structuredData && (
                      <div className="mt-3 pt-3 border-t border-surface-700/50">
                        <details className="text-xs">
                          <summary className="font-medium text-brand-400 cursor-pointer hover:underline mb-2">
                            View Structured Payload
                          </summary>
                          <pre className="bg-surface-950 p-3 rounded-lg overflow-x-auto text-[11px] text-surface-300 font-mono">
                            {JSON.stringify(m.structuredData, null, 2)}
                          </pre>
                        </details>
                      </div>
                    )}

                    {/* Trace ID Bar */}
                    {m.traceId && (
                      <div className="mt-2.5 pt-2 flex items-center justify-between text-[11px] text-surface-400 border-t border-surface-700/30">
                        <span className="font-mono text-[10px]">Trace: {m.traceId}</span>
                        <button
                          onClick={() => handleCopyTrace(m.traceId!)}
                          className="hover:text-white flex items-center gap-1 transition-colors"
                          title="Copy Trace ID for audit"
                        >
                          {copiedTrace === m.traceId ? (
                            <Check className="w-3 h-3 text-emerald-400" />
                          ) : (
                            <Copy className="w-3 h-3" />
                          )}
                          <span>{copiedTrace === m.traceId ? 'Copied' : 'Copy'}</span>
                        </button>
                      </div>
                    )}
                  </div>
                  <span className="text-[10px] text-surface-400 px-1">{m.timestamp}</span>
                </div>
              ))
            )}

            {/* Loading indicator */}
            {loading && (
              <div className="flex items-center gap-3 p-4 bg-surface-800/50 rounded-2xl max-w-sm border border-surface-700/40 animate-pulse">
                <Bot className="w-5 h-5 text-brand-400 animate-spin" />
                <span className="text-xs text-surface-300 font-medium">
                  {agentMode === 'analytics'
                    ? 'Analytics Agent retrieving real-time metrics...'
                    : agentMode === 'buyer'
                    ? 'Buyer Agent searching catalog & inventory...'
                    : 'Orchestrating agent & executing verified tools...'}
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Error Banner */}
          {errorMsg && (
            <div className="mx-6 mb-2 p-3 bg-red-950/50 border border-red-800/50 rounded-lg flex items-center gap-2 text-xs text-red-300">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Chat Input Bar */}
          <div className="p-4 bg-surface-900 border-t border-surface-700/60">
            <form
              onSubmit={e => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center gap-2"
            >
              <input
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                placeholder={
                  agentMode === 'analytics'
                    ? 'Ask about revenue, orders, payments, or conversion...'
                    : agentMode === 'buyer'
                    ? 'Search catalog, check stock, or compare products...'
                    : 'Ask anything (e.g., "Why did revenue drop yesterday?")...'
                }
                disabled={loading}
                className="input-field flex-1 text-sm py-2.5 px-4"
              />
              <button
                type="submit"
                disabled={loading || !inputValue.trim()}
                className="btn-primary py-2.5 px-4 flex items-center gap-2 disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span>Send</span>
              </button>
            </form>
          </div>
        </div>

        {/* Sidebar: Context & Recent Sessions (1 Col) */}
        <div className="space-y-4">
          {/* Security & Isolation Guardrail Card */}
          <div className="card p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Security Guardrails
            </div>
            <ul className="text-xs text-surface-300 space-y-2">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Tenant isolation enforced at DB level</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Strictly read-only execution</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Prompt injection defense active</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Every trace logged for audit</span>
              </li>
            </ul>
          </div>

          {/* Recent Sessions Card */}
          <div className="card p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-white">Recent Sessions</span>
              <span className="text-[11px] text-surface-400">{sessions.length} recorded</span>
            </div>

            {sessions.length === 0 ? (
              <div className="text-xs text-surface-400 py-3 text-center">
                No past sessions recorded
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {sessions.map(s => (
                  <div
                    key={s.id}
                    onClick={() => setSessionId(s.id)}
                    className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-colors ${
                      sessionId === s.id
                        ? 'bg-brand-600/15 border-brand-500/40 text-brand-300'
                        : 'bg-surface-800/40 border-surface-700/50 text-surface-300 hover:bg-surface-800'
                    }`}
                  >
                    <div className="font-medium truncate text-white">
                      {s.title || 'Conversation Session'}
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[10px] text-surface-400">
                      <span>{s.agent_name}</span>
                      <span>{new Date(s.updated_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
