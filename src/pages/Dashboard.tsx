/**
 * Dashboard — redesigned to match the vibrant gradient card theme.
 *
 * Layout:
 *   1. Header card  — greeting, role badge, last-refreshed clock, mini KPI chips
 *   2. TODAY AT A GLANCE — 4 coloured gradient cards
 *   3. MONTH TO DATE — 4 purple gradient cards
 *   4. Performance — revenue trend + category donut
 *   5. Operational — bills/day, branch bars, qty vs bills
 *   6. Intelligence — AI insights + recent transactions
 */

import { type ReactNode, useState, useCallback, useMemo, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, ResponsiveContainer,
  Tooltip as ReTooltip, PieChart, Pie, Cell,
  BarChart, Bar, CartesianGrid,
} from 'recharts';
import {
  TrendingUp, TrendingDown, RefreshCw, FlaskConical, X,
  ChevronRight, WifiOff, AlertTriangle, Lightbulb,
  Zap, ArrowUpRight, ArrowDownRight, Activity,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { useDashboardPage, summaryFromKpis, resolveTodaySummary, fetchAndApplySnapshot } from '../hooks/useAnalytics';
import { fmtLakhs, fmtCount, fmtRupees, fmtSmart } from '../lib/format';

// ─── Types ────────────────────────────────────────────────────────────────────

interface TrendPt  { label: string; date: string; current: number; prior: number; bills: number; quantity: number }
interface CatPt    { name: string; revenue: number; percentage: number }
interface BranchPt { name: string; revenue: number; percentage: number }

// ─── Demo data ────────────────────────────────────────────────────────────────

function genDemoTrend(): TrendPt[] {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  let base = 18_000_000;
  return months.map((m, i) => {
    base += Math.random() * 2_500_000 - 600_000;
    return {
      label: m,
      date: `2026-${String(i+1).padStart(2,'0')}-01`,
      current: base, prior: base * 0.88,
      bills: 3200 + Math.floor(Math.random() * 900),
      quantity: 2900 + Math.floor(Math.random() * 700),
    };
  });
}

const DEMO_TREND = genDemoTrend();

const DEMO = {
  today: { mtd_sales: 938_000, bills: 350, quantity: 294, sales_growth_pct: 16.8, ly_sales: 803_000, customers: 134 },
  mtd:   { mtd_sales: 262_000_000, bills: 105_871, quantity: 94_052, sales_growth_pct: 8.3, ly_sales: 242_000_000, customers: 18_247 },
  trend: DEMO_TREND,
  categories: [
    { name: 'Electronics', revenue: 82_000_000, percentage: 31.3 },
    { name: 'Apparel',     revenue: 55_000_000, percentage: 21.0 },
    { name: 'Grocery',     revenue: 49_000_000, percentage: 18.7 },
    { name: 'Beauty',      revenue: 38_000_000, percentage: 14.5 },
    { name: 'Home',        revenue: 38_000_000, percentage: 14.5 },
  ] as CatPt[],
  branches: [
    { name: 'Chennai',   revenue: 68_000_000, percentage: 26.0 },
    { name: 'Bangalore', revenue: 62_000_000, percentage: 23.7 },
    { name: 'Mumbai',    revenue: 55_000_000, percentage: 21.0 },
    { name: 'Delhi',     revenue: 48_000_000, percentage: 18.3 },
    { name: 'Hyderabad', revenue: 29_000_000, percentage: 11.0 },
  ] as BranchPt[],
  transactions: [
    { id:'INV-010264', date:'2026-05-26', branch:'Hyderabad', category:'Electronics', department:'Appliances', amount:62500,  salesperson:'Vikram Singh', status:'completed' as const },
    { id:'INV-010286', date:'2026-05-26', branch:'Mumbai',    category:'Electronics', department:'Audio',      amount:18600,  salesperson:'Rahul Iyer',   status:'pending'   as const },
    { id:'INV-010292', date:'2026-05-25', branch:'Mumbai',    category:'Apparel',     department:'Footwear',   amount:72000,  salesperson:'Rohan Gupta',  status:'completed' as const },
    { id:'INV-010316', date:'2026-05-25', branch:'Mumbai',    category:'Electronics', department:'Audio',      amount:34100,  salesperson:'Rohan Gupta',  status:'completed' as const },
    { id:'INV-010323', date:'2026-05-25', branch:'Delhi',     category:'Apparel',     department:'Denim',      amount:27000,  salesperson:'Sneha Reddy',  status:'pending'   as const },
    { id:'INV-010254', date:'2026-05-25', branch:'Chennai',   category:'Electronics', department:'Appliances', amount:15100,  salesperson:'Karthik Raj',  status:'pending'   as const },
    { id:'INV-010263', date:'2026-05-25', branch:'Delhi',     category:'Apparel',     department:'Denim',      amount:73000,  salesperson:'Sneha Reddy',  status:'completed' as const },
    { id:'INV-010250', date:'2026-05-24', branch:'Mumbai',    category:'Electronics', department:'Audio',      amount:11700,  salesperson:'Rahul Iyer',   status:'completed' as const },
  ],
};

// ─── Card surface + category colors ───────────────────────────────────────────

const CAT_COLORS   = ['#5C6BC0','#26C6DA','#EC407A','#66BB6A','#FFA726','#AB47BC'];
const CARD_SURFACE = { background:'rgba(255,255,255,0.03)', border:'1px solid rgba(88,130,255,0.1)' } as const;

// ─── Mini Sparkline ────────────────────────────────────────────────────────────

function MiniSparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const W = 100, H = 32;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const dLine = `M ${pts.join(' L ')}`;
  // Filled area path
  const dFill = `M 0,${H} L ${pts.join(' L ')} L ${W},${H} Z`;
  const uid = color.replace(/[^a-z0-9]/gi, '');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ overflow: 'visible', display: 'block' }}>
      <defs>
        <linearGradient id={`sg_${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.28} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={dFill} fill={`url(#sg_${uid})`} />
      <path d={dLine} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ─── Shimmer skeleton bar ──────────────────────────────────────────────────────

function ShimmerBar({ width = '60%', height = 20, radius = 6 }: { width?: string | number; height?: number; radius?: number }) {
  return (
    <div style={{
      width, height, borderRadius: radius,
      background: 'linear-gradient(90deg, rgba(88,130,255,0.07) 25%, rgba(88,130,255,0.18) 50%, rgba(88,130,255,0.07) 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmerSlide 1.6s linear infinite',
    }} />
  );
}

// Inject keyframe once
const _shimmerStyle = typeof document !== 'undefined' && (() => {
  if (document.getElementById('shimmer-kf')) return;
  const s = document.createElement('style');
  s.id = 'shimmer-kf';
  s.textContent = `@keyframes shimmerSlide { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`;
  document.head.appendChild(s);
})();
void _shimmerStyle;

// ─── KPI Sparkline Card (matches Nebula reference) ────────────────────────────

interface KpiCardProps {
  icon: ReactNode;
  value: string;
  label: string;
  sub?: string;
  growth?: number | null;
  sparkData: number[];
  color: string;
  delay?: number;
  pending?: boolean;   // show shimmer skeleton instead of value
}

function KpiCard({ icon, value, label, sub, growth, sparkData, color, delay = 0, pending = false }: KpiCardProps) {
  const up = growth == null || growth >= 0;
  const isPending = pending || value === '…';
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, type: 'spring', stiffness: 260, damping: 22 }}
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(88,130,255,0.1)',
        borderRadius: 20,
        padding: '16px 18px 12px',
        position: 'relative',
        overflow: 'hidden',
        minHeight: 140,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Subtle top accent line */}
      <div style={{ position:'absolute', top:0, left:0, right:0, height:2, borderRadius:'20px 20px 0 0',
        background: isPending
          ? 'linear-gradient(90deg, transparent, rgba(88,130,255,0.3), transparent)'
          : `linear-gradient(90deg, transparent, ${color}, transparent)` }} />

      {/* Icon + growth badge row */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:10 }}>
        <div style={{
          width:36, height:36, borderRadius:10,
          background:`${color}1a`,
          border:`1px solid ${color}40`,
          display:'flex', alignItems:'center', justifyContent:'center',
          opacity: isPending ? 0.5 : 1,
        }}>
          {icon}
        </div>
        {!isPending && growth != null && (
          <span style={{
            fontSize:10, fontWeight:700, padding:'3px 7px', borderRadius:7,
            color: up ? '#00e67a' : '#f87171',
            background: up ? 'rgba(0,230,122,0.12)' : 'rgba(248,113,113,0.12)',
          }}>
            {up ? '▲' : '▼'} {Math.abs(growth).toFixed(1)}%
          </span>
        )}
        {isPending && <ShimmerBar width={44} height={20} radius={6} />}
      </div>

      {/* Value — shimmer when pending */}
      {isPending ? (
        <div style={{ marginBottom: 6 }}>
          <ShimmerBar width="72%" height={26} radius={7} />
        </div>
      ) : (
        <p style={{
          fontSize:22, fontWeight:900, color:'var(--text-primary)',
          letterSpacing:'-0.02em', fontVariantNumeric:'tabular-nums', lineHeight:1.1,
        }}>
          {value}
        </p>
      )}

      {/* Label */}
      <p style={{
        fontSize:10, fontWeight:700, color:'var(--text-muted)',
        textTransform:'uppercase', letterSpacing:'0.08em', marginTop:3,
      }}>
        {label}
      </p>

      {/* Sub */}
      {sub && !isPending && (
        <p style={{ fontSize:10, color:'var(--text-muted)', marginTop:2, opacity:0.8 }}>{sub}</p>
      )}
      {isPending && <ShimmerBar width="50%" height={10} radius={4} />}

      {/* Sparkline */}
      <div style={{ marginTop:'auto', paddingTop:8, opacity: isPending ? 0.25 : 1 }}>
        <MiniSparkline data={sparkData} color={color} />
      </div>
    </motion.div>
  );
}

