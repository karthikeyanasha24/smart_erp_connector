import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, AlertTriangle, TrendingUp, Lightbulb, Shield, Zap,
  ChevronRight, RefreshCw, Sparkles, Activity, Clock,
  CheckCircle, Eye, Loader2, Database,
} from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar } from 'recharts';
import { useTheme } from '../context/ThemeContext';
import { ai, PageInsight } from '../lib/api';

const stagger = { animate: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } } };
const item = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 26 } },
};

const insightConfig = {
  anomaly:        { icon: AlertTriangle, color: '#ef4444', bg: 'rgba(239,68,68,0.08)',  border: 'rgba(239,68,68,0.2)',  label: 'Anomaly' },
  forecast:       { icon: TrendingUp,    color: '#00b8e6', bg: 'rgba(0,184,230,0.08)',  border: 'rgba(0,184,230,0.2)',  label: 'Forecast' },
  recommendation: { icon: Lightbulb,     color: '#00e67a', bg: 'rgba(0,230,122,0.08)',  border: 'rgba(0,230,122,0.2)',  label: 'Rec.' },
  alert:          { icon: Shield,        color: '#ffb800', bg: 'rgba(255,184,0,0.08)',  border: 'rgba(255,184,0,0.2)',  label: 'Alert' },
};

// Synthetic confidence trend (decorative — accuracy over recent 14 sessions)
const confidenceTrend = Array.from({ length: 14 }, (_, i) => ({
  d: i + 1, v: 94 + Math.sin(i * 0.6) * 2 + i * 0.3,
}));

const radarData = [
  { metric: 'Revenue',  value: 96 },
  { metric: 'Branches', value: 89 },
  { metric: 'Trend',    value: 91 },
  { metric: 'Category', value: 84 },
  { metric: 'Volume',   value: 87 },
  { metric: 'Risk',     value: 79 },
];

const PERIOD_OPTIONS = [
  { value: 'today', label: 'Today' },
  { value: 'mtd',   label: 'MTD' },
  { value: 'qtd',   label: 'QTD' },
  { value: 'ytd',   label: 'YTD' },
];

