import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, AlertTriangle, TrendingUp, Lightbulb, Shield, Zap,
  ChevronRight, RefreshCw, Sparkles, Activity, Clock,
  CheckCircle, Eye
} from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar } from 'recharts';
import { useTheme } from '../context/ThemeContext';
import { aiInsights } from '../lib/data';

const stagger = { animate: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } } };
const item = {
  initial: { opacity: 0, y: 18 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 26 } },
};

const insightConfig = {
  anomaly: { icon: AlertTriangle, color: '#ef4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.2)', label: 'Anomaly' },
  forecast: { icon: TrendingUp, color: '#00b8e6', bg: 'rgba(0,184,230,0.08)', border: 'rgba(0,184,230,0.2)', label: 'Forecast' },
  recommendation: { icon: Lightbulb, color: '#00e67a', bg: 'rgba(0,230,122,0.08)', border: 'rgba(0,230,122,0.2)', label: 'Rec.' },
  alert: { icon: Shield, color: '#ffb800', bg: 'rgba(255,184,0,0.08)', border: 'rgba(255,184,0,0.2)', label: 'Alert' },
};

const aiConfidenceTrend = Array.from({ length: 14 }, (_, i) => ({
  d: i + 1, v: 94 + Math.sin(i * 0.6) * 2 + i * 0.3,
}));

const radarData = [
  { metric: 'Fraud', value: 97 },
  { metric: 'Revenue', value: 89 },
  { metric: 'Risk', value: 84 },
  { metric: 'Growth', value: 91 },
  { metric: 'Ops', value: 78 },
  { metric: 'Customer', value: 86 },
];

const EXTRA_INSIGHTS = [
  {
    id: '5', type: 'recommendation' as const,
    title: 'Expand digital wallet adoption program',
    description: 'Digital wallet users show 2.4x higher lifetime value. Targeted incentives could convert 18% of traditional card holders.',
    confidence: 91.2, impact: 'high' as const, timestamp: '2 hr ago',
  },
  {
    id: '6', type: 'forecast' as const,
    title: 'December transaction volume surge predicted',
    description: 'Historical patterns + macro indicators suggest a 28% surge in December. Pre-allocate capacity by Nov 28.',
    confidence: 86.4, impact: 'high' as const, timestamp: '3 hr ago',
  },
];

const allInsights = [...aiInsights, ...EXTRA_INSIGHTS];

export default function Insights() {
  const { isDark } = useTheme();
  const [filter, setFilter] = useState<string>('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await new Promise(r => setTimeout(r, 1200));
    setRefreshing(false);
  };

  const filtered = allInsights.filter(i => filter === 'all' || i.type === filter);

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
            Autonomous intelligence · {allInsights.length} active signals
          </p>
        </div>
        <div className="flex items-center gap-2">
          <motion.button onClick={handleRefresh}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', color: 'var(--text-secondary)' }}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
            <motion.div animate={refreshing ? { rotate: 360 } : {}} transition={{ duration: 0.8, repeat: refreshing ? Infinity : 0, ease: 'linear' }}>
              <RefreshCw size={12} />
            </motion.div>
            Refresh
          </motion.button>
          <motion.button className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 20px rgba(0,184,230,0.3)' }}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
            <Sparkles size={12} /> Generate Report
          </motion.button>
        </div>
      </motion.div>

      {/* AI Status cards */}
      <motion.div variants={item} className="grid grid-cols-4 gap-3">
        {[
          { label: 'AI Confidence', value: '99.4%', sub: '+0.2% today', color: '#00b8e6', icon: Brain },
          { label: 'Active Signals', value: '6', sub: '4 high impact', color: '#ef4444', icon: Activity },
          { label: 'Predictions Made', value: '847', sub: 'This month', color: '#00e67a', icon: Zap },
          { label: 'Avg Response', value: '1.2s', sub: 'Query latency', color: '#ffb800', icon: Clock },
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
              <p className="text-xs mt-1" style={{ color: stat.color }}>{stat.sub}</p>
            </div>
          );
        })}
      </motion.div>

      <div className="grid grid-cols-12 gap-4">

        {/* AI Confidence trend */}
        <motion.div variants={item} className="col-span-4 flex flex-col gap-4">
          <div className="rounded-2xl p-5"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
            }}>
            <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>AI Confidence Trend</h3>
            <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>14-day model accuracy</p>
            <div className="h-28">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={aiConfidenceTrend} margin={{ top: 5, right: 5, left: -30, bottom: 0 }}>
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
              <span className="text-xs font-semibold" style={{ color: '#00b8e6' }}>Current: 99.4%</span>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Max: 99.6%</span>
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

        {/* Insight feed */}
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
                  <div className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse" />
                  <p className="text-xs" style={{ color: '#00e67a' }}>Live analysis active</p>
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
            <AnimatePresence>
              {filtered.map((insight, i) => {
                const config = insightConfig[insight.type];
                const Icon = config.icon;
                const isExpanded = expanded === insight.id;

                return (
                  <motion.div
                    key={insight.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ delay: i * 0.07 }}
                    className="relative"
                    style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(0,0,0,0.04)' }}
                  >
                    <div
                      className="p-5 cursor-pointer"
                      onClick={() => setExpanded(isExpanded ? null : insight.id)}
                    >
                      <div className="flex gap-3">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                          style={{ background: config.bg, border: `1px solid ${config.border}` }}>
                          <Icon size={15} style={{ color: config.color }} />
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="px-2 py-0.5 rounded text-2xs font-bold"
                              style={{ background: config.bg, color: config.color }}>
                              {config.label.toUpperCase()}
                            </span>
                            <span className={`px-2 py-0.5 rounded text-2xs font-bold ${
                              insight.impact === 'high' ? 'bg-red-500/10 text-red-400' : 'bg-yellow-500/10 text-yellow-400'
                            }`}>{insight.impact} impact</span>
                            <span className="text-2xs ml-auto" style={{ color: 'var(--text-muted)' }}>{insight.timestamp}</span>
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
                                    style={{ background: `${config.color}18`, color: config.color, border: `1px solid ${config.border}` }}
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
                                  style={{ background: config.color }} />
                              </div>
                              <span className="text-2xs font-semibold" style={{ color: config.color }}>
                                {insight.confidence}% confidence
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