// ─── Custom Chart Tooltip ──────────────────────────────────────────────────────

function ChartTip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl px-3 py-2.5"
      style={{ background:'rgba(5,9,24,0.96)', border:'1px solid rgba(88,130,255,0.2)', boxShadow:'0 8px 24px rgba(0,0,0,0.5)' }}>
      <p className="text-[10px] mb-1.5 font-medium" style={{ color:'var(--text-muted)' }}>{label}</p>
      {payload.map((p: { color: string; name: string; value: number }, i: number) => (
        <div key={i} className="flex items-center gap-2 text-[11px]">
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.color }} />
          <span style={{ color:'var(--text-secondary)' }}>{p.name}:</span>
          <span className="font-semibold" style={{ color:'var(--text-primary)' }}>{fmtSmart(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

// ─── AI Insight Card ──────────────────────────────────────────────────────────

interface InsightProps {
  type: 'trend' | 'anomaly' | 'recommendation';
  impact: 'high' | 'medium' | 'low';
  title: string;
  desc: string;
}

const TYPE_COLOR   = { trend:'#5882ff', anomaly:'#FFA726', recommendation:'#26C6DA' } as const;
const IMPACT_COLOR = { high:'#EC407A',  medium:'#FFA726',  low:'#66BB6A' }             as const;
const TYPE_ICON    = { trend: TrendingUp, anomaly: AlertTriangle, recommendation: Lightbulb };

function InsightCard({ type, impact, title, desc }: InsightProps) {
  const Icon = TYPE_ICON[type];
  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }}
      className="p-3 rounded-xl mb-2"
      style={{ background:'rgba(255,255,255,0.03)', border:'1px solid rgba(88,130,255,0.07)' }}>
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon size={10} style={{ color: TYPE_COLOR[type] }} />
        <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
          style={{ background:`${TYPE_COLOR[type]}18`, color: TYPE_COLOR[type] }}>{type}</span>
        <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
          style={{ background:`${IMPACT_COLOR[impact]}18`, color: IMPACT_COLOR[impact] }}>{impact} impact</span>
      </div>
      <p className="text-xs font-semibold mb-0.5" style={{ color:'var(--text-primary)' }}>{title}</p>
      <p className="text-[10px] leading-relaxed" style={{ color:'var(--text-muted)' }}>{desc}</p>
    </motion.div>
  );
}

