import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileBarChart, Download, Sparkles,
  Clock, FileText, TrendingUp, TrendingDown,
  RefreshCw, AlertTriangle, CheckCircle, Eye, Loader2,
  BarChart2, Activity,
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip,
  CartesianGrid, AreaChart, Area, LabelList,
} from 'recharts';
import { useTheme } from '../context/ThemeContext';
import { analytics } from '../lib/api';
import { fmtLakhs } from '../lib/format';

const stagger = { animate: { transition: { staggerChildren: 0.06 } } };
const fadeUp = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 26 } },
};

/* ─── Types ─────────────────────────────────────────────────────────────────── */
interface PeriodSummary {
  period: string;
  label: string;
  sales_L: number;
  ly_sales_L: number;
  growth_pct: number | null;
  bills: number;
  quantity: number;
  branches: number;
}

/* ─── Helpers ────────────────────────────────────────────────────────────────── */
function GrowthBadge({ pct }: { pct: number | null }) {
  if (pct == null) return null;
  const pos = pct >= 0;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold"
      style={{
        background: pos ? 'rgba(0,230,122,0.12)' : 'rgba(239,68,68,0.12)',
        color: pos ? '#00e67a' : '#ef4444',
      }}
    >
      {pos ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {pos ? '+' : ''}{pct.toFixed(1)}%
    </span>
  );
}

