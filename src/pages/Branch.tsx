import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin, TrendingUp, Activity, ChevronRight,
  Zap, Building2, RefreshCw, Wifi, WifiOff, BarChart2,
} from 'lucide-react';
import {
  BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip,
  AreaChart, Area, CartesianGrid,
} from 'recharts';
import { useTheme } from '../context/ThemeContext';
import { useBranches, fmtRevenue, fmtCount, prefetchBranchesChart } from '../hooks/useAnalytics';
import { analytics, BranchPoint } from '../lib/api';

const stagger = { animate: { transition: { staggerChildren: 0.06 } } };
const item = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 26 } },
};

interface BranchDetail {
  branch: string;
  period: string;
  period_label: string;
  total_revenue: number;
  total_transactions: number;
  avg_daily_revenue: number;
  trend: { date: string; revenue: number; transactions: number }[];
}

type BranchPeriod = 'today' | 'last_7d' | 'last_30d' | 'mtd' | 'qtd';

const PERIOD_TABS: { key: BranchPeriod; label: string; detail: string }[] = [
  { key: 'today',    label: 'Today',  detail: 'today' },
  { key: 'last_7d',  label: '7D',     detail: 'last_7d' },
  { key: 'last_30d', label: '30D',    detail: 'last_30d' },
  { key: 'mtd',      label: 'MTD',    detail: 'last_30d' },
  { key: 'qtd',      label: 'QTD',    detail: 'last_30d' },
];

const PERIOD_SUBTITLE: Record<BranchPeriod, string> = {
  today:    "Today's branch performance",
  last_7d:  'Last 7 days branch performance',
  last_30d: 'Last 30 days branch performance',
  mtd:      'Month-to-date branch performance',
  qtd:      'Quarter-to-date branch performance',
};