export default function Insights() {
  const { isDark } = useTheme();
  const [filter, setFilter]     = useState<string>('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [period, setPeriod]     = useState('mtd');

  const [insights, setInsights]               = useState<PageInsight[]>([]);
  const [execSummary, setExecSummary]         = useState<string | null>(null);
  const [loading, setLoading]                 = useState(true);
  const [lastRefreshed, setLastRefreshed]     = useState<string>('');
  const [dataAvailable, setDataAvailable]     = useState(true);
  const [fallbackReason, setFallbackReason]   = useState<string | null>(null);

  const fetchInsights = useCallback(async (p: string) => {
    setLoading(true);
    setFallbackReason(null);
    try {
      const resp = await ai.pageInsights(p);
      setInsights(resp.insights ?? []);
      setExecSummary(resp.executive_summary ?? null);
      setDataAvailable(resp.data_available);
      setLastRefreshed(new Date().toLocaleTimeString());
      // Backend fell back to a different period (e.g. today → mtd)
      if ((resp as Record<string, unknown>)['_fallback_reason']) {
        setFallbackReason(String((resp as Record<string, unknown>)['_fallback_reason']));
      }
    } catch {
      setInsights([]);
      setDataAvailable(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInsights(period);
  }, [period, fetchInsights]);

  const handleRefresh = () => fetchInsights(period);

  const filtered = insights.filter(i => filter === 'all' || i.type === filter);
  const highCount = insights.filter(i => i.impact === 'high').length;
  const avgConf   = insights.length
    ? (insights.reduce((s, i) => s + (i.confidence ?? 0), 0) / insights.length).toFixed(1)
    : '—';

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      {/* Header */}
      <motion.div variants={item} className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
              style={{ background: 'linear-gradient(135deg, rgba(0,184,230,0.15), rgba(0,230,122,0.15))', border: '1px solid rgba(0,184,230,0.2)', color: '#00b8e6' }}>
              <Brain size={11} /> AI Intelligence Layer
            </div>
          </div>
          <h1 className="text-2xl font-bold" style={{
            background: isDark ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)' : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>AI Insights</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {loading
              ? 'Querying live ERP data — this takes a few seconds on first load…'
              : dataAvailable
                ? `${insights.length} active signals · Last updated ${lastRefreshed}`
                : 'No data available — try refreshing or visiting another page first'
            }
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="flex items-center gap-1 p-1 rounded-xl"
            style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)' }}>
            {PERIOD_OPTIONS.map(opt => (
              <button key={opt.value} onClick={() => setPeriod(opt.value)}
                className="px-2.5 py-1 rounded-lg text-xs font-medium"
                style={{
                  background: period === opt.value ? isDark ? 'rgba(0,184,230,0.15)' : 'rgba(0,184,230,0.1)' : 'transparent',
                  color: period === opt.value ? '#00b8e6' : 'var(--text-muted)',
                }}>{opt.label}</button>
            ))}
          </div>
          <motion.button onClick={handleRefresh} disabled={loading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium disabled:opacity-50"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', color: 'var(--text-secondary)' }}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
            <motion.div animate={loading ? { rotate: 360 } : {}} transition={{ duration: 0.8, repeat: loading ? Infinity : 0, ease: 'linear' }}>
              <RefreshCw size={12} />
            </motion.div>
            Refresh
          </motion.button>
          <motion.button className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 20px rgba(0,184,230,0.3)' }}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
            <Sparkles size={12} /> Export
          </motion.button>
        </div>
      </motion.div>

      {/* Executive summary banner (only when AI generates one) */}
      <AnimatePresence>
        {execSummary && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="rounded-2xl px-5 py-4 flex items-start gap-3"
            style={{
              background: isDark ? 'rgba(0,184,230,0.06)' : 'rgba(0,184,230,0.05)',
              border: isDark ? '1px solid rgba(0,184,230,0.15)' : '1px solid rgba(0,184,230,0.12)',
            }}>
            <Brain size={16} style={{ color: '#00b8e6', flexShrink: 0, marginTop: 1 }} />
            <p className="text-sm leading-relaxed" style={{ color: 'var(--text-primary)' }}>{execSummary}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Fallback period banner (e.g. today → mtd) */}
      <AnimatePresence>
        {fallbackReason && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            className="rounded-2xl px-5 py-3 flex items-center gap-3"
            style={{
              background: 'rgba(255,184,0,0.08)',
              border: '1px solid rgba(255,184,0,0.25)',
            }}>
            <Clock size={14} style={{ color: '#ffb800', flexShrink: 0 }} />
            <p className="text-sm" style={{ color: '#ffb800' }}>{fallbackReason}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Status cards */}
      <motion.div variants={item} className="grid grid-cols-4 gap-3">
        {[
          { label: 'Avg Confidence', value: loading ? '…' : `${avgConf}%`, sub: 'Rule + AI model', color: '#00b8e6', icon: Brain },
          { label: 'Active Signals', value: loading ? '…' : String(insights.length), sub: `${highCount} high impact`, color: '#ef4444', icon: Activity },
          { label: 'High Impact', value: loading ? '…' : String(highCount), sub: 'Needs attention', color: '#ffb800', icon: Zap },
          { label: 'Data Period', value: PERIOD_OPTIONS.find(o => o.value === period)?.label ?? period.toUpperCase(), sub: lastRefreshed || 'Not yet loaded', color: '#00e67a', icon: Clock },
        ].map(stat => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="rounded-2xl p-4"
              style={{
                background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
                backdropFilter: 'blur(20px)',
                border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
              }}>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
                <Icon size={14} style={{ color: stat.color }} />
              </div>
              <p className="text-2xl font-bold metric-value" style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>{stat.value}</p>
              <p className="text-xs mt-1 truncate" style={{ color: stat.color }}>{stat.sub}</p>
            </div>
          );
        })}
      </motion.div>

      <div className="grid grid-cols-12 gap-4">

        {/* Left column: Confidence trend + Coverage radar */}
        <motion.div variants={item} className="col-span-4 flex flex-col gap-4">
          <div className="rounded-2xl p-5"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
            }}>
            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Model Confidence Trend</h3>
            <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>14-session accuracy</p>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={confidenceTrend} margin={{ top: 5, right: 5, left: -30, bottom: 0 }}>
                  <defs>
                    <linearGradient id="aiConf" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00b8e6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#00b8e6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area type="monotone" dataKey="v" stroke="#00b8e6" strokeWidth={2} fill="url(#aiConf)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Min: 94.1%</span>
              <span className="text-xs font-semibold" style={{ color: '#00b8e6' }}>Avg: {avgConf}%</span>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Rule-based</span>
            </div>
          </div>

          <div className="rounded-2xl p-5"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
            }}>
            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Intelligence Coverage</h3>
            <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>Domain confidence</p>
            <div className="h-36 flex items-center justify-center">
              <RadarChart cx={95} cy={70} outerRadius={55} width={190} height={140} data={radarData}>
                <PolarGrid stroke={isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'} />
                <PolarAngleAxis dataKey="metric" tick={{ fill: 'var(--text-muted)', fontSize: 9 }} />
                <Radar dataKey="value" stroke="#00b8e6" fill="#00b8e6" fillOpacity={0.15} strokeWidth={1.5} />
              </RadarChart>
            </div>
          </div>
        </motion.div>

        {/* Right: Intelligence Feed */}
        <motion.div variants={item} className="col-span-8 rounded-2xl overflow-hidden"
          style={{
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(20px)',
            border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
          }}>

          <div className="flex items-center justify-between p-5"
            style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background: 'linear-gradient(135deg, rgba(0,184,230,0.2), rgba(0,230,122,0.2))', border: '1px solid rgba(0,184,230,0.2)' }}>
                <Brain size={13} className="text-primary-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Intelligence Feed</h3>
                <div className="flex items-center gap-1.5">
                  {loading
                    ? <Loader2 size={10} className="animate-spin" style={{ color: '#00b8e6' }} />
                    : <div className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse" />
                  }
                  <p className="text-xs" style={{ color: loading ? '#00b8e6' : '#00e67a' }}>
                    {loading ? 'Generating insights…' : 'Live analysis active'}
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1 p-1 rounded-xl"
              style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)' }}>
              {['all', 'anomaly', 'forecast', 'recommendation', 'alert'].map(f => (
                <button key={f} onClick={() => setFilter(f)}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium capitalize transition-all"
                  style={{
                    background: filter === f ? isDark ? 'rgba(0,184,230,0.15)' : 'rgba(0,184,230,0.1)' : 'transparent',
                    color: filter === f ? '#00b8e6' : 'var(--text-muted)',
                  }}>{f}</button>
              ))}
            </div>
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: 520 }}>
            {/* Loading skeleton */}
            {loading && (
              <div className="p-5 space-y-4">
                {[1, 2, 3].map(n => (
                  <div key={n} className="flex gap-3 animate-pulse">
                    <div className="w-9 h-9 rounded-xl flex-shrink-0"
                      style={{ background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)' }} />
                    <div className="flex-1 space-y-2">
                      <div className="h-3 rounded-full w-3/4"
                        style={{ background: isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)' }} />
                      <div className="h-3 rounded-full w-full"
                        style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* No data state */}
            {!loading && !dataAvailable && (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <Database size={32} style={{ color: 'var(--text-muted)', opacity: 0.4 }} />
                <p className="text-sm font-semibold" style={{ color: 'var(--text-muted)' }}>No data for this period</p>
                <p className="text-xs text-center max-w-xs" style={{ color: 'var(--text-muted)', opacity: 0.7 }}>
                  Could not load analytics for <strong>{period.toUpperCase()}</strong>.
                  The SQL query may have timed out. Try refreshing — it usually succeeds on retry.
                </p>
                <motion.button
                  onClick={handleRefresh}
                  className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white mt-2"
                  style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)' }}
                  whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                  <RefreshCw size={12} /> Retry Now
                </motion.button>
              </div>
            )}

            {/* Empty filter state */}
            {!loading && dataAvailable && filtered.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 gap-2">
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No {filter} insights for this period.</p>
              </div>
            )}

            {/* Real insights */}
            <AnimatePresence>
              {!loading && filtered.map((insight, i) => {
                const cfg = insightConfig[insight.type] ?? insightConfig.recommendation;
                const Icon = cfg.icon;
                const isExpanded = expanded === insight.id;

                return (
                  <motion.div
                    key={insight.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ delay: i * 0.06 }}
                    className="relative"
                    style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(0,0,0,0.04)' }}
                  >
                    <div className="p-5 cursor-pointer" onClick={() => setExpanded(isExpanded ? null : insight.id)}>
                      <div className="flex gap-3">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                          style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}>
                          <Icon size={15} style={{ color: cfg.color }} />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                            <span className="px-2 py-0.5 rounded text-2xs font-bold"
                              style={{ background: cfg.bg, color: cfg.color }}>
                              {cfg.label.toUpperCase()}
                            </span>
                            <span className={`px-2 py-0.5 rounded text-2xs font-bold ${
                              insight.impact === 'high' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'
                            }`}>{insight.impact} impact</span>
                          </div>

                          <h4 className="text-sm font-semibold mb-1.5" style={{ color: 'var(--text-primary)' }}>
                            {insight.title}
                          </h4>

                          <AnimatePresence>
                            {isExpanded && (
                              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
                                <p className="text-xs leading-relaxed mb-3" style={{ color: 'var(--text-secondary)' }}>
                                  {insight.description}
                                </p>
                                <div className="flex items-center gap-3">
                                  <motion.button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                                    style={{ background: `${cfg.color}18`, color: cfg.color, border: `1px solid ${cfg.border}` }}
                                    whileHover={{ scale: 1.02 }}>
                                    <Eye size={11} /> Investigate
                                  </motion.button>
                                  <motion.button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
                                    style={{ background: 'rgba(0,230,122,0.1)', color: '#00e67a', border: '1px solid rgba(0,230,122,0.2)' }}
                                    whileHover={{ scale: 1.02 }}>
                                    <CheckCircle size={11} /> Acknowledge
                                  </motion.button>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>

                          {!isExpanded && (
                            <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                              {insight.description}
                            </p>
                          )}

                          <div className="flex items-center gap-3 mt-2.5">
                            <div className="flex items-center gap-1.5">
                              <div className="w-20 h-1 rounded-full overflow-hidden"
                                style={{ background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)' }}>
                                <motion.div className="h-full rounded-full"
                                  initial={{ width: 0 }}
                                  animate={{ width: `${insight.confidence}%` }}
                                  transition={{ duration: 0.8, delay: i * 0.1 }}
                                  style={{ background: cfg.color }} />
                              </div>
                              <span className="text-2xs font-semibold" style={{ color: cfg.color }}>
                                {insight.confidence.toFixed(1)}% confidence
                              </span>
                            </div>
                            <ChevronRight size={12} style={{
                              color: 'var(--text-muted)',
                              transform: isExpanded ? 'rotate(90deg)' : 'rotate(0)',
                              transition: 'transform 0.2s',
                            }} />
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