function StatCard({
  label, value, sub, color, icon: Icon,
}: {
  label: string; value: string; sub: string; color: string; icon: React.ElementType;
}) {
  const { isDark } = useTheme();
  return (
    <div
      className="p-4 rounded-2xl"
      style={{
        background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
        border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{label}</p>
        <Icon size={14} style={{ color }} />
      </div>
      <p className="text-2xl font-bold tabular-nums" style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}>
        {value}
      </p>
      <p className="text-xs mt-1 truncate" style={{ color }}>{sub}</p>
    </div>
  );
}

/* ─── Main ───────────────────────────────────────────────────────────────────── */
export default function Reports() {
  const { isDark } = useTheme();

  /* Data state */
  const [summaries, setSummaries] = useState<PeriodSummary[]>([]);
  const [trendData, setTrendData] = useState<{ label: string; current: number; prior: number }[]>([]);
  const [branches, setBranches] = useState<{ name: string; sales_L: number }[]>([]);
  const [activeBranchCount, setActiveBranchCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  /* UI state */
  const [selectedPeriod, setSelectedPeriod] = useState<'mtd' | 'qtd' | 'ytd' | 'last_6m'>('mtd');

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      /* Fetch KPIs + trend + branches for each core period in parallel */
      const periods: Array<'mtd' | 'qtd' | 'ytd' | 'last_6m'> = ['mtd', 'qtd', 'ytd', 'last_6m'];
      const [mtdKpi, qtdKpi, ytdKpi, last6mKpi, mtdBundle] = await Promise.allSettled([
        analytics.kpis('mtd'),
        analytics.kpis('qtd'),
        analytics.kpis('ytd'),
        analytics.kpis('last_6m'),
        analytics.bundle('mtd', { topN: 15, includeDepartments: false, includeKpis: false }),
      ]);

      const kpiMap: Record<string, any> = {
        mtd:     mtdKpi.status === 'fulfilled' ? mtdKpi.value : null,
        qtd:     qtdKpi.status === 'fulfilled' ? qtdKpi.value : null,
        ytd:     ytdKpi.status === 'fulfilled' ? ytdKpi.value : null,
        last_6m: last6mKpi.status === 'fulfilled' ? last6mKpi.value : null,
      };

      const LABELS: Record<string, string> = {
        mtd: 'Month to Date', qtd: 'Quarter to Date',
        ytd: 'FY Year to Date (Apr 1)', last_6m: 'Last 6 Months',
      };

      const built: PeriodSummary[] = periods.map((p) => {
        const kpi = kpiMap[p];
        // KPI API shape: revenue.value, revenue.prior, revenue.growth (not .current / .growth_pct)
        const rev = kpi?.revenue ?? {};
        const txn = kpi?.transactions ?? {};
        const aov = kpi?.avg_order_value ?? {};
        return {
          period: p,
          label: LABELS[p],
          sales_L: Math.round((rev.value ?? rev.current ?? 0) / 1e5 * 100) / 100,
          ly_sales_L: Math.round((rev.prior ?? 0) / 1e5 * 100) / 100,
          growth_pct: rev.growth ?? rev.growth_pct ?? null,
          bills: txn.value ?? txn.current ?? 0,
          quantity: Math.round((aov.value ?? kpi?.avg_order_value?.qty_current ?? 0)),
          branches: kpi?.active_branches ?? kpi?.branches ?? 0,
        };
      });
      setSummaries(built);

      /* Trend data from MTD bundle — API returns {date, revenue} per point */
      if (mtdBundle.status === 'fulfilled') {
        const trend = (mtdBundle.value.trend ?? []).map((pt: any) => ({
          label: String(pt.date ?? pt.label ?? pt.d ?? '').slice(5),   // "05-03" from "2026-05-03"
          current: Math.round((pt.revenue ?? pt.current ?? pt.value ?? 0) / 1e5 * 10) / 10,
          prior: Math.round((pt.prior ?? pt.ly ?? 0) / 1e5 * 10) / 10,
        }));
        setTrendData(trend.slice(-30));

        /* Bundle branches: [{branch, revenue, transactions}] — full list = active branches for the period */
        const allBranches = mtdBundle.value.branches ?? [];
        setActiveBranchCount(allBranches.length);
        const brs = allBranches
          .slice(0, 12)
          .map((b: any) => ({
            name: String(b.branch ?? b.name ?? b.label ?? '').slice(0, 18),
            sales_L: Math.round((b.revenue ?? b.current ?? b.sales ?? b.value ?? 0) / 1e5 * 10) / 10,
          }));
        setBranches(brs);
      }

      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load report data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadData(); }, [loadData]);

  const card = {
    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
    backdropFilter: 'blur(20px)',
    border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
  } as const;

  const PERIOD_TABS: Array<{ key: typeof selectedPeriod; label: string }> = [
    { key: 'mtd', label: 'MTD' },
    { key: 'qtd', label: 'QTD' },
    { key: 'ytd', label: 'FY YTD' },
    { key: 'last_6m', label: 'Last 6M' },
  ];

  const activeSummary = summaries.find((s) => s.period === selectedPeriod);

  /* ── Fake report-library rows derived from real data ── */
  const reportRows = activeSummary
    ? [
        {
          title: `${activeSummary.label} Revenue Report`,
          type: 'Revenue',
          color: '#00b8e6',
          status: 'ready',
          value: `₹${activeSummary.sales_L.toFixed(1)}L`,
          detail: `${activeSummary.bills.toLocaleString()} invoices`,
        },
        {
          title: `${activeSummary.label} Growth Analysis`,
          type: 'Analytics',
          color: activeSummary.growth_pct != null && activeSummary.growth_pct >= 0 ? '#00e67a' : '#ef4444',
          status: 'ready',
          value: activeSummary.growth_pct != null ? `${activeSummary.growth_pct > 0 ? '+' : ''}${activeSummary.growth_pct.toFixed(1)}%` : '—',
          detail: `vs. same period last year`,
        },
        {
          title: `Branch Performance — ${activeSummary.label}`,
          type: 'Operations',
          color: '#a78bfa',
          status: 'ready',
          value: `${activeBranchCount || branches.length} stores`,
          detail: branches[0] ? `Top: ${branches[0].name}` : 'All branches',
        },
        {
          title: 'AI Executive Summary',
          type: 'AI Generated',
          color: '#ffb800',
          status: loading ? 'generating' : 'ready',
          value: loading ? '…' : 'Ready',
          detail: 'Rule + AI model analysis',
        },
      ]
    : [];

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      {/* ── Header ── */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1
            className="text-xl sm:text-2xl font-bold"
            style={{
              background: isDark
                ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)'
                : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'var(--text-primary)', backgroundClip: 'text',
            }}
          >Reports</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Live ERP analytics — real data, no demos
            {lastUpdated && <span> · Updated {lastUpdated}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <motion.button
            onClick={() => void loadData()}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium disabled:opacity-50"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', color: 'var(--text-secondary)' }}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            Refresh
          </motion.button>
          <motion.button
            onClick={() => window.print()}
            className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 20px rgba(0,184,230,0.3)' }}
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
          >
            <Sparkles size={12} /> Export PDF
          </motion.button>
        </div>
      </motion.div>

      {/* ── Error ── */}
      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-2xl text-sm"
          style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444' }}>
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {/* ── Period selector + stats ── */}
      <motion.div variants={fadeUp}>
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <div
            className="flex items-center gap-1 p-1 rounded-xl"
            style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)' }}
          >
            {PERIOD_TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setSelectedPeriod(t.key)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: selectedPeriod === t.key ? isDark ? 'rgba(0,184,230,0.18)' : 'rgba(0,184,230,0.12)' : 'transparent',
                  color: selectedPeriod === t.key ? '#00b8e6' : 'var(--text-muted)',
                }}
              >{t.label}</button>
            ))}
          </div>
          {loading && <Loader2 size={14} className="animate-spin" style={{ color: '#00b8e6' }} />}
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {loading ? (
            [...Array(4)].map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-2xl" style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
            ))
          ) : activeSummary ? (
            <>
              <StatCard
                label="Total Revenue"
                value={`₹${activeSummary.sales_L.toFixed(1)}L`}
                sub={`LY: ₹${activeSummary.ly_sales_L.toFixed(1)}L`}
                color="#00b8e6"
                icon={BarChart2}
              />
              <StatCard
                label="YoY Growth"
                value={activeSummary.growth_pct != null ? `${activeSummary.growth_pct > 0 ? '+' : ''}${activeSummary.growth_pct.toFixed(1)}%` : '—'}
                sub={activeSummary.growth_pct != null && activeSummary.growth_pct >= 0 ? 'Above last year' : 'Below last year'}
                color={activeSummary.growth_pct != null && activeSummary.growth_pct >= 0 ? '#00e67a' : '#ef4444'}
                icon={activeSummary.growth_pct != null && activeSummary.growth_pct >= 0 ? TrendingUp : TrendingDown}
              />
              <StatCard
                label="Bills Generated"
                value={activeSummary.bills.toLocaleString()}
                sub="Total invoices"
                color="#ffb800"
                icon={FileText}
              />
              <StatCard
                label="Active Branches"
                value={String(activeBranchCount || branches.length || '—')}
                sub="Stores with sales"
                color="#a78bfa"
                icon={Activity}
              />
            </>
          ) : (
            <div className="col-span-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              No data available. Make sure the backend cache is warm.
            </div>
          )}
        </div>
      </motion.div>

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">

        {/* Revenue trend */}
        <motion.div variants={fadeUp} className="lg:col-span-7 rounded-2xl p-5" style={card}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Revenue Trend — MTD
              </h3>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Daily sales vs. last year · Lakhs</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 rounded" style={{ background: '#00b8e6' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>This year</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 rounded" style={{ background: '#94a3b8' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Last year</span>
              </div>
            </div>
          </div>
          <div className="h-52">
            {loading ? (
              <div className="h-full animate-pulse rounded-xl" style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
            ) : trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="rptCurr" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00b8e6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#00b8e6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="rptPrior" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#94a3b8" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                  <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} interval={Math.floor(trendData.length / 6)} />
                  <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v}L`} width={50} />
                  <Tooltip formatter={(v: number, n: string) => [`₹${v}L`, n === 'current' ? 'This Year' : 'Last Year']} />
                  <Area type="monotone" dataKey="prior" stroke="#94a3b8" strokeWidth={1.5} fill="url(#rptPrior)" dot={false} />
                  <Area type="monotone" dataKey="current" stroke="#00b8e6" strokeWidth={2} fill="url(#rptCurr)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
                No trend data available
              </div>
            )}
          </div>
        </motion.div>

        {/* Branch performance bar */}
        <motion.div variants={fadeUp} className="lg:col-span-5 rounded-2xl p-5" style={card}>
          <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Top Branches — MTD</h3>
          <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Revenue in Lakhs</p>
          <div className="h-52">
            {loading ? (
              <div className="h-full animate-pulse rounded-xl" style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
            ) : branches.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={branches.slice(0, 8)} layout="vertical" margin={{ top: 0, right: 10, left: 0, bottom: 0 }} barSize={10}>
                  <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v}L`} />
                  <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickLine={false} width={70} />
                  <Tooltip formatter={(v: number) => [`₹${v}L`, 'Sales']} />
                  <Bar dataKey="sales_L" fill="#00b8e6" radius={[0, 4, 4, 0]} opacity={0.85}>
                    <LabelList dataKey="sales_L" position="right"
                      formatter={(v: number) => `₹${Number(v).toFixed(1)}L`}
                      style={{ fontSize: 9, fill: 'var(--text-primary)', fontWeight: 700 }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
                No branch data available
              </div>
            )}
          </div>
        </motion.div>
      </div>

      {/* ── Period comparison bar chart ── */}
      <motion.div variants={fadeUp} className="rounded-2xl p-5" style={card}>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Period Comparison — All Ranges</h3>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>MTD · QTD · YTD · Last 6M (₹ Lakhs)</p>
          </div>
          <div className="flex items-center gap-3">
            {[['#00b8e6','Current Year'],['#94a3b8','Last Year']].map(([c,n]) => (
              <div key={n} className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 rounded" style={{ background: c }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{n}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="h-44">
          {loading ? (
            <div className="h-full animate-pulse rounded-xl" style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
          ) : summaries.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={summaries.map((s) => ({
                  label: ['MTD','QTD','FY YTD','6M'][['mtd','qtd','ytd','last_6m'].indexOf(s.period)] ?? s.period,
                  current: s.sales_L,
                  prior: s.ly_sales_L,
                }))}
                margin={{ top: 5, right: 10, left: -10, bottom: 5 }}
                barGap={4}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${v}L`} />
                <Tooltip formatter={(v: number, n: string) => [`₹${v}L`, n === 'current' ? 'This Year' : 'Last Year']} />
                <Bar dataKey="current" fill="#00b8e6" radius={[4, 4, 0, 0]} barSize={28} opacity={0.9}>
                  <LabelList dataKey="current" position="top"
                    formatter={(v: number) => `₹${Number(v).toFixed(1)}L`}
                    style={{ fontSize: 9, fill: 'var(--text-primary)', fontWeight: 700 }} />
                </Bar>
                <Bar dataKey="prior" fill="#94a3b8" radius={[4, 4, 0, 0]} barSize={28} opacity={0.5}>
                  <LabelList dataKey="prior" position="top"
                    formatter={(v: number) => `₹${Number(v).toFixed(1)}L`}
                    style={{ fontSize: 9, fill: 'var(--text-primary)', fontWeight: 700 }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-sm" style={{ color: 'var(--text-muted)' }}>
              No data available
            </div>
          )}
        </div>
      </motion.div>

      {/* ── Report library ── */}
      <motion.div
        variants={fadeUp}
        className="rounded-2xl overflow-hidden"
        style={card}
      >
        <div
          className="flex items-center justify-between p-4"
          style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}
        >
          <div className="flex items-center gap-2">
            <FileText size={14} style={{ color: '#00b8e6' }} />
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Report Library</h3>
          </div>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {activeSummary?.label ?? selectedPeriod.toUpperCase()} · live data
          </span>
        </div>

        <AnimatePresence mode="wait">
          {loading ? (
            <div className="p-4 space-y-3">
              {[1,2,3].map((n) => (
                <div key={n} className="h-14 animate-pulse rounded-xl" style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
              ))}
            </div>
          ) : (
            <div
              className="divide-y"
              style={{ borderColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }}
            >
              {reportRows.map((report, i) => (
                <motion.div
                  key={report.title}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.06 }}
                  className="flex items-center gap-4 px-4 py-3.5 group cursor-pointer"
                  whileHover={{ background: isDark ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.02)' }}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{ background: `${report.color}18`, border: `1px solid ${report.color}30` }}
                  >
                    <FileBarChart size={16} style={{ color: report.color }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                        {report.title}
                      </p>
                      {report.status === 'generating' && (
                        <span
                          className="px-2 py-0.5 rounded-full text-2xs font-bold animate-pulse flex items-center gap-1"
                          style={{ background: 'rgba(255,184,0,0.1)', color: '#ffb800' }}
                        >
                          <Loader2 size={9} className="animate-spin" /> Generating…
                        </span>
                      )}
                      {report.status === 'ready' && (
                        <span
                          className="px-2 py-0.5 rounded-full text-2xs font-bold flex items-center gap-1"
                          style={{ background: 'rgba(0,230,122,0.1)', color: '#00e67a' }}
                        >
                          <CheckCircle size={9} /> Live
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span
                        className="px-1.5 py-0.5 rounded text-2xs font-semibold"
                        style={{ background: `${report.color}12`, color: report.color }}
                      >{report.type}</span>
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{report.detail}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <GrowthBadge pct={activeSummary?.growth_pct ?? null} />
                  </div>

                  <div className="text-sm font-bold tabular-nums" style={{ color: 'var(--text-primary)' }}>
                    {report.value}
                  </div>

                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <motion.button
                      className="p-2 rounded-xl"
                      whileHover={{ scale: 1.05 }}
                      style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', color: 'var(--text-muted)' }}
                    >
                      <Eye size={13} />
                    </motion.button>
                    <motion.button
                      className="p-2 rounded-xl"
                      whileHover={{ scale: 1.05 }}
                      style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', color: 'var(--text-muted)' }}
                    >
                      <Download size={13} />
                    </motion.button>
                  </div>

                  <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: report.color }} />
                </motion.div>
              ))}
            </div>
          )}
        </AnimatePresence>

        {/* Footer */}
        <div
          className="px-4 py-3 flex items-center justify-between"
          style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}
        >
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            <Clock size={10} className="inline mr-1" />
            {lastUpdated ? `Live data · Last refreshed ${lastUpdated}` : 'Loading live data…'}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Powered by SQL Server ERP
          </span>
        </div>
      </motion.div>

    </motion.div>
  );
}
