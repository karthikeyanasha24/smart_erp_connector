import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MapPin, TrendingUp,
  Activity, ChevronRight, Zap, Globe, Building2, RefreshCw, Wifi, WifiOff
} from 'lucide-react';
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, AreaChart, Area, CartesianGrid } from 'recharts';
import { useTheme } from '../context/ThemeContext';
import { useBranches, fmtRevenue, fmtCount, prefetchBranchesChart } from '../hooks/useAnalytics';
import { analytics, BranchPoint } from '../lib/api';

const stagger = { animate: { transition: { staggerChildren: 0.07 } } };
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

export default function Branch() {
  const { isDark } = useTheme();

  const { branches, loading, error, refetch, fromApi } = useBranches('mtd');
  const [selectedBranch, setSelectedBranch] = useState<BranchPoint | null>(null);
  const [detail, setDetail] = useState<BranchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  /** True only when there is nothing to paint yet — never replace real rows with skeleton on SWR refresh. */
  const listSkeleton = loading && branches.length === 0;

  useEffect(() => {
    void prefetchBranchesChart('mtd');
  }, []);

  // Auto-select first branch when list loads
  useEffect(() => {
    if (branches.length > 0 && !selectedBranch) {
      setSelectedBranch(branches[0]);
    }
  }, [branches]);

  // Fetch detail when selected branch changes
  useEffect(() => {
    if (!selectedBranch) return;
    let ignore = false;
    setDetailLoading(true);
    analytics.branchDetail(selectedBranch.branch, 'last_14d')
      .then((d) => {
        if (!ignore) setDetail(d as BranchDetail);
      })
      .catch(() => {
        if (!ignore) setDetail(null);
      })
      .finally(() => {
        if (!ignore) setDetailLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [selectedBranch]);

  const maxRevenue = branches.length > 0 ? Math.max(...branches.map(b => b.revenue)) : 1;

  // Top 3 branches for comparison chart
  const top3 = branches.slice(0, 3);

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      {/* Header */}
      <motion.div variants={item} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{
            background: isDark ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)' : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>Branch Intelligence</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Live performance monitoring across all locations</p>
        </div>
        <div className="flex items-center gap-2">
          {fromApi ? (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
              style={{ background: 'rgba(0,230,122,0.1)', border: '1px solid rgba(0,230,122,0.2)', color: '#00e67a' }}>
              <Wifi size={10} />
              {listSkeleton ? 'Loading...' : `${branches.length} Branches`}
            </div>
          ) : !loading && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
              style={{ background: 'rgba(255,184,0,0.1)', border: '1px solid rgba(255,184,0,0.2)', color: '#ffb800' }}>
              <WifiOff size={10} /> Demo Mode
            </div>
          )}
          <motion.button onClick={() => refetch()}
            className="p-2 rounded-xl"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)', color: 'var(--text-muted)' }}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <RefreshCw size={13} className={listSkeleton ? 'animate-spin' : ''} />
          </motion.button>
        </div>
      </motion.div>

      <div className="grid grid-cols-12 gap-4">

        {/* Branch list */}
        <motion.div variants={item} className="col-span-5 flex flex-col gap-3">
          {listSkeleton ? (
            [...Array(4)].map((_, i) => (
              <div key={i} className="rounded-2xl p-4 animate-pulse"
                style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)' }}>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl" style={{ background: 'rgba(255,255,255,0.06)' }} />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 rounded" style={{ background: 'rgba(255,255,255,0.06)', width: '60%' }} />
                    <div className="h-2.5 rounded" style={{ background: 'rgba(255,255,255,0.04)', width: '40%' }} />
                  </div>
                </div>
              </div>
            ))
          ) : branches.length === 0 ? (
            <div className="rounded-2xl p-8 text-center" style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)' }}>
              <Building2 size={24} style={{ color: 'var(--text-muted)' }} className="mx-auto mb-2" />
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                {error ? `Could not load branches — ${error}` : 'No branch data available'}
              </p>
            </div>
          ) : (
            branches.map((branch, i) => {
              const isSelected = selectedBranch?.branch === branch.branch;
              const revenueShare = ((branch.revenue / maxRevenue) * 100).toFixed(0);
              return (
                <motion.div
                  key={branch.branch}
                  onClick={() => setSelectedBranch(branch)}
                  initial={{ opacity: 0, x: -16 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="rounded-2xl p-4 cursor-pointer relative overflow-hidden"
                  style={{
                    background: isSelected
                      ? isDark ? 'rgba(0,184,230,0.08)' : 'rgba(0,184,230,0.06)'
                      : isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
                    backdropFilter: 'blur(20px)',
                    border: isSelected ? '1px solid rgba(0,184,230,0.3)' : isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
                    boxShadow: isSelected ? '0 0 20px rgba(0,184,230,0.1)' : 'none',
                  }}
                  whileHover={{ y: -1 }}
                >
                  {isSelected && (
                    <motion.div layoutId="branchSelect" className="absolute left-0 top-0 bottom-0 w-0.5"
                      style={{ background: '#00b8e6' }} />
                  )}

                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: 'rgba(0,184,230,0.12)', border: '1px solid rgba(0,184,230,0.2)' }}>
                      <Building2 size={16} style={{ color: '#00b8e6' }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{branch.branch}</p>
                        <span className="w-1.5 h-1.5 rounded-full flex-shrink-0 bg-green-400" />
                      </div>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>#{i + 1} by revenue · {revenueShare}% share</p>
                    </div>
                    <ChevronRight size={14} style={{ color: isSelected ? '#00b8e6' : 'var(--text-muted)' }} />
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-3">
                    <div>
                      <p className="text-2xs" style={{ color: 'var(--text-muted)' }}>Revenue</p>
                      <p className="text-sm font-bold metric-value" style={{ color: 'var(--text-primary)' }}>
                        {fmtRevenue(branch.revenue)}
                      </p>
                    </div>
                    <div>
                      <p className="text-2xs" style={{ color: 'var(--text-muted)' }}>Transactions</p>
                      <p className="text-sm font-bold metric-value" style={{ color: 'var(--text-primary)' }}>
                        {fmtCount(branch.transactions)}
                      </p>
                    </div>
                  </div>

                  {/* Mini revenue bar */}
                  <div className="mt-2.5 h-1 rounded-full overflow-hidden"
                    style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
                    <motion.div className="h-full rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${revenueShare}%` }}
                      transition={{ duration: 0.7, delay: i * 0.05 }}
                      style={{ background: 'linear-gradient(90deg, #00b8e6, #00e67a)' }} />
                  </div>
                </motion.div>
              );
            })
          )}
        </motion.div>

        {/* Branch detail + charts */}
        <div className="col-span-7 flex flex-col gap-4">

          <AnimatePresence mode="wait">
            {selectedBranch ? (
              <motion.div
                key={selectedBranch.branch}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
                className="rounded-2xl p-5"
                style={{
                  background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
                  backdropFilter: 'blur(20px)',
                  border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
                }}
              >
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <MapPin size={14} style={{ color: '#00b8e6' }} />
                      <span className="text-xs font-semibold" style={{ color: '#00b8e6' }}>Branch Detail</span>
                      <span className="px-2 py-0.5 rounded-full text-2xs font-bold"
                        style={{ background: 'rgba(0,230,122,0.15)', color: '#00e67a' }}>
                        ACTIVE
                      </span>
                    </div>
                    <h2 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{selectedBranch.branch}</h2>
                    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Last 14 days performance</p>
                  </div>
                  <div className="text-right">
                    {detailLoading ? (
                      <div className="h-7 w-28 rounded animate-pulse" style={{ background: 'rgba(255,255,255,0.06)' }} />
                    ) : (
                      <>
                        <p className="text-2xl font-bold metric-value" style={{ color: 'var(--text-primary)' }}>
                          {fmtRevenue(detail?.total_revenue ?? selectedBranch.revenue)}
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: '#00e67a' }}>MTD Revenue</p>
                      </>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-5">
                  {[
                    { label: 'Transactions', value: fmtCount(detail?.total_transactions ?? selectedBranch.transactions), icon: Activity, color: '#00b8e6' },
                    { label: 'Avg Daily Rev', value: `${fmtRevenue(detail?.avg_daily_revenue ?? 0)}`, icon: TrendingUp, color: '#00e67a' },
                    { label: 'Avg Ticket', value: detail && detail.total_transactions > 0 ? `${fmtRevenue(detail.total_revenue / detail.total_transactions)}` : '—', icon: Zap, color: '#ffb800' },
                  ].map(stat => {
                    const Icon = stat.icon;
                    return (
                      <div key={stat.label} className="p-3 rounded-xl text-center"
                        style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}>
                        <Icon size={14} style={{ color: stat.color }} className="mx-auto mb-1.5" />
                        {detailLoading ? (
                          <div className="h-4 rounded animate-pulse mx-auto" style={{ background: 'rgba(255,255,255,0.06)', width: '70%' }} />
                        ) : (
                          <p className="text-sm font-bold" style={{ color: stat.color }}>{stat.value}</p>
                        )}
                        <p className="text-2xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
                      </div>
                    );
                  })}
                </div>

                {/* 14-day trend chart */}
                <div className="h-32">
                  {detailLoading ? (
                    <div className="h-full flex items-end gap-1">
                      {[...Array(14)].map((_, i) => (
                        <div key={i} className="flex-1 rounded-t animate-pulse"
                          style={{ height: `${30 + Math.random() * 60}%`, background: 'rgba(0,184,230,0.12)' }} />
                      ))}
                    </div>
                  ) : detail && detail.trend.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={detail.trend.map(d => ({ ...d, label: d.date?.slice(5) }))}
                        margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                        <defs>
                          <linearGradient id="brGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#00b8e6" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="#00b8e6" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                        <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickLine={false} interval={2} />
                        <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickLine={false} tickFormatter={v => `₹${(v / 100000).toFixed(0)}L`} />
                        <Tooltip formatter={(v: number) => [fmtRevenue(v), 'Revenue']} />
                        <Area type="monotone" dataKey="revenue" stroke="#00b8e6" strokeWidth={2} fill="url(#brGrad)" dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs" style={{ color: 'var(--text-muted)' }}>
                      No trend data
                    </div>
                  )}
                </div>
              </motion.div>
            ) : (
              <motion.div key="empty" className="rounded-2xl p-8 flex items-center justify-center"
                style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)', border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)' }}>
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Select a branch to view details</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Branch comparison bar chart */}
          <motion.div variants={item} className="rounded-2xl p-5"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
            }}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>All Branches — Revenue Ranking</h3>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Month-to-date total revenue</p>
              </div>
            </div>
            <div className="h-36">
              {listSkeleton ? (
                <div className="h-full flex items-end gap-2">
                  {[...Array(6)].map((_, i) => (
                    <div key={i} className="flex-1 rounded-t animate-pulse"
                      style={{ height: `${30 + i * 10}%`, background: 'rgba(0,184,230,0.12)' }} />
                  ))}
                </div>
              ) : branches.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={branches.slice(0, 10).map(b => ({ label: b.branch?.slice(0, 8) ?? '?', revenue: b.revenue }))}
                    margin={{ top: 5, right: 5, left: 0, bottom: 5 }} barSize={20}>
                    <CartesianGrid strokeDasharray="3 3" stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 9 }} axisLine={false} tickLine={false} tickFormatter={v => `₹${(v / 100000).toFixed(0)}L`} />
                    <Tooltip formatter={(v: number) => [fmtRevenue(v), 'Revenue']} />
                    <Bar dataKey="revenue" fill="#00b8e6" radius={[4, 4, 0, 0]} opacity={0.85} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-xs" style={{ color: 'var(--text-muted)' }}>
                  No data available
                </div>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
}
