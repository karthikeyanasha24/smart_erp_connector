import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AreaChart, Area, ResponsiveContainer, XAxis, YAxis, BarChart, Bar,
  LineChart, Line, PieChart, Pie, Cell, Tooltip, Legend,
} from 'recharts';
import {
  Send, Sparkles, Code2, BarChart2, Loader2,
  Zap, Brain, Terminal, Copy, Check, ArrowRight, Database, ShieldCheck, ChevronDown,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { ai, NLQResponse, fetchPublicHealth } from '../lib/api';
import {
  buildNLQVisualization,
  formatChartValue,
  type ChartPoint,
  type KPICard,
} from '../lib/nlqVisualization';
import verifiedQueriesFallback from '../data/verified_nlq_queries.json';

const PIE_COLORS = ['#00b8e6', '#00e67a', '#ffb800', '#a78bfa', '#f472b6', '#fb923c', '#38bdf8', '#4ade80'];

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  sql?: string;
  chartType?: 'bar' | 'area' | 'line' | 'pie' | 'none';
  chart?: { data: ChartPoint[]; valueKey: string };
  kpiCards?: KPICard[];
  table?: { columns: string[]; rows: string[][] };
  insights?: Array<{ title?: string; description?: string; severity?: string }>;
  thinking?: string;
  faqTemplateId?: string | null;
  provider?: 'claude' | 'openai';
  timestamp: string;
}

function SQLBlock({ sql }: { sql: string }) {
  const { isDark } = useTheme();
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="mt-3 rounded-xl overflow-hidden"
      style={{ background: isDark ? 'rgba(0,0,0,0.4)' : 'rgba(0,0,0,0.05)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.1)' }}>
      <div className="flex items-center justify-between px-4 py-2"
        style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
        <div className="flex items-center gap-2">
          <Terminal size={11} style={{ color: '#00b8e6' }} />
          <span className="text-xs font-semibold font-mono" style={{ color: '#00b8e6' }}>SQL</span>
        </div>
        <motion.button onClick={copy} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
          className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg"
          style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: 'var(--text-muted)' }}>
          {copied ? <Check size={10} /> : <Copy size={10} />}
          {copied ? 'Copied' : 'Copy'}
        </motion.button>
      </div>
      <pre className="p-4 text-xs font-mono overflow-x-auto max-h-48" style={{ color: isDark ? '#a5f3fc' : '#0369a1' }}>{sql}</pre>
    </div>
  );
}