export default function Branch() {
  const { isDark } = useTheme();
  const [period, setPeriod] = useState<BranchPeriod>('mtd');

  const { branches, loading, error, refetch, fromApi } = useBranches(period);
  const [selectedBranch, setSelectedBranch] = useState<BranchPoint | null>(null);
  const [detail, setDetail] = useState<BranchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const listSkeleton = loading && branches.length === 0;
  const detailPeriod = PERIOD_TABS.find(t => t.key === period)?.detail ?? 'last_30d';

  // Prefetch visible periods on mount
  useEffect(() => {
    void prefetchBranchesChart('mtd');
    void prefetchBranchesChart('last_7d');
    void prefetchBranchesChart('last_30d');
  }, []);

  // Auto-select first branch when list loads (or period changes)
  useEffect(() => {
    if (branches.length > 0) {
      setSelectedBranch(branches[0]);
    } else if (branches.length === 0 && !loading) {
      setSelectedBranch(null);
    }
  }, [branches, period]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch branch detail when selected branch or period changes
  useEffect(() => {
    if (!selectedBranch) return;
    let ignore = false;
    setDetailLoading(true);
    setDetail(null);
    analytics.branchDetail(selectedBranch.branch, detailPeriod)
      .then((d) => {
        if (!ignore) setDetail(d as BranchDetail);
      })
      .catch(() => {
        if (!ignore) setDetail(null);
      })
      .finally(() => {
        if (!ignore) setDetailLoading(false);
      });
    return () => { ignore = true; };
  }, [selectedBranch, detailPeriod]);

  const maxRevenue = branches.length > 0 ? Math.max(...branches.map(b => b.revenue)) : 1;

  const cardBg = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.88)';
  const cardBorder = isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)';
  const innerBg = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)';
  const innerBorder = isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)';

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      {/* ── Header ── */}
      <motion.div variants={item} className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold" style={{
            background: isDark
              ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)'
              : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>Branch Intelligence</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {PERIOD_SUBTITLE[period]}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Period tabs */}
          <div className="flex items-center rounded-xl p-1 gap-0.5"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: cardBorder }}>
            {PERIOD_TABS.map(tab => (
              <button
                key={tab.key}
                onClick={() => { if (tab.key !== period) { setPeriod(tab.key); setSelectedBranch(null); } }}
                onMouseEnter={() => prefetchBranchesChart(tab.key)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                style={{
                  background: period === tab.key
                    ? isDark ? 'rgba(0,184,230,0.18)' : 'rgba(0,184,230,0.12)'
                    : 'transparent',
                  color: period === tab.key ? '#00b8e6' : 'var(--text-muted)',
                  border: period === tab.key ? '1px solid rgba(0,184,230,0.3)' : '1px solid transparent',
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Status pill */}
          {fromApi ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
              style={{ background: 'rgba(0,230,122,0.1)', border: '1px solid rgba(0,230,122,0.2)', color: '#00e67a' }}>
              <Wifi size={10} />
              {listSkeleton ? 'Loading…' : loading ? 'Updating…' : `${branches.length} Branches`}
            </div>
          ) : !loading && !listSkeleton && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
              style={{ background: 'rgba(255,184,0,0.1)', border: '1px solid rgba(255,184,0,0.2)', color: '#ffb800' }}>
              <WifiOff size={10} /> Demo
            </div>
          )}

          <motion.button onClick={() => refetch()}
            className="p-2 rounded-xl"
            style={{ background: innerBg, border: cardBorder, color: 'var(--text-muted)' }}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </motion.button>
        </div>
      </motion.div>

      {/* ── Main content: branch list + detail side-by-side ── */}
      <div className="grid grid-cols-12 gap-4">

        {/* Branch list — 4 cols */}
        <motion.div variants={item} className="col-span-12 md:col-span-4 flex flex-col gap-2.5">
          <div className="rounded-2xl flex flex-col overflow-hidden"
            style={{ background: cardBg, backdropFilter: 'blur(20px)', border: cardBorder }}>
            <div className="flex items-center justify-between px-4 pt-4 pb-2 flex-shrink-0">
              <span className="text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>
                ALL BRANCHES
              </span>
              <span className="text-xs flex items-center gap-1" style={{ color: loading && !listSkeleton ? '#00b8e6' : 'var(--text-muted)' }}>
                {loading && !listSkeleton && <RefreshCw size={9} className="animate-spin" />}
                {loading && !listSkeleton ? 'Refreshing…' : 'Ranked by Revenue'}
              </span>
            </div>

            {/* Scrollable branch list — fixed height so 95 branches don't make page too tall */}
            <div className="overflow-y-auto flex flex-col gap-1.5 px-3 pb-3"
              style={{ maxHeight: '70vh', scrollbarWidth: 'thin', scrollbarColor: 'rgba(0,184,230,0.25) transparent' }}>

            {listSkeleton ? (
              [...Array(5)].map((_, i) => (
                <div key={i} className="rounded-xl p-3 animate-pulse"
                  style={{ background: innerBg, border: innerBorder }}>
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg" style={{ background: 'rgba(0,184,230,0.08)' }} />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3 rounded" style={{ background: 'rgba(255,255,255,0.06)', width: '55%' }} />
                      <div className="h-2 rounded" style={{ background: 'rgba(255,255,255,0.04)', width: '38%' }} />
                    </div>
                  </div>
                </div>
              ))
            ) : branches.length === 0 ? (
              <div className="py-8 text-center">
                <Building2 size={24} style={{ color: 'var(--text-muted)' }} className="mx-auto mb-2" />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  {error ? `Could not load — ${error}` : 'No branch data'}
                </p>
              </div>
            ) : (
              branches.map((branch, i) => {
                const isSelected = selectedBranch?.branch === branch.branch;
                const revenueShare = ((branch.revenue / maxRevenue) * 100);
                return (
                  <motion.div
                    key={branch.branch}
                    onClick={() => setSelectedBranch(branch)}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="rounded-xl p-2.5 cursor-pointer relative overflow-hidden"
                    style={{
                      background: isSelected
                        ? isDark ? 'rgba(0,184,230,0.1)' : 'rgba(0,184,230,0.08)'
                        : innerBg,
                      border: isSelected ? '1px solid rgba(0,184,230,0.35)' : innerBorder,
                    }}
                    whileHover={{ y: -1 }}
                  >
                    {isSelected && (
                      <motion.div layoutId="branchSelect"
                        className="absolute left-0 top-0 bottom-0 w-0.5 rounded-r"
                        style={{ background: '#00b8e6' }} />
                    )}
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{ background: 'rgba(0,184,230,0.12)', border: '1px solid rgba(0,184,230,0.2)' }}>
                        <Building2 size={14} style={{ color: '#00b8e6' }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <p className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                            {branch.branch}
                          </p>
                          <span className="text-2xs shrink-0" style={{ color: 'var(--text-muted)' }}>#{i + 1}</span>
                        </div>
                        <p className="text-2xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                          {fmtRevenue(branch.revenue)} · {fmtCount(branch.transactions)} txns
                        </p>
                      </div>
                      <ChevronRight size={12} style={{ color: isSelected ? '#00b8e6' : 'var(--text-muted)', flexShrink: 0 }} />
                    </div>
                    {/* Revenue bar */}
                    <div className="mt-2 h-1 rounded-full overflow-hidden"
                      style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
                      <motion.div className="h-full rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: `${revenueShare}%` }}
                        transition={{ duration: 0.6, delay: i * 0.04 }}
                        style={{ background: 'linear-gradient(90deg, #00b8e6, #00e67a)' }} />
                    </div>
                  </motion.div>
                );
              })
            )}
            </div>{/* end scrollable list */}
          </div>
        </motion.div>

        {/* Right panel — 8 cols */}
        <div className="col-span-12 md:col-span-8 flex flex-col gap-4">

          {/* Branch detail card */}
          <AnimatePresence mode="wait">
            {selectedBranch ? (
              <motion.div
                key={selectedBranch.branch + period}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className="rounded-2xl p-5"
                style={{ background: cardBg, backdropFilter: 'blur(20px)', border: cardBorder }}
              >
                {/* Detail header */}
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <MapPin size={13} style={{ color: '#00b8e6' }} />
                      <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: '#00b8e6' }}>
                        Branch Detail
                      </span>
                      <span className="px-2 py-0.5 rounded-full text-2xs font-bold"
                        style={{ background: 'rgba(0,230,122,0.15)', color: '#00e67a' }}>
                        ACTIVE
                      </span>
                    </div>
                    <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                      {selectedBranch.branch}
                    </h2>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      {PERIOD_TABS.find(t => t.key === period)?.label} performance
                    </p>
                  </div>
                  <div className="text-right">
                    {detailLoading ? (
                      <div className="h-7 w-28 rounded animate-pulse" style={{ background: innerBg }} />
                    ) : (
                      <>
                        <p className="text-2xl font-bold metric-value" style={{ color: 'var(--text-primary)' }}>
                          {fmtRevenue(detail?.total_revenue ?? selectedBranch.revenue)}
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: '#00e67a' }}>Total Revenue</p>
                      </>
                    )}
                  </div>
                </div>

                {/* Stat chips */}
                <div className="grid grid-cols-3 gap-3 mb-4">
                  {[
                    {
                      label: 'Transactions',
                      value: fmtCount(detail?.total_transactions ?? selectedBranch.transactions),
                      icon: Activity,
                      color: '#00b8e6',
                    },
                    {
                      label: 'Avg Daily Rev',
                      value: fmtRevenue(detail?.avg_daily_revenue ?? 0),
                      icon: TrendingUp,
                      color: '#00e67a',
                    },
                    {
                      label: 'Avg Ticket',
                      value: detail && detail.total_transactions > 0
                        ? fmtRevenue(detail.total_revenue / detail.total_transactions)
                        : '—',
                      icon: Zap,
                      color: '#ffb800',
                    },
                  ].map(stat => {
                    const Icon = stat.icon;
                    return (
                      <div key={stat.label} className="p-3 rounded-xl text-center"
                        style={{ background: innerBg, border: innerBorder }}>
                        <Icon size={14} style={{ color: stat.color }} className="mx-auto mb-1" />
                        {detailLoading ? (
                          <div className="h-4 rounded animate-pulse mx-auto"
                            style={{ background: innerBg, width: '65%' }} />
                        ) : (
                          <p className="text-sm font-bold" style={{ color: stat.color }}>
                            {stat.value}
                          </p>
                        )}
                        <p className="text-2xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                          {stat.label}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {/* Trend chart */}
                <div className="h-36">
                  {detailLoading ? (
                    <div className="h-full flex items-end gap-1">
                      {[...Array(14)].map((_, i) => (
                        <div key={i} className="flex-1 rounded-t animate-pulse"
                          style={{ height: `${25 + (i % 5) * 13}%`, background: 'rgba(0,184,230,0.10)' }} />
                      ))}
                    </div>
                  ) : detail && detail.trend.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart
                        data={detail.trend.map(d => ({ ...d, label: d.date?.slice(5) }))}
                        margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                        <defs>
                          <linearGradient id="brGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#00b8e6" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="#00b8e6" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3"
                          stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                        <XAxis dataKey="label"
                          tick={{ fill: 'var(--text-muted)', fontSize: 9 }}
                          axisLine={false} tickLine={false} interval={2} />
                        <YAxis
                          tick={{ fill: 'var(--text-muted)', fontSize: 9 }}
                          axisLine={false} tickLine={false}
                          tickFormatter={v => `₹${(v / 100000).toFixed(0)}L`} />
                        <Tooltip formatter={(v: number) => [fmtRevenue(v), 'Revenue']}
                          contentStyle={{
                            background: isDark ? '#0f172a' : '#fff',
                            border: cardBorder,
                            borderRadius: 8,
                            fontSize: 11,
                            color: isDark ? '#e8eeff' : '#0f172a',
                          }}
                          labelStyle={{ color: isDark ? '#94a3b8' : '#64748b', fontWeight: 500 }}
                          itemStyle={{ color: isDark ? '#00b8e6' : '#0369a1' }} />
                        <Area type="monotone" dataKey="revenue" stroke="#00b8e6" strokeWidth={2}
                          fill="url(#brGrad)" dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs"
                      style={{ color: 'var(--text-muted)' }}>
                      No trend data for this period
                    </div>
                  )}
                </div>
              </motion.div>
            ) : (
              <motion.div key="empty"
                className="rounded-2xl p-8 flex flex-col items-center justify-center gap-2"
                style={{ background: cardBg, border: cardBorder }}>
                <Building2 size={24} style={{ color: 'var(--text-muted)' }} />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Select a branch to view details</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* All-branches ranking chart */}
          <motion.div variants={item} className="rounded-2xl p-5"
            style={{ background: cardBg, backdropFilter: 'blur(20px)', border: cardBorder }}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <BarChart2 size={13} style={{ color: '#00b8e6' }} />
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                    Revenue Ranking — All Branches
                  </h3>
                </div>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  Top 10 branches by {PERIOD_TABS.find(t => t.key === period)?.label} revenue
                </p>
              </div>
            </div>
            <div className="h-40">
              {listSkeleton ? (
                <div className="h-full flex items-end gap-2">
                  {[...Array(8)].map((_, i) => (
                    <div key={i} className="flex-1 rounded-t animate-pulse"
                      style={{ height: `${25 + i * 9}%`, background: 'rgba(0,184,230,0.10)' }} />
                  ))}
                </div>
              ) : branches.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={branches.slice(0, 10).map(b => ({
                      label: b.branch?.slice(0, 9) ?? '?',
                      revenue: b.revenue,
                    }))}
                    margin={{ top: 5, right: 5, left: 0, bottom: 5 }}
                    barSize={18}
                  >
                    <CartesianGrid strokeDasharray="3 3"
                      stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                    <XAxis dataKey="label"
                      tick={{ fill: 'var(--text-muted)', fontSize: 8 }}
                      axisLine={false} tickLine={false} />
                    <YAxis
                      tick={{ fill: 'var(--text-muted)', fontSize: 9 }}
                      axisLine={false} tickLine={false}
                      tickFormatter={v => `₹${(v / 100000).toFixed(0)}L`} />
                    <Tooltip formatter={(v: number) => [fmtRevenue(v), 'Revenue']}
                      contentStyle={{
                        background: isDark ? '#0f172a' : '#fff',
                        border: cardBorder,
                        borderRadius: 8,
                        fontSize: 11,
                        color: isDark ? '#e8eeff' : '#0f172a',
                      }}
                      labelStyle={{ color: isDark ? '#94a3b8' : '#64748b', fontWeight: 500 }}
                      itemStyle={{ color: isDark ? '#00b8e6' : '#0369a1' }} />
                    <Bar dataKey="revenue" radius={[4, 4, 0, 0]} opacity={0.85}
                      fill="#00b8e6" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs"
                  style={{ color: 'var(--text-muted)' }}>No data available</div>
              )}
            </div>
          </motion.div>

        </div>
      </div>
    </motion.div>
  );
}