// ─── Section heading ──────────────────────────────────────────────────────────

function SectionHead({ title, date }: { title: string; date: string }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <p className="text-xs font-black uppercase tracking-widest" style={{ color:'var(--text-muted)' }}>{title}</p>
      <span className="text-[10px] px-2 py-0.5 rounded-full"
        style={{ background:'rgba(88,130,255,0.08)', color:'var(--text-muted)', border:'1px solid rgba(88,130,255,0.12)' }}>
        {date}
      </span>
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function Dashboard() {
  const { isDark } = useTheme();
  const { user }   = useAuth();
  const [demo,     setDemo]     = useState(false);
  const [spinning, setSpinning] = useState(false);
  const [now, setNow] = useState(new Date());

  // ── Fire snapshot on mount — populates SWR cache instantly from server memory
  // This ensures the dashboard renders real data on first paint with zero SQL delay.
  useEffect(() => {
    void fetchAndApplySnapshot();
  }, []);

  // Live clock
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(t);
  }, []);

  const {
    mtdRaw, todayRaw, kpis, todayKpis,
    loading: mLoading, todayLoading, error: fetchError, refetch,
  } = useDashboardPage();

  const doRefresh = useCallback(() => {
    // Re-fetch snapshot + full data on manual refresh
    void fetchAndApplySnapshot();
    refetch();
    setSpinning(true);
    setTimeout(() => setSpinning(false), 900);
  }, [refetch]);

  // ── Resolve data ──────────────────────────────────────────────────────────
  const tS         = demo ? DEMO.today : resolveTodaySummary(todayRaw, todayKpis);
  const mS         = demo ? DEMO.mtd        : (mtdRaw?.summary ?? (kpis ? summaryFromKpis(kpis) : null));
  const trend      = (demo ? DEMO.trend      : mtdRaw?.trend      ?? []) as TrendPt[];
  const dataPending = !demo && !mS && mLoading && !kpis;
  const dash = (formatted: string) => (dataPending ? '…' : formatted);
  const categories    = (demo ? DEMO.categories : mtdRaw?.categories ?? []) as CatPt[];
  const branches      = (demo ? DEMO.branches   : mtdRaw?.branches   ?? []) as BranchPt[];
  const hasChartData  = trend.length > 0 || categories.length > 0;
  // Only show skeleton when we genuinely have no data yet (snapshot + cache both cold)
  const isSkeletonMode = !demo && !hasChartData && mLoading;

  const txnGrowth = demo ? null : (kpis?.transactions?.growth ?? null);
  const aovGrowth = demo ? null : (kpis?.avg_order_value?.growth ?? null);

  // ── KPI strip: wrap in skeleton opacity when data is pending ─────────────
  // isSkeletonMode already handles charts; for KPI numbers we rely on dataPending/'…'

  // ── KPI values (avoid ₹0.00 while SQL still loading — test.py shows real values after dashboard returns) ──
  const todayPending = !demo && !tS && todayLoading;
  const mtdSales     = dash(fmtLakhs(mS?.mtd_sales ?? 0));
  const mtdBills     = dash(fmtCount(mS?.bills ?? 0));
  const mtdQty       = dash(fmtCount(mS?.quantity ?? 0));
  const mtdAvg       = dash(fmtRupees(mS && mS.bills > 0 ? mS.mtd_sales / mS.bills : 0));
  const mtdGrowth    = mS?.sales_growth_pct ?? null;
  const todaySales   = todayPending ? '…' : fmtLakhs(tS?.mtd_sales ?? 0);
  const todayBills   = todayPending ? '…' : (tS?.bills ? fmtCount(tS.bills) : '—');
  const todayQty     = todayPending ? '…' : (tS?.quantity ? fmtCount(tS.quantity) : '—');
  const todayAvg     = todayPending ? '…' : (tS && tS.bills > 0 ? fmtRupees(tS.mtd_sales / tS.bills) : '—');
  const mtdCustomers = mS?.customers != null ? fmtCount(mS.customers) : null;

  // When we have real data, use it. Only fall back to demo ghost shapes when
  // isSkeletonMode is true (snapshot cold + SWR still loading — rare after first run).
  const effectiveTrend    = demo ? DEMO_TREND      : (trend.length > 0 ? trend : (isSkeletonMode ? DEMO_TREND : []));
  const effectiveCats     = demo ? DEMO.categories : (categories.length > 0 ? categories : (isSkeletonMode ? DEMO.categories : []));
  const effectiveBranches = demo ? DEMO.branches   : (branches.length > 0  ? branches  : (isSkeletonMode ? DEMO.branches   : []));
  const txns              = demo ? DEMO.transactions : [];

  const CATEGORY_PIE_TOP = 8;
  const pieCategories = useMemo((): CatPt[] => {
    const src = effectiveCats;
    if (demo || src.length <= CATEGORY_PIE_TOP) return src;
    const top = src.slice(0, CATEGORY_PIE_TOP);
    const rest = src.slice(CATEGORY_PIE_TOP);
    return [...top, { name: `Others (${rest.length})`, revenue: rest.reduce((s,c)=>s+c.revenue,0), percentage: rest.reduce((s,c)=>s+c.percentage,0) }];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveCats, demo]);

  const trendChart  = effectiveTrend.map(p => ({ label: p.label, Revenue: p.current, 'Last Year': p.prior }));
  const billsChart  = effectiveTrend.slice(-30).map(p => ({ label: p.label, Bills: p.bills }));
  const branchChart = effectiveBranches.slice(0, 6);
  const revSpark    = effectiveTrend.slice(-15).map(p => p.current);
  const billsSpark  = effectiveTrend.slice(-15).map(p => p.bills);
  const qtySpark    = effectiveTrend.slice(-15).map(p => p.quantity);

  // ── AI Insights ────────────────────────────────────────────────────────────
  const insights: InsightProps[] = [];
  if (mS) {
    const g = mS.sales_growth_pct ?? 0;
    if (g > 5) insights.push({ type:'trend', impact:'high', title:`Revenue +${g.toFixed(1)}% above last year`, desc:`MTD gross ${fmtLakhs(mS.mtd_sales)} outperforming same period. Momentum is strong across branches.` });
    else if (g < 0) insights.push({ type:'anomaly', impact:'high', title:`Revenue down ${Math.abs(g).toFixed(1)}% vs LY`, desc:`MTD below last year's ${fmtLakhs(mS.ly_sales)}. Review branch and category performance immediately.` });
    else insights.push({ type:'trend', impact:'medium', title:`Revenue tracking in line with last year`, desc:`MTD sales of ${fmtLakhs(mS.mtd_sales)} are close to last year's pace.` });
  }
  if (branches.length > 0) { const top = branches[0]; insights.push({ type:'recommendation', impact:'medium', title:`${top.name} leads at ${top.percentage.toFixed(1)}% share`, desc:`${top.name} contributes ${fmtLakhs(top.revenue)}. Maintain supply chain and staffing lead.` }); }
  if (categories.length > 0) { const topCat = categories[0]; insights.push({ type:'trend', impact:'medium', title:`${topCat.name} drives ${topCat.percentage.toFixed(1)}% of mix`, desc:`${topCat.name} at ${fmtLakhs(topCat.revenue)} dominates category mix. Cross-sell adjacent categories.` }); }
  if (mS && mS.bills > 0) insights.push({ type:'recommendation', impact:'low', title:`Avg bill ₹${(mS.mtd_sales/mS.bills/1000).toFixed(1)}K across ${fmtCount(mS.bills)} bills`, desc:`Bundle promotions or loyalty incentives could lift average transaction size.` });

  // ── Date/time helpers ──────────────────────────────────────────────────────
  const hour = now.getHours();
  const greeting = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : hour < 21 ? 'evening' : 'night';
  const dayFmt   = now.toLocaleDateString('en-IN', { weekday:'long', day:'numeric', month:'long', year:'numeric' });
  const timeFmt  = now.toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit', hour12:true }).toLowerCase();
  const mtdLabel = `1 ${now.toLocaleDateString('en-IN',{month:'short'})} – ${now.getDate()} ${now.toLocaleDateString('en-IN',{month:'short'})}`;
  const todayDate = now.toLocaleDateString('en-IN', { day:'numeric', month:'long', year:'numeric' });
  const mtdPeriodHint = `Month-to-date: 1st through today (${mtdLabel}).`;

  void isDark; // used via CSS vars

  return (
    <div className="space-y-5 pb-6">

      {/* ── 1. Header card ────────────────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(140deg, #0d1433 0%, #0a1028 60%, #0d1840 100%)',
        borderRadius: 24,
        padding: '22px 24px 20px',
        border: '1px solid rgba(88,130,255,0.18)',
        boxShadow: '0 8px 40px rgba(0,0,0,0.45)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* subtle grid overlay */}
        <div style={{ position:'absolute', inset:0, backgroundImage:'radial-gradient(rgba(88,130,255,0.07) 1px, transparent 1px)', backgroundSize:'28px 28px', pointerEvents:'none', borderRadius:24 }} />

        <div className="flex items-start justify-between gap-4" style={{ position:'relative' }}>
          {/* Left: greeting + name + badge */}
          <div>
            <p style={{ fontSize:12, color:'rgba(255,255,255,0.45)', marginBottom:4, letterSpacing:'0.03em' }}>
              Good {greeting} · {dayFmt}
            </p>
            <h1 style={{ fontSize:34, fontWeight:900, color:'#fff', lineHeight:1.05, letterSpacing:'-0.03em' }}>
              {user?.name ?? 'Manager'}
            </h1>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:10, flexWrap:'wrap' }}>
              <span style={{
                background:'#5c6bc0', color:'#fff',
                fontSize:10, fontWeight:700, padding:'3px 10px 3px 8px',
                borderRadius:6, textTransform:'uppercase', letterSpacing:'0.07em',
                display:'inline-flex', alignItems:'center', gap:5,
              }}>
                <span style={{ fontSize:8 }}>■</span>
                {(user?.role ?? 'MANAGER').toUpperCase()}
              </span>
              <span style={{ fontSize:12, color:'rgba(255,255,255,0.45)' }}>
                {user?.email ?? 'karthikeyanasha24@gmail.com'}
              </span>
            </div>
          </div>

          {/* Right: last refreshed + action buttons */}
          <div style={{ textAlign:'right', flexShrink:0 }}>
            <p style={{ fontSize:10, color:'rgba(255,255,255,0.35)', textTransform:'uppercase', letterSpacing:'0.1em', marginBottom:2 }}>Last Refreshed</p>
            <p style={{ fontSize:28, fontWeight:800, color:'#fff', letterSpacing:'-0.02em', lineHeight:1 }}>{timeFmt}</p>
            <div style={{ display:'flex', gap:6, marginTop:10, justifyContent:'flex-end' }}>
              <button type="button" onClick={doRefresh}
                style={{ border:'1px solid rgba(88,130,255,0.25)', color:'rgba(255,255,255,0.6)', background:'rgba(88,130,255,0.08)', borderRadius:10, padding:'5px 12px', fontSize:11, cursor:'pointer', display:'flex', alignItems:'center', gap:4 }}>
                <RefreshCw size={10} className={spinning ? 'animate-spin' : ''} /> Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Mini KPI chip strip */}
        <div style={{ display:'flex', gap:10, marginTop:18, paddingTop:16, borderTop:'1px solid rgba(255,255,255,0.08)', flexWrap:'wrap', position:'relative' }}>
          {[
            { label:'Today',       value: todaySales,            loading: todayPending },
            { label:'Bills Today', value: todayBills,            loading: todayPending },
            { label:'MTD Sales',   value: mS ? mtdSales : '…',  loading: !mS && mLoading },
            { label:'MTD Qty',     value: mS ? mtdQty   : '…',  loading: !mS && mLoading },
          ].map((chip) => (
            <div key={chip.label} style={{
              background:'rgba(255,255,255,0.07)',
              borderRadius:12, padding:'8px 18px',
              border:'1px solid rgba(255,255,255,0.09)',
              minWidth:90,
            }}>
              {chip.loading ? (
                <div style={{ marginBottom:4 }}>
                  <ShimmerBar width={64} height={18} radius={5} />
                </div>
              ) : (
                <p style={{ fontSize:15, fontWeight:800, color:'#fff', letterSpacing:'-0.01em', fontVariantNumeric:'tabular-nums' }}>
                  {chip.value}
                </p>
              )}
              <p style={{ fontSize:10, color:'rgba(255,255,255,0.45)', marginTop:2 }}>{chip.label}</p>
            </div>
          ))}
          {mtdGrowth != null && (
            <div style={{
              background: mtdGrowth >= 0 ? 'rgba(0,230,122,0.1)' : 'rgba(239,68,68,0.1)',
              borderRadius:12, padding:'8px 18px',
              border: `1px solid ${mtdGrowth >= 0 ? 'rgba(0,230,122,0.2)' : 'rgba(239,68,68,0.2)'}`,
              display:'flex', alignItems:'center', gap:6,
            }}>
              {mtdGrowth >= 0
                ? <ArrowUpRight size={14} style={{ color:'#00e67a' }} />
                : <ArrowDownRight size={14} style={{ color:'#ef4444' }} />}
              <div>
                <p style={{ fontSize:15, fontWeight:800, color: mtdGrowth >= 0 ? '#00e67a' : '#ef4444' }}>
                  {mtdGrowth >= 0 ? '+' : ''}{mtdGrowth.toFixed(1)}%
                </p>
                <p style={{ fontSize:10, color:'rgba(255,255,255,0.45)', marginTop:2 }}>vs Last Year</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Period guide */}
      <div className="rounded-xl px-3.5 py-2.5 text-[11px] leading-relaxed"
        style={{ background:'rgba(88,130,255,0.06)', border:'1px solid rgba(88,130,255,0.12)', color:'var(--text-muted)' }}>
        <span className="font-semibold" style={{ color:'var(--text-secondary)' }}>How to read: </span>
        {mtdPeriodHint} Cards marked <span className="font-semibold">Today</span> cover {todayDate} only.
        Growth % compares the <span className="font-semibold">same dates last year</span>.
      </div>

      {/* ── 2. KPI STRIP ─────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3">
        <KpiCard
          icon={<TrendingUp size={16} style={{ color:'#5882ff' }} />}
          value={mtdSales}
          label="Total Revenue"
          sub={dataPending ? undefined : `LY: ${fmtLakhs(mS?.ly_sales ?? 0)}`}
          growth={dataPending ? null : mtdGrowth}
          sparkData={revSpark}
          color="#5882ff"
          delay={0.00}
          pending={dataPending}
        />
        <KpiCard
          icon={<Activity size={16} style={{ color:'#26C6DA' }} />}
          value={mtdBills}
          label="Transactions"
          sub={dataPending ? undefined : 'Bills MTD'}
          growth={dataPending ? null : txnGrowth}
          sparkData={billsSpark}
          color="#26C6DA"
          delay={0.05}
          pending={dataPending}
        />
        <KpiCard
          icon={<ArrowUpRight size={16} style={{ color:'#FFA726' }} />}
          value={mtdAvg}
          label="Avg Order Value"
          sub={dataPending ? undefined : 'Per invoice'}
          growth={dataPending ? null : aovGrowth}
          sparkData={[]}
          color="#FFA726"
          delay={0.10}
          pending={dataPending}
        />
        <KpiCard
          icon={<TrendingUp size={16} style={{ color:'#00e67a' }} />}
          value={dataPending ? '…' : (mtdGrowth != null ? `${mtdGrowth >= 0 ? '+' : ''}${mtdGrowth.toFixed(1)}%` : '—')}
          label="Growth"
          sub={dataPending ? undefined : 'vs same period LY'}
          growth={null}
          sparkData={revSpark.map((v, i, arr) => (i > 0 ? (v - arr[i-1]) / (arr[i-1] || 1) * 100 : 0))}
          color="#00e67a"
          delay={0.15}
          pending={dataPending}
        />
        <KpiCard
          icon={<Zap size={16} style={{ color:'#8B5CF6' }} />}
          value={mtdQty}
          label="Units Sold"
          sub={dataPending ? undefined : 'Quantity MTD'}
          growth={null}
          sparkData={qtySpark}
          color="#8B5CF6"
          delay={0.20}
          pending={dataPending}
        />
        <KpiCard
          icon={<Activity size={16} style={{ color:'#EC407A' }} />}
          value={todaySales}
          label="Today's Sales"
          sub={todayPending ? undefined : `${todayBills} bills · ${todayQty} units`}
          growth={todayPending ? null : (tS?.sales_growth_pct ?? null)}
          sparkData={[]}
          color="#EC407A"
          delay={0.25}
          pending={todayPending}
        />
      </div>

      {/* ── 4. Performance ────────────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div>
            <p className="text-sm font-bold" style={{ color:'var(--text-primary)' }}>Performance</p>
            <p className="text-[10px]" style={{ color:'var(--text-muted)' }}>Revenue, transactions and branch comparisons · {mtdLabel}</p>
          </div>
          <div className="flex items-center gap-2">
            {mLoading && !demo && <WifiOff size={11} style={{ color:'var(--text-muted)' }} title="Refreshing…" />}
            {fetchError && !demo && <span className="text-[10px] text-red-400" title={fetchError}>Error</span>}
            <Link to="/analytics"
              className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-xl"
              style={{ color:'#5882ff', border:'1px solid rgba(88,130,255,0.2)', background:'rgba(88,130,255,0.04)' }}>
              Full Analytics <ChevronRight size={11} />
            </Link>
          </div>
        </div>

        {/* ── Skeleton / loading badge — only shows on true cold start (rare after first run) ── */}
        {isSkeletonMode && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: '#5882ff' }} />
            <span className="text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: 'var(--text-muted)' }}>
              Fetching live data — this is a one-time delay on first startup
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" style={isSkeletonMode ? { opacity: 0.45, pointerEvents: 'none', filter: 'saturate(0.4)' } : {}}>

          {/* Revenue trend */}
          <div className="lg:col-span-2 rounded-2xl p-4" style={CARD_SURFACE}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <p className="text-sm font-semibold" style={{ color:'var(--text-primary)' }}>Daily sales trend</p>
                <p className="text-[10px]" style={{ color:'var(--text-muted)' }}>Each day in {mtdLabel} vs same day last year</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 rounded" style={{ background:'#5882ff' }} /><span className="text-[10px]" style={{ color:'var(--text-muted)' }}>Revenue</span></div>
                <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 rounded" style={{ borderTop:'1px dashed #26C6DA', background:'transparent' }} /><span className="text-[10px]" style={{ color:'var(--text-muted)' }}>Last Year</span></div>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trendChart} margin={{ top: 5, right: 4, left: -8, bottom: 0 }}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#5882ff" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#5882ff" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="lyGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#26C6DA" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#26C6DA" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(88,130,255,0.06)" />
                <XAxis dataKey="label" tick={{ fontSize: 9, fill:'var(--text-muted)' }} tickLine={false} axisLine={false} />
                <YAxis tickFormatter={v => fmtLakhs(v)} tick={{ fontSize: 9, fill:'var(--text-muted)' }} tickLine={false} axisLine={false} />
                <ReTooltip content={<ChartTip />} />
                <Area type="monotone" dataKey="Revenue"   stroke="#5882ff" strokeWidth={2}   fill="url(#revGrad)" dot={false} />
                <Area type="monotone" dataKey="Last Year" stroke="#26C6DA" strokeWidth={1.5} fill="url(#lyGrad)"  dot={false} strokeDasharray="5 3" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Category pie */}
          <div className="rounded-2xl p-4 flex flex-col" style={CARD_SURFACE}>
            <p className="text-sm font-semibold mb-0.5" style={{ color:'var(--text-primary)' }}>Sales by category</p>
            <p className="text-[10px] mb-2" style={{ color:'var(--text-muted)' }}>
              {isSkeletonMode ? 'Loading live data…' : `All ${categories.length} categories · ${mtdLabel} · top ${Math.min(CATEGORY_PIE_TOP, categories.length)}`}
            </p>
            <ResponsiveContainer width="100%" height={120}>
              <PieChart>
                <Pie data={pieCategories} cx="50%" cy="50%" innerRadius={36} outerRadius={56} paddingAngle={2} dataKey="revenue">
                  {pieCategories.map((_, i) => <Cell key={i} fill={CAT_COLORS[i % CAT_COLORS.length]} />)}
                </Pie>
                <ReTooltip
                  formatter={(v: number, _: string, p: { payload?: CatPt }) => [fmtLakhs(v), p.payload?.name ?? '']}
                  contentStyle={{ background:'rgba(5,9,24,0.96)', border:'1px solid rgba(88,130,255,0.2)', borderRadius:12, fontSize:11 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-2 flex-1 min-h-0 max-h-44 overflow-y-auto scrollbar-none space-y-1 pr-1">
              {effectiveCats.map((c, i) => (
                <div key={c.name} className="flex items-center justify-between gap-2 text-[10px]">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: CAT_COLORS[i % CAT_COLORS.length] }} />
                    <span className="truncate" style={{ color:'var(--text-secondary)' }} title={c.name}>{c.name}</span>
                  </div>
                  <span className="flex-shrink-0 font-semibold tabular-nums" style={{ color:'var(--text-primary)' }}>
                    {fmtLakhs(c.revenue)} <span style={{ color:'var(--text-muted)', fontWeight:500 }}>({c.percentage.toFixed(1)}%)</span>
                  </span>
                </div>
              ))}
              {effectiveCats.length === 0 && !isSkeletonMode && (
                <p className="text-center py-4 text-[10px]" style={{ color:'var(--text-muted)' }}>No category data</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── 5. Operational Analytics Row ─────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4" style={isSkeletonMode ? { opacity: 0.45, pointerEvents: 'none', filter: 'saturate(0.4)' } : {}}>

        {/* Bills per day */}
        <div className="rounded-2xl p-4" style={CARD_SURFACE}>
          <p className="text-sm font-semibold" style={{ color:'var(--text-primary)' }}>Bills per day</p>
          <p className="text-[10px] mb-3" style={{ color:'var(--text-muted)' }}>Bill count each day · {mtdLabel}</p>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={billsChart} margin={{ top: 2, right: 0, left: -14, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(88,130,255,0.05)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 8, fill:'var(--text-muted)' }} tickLine={false} axisLine={false}
                interval={Math.max(0, Math.floor(billsChart.length / 5) - 1)} />
              <YAxis tick={{ fontSize: 8, fill:'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <ReTooltip contentStyle={{ background:'rgba(5,9,24,0.96)', border:'1px solid rgba(88,130,255,0.2)', borderRadius:12, fontSize:11 }} />
              <Bar dataKey="Bills" fill="#26C6DA" radius={[2,2,0,0]} maxBarSize={14} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Top branches */}
        <div className="rounded-2xl p-4" style={CARD_SURFACE}>
          <p className="text-sm font-semibold" style={{ color:'var(--text-primary)' }}>Top branches</p>
          <p className="text-[10px] mb-3" style={{ color:'var(--text-muted)' }}>
            {isSkeletonMode ? 'Loading live data…' : `Top ${Math.min(5, branches.length)} of ${branches.length} · ${mtdLabel}`}
          </p>
          <div className="space-y-2.5">
            {branchChart.slice(0,5).map((b, i) => {
              const max = branchChart[0]?.revenue ?? 1;
              const pct = (b.revenue / max) * 100;
              return (
                <div key={b.name} className="flex items-center gap-2">
                  <p className="text-[10px] w-16 text-right shrink-0 truncate" style={{ color:'var(--text-muted)' }}>{b.name}</p>
                  <div className="flex-1 h-5 rounded overflow-hidden" style={{ background:'rgba(88,130,255,0.07)' }}>
                    <motion.div
                      initial={{ width: 0 }} animate={{ width: `${pct}%` }}
                      transition={{ delay: i * 0.06, duration: 0.55, ease:'easeOut' }}
                      className="h-full rounded"
                      style={{ background:'linear-gradient(90deg, #1d4ed8, #a855f7)' }}
                    />
                  </div>
                  <p className="text-[10px] w-14 shrink-0 font-semibold text-right"
                    style={{ color:'var(--text-secondary)', fontVariantNumeric:'tabular-nums' }}>
                    {fmtLakhs(b.revenue)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Units vs bills */}
        <div className="rounded-2xl p-4" style={CARD_SURFACE}>
          <p className="text-sm font-semibold" style={{ color:'var(--text-primary)' }}>Units vs bills</p>
          <p className="text-[10px] mb-3" style={{ color:'var(--text-muted)' }}>Quantity sold and bill count by day · {mtdLabel}</p>
          <ResponsiveContainer width="100%" height={140}>
            <AreaChart
              data={trend.slice(-15).map(p => ({ label: p.label, QTY: p.quantity, Bills: p.bills }))}
              margin={{ top: 2, right: 0, left: -14, bottom: 0 }}>
              <defs>
                <linearGradient id="qtyGr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#8B5CF6" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(88,130,255,0.05)" />
              <XAxis dataKey="label" tick={{ fontSize: 8, fill:'var(--text-muted)' }} tickLine={false} axisLine={false} interval={4} />
              <YAxis tick={{ fontSize: 8, fill:'var(--text-muted)' }} tickLine={false} axisLine={false} />
              <ReTooltip contentStyle={{ background:'rgba(5,9,24,0.96)', border:'1px solid rgba(88,130,255,0.2)', borderRadius:12, fontSize:11 }} />
              <Area type="monotone" dataKey="QTY"   stroke="#8B5CF6" strokeWidth={1.5} fill="url(#qtyGr)" dot={false} />
              <Area type="monotone" dataKey="Bills" stroke="#26C6DA" strokeWidth={1.5} fill="transparent" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
          <div className="flex items-center gap-4 mt-1">
            <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 rounded" style={{ background:'#8B5CF6' }} /><span className="text-[9px]" style={{ color:'var(--text-muted)' }}>QTY</span></div>
            <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 rounded" style={{ background:'#26C6DA' }} /><span className="text-[9px]" style={{ color:'var(--text-muted)' }}>Bills</span></div>
          </div>
        </div>
      </div>

      {/* ── 6. Intelligence Row ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* AI Insights */}
        <div className="rounded-2xl p-4 flex flex-col" style={CARD_SURFACE}>
          <div className="flex items-center justify-between mb-3 flex-shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                style={{ background:'linear-gradient(135deg,#4158D0,#8B5CF6)' }}>
                <Zap size={12} className="text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold" style={{ color:'var(--text-primary)' }}>AI Insights</p>
                <p className="text-[10px]" style={{ color:'var(--text-muted)' }}>Auto-generated from your data</p>
              </div>
            </div>
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full"
              style={{ background:'rgba(88,130,255,0.1)', color:'#5882ff', border:'1px solid rgba(88,130,255,0.2)' }}>LIVE</span>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-none">
            {insights.length > 0
              ? insights.map((ins, i) => <InsightCard key={i} {...ins} />)
              : (
                <div className="flex flex-col items-center justify-center py-8 gap-2">
                  {isSkeletonMode || (mLoading && !mS)
                    ? <><div className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'rgba(88,130,255,0.3)', borderTopColor: '#5882ff' }} /><p className="text-xs" style={{ color:'var(--text-muted)' }}>Fetching live data…</p></>
                    : <p className="text-xs" style={{ color:'var(--text-muted)' }}>No data available</p>
                  }
                </div>
              )}
          </div>
          <Link to="/insights"
            className="mt-3 block text-center text-xs font-semibold py-2 rounded-xl flex-shrink-0"
            style={{ color:'#5882ff', background:'rgba(88,130,255,0.06)', border:'1px solid rgba(88,130,255,0.15)' }}>
            View all AI Insights →
          </Link>
        </div>

        {/* Recent Transactions */}
        <div className="lg:col-span-2 rounded-2xl p-4" style={CARD_SURFACE}>
          <div className="flex items-center justify-between mb-3">
            <div>
              <p className="text-sm font-semibold" style={{ color:'var(--text-primary)' }}>Recent Transactions</p>
              <p className="text-[10px]" style={{ color:'var(--text-muted)' }}>
                {txns.length > 0 ? `Latest ${txns.length} records` : 'Open Transactions page for live list'}
              </p>
            </div>
            <Link to="/transactions" className="text-xs font-semibold flex items-center gap-1" style={{ color:'#5882ff' }}>
              View all <ChevronRight size={11} />
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr style={{ borderBottom:'1px solid rgba(88,130,255,0.08)' }}>
                  {['Invoice','Branch','Category','Amount','Date','Status'].map(h => (
                    <th key={h} className="text-left py-2 px-2 text-[10px] font-bold uppercase tracking-wider"
                      style={{ color:'var(--text-muted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {txns.length === 0 && !demo && (
                  <tr><td colSpan={6} className="py-8 text-center text-xs" style={{ color:'var(--text-muted)' }}>
                    Transaction feed unavailable — use{' '}
                    <Link to="/transactions" className="font-semibold" style={{ color:'#5882ff' }}>Transactions</Link>
                  </td></tr>
                )}
                {txns.slice(0,8).map((t, i) => (
                  <motion.tr key={t.id}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.025 }}
                    style={{ borderBottom:'1px solid rgba(88,130,255,0.05)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(88,130,255,0.03)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    <td className="py-2.5 px-2 text-[11px] font-mono font-semibold" style={{ color:'var(--text-secondary)' }}>{t.id}</td>
                    <td className="py-2.5 px-2 text-[11px]" style={{ color:'var(--text-secondary)' }}>{t.branch}</td>
                    <td className="py-2.5 px-2 text-[11px]" style={{ color:'var(--text-muted)' }}>{t.category}</td>
                    <td className="py-2.5 px-2 text-[11px] font-semibold font-mono"
                      style={{ color:'var(--text-primary)', fontVariantNumeric:'tabular-nums' }}>{fmtRupees(t.amount)}</td>
                    <td className="py-2.5 px-2 text-[11px]" style={{ color:'var(--text-muted)' }}>{t.date}</td>
                    <td className="py-2.5 px-2">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                        style={{
                          background: t.status==='completed' ? 'rgba(0,230,122,0.1)' : t.status==='pending' ? 'rgba(255,167,38,0.1)' : 'rgba(239,68,68,0.1)',
                          color:      t.status==='completed' ? '#00e67a'              : t.status==='pending' ? '#ffa726'              : '#ef4444',
                        }}>
                        {t.status.charAt(0).toUpperCase()+t.status.slice(1)}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* unused import guard */}
      {false && <><TrendingUp size={0} /><TrendingDown size={0} /><Activity size={0} /></>}
    </div>
  );
}