function KPICards({ cards }: { cards: KPICard[] }) {
  const { isDark } = useTheme();
  if (!cards.length) return null;
  return (
    <div className="mt-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
      {cards.map(card => (
        <div key={card.label} className="rounded-xl px-3 py-2.5"
          style={{
            background: isDark ? 'rgba(0,184,230,0.08)' : 'rgba(0,184,230,0.06)',
            border: isDark ? '1px solid rgba(0,184,230,0.15)' : '1px solid rgba(0,184,230,0.12)',
          }}>
          <p className="text-2xs uppercase tracking-wide truncate" style={{ color: 'var(--text-muted)' }} title={card.label}>
            {card.label}
          </p>
          <p className="text-base font-bold mt-0.5 tabular-nums" style={{ color: 'var(--text-primary)' }}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function ResultChart({
  type,
  data,
  valueKey,
}: {
  type: 'bar' | 'area' | 'line' | 'pie';
  data: ChartPoint[];
  valueKey: string;
}) {
  const { isDark } = useTheme();
  if (!data.length) return null;

  const tick = { fill: 'var(--text-muted)', fontSize: 9 };
  const tooltipFmt = (v: number) => [formatChartValue(v), valueKey];

  return (
    <div className="mt-3 rounded-xl p-4"
      style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
      <div className="flex items-center gap-2 mb-3">
        <BarChart2 size={11} style={{ color: '#00b8e6' }} />
        <span className="text-xs font-semibold" style={{ color: '#00b8e6' }}>{valueKey}</span>
      </div>
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          {type === 'pie' ? (
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="label" cx="50%" cy="50%" outerRadius={70} label={({ name, percent }) =>
                `${String(name).slice(0, 8)} ${((percent ?? 0) * 100).toFixed(0)}%`
              }>
                {data.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => formatChartValue(v)} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
            </PieChart>
          ) : type === 'area' ? (
            <AreaChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="aiChartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00b8e6" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#00b8e6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="label" tick={tick} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={tick} axisLine={false} tickLine={false} tickFormatter={formatChartValue} width={48} />
              <Tooltip formatter={tooltipFmt} />
              <Area type="monotone" dataKey="value" stroke="#00b8e6" strokeWidth={2} fill="url(#aiChartGrad)" dot={false} />
            </AreaChart>
          ) : type === 'line' ? (
            <LineChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="label" tick={tick} axisLine={false} tickLine={false} interval="preserveStartEnd" />
              <YAxis tick={tick} axisLine={false} tickLine={false} tickFormatter={formatChartValue} width={48} />
              <Tooltip formatter={tooltipFmt} />
              <Line type="monotone" dataKey="value" stroke="#00e67a" strokeWidth={2} dot={{ r: 2 }} />
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 0 }} barSize={14}>
              <XAxis dataKey="label" tick={tick} axisLine={false} tickLine={false} interval={0} angle={-25} textAnchor="end" height={50} />
              <YAxis tick={tick} axisLine={false} tickLine={false} tickFormatter={formatChartValue} width={48} />
              <Tooltip formatter={tooltipFmt} />
              <Bar dataKey="value" fill="#00b8e6" radius={[4, 4, 0, 0]} opacity={0.85} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ResultTable({ columns, rows }: { columns: string[]; rows: string[][] }) {
  const { isDark } = useTheme();
  return (
    <div className="mt-3 rounded-xl overflow-x-auto"
      style={{ border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)' }}>
      <table className="w-full text-xs min-w-[280px]">
        <thead>
          <tr style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }}>
            {columns.map(col => (
              <th key={col} className="px-3 py-2 text-left font-semibold whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(0,0,0,0.04)' }}>
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 whitespace-nowrap" style={{ color: j === 0 ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ThinkingBubble({ text }: { text: string }) {
  const { isDark } = useTheme();
  return (
    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
      className="mt-2 px-3 py-2 rounded-lg text-xs font-mono flex items-start gap-2"
      style={{ background: isDark ? 'rgba(0,184,230,0.06)' : 'rgba(0,184,230,0.04)', border: isDark ? '1px solid rgba(0,184,230,0.12)' : '1px solid rgba(0,184,230,0.1)', color: '#00b8e6' }}>
      <Brain size={10} className="flex-shrink-0 mt-0.5" />
      <span style={{ opacity: 0.8 }}>{text}</span>
    </motion.div>
  );
}

function nlqToMessage(resp: NLQResponse, id: string, usedProvider: 'claude' | 'openai'): Message {
  const viz = buildNLQVisualization(resp.records ?? [], resp.chart_type);

  const providerLabel = usedProvider === 'openai' ? 'ChatGPT' : 'Claude';
  const thinkingParts = [
    resp.faq_template_id ? `Verified FAQ · ${resp.faq_template_id}` : resp.from_template ? 'Template SQL' : 'Generated SQL',
    `${resp.record_count} rows`,
    resp.period_label || resp.period,
    `${resp.duration_ms}ms`,
    providerLabel,
  ];

  return {
    id,
    role: 'ai',
    content: resp.summary || resp.description || 'Query executed successfully.',
    sql: resp.sql,
    chartType: viz.chartType,
    chart: viz.chartType !== 'none' && viz.chartData.length
      ? { data: viz.chartData, valueKey: viz.valueKey }
      : undefined,
    kpiCards: viz.kpiCards.length ? viz.kpiCards : undefined,
    table: viz.table,
    insights: (resp.insights ?? []) as Message['insights'],
    thinking: thinkingParts.join(' · '),
    faqTemplateId: resp.faq_template_id,
    provider: usedProvider,
    timestamp: new Date().toLocaleTimeString(),
  };
}

export default function AIQuery() {
  const { isDark } = useTheme();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showSQL, setShowSQL] = useState<Record<string, boolean>>({});
  const [suggestions, setSuggestions] = useState<string[]>(verifiedQueriesFallback as string[]);
  const [suggestionFilter, setSuggestionFilter] = useState('');
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [dbConnected, setDbConnected] = useState<boolean | null>(null);
  const [queryCount, setQueryCount] = useState(0);
  const [lastDurationMs, setLastDurationMs] = useState<number | null>(null);
  const [provider, setProvider] = useState<'claude' | 'openai'>('claude');
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    ai.verifiedSuggestions(50)
      .then(r => { if (r.queries?.length) setSuggestions(r.queries); })
      .catch(() => { /* keep JSON fallback */ });
  }, []);

  useEffect(() => {
    fetchPublicHealth().then(h => setDbConnected(h?.mssql?.connected ?? false));
  }, []);

  const filteredSuggestions = suggestions.filter(s =>
    !suggestionFilter.trim() || s.toLowerCase().includes(suggestionFilter.toLowerCase()),
  );

  const sendMessage = useCallback(async (text?: string) => {
    const msg = text ?? input.trim();
    if (!msg || loading) return;
    setInput('');

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: msg,
      timestamp: new Date().toLocaleTimeString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const resp = await ai.query({ query: msg, conversation_id: conversationId, provider });
      if (resp.conversation_id) setConversationId(resp.conversation_id);
      setQueryCount(c => c + 1);
      setLastDurationMs(resp.duration_ms);

      const aiMsg = nlqToMessage(resp, (Date.now() + 1).toString(), provider);
      setMessages(prev => [...prev, aiMsg]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'ai',
        content: `Query failed: ${err instanceof Error ? err.message : 'Unknown error'}. Check login and SQL Server connection.`,
        timestamp: new Date().toLocaleTimeString(),
      }]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, conversationId]);

  const renderAiResults = (msg: Message) => (
    <div className="w-full mt-1 space-y-0">
      {msg.thinking && <ThinkingBubble text={msg.thinking} />}
      {msg.faqTemplateId && (
        <div className="mt-2 inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs font-medium"
          style={{ background: 'rgba(0,230,122,0.1)', color: '#00e67a', border: '1px solid rgba(0,230,122,0.25)' }}>
          <ShieldCheck size={10} />
          Verified FAQ SQL
        </div>
      )}
      {msg.kpiCards && <KPICards cards={msg.kpiCards} />}
      {msg.chart && msg.chartType && msg.chartType !== 'none' && (
        <ResultChart type={msg.chartType as 'bar' | 'area' | 'line' | 'pie'} data={msg.chart.data} valueKey={msg.chart.valueKey} />
      )}
      {msg.table && <ResultTable columns={msg.table.columns} rows={msg.table.rows} />}
      {msg.insights && msg.insights.length > 0 && (
        <div className="mt-2 space-y-1">
          {msg.insights.slice(0, 3).map((ins, i) => (
            <p key={i} className="text-xs px-2 py-1 rounded-lg" style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', color: 'var(--text-secondary)' }}>
              {ins.title ? <span className="font-semibold">{ins.title}: </span> : null}
              {ins.description}
            </p>
          ))}
        </div>
      )}
      {msg.sql && (
        <div>
          <button onClick={() => setShowSQL(prev => ({ ...prev, [msg.id]: !prev[msg.id] }))}
            className="flex items-center gap-1.5 mt-2 text-xs px-2 py-1 rounded-lg"
            style={{ color: '#00b8e6', background: 'rgba(0,184,230,0.08)' }}>
            <Code2 size={10} />
            {showSQL[msg.id] ? 'Hide SQL' : 'View SQL'}
          </button>
          <AnimatePresence>
            {showSQL[msg.id] && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                <SQLBlock sql={msg.sql} />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );

  return (
    <div className="flex gap-4 h-[calc(100vh-108px)]">

      {/* Left: suggestions */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className="w-72 flex-shrink-0 flex flex-col gap-3 min-h-0"
      >
        <div className="rounded-2xl p-4 flex-shrink-0"
          style={{
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(20px)',
            border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
          }}>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, rgba(0,184,230,0.2), rgba(0,230,122,0.2))', border: '1px solid rgba(0,184,230,0.2)' }}>
              <Brain size={16} className="text-primary-400" />
            </div>
            <div>
              <p className="text-xs font-semibold" style={{ color: 'var(--text-primary)' }}>AI Analyst</p>
              <div className="flex items-center gap-1">
                <div className={`w-1.5 h-1.5 rounded-full ${dbConnected ? 'bg-accent-400 animate-pulse' : 'bg-amber-400'}`} />
                <p className="text-2xs" style={{ color: dbConnected ? '#00e67a' : '#ffb800' }}>
                  {dbConnected === null ? 'Checking DB…' : dbConnected ? 'SQL Server connected' : 'DB offline'}
                </p>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Queries this session</span>
              <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{queryCount}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Last response</span>
              <span className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>
                {lastDurationMs != null ? `${(lastDurationMs / 1000).toFixed(1)}s` : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Verified prompts</span>
              <span className="text-xs font-bold" style={{ color: '#00e67a' }}>{suggestions.length}</span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl p-4 flex-1 flex flex-col min-h-0 overflow-hidden"
          style={{
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(20px)',
            border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
          }}>
          <div className="flex items-center gap-1.5 mb-2 flex-shrink-0">
            <ShieldCheck size={12} style={{ color: '#00e67a' }} />
            <p className="text-xs font-semibold" style={{ color: 'var(--text-secondary)' }}>
              Top {suggestions.length} verified queries
            </p>
          </div>
          <input
            type="search"
            placeholder="Filter suggestions…"
            value={suggestionFilter}
            onChange={e => setSuggestionFilter(e.target.value)}
            className="w-full mb-2 px-3 py-1.5 rounded-lg text-xs outline-none flex-shrink-0"
            style={{
              background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
              border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
              color: 'var(--text-primary)',
            }}
          />
          <div className="space-y-1.5 overflow-y-auto flex-1 scrollbar-none pr-0.5">
            {filteredSuggestions.map((s, i) => (
              <motion.button
                key={`${i}-${s.slice(0, 24)}`}
                onClick={() => sendMessage(s)}
                disabled={loading}
                className="w-full text-left px-3 py-2 rounded-xl text-xs flex items-start gap-2 disabled:opacity-50"
                style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}
                whileHover={{ borderColor: 'rgba(0,184,230,0.3)', background: isDark ? 'rgba(0,184,230,0.06)' : 'rgba(0,184,230,0.04)' }}
                whileTap={{ scale: 0.98 }}
              >
                <Zap size={10} className="flex-shrink-0 mt-0.5 text-primary-400" />
                <span style={{ color: 'var(--text-secondary)' }}>{s}</span>
              </motion.button>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Main chat */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
        className="flex-1 flex flex-col rounded-2xl overflow-hidden min-w-0"
        style={{
          background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(20px)',
          border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
        }}
      >
        <div className="flex items-center justify-between px-5 py-3.5 flex-shrink-0"
          style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 16px rgba(0,184,230,0.3)' }}>
              <Sparkles size={14} className="text-white" />
            </div>
            <div>
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>AI Query Workspace</h2>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Verified FAQ SQL → live data → charts & KPI cards</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Provider toggle */}
            <div className="relative">
              <motion.button
                type="button"
                onClick={() => setShowProviderMenu(v => !v)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold"
                style={{
                  background: provider === 'claude'
                    ? 'linear-gradient(135deg, rgba(88,130,255,0.15), rgba(139,92,246,0.15))'
                    : 'linear-gradient(135deg, rgba(16,163,127,0.15), rgba(0,184,230,0.15))',
                  border: provider === 'claude'
                    ? '1px solid rgba(88,130,255,0.35)'
                    : '1px solid rgba(16,163,127,0.35)',
                  color: provider === 'claude' ? '#818cf8' : '#10a37f',
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
              >
                <span className="text-base leading-none">{provider === 'claude' ? '⬡' : '⬢'}</span>
                {provider === 'claude' ? 'Claude' : 'ChatGPT'}
                <ChevronDown size={11} />
              </motion.button>

              <AnimatePresence>
                {showProviderMenu && (
                  <motion.div
                    initial={{ opacity: 0, y: -6, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.96 }}
                    transition={{ duration: 0.12 }}
                    className="absolute right-0 top-full mt-1.5 rounded-xl overflow-hidden z-50 min-w-[160px]"
                    style={{
                      background: isDark ? '#141929' : 'white',
                      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                      boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
                    }}
                    onMouseLeave={() => setShowProviderMenu(false)}
                  >
                    {([
                      { key: 'claude', label: 'Claude', sub: 'Anthropic API', icon: '⬡', color: '#818cf8', border: 'rgba(88,130,255,0.3)' },
                      { key: 'openai', label: 'ChatGPT', sub: 'OpenAI API', icon: '⬢', color: '#10a37f', border: 'rgba(16,163,127,0.3)' },
                    ] as const).map(opt => (
                      <button
                        key={opt.key}
                        type="button"
                        onClick={() => { setProvider(opt.key); setShowProviderMenu(false); }}
                        className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-left"
                        style={{
                          background: provider === opt.key
                            ? isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)'
                            : 'transparent',
                        }}
                      >
                        <span className="text-base">{opt.icon}</span>
                        <div>
                          <p className="text-xs font-semibold" style={{ color: provider === opt.key ? opt.color : 'var(--text-primary)' }}>
                            {opt.label}
                          </p>
                          <p className="text-2xs" style={{ color: 'var(--text-muted)' }}>{opt.sub}</p>
                        </div>
                        {provider === opt.key && (
                          <div className="ml-auto w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: opt.color }} />
                        )}
                      </button>
                    ))}
                    <div className="px-3.5 py-2 border-t" style={{ borderColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
                      <p className="text-2xs" style={{ color: 'var(--text-muted)' }}>
                        Affects AI summary &amp; insights generation. SQL always runs against your ERP.
                      </p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="px-2.5 py-1 rounded-full text-xs font-semibold flex items-center gap-1"
              style={{ background: 'rgba(0,230,122,0.1)', color: '#00e67a', border: '1px solid rgba(0,230,122,0.2)' }}>
              <Database size={10} />
              FAQ templates
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5 scrollbar-none">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-5 py-8">
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="w-20 h-20 rounded-3xl flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, rgba(0,184,230,0.15), rgba(0,230,122,0.15))', border: '1px solid rgba(0,184,230,0.2)' }}>
                <Brain size={36} style={{ color: '#00b8e6' }} />
              </motion.div>
              <div className="text-center max-w-lg">
                <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text-primary)' }}>Ask with verified retail SQL</h3>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  Pick any of the {suggestions.length} tested prompts on the left, or type your own question.
                  Results show KPI cards, charts, and tables from your SQL Server warehouse — not sample data.
                </p>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-w-2xl">
                {suggestions.slice(0, 6).map((s, i) => (
                  <motion.button key={i} onClick={() => sendMessage(s)} disabled={loading}
                    className="px-3 py-2 rounded-xl text-xs flex items-center gap-1.5 max-w-xs text-left disabled:opacity-50"
                    style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', color: 'var(--text-secondary)' }}
                    whileHover={{ borderColor: 'rgba(0,184,230,0.3)', color: '#00b8e6' }}>
                    <ArrowRight size={10} className="flex-shrink-0" />
                    <span className="line-clamp-2">{s}</span>
                  </motion.button>
                ))}
              </div>
            </div>
          )}

          {messages.map(msg => (
            <motion.div key={msg.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0`}
                style={msg.role === 'ai' ? { background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 12px rgba(0,184,230,0.3)' } : { background: 'rgba(0,184,230,0.15)' }}>
                {msg.role === 'ai' ? <Sparkles size={13} className="text-white" /> : <span className="text-xs font-bold text-primary-400">You</span>}
              </div>
              <div className={`max-w-3xl flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                <div className={`rounded-2xl px-4 py-3 ${msg.role === 'user' ? 'rounded-tr-sm' : 'rounded-tl-sm'}`}
                  style={{
                    background: msg.role === 'user'
                      ? 'linear-gradient(135deg, #00b8e6, #0092b8)'
                      : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                    border: msg.role === 'user' ? 'none' : isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
                  }}>
                  <p className="text-sm leading-relaxed" style={{ color: msg.role === 'user' ? 'white' : 'var(--text-primary)' }}>
                    {msg.content}
                  </p>
                </div>
                {msg.role === 'ai' && renderAiResults(msg)}
                <span className="text-2xs mt-1.5 px-1" style={{ color: 'var(--text-muted)' }}>{msg.timestamp}</span>
              </div>
            </motion.div>
          ))}

          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3">
              <div className="w-7 h-7 rounded-xl flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)' }}>
                <Sparkles size={13} className="text-white" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-tl-sm"
                style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)' }}>
                <div className="flex items-center gap-2">
                  <Loader2 size={13} className="animate-spin" style={{ color: '#00b8e6' }} />
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Running verified SQL on warehouse…</span>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="p-4 flex-shrink-0"
          style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
          <div className="flex gap-3 items-end">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="Ask a verified question or type your own…"
              rows={1}
              className="flex-1 px-4 py-3 rounded-2xl text-sm resize-none outline-none scrollbar-none"
              style={{
                background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
                color: 'var(--text-primary)',
                maxHeight: 120,
              }}
            />
            <motion.button
              onClick={() => sendMessage()}
              disabled={!input.trim() || loading}
              className="w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0"
              style={{
                background: input.trim() && !loading ? 'linear-gradient(135deg, #00b8e6, #00e67a)' : isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
              }}
              whileTap={input.trim() && !loading ? { scale: 0.95 } : {}}>
              <Send size={15} className="text-white" />
            </motion.button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
