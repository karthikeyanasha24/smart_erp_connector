import { useMemo, useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  AreaChart, Area, LineChart, Line, LabelList,
  PieChart, Pie, Cell, Sector,
} from 'recharts';
import {
  RefreshCw, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp,
  TrendingUp, TrendingDown, ShoppingBag, Users, Receipt, BarChart2, CalendarRange,
  Truck, Trash2,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAnalyticsPage, prefetchAnalyticsPage, fetchAndApplySnapshot, hasLyTrendData, formatLySub, lyGrowthReady, formatCustomerKpi, clearCustomAnalyticsClientCache } from '../hooks/useAnalytics';
import { fmtLakhs, fmtCount, fmtCountAxis, fmtLakhsAxis, formatChartLabel } from '../lib/format';
import { analytics as analyticsApi } from '../lib/api';

// ─── Constants ────────────────────────────────────────────────────────────────

const PERIOD_TABS = [
  { label: 'Today',   period: 'today'   },
  { label: 'MTD',     period: 'mtd'     },
  { label: 'QTD',     period: 'qtd'     },
  { label: 'FY YTD',  period: 'ytd'     },
  { label: 'Last 6M', period: 'last_6m' },
  { label: 'Custom',  period: 'custom'  },
];

/** Helps explain why rolling 180d revenue may exceed calendar YTD, etc. */
const PERIOD_WINDOW_HINT: Partial<Record<string, string>> = {
  today: 'Single day snapshot.',
  mtd: 'Calendar month-to-date.',
  qtd: 'Calendar quarter-to-date.',
  ytd:
    'Indian Financial Year-to-date (Apr 1–today). Last year compares the same FY slice.',
  last_6m:
    'Rolling last 180 days (today back 179 days), not half a calendar year — it can include last year and total more than YTD.',
  custom: 'Uses the dates you pick; last year uses the same calendar shift.',
};

const PIE_COLORS = [
  '#5882ff','#8B5CF6','#26C6DA','#EC407A',
  '#66BB6A','#FFA726','#AB47BC','#42A5F5',
  '#EF5350','#26A69A','#7E57C2','#FF7043',
  '#29B6F6','#9CCC65','#FFCA28','#78909C',
];

const KPI_ICONS = [ShoppingBag, BarChart2, Receipt, Users];
const KPI_COLORS = ['#5882ff','#26C6DA','#FFA726','#8B5CF6'];

// ─── Custom donut active shape ─────────────────────────────────────────────────
function ActiveShape(props: any) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload, percent } = props;
  return (
    <g>
      <text x={cx} y={cy - 10} textAnchor="middle" fill="var(--text-primary)"
        style={{ fontSize: 13, fontWeight: 700 }}>
        {String(payload.name ?? '').slice(0, 14)}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fill={fill}
        style={{ fontSize: 12, fontWeight: 600 }}>
        {(percent * 100).toFixed(2)}%
      </text>
      <Sector cx={cx} cy={cy} innerRadius={innerRadius} outerRadius={outerRadius + 8}
        startAngle={startAngle} endAngle={endAngle} fill={fill} />
      <Sector cx={cx} cy={cy} innerRadius={innerRadius - 4} outerRadius={innerRadius - 1}
        startAngle={startAngle} endAngle={endAngle} fill={fill} />
    </g>
  );
}

// ─── Glass card wrapper ────────────────────────────────────────────────────────
function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const { isDark } = useTheme();
  return (
    <div className={`rounded-2xl ${className}`} style={{
      background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.92)',
      backdropFilter: 'blur(20px)',
      border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
      boxShadow: isDark ? '0 4px 24px rgba(0,0,0,0.25)' : '0 2px 16px rgba(0,0,0,0.06)',
    }}>
      {children}
    </div>
  );
}

function useChartHeight(mobile: number, desktop: number): number {
  const [h, setH] = useState(desktop);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 639px)');
    const update = () => setH(mq.matches ? mobile : desktop);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, [mobile, desktop]);
  return h;
}

function useIsMobile(): boolean {
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 639px)');
    const update = () => setMobile(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);
  return mobile;
}

// ─── Chart tooltip (bars, areas, lines) ───────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  const { isDark } = useTheme();
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: isDark ? 'rgba(8,15,26,0.97)' : 'rgba(255,255,255,0.98)',
      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
      borderRadius: 10, padding: '10px 14px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
    }}>
      <p style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 6, fontWeight: 600 }}>{label}</p>
      {payload.map((p: any) => {
        const clr = p.stroke ?? (typeof p.fill === 'string' && !p.fill.startsWith('url') ? p.fill : '#888');
        return (
          <div key={p.dataKey} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: clr, flexShrink: 0 }} />
            <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>{p.name}:</span>
            <span style={{ color: clr, fontSize: 11, fontWeight: 700 }}>{fmtLakhs(Number(p.value ?? 0))}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Pie side-legend ──────────────────────────────────────────────────────────
function PieLegend({ items, isDark, className = '' }: { items: { name: string; value: number }[]; isDark: boolean; className?: string }) {
  return (
    <div className={`w-full overflow-y-auto ${className}`} style={{ maxHeight: 200 }}>
      {items.map((item, i) => (
        <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 4px' }}>
          <div style={{
            width: 8, height: 8, borderRadius: 2,
            background: PIE_COLORS[i % PIE_COLORS.length], flexShrink: 0,
          }} />
          <span style={{
            fontSize: 11, flex: 1, color: isDark ? 'rgba(255,255,255,0.65)' : 'rgba(0,0,0,0.55)',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {item.name}
          </span>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#5882ff', flexShrink: 0 }}>
            {fmtLakhs(item.value)}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Compact label formatter ─────────────────────────────────────────────────
function fmtBarLabel(rawRupees: number): string {
  const l = rawRupees / 100000;
  if (l >= 100) return `${Math.round(l)}L`;
  if (l >= 1)   return `${l.toFixed(1)}L`;
  return `${Math.round(l * 100)}K`;
}

// ─── Collision-aware bar label ────────────────────────────────────────────────
// Recharts renders all of Bar-A before Bar-B (across all indices).
// We cache Bar-A's label y-positions; when Bar-B renders, if the gap < 13px
// we push Bar-B's label up so both are always clearly separated.
// Pass barKey="current"|"prior" and idx={props.index} from each LabelList.
const _lblY = new Map<string, number>();
function SmartBarLabel({ x, y, width, value, fill, barKey = 'a', idx = 0 }: any) {
  if (value == null || Number(value) === 0) return null;
  const label = fmtBarLabel(Number(value));
  if (label === '0L') return null;

  const cx  = Number(x ?? 0) + Number(width ?? 0) / 2;
  const otherKey = `${idx}:${barKey === 'current' ? 'prior' : 'current'}`;
  let ty = Number(y ?? 0) - 5;

  const otherTy = _lblY.get(otherKey);
  if (otherTy !== undefined && Math.abs(ty - otherTy) < 13) {
    // Push this label above the other one with a 13px clear gap
    ty = Math.min(ty, otherTy) - 13;
  }
  _lblY.set(`${idx}:${barKey}`, ty);

  return (
    <text x={cx} y={ty} textAnchor="middle" dominantBaseline="auto"
      style={{ fontSize: 8, fontWeight: 700, fill: fill ?? 'var(--text-muted)', pointerEvents: 'none' }}
    >{label}</text>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function Analytics() {
  const { isDark } = useTheme();
  const isMobile = useIsMobile();
  const yoyChartHeight = useChartHeight(240, 360);
  const breakdownBarHeight = useChartHeight(220, 280);
  const breakdownLineHeight = useChartHeight(180, 240);
  const daywiseBarHeight = useChartHeight(220, 260);
  const daywiseLineHeight = useChartHeight(160, 200);
  const pieChartSize = isMobile ? 168 : 200;
  const categoryPieSize = isMobile ? 190 : 220;
  const [period, setPeriod] = useState('mtd');
  // Committed dates drive the actual query; pending update on every keystroke.
  // Clicking Apply copies pending → committed, firing a single fetch.
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [pendingStart, setPendingStart] = useState('');
  const [pendingEnd, setPendingEnd] = useState('');
  const [expandBranches, setExpandBranches] = useState(false);
  const [expandCategories, setExpandCategories] = useState(false);
  const [activePieIndex, setActivePieIndex] = useState<number>(0);

  const canFetchCustom = period !== 'custom' || (!!customStart && !!customEnd);
  const waitingForCustomDates = period === 'custom' && !canFetchCustom;
  const startDate = period === 'custom' && canFetchCustom ? customStart : undefined;
  const endDate   = period === 'custom' && canFetchCustom ? customEnd   : undefined;

  const { data, loading, chartLoading, error, refetchForce } = useAnalyticsPage(
    canFetchCustom ? period : '__hold__',
    startDate,
    endDate,
  );

  // Local spinning state so the Refresh button always shows feedback even when
  // data is already cached (SWR silent-revalidate keeps `loading` false in that case).
  const [refreshSpinning, setRefreshSpinning] = useState(false);
  const handleRefresh = useCallback(() => {
    refetchForce();
    setRefreshSpinning(true);
    setTimeout(() => setRefreshSpinning(false), 1200);
  }, [refetchForce]);

  // Apply button — copy pending → committed to fire the query
  const customDirty = period === 'custom' && (pendingStart !== customStart || pendingEnd !== customEnd);
  const isReversedRange = !!pendingStart && !!pendingEnd && pendingStart > pendingEnd;
  const canApplyCustom = !!pendingStart && !!pendingEnd && pendingStart <= pendingEnd;
  const applyCustom = useCallback(() => {
    if (!canApplyCustom) return;
    setCustomStart(pendingStart);
    setCustomEnd(pendingEnd);
  }, [canApplyCustom, pendingStart, pendingEnd]);

  // Clear custom cache — wipes both client SWR cache and server PostgreSQL cache,
  // then refetches fresh data from SQL Server.
  const [clearingCache, setClearingCache] = useState(false);
  const [clearCacheMsg, setClearCacheMsg] = useState<string | null>(null);
  const handleClearCustomCache = useCallback(async () => {
    setClearingCache(true);
    setClearCacheMsg(null);
    try {
      clearCustomAnalyticsClientCache();
      const res = await analyticsApi.clearCustomCache();
      setClearCacheMsg(res.deleted > 0 ? `Cleared ${res.deleted} entr${res.deleted === 1 ? 'y' : 'ies'}` : 'Cache empty');
      refetchForce();
    } catch {
      setClearCacheMsg('Clear failed');
    } finally {
      setClearingCache(false);
      setTimeout(() => setClearCacheMsg(null), 3000);
    }
  }, [refetchForce]);

  const uiLoading = loading && !data && !waitingForCustomDates;
  // For custom range, show a descriptive "fetching..." message while loading.
  const customFetching = period === 'custom' && canFetchCustom && loading && !data;

  useEffect(() => {
    // fetchAndApplySnapshot seeds the analytics-page cache from the backend snapshot.
    // Called here to ensure the Analytics page gets fresh data after navigation.
    // We do NOT call prefetchAnalyticsShell() — that fires all 5 periods simultaneously
    // causing a request storm. Each period loads on-demand when the tab is clicked.
    void fetchAndApplySnapshot();
  }, []);

  const gran = data?.granularity === 'month' ? 'month' as const : 'day' as const;

  const chartData = useMemo(() => {
    if (!data?.yoyTrend?.length) return [];
    return data.yoyTrend.map((p) => ({
      label:   formatChartLabel(p.label ?? p.date ?? '', gran),
      current: p.current,
      prior:   p.prior,
    }));
  }, [data, gran]);

  const hasLyData = useMemo(
    () => chartData.some((p) => (p.prior ?? 0) > 0),
    [chartData],
  );

  const allCategories = data?.categories ?? [];

  // Build clean donut data: top 8 + "Others" grouping
  // Recompute percentages from revenue so we never show raw backend decimals.
  const TOP_PIE = expandCategories ? 16 : 8;
  const pieData = useMemo(() => {
    if (!allCategories.length) return [];
    const totalRev = allCategories.reduce((s, c) => s + c.revenue, 0);
    const top = allCategories.slice(0, TOP_PIE);
    const rest = allCategories.slice(TOP_PIE);
    const items = top.map(c => ({
      name: c.name,
      revenue: c.revenue,
      percentage: totalRev > 0 ? (c.revenue / totalRev) * 100 : 0,
    }));
    if (rest.length) {
      const othRev = rest.reduce((s, c) => s + c.revenue, 0);
      items.push({
        name: `Others (${rest.length})`,
        revenue: othRev,
        percentage: totalRev > 0 ? (othRev / totalRev) * 100 : 0,
      });
    }
    return items;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allCategories, expandCategories, TOP_PIE]);

  const allBranches = data?.branches ?? [];
  const branchList  = expandBranches ? allBranches : allBranches.slice(0, 20);

  const s = data?.summary;
  const isError = !!error && !uiLoading;
  /** After /analytics/dashboard merges, KPIs/LY/customers match transaction totals checksum. */
  const dashMerged = data?.checksum != null;
  const lyKpiDisplay = hasLyData
    ? fmtLakhs(s?.ly_sales ?? 0)
    : (uiLoading || chartLoading ? 'Loading…' : '—');
  const customerPending =
    !dashMerged
    && (s?.mtd_sales ?? 0) > 0
    && (s?.bills ?? 0) > 0
    && s?.customers == null;
  const customerKpiDisplay = formatCustomerKpi(s?.customers, {
    loading: (uiLoading || chartLoading || customerPending) && s?.customers == null,
    hasSalesActivity: (s?.mtd_sales ?? 0) > 0 && ((s?.bills ?? 0) > 0 || (s?.quantity ?? 0) > 0),
  });

  const kpiCards = s ? [
    { label: period === 'today' ? "Today's Sales" : `${PERIOD_TABS.find(t=>t.period===period)?.label ?? ''} Sales`,
      value: fmtLakhs(s.mtd_sales), sub: lyKpiDisplay === 'Loading…' ? 'LY: Loading…' : `LY: ${lyKpiDisplay}`,
      growth: lyGrowthReady(hasLyData, s.sales_growth_pct), icon: KPI_ICONS[0], color: KPI_COLORS[0] },
    { label: 'Quantity Sold', value: fmtCount(s.quantity), sub: 'Units sold',
      icon: KPI_ICONS[1], color: KPI_COLORS[1] },
    { label: 'Bills Generated', value: fmtCount(s.bills), sub: 'Total invoices',
      icon: KPI_ICONS[2], color: KPI_COLORS[2] },
    { label: 'Customer Count', value: customerKpiDisplay, sub: customerKpiDisplay === 'Loading…' ? 'Distinct customers' : 'Unique customers',
      icon: KPI_ICONS[3], color: KPI_COLORS[3] },
  ] : [];

  // Suppliers only — bills/customers already shown in main KPI row above.
  const extras = data?.kpis;
  const extraCards =
    extras?.distinct_suppliers?.value != null
      ? [{
          label: 'Distinct Suppliers',
          value: fmtCount(extras.distinct_suppliers.value),
          sub: 'Active suppliers',
          icon: Truck,
          color: '#FFA726',
        }]
      : [];

  const onPieEnter = useCallback((_: any, index: number) => setActivePieIndex(index), []);

  // Custom ranges keep day-level granularity up to 31 days (see
  // trend_granularity_for_custom), and users picking a custom range expect
  // labels on every bar regardless of count — so use the relaxed (31) cap
  // for custom periods even when gran === 'day'.
  const labelCap = (gran === 'month' || period === 'custom') ? 31 : 14;
  const showBarLabels = chartData.length <= labelCap;
  const daywiseLabelMax = labelCap;
  const periodUnit = gran === 'month' ? 'months' : 'days';

  // Show a subtle "loading LY data" badge for YoY periods until prior values arrive.
  const lyLoadingBadge =
    !hasLyData
    && !chartLoading
    && chartData.length > 0
    && (period === 'today' || period === 'qtd' || period === 'ytd' || period === 'last_6m' || period === 'mtd')
    && !data?.checksum;

  // ── Breakdown chart data ───────────────────────────────────────────────────
  const daywiseAreaData = useMemo(() =>
    (data?.daywise ?? []).map(d => ({
      label: formatChartLabel(d.label || d.date, gran),
      current: d.sales,
      prior: d.prior,
    })),
    [data?.daywise, gran]);

  const daywiseBillsData = useMemo(() =>
    (data?.daywise ?? []).map(d => ({
      label: formatChartLabel(d.label || d.date, gran),
      bills: d.bills ?? 0,
    })),
    [data?.daywise, gran]);

  const daywiseBillsSum = useMemo(
    () => (data?.daywise ?? []).reduce((s, d) => s + (d.bills ?? 0), 0),
    [data?.daywise],
  );

  const topCategories = useMemo(() =>
    allCategories.slice(0, 12).map(c => ({ name: c.name.slice(0, 14), value: c.revenue })),
    [allCategories]);

  const topBranches = useMemo(() =>
    allBranches.slice(0, 15).map(b => ({ name: b.name.slice(0, 12), value: b.revenue })),
    [allBranches]);

  const departmentRows = data?.departments ?? [];
  const deptChartLoading =
    (chartLoading || loading) && departmentRows.length === 0
    && ((data?.categories?.length ?? 0) > 0 || (data?.branches?.length ?? 0) > 0);

  const topDepts = useMemo(() =>
    departmentRows.slice(0, 15).map(d => ({
      name: (d.name || '—').slice(0, 14),
      value: d.revenue,
    })),
    [departmentRows]);

  // ── Breakdown renderChart helpers ──────────────────────────────────────────
  /** Wrap a chart in a horizontal-scroll container once it has more bars/points
   *  than comfortably fit on a narrow screen, instead of letting Recharts
   *  squash everything down. */
  function withHScroll(node: React.ReactNode, itemCount: number, slotPx = 56, threshold = 10): React.ReactNode {
    if (itemCount <= threshold) return node;
    return (
      <div className="w-full overflow-x-auto overflow-y-hidden -mx-1 px-1" style={{ WebkitOverflowScrolling: 'touch' }}>
        <div style={{ minWidth: itemCount * slotPx }}>{node}</div>
      </div>
    );
  }
  const tooltipStyle = {
    background: isDark ? 'rgba(8,15,26,0.97)' : 'rgba(255,255,255,0.98)',
    border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
    borderRadius: 10, fontSize: 11,
  };
  const gridColor = isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
  const cursorFill = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)';

  /** Single-series (category/branch/dept): renders Bar, Line or Pie */
  function renderSingleSeries(
    type: 'bar' | 'line' | 'pie',
    items: { name: string; value: number }[],
  ): React.ReactNode {
    if (!items.length) return undefined;
    const many = items.length > 8;
    const angle = many ? -38 : 0;
    const ta = many ? ('end' as const) : ('middle' as const);
    const mbottom = many ? 58 : 20;

    if (type === 'bar') return withHScroll(
      <ResponsiveContainer width="100%" height={breakdownBarHeight}>
        <BarChart data={items} barCategoryGap="28%"
          margin={{ top: 10, right: 8, left: 4, bottom: mbottom }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="name" axisLine={false} tickLine={false} interval={0}
            tick={{ fontSize: 10, fill: 'var(--text-muted)', angle, textAnchor: ta }} />
          <YAxis tickFormatter={fmtLakhsAxis} axisLine={false} tickLine={false}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={50} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: cursorFill, radius: 4 }} />
          <Bar dataKey="value" name="Revenue" radius={[4, 4, 0, 0]} maxBarSize={44}>
            {items.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            {items.length <= 20 && (
              <LabelList dataKey="value" position="top"
                formatter={(v: number) => fmtLakhsAxis(Number(v))}
                style={{ fontSize: 9, fill: 'var(--text-muted)', fontWeight: 600 }} />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>,
      items.length,
    );

    if (type === 'line') return withHScroll(
      <ResponsiveContainer width="100%" height={breakdownLineHeight}>
        <LineChart data={items} margin={{ top: 10, right: 8, left: 4, bottom: mbottom }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="name" axisLine={false} tickLine={false} interval={0}
            tick={{ fontSize: 10, fill: 'var(--text-muted)', angle, textAnchor: ta }} />
          <YAxis tickFormatter={fmtLakhsAxis} axisLine={false} tickLine={false}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={50} />
          <Tooltip content={<ChartTooltip />} />
          <Line type="monotone" dataKey="value" name="Revenue"
            stroke="#5882ff" strokeWidth={2}
            dot={{ fill: '#5882ff', r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, fill: '#5882ff' }}>
            {items.length <= 20 && (
              <LabelList dataKey="value" position="top"
                formatter={(v: number) => v >= 100 ? `${(v/100).toFixed(1)}L` : `${v.toFixed(1)}`}
                style={{ fontSize: 9, fill: 'var(--text-muted)', fontWeight: 600 }} />
            )}
          </Line>
        </LineChart>
      </ResponsiveContainer>,
      items.length,
    );

    if (type === 'pie') {
      const innerR = isMobile ? 46 : 55;
      const outerR = isMobile ? 72 : 85;
      return (
        <div className={`flex items-center gap-3 md:gap-4 ${isMobile ? 'flex-col' : 'flex-row'}`}>
          <PieChart width={pieChartSize} height={pieChartSize} className="mx-auto shrink-0">
            <Pie data={items} dataKey="value" nameKey="name"
              cx="50%" cy="50%" innerRadius={innerR} outerRadius={outerR}
              paddingAngle={2} strokeWidth={0}>
              {items.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            </Pie>
            <Tooltip
              formatter={(v: number, name) => [fmtLakhs(Number(v)), String(name)]}
              contentStyle={tooltipStyle} />
          </PieChart>
          <PieLegend items={items} isDark={isDark} className={isMobile ? 'max-h-[180px]' : 'flex-1 min-w-0'} />
        </div>
      );
    }
    return undefined;
  }

  /** Day-wise bill counts — same SQL definition as Bills Generated KPI */
  function renderDaywiseBills(type: 'bar' | 'line' | 'pie'): React.ReactNode {
    if (!daywiseBillsData.length) return undefined;
    const interval = daywiseBillsData.length > 20 ? ('preserveStartEnd' as const) : 0;
    const showLabels = daywiseBillsData.length <= 31;

    if (type === 'bar') return withHScroll(
      <ResponsiveContainer width="100%" height={daywiseBarHeight}>
        <BarChart data={daywiseBillsData} barCategoryGap="28%" margin={{ top: showLabels ? 22 : 10, right: 8, left: 2, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} interval={interval}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <YAxis tickFormatter={fmtCountAxis} axisLine={false} tickLine={false} width={48}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <Tooltip
            formatter={(v: number) => [fmtCount(Number(v)), 'Bills']}
            labelFormatter={(l) => String(l)}
            contentStyle={tooltipStyle} cursor={{ fill: cursorFill, radius: 4 }} />
          <Bar dataKey="bills" name="Bills" fill="#26C6DA" radius={[4, 4, 0, 0]} maxBarSize={28}>
            {showLabels && (
              <LabelList dataKey="bills" position="top"
                formatter={(v: number) => fmtCountAxis(Number(v))}
                style={{ fontSize: 9, fill: 'var(--text-muted)', fontWeight: 600 }} />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>,
      daywiseBillsData.length, 40, 14,
    );

    if (type === 'line') return withHScroll(
      <ResponsiveContainer width="100%" height={daywiseLineHeight}>
        <LineChart data={daywiseBillsData} margin={{ top: 8, right: 8, left: 2, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} interval={interval}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <YAxis tickFormatter={fmtCountAxis} axisLine={false} tickLine={false} width={48}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <Tooltip
            formatter={(v: number) => [fmtCount(Number(v)), 'Bills']}
            contentStyle={tooltipStyle} />
          <Line type="monotone" dataKey="bills" name="Bills" stroke="#26C6DA" strokeWidth={2}
            dot={daywiseBillsData.length <= 12 ? { fill: '#26C6DA', r: 3, strokeWidth: 0 } : false} />
        </LineChart>
      </ResponsiveContainer>,
      daywiseBillsData.length, 40, 20,
    );

    if (type === 'pie') {
      const top = daywiseBillsData.slice(0, 10).map(d => ({ name: d.label, value: d.bills }));
      return renderSingleSeries('pie', top);
    }
    return undefined;
  }

  /** Day-wise (two series: current + prior): Bar, Area/Line, Pie */
  function renderDaywise(type: 'bar' | 'line' | 'pie'): React.ReactNode {
    if (!daywiseAreaData.length) return undefined;
    const interval = daywiseAreaData.length > 20 ? ('preserveStartEnd' as const) : 0;

    if (type === 'bar') {
      _lblY.clear();
      return withHScroll(
      <ResponsiveContainer width="100%" height={daywiseBarHeight}>
        <BarChart data={daywiseAreaData} barCategoryGap="28%" barGap={3}
          margin={{ top: daywiseAreaData.length <= daywiseLabelMax ? 26 : 10, right: 8, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
          <XAxis dataKey="label" axisLine={false} tickLine={false} interval={interval}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
          <YAxis tickFormatter={fmtLakhsAxis} axisLine={false} tickLine={false}
            tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={48} />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: cursorFill, radius: 4 }} />
          <Bar dataKey="prior" name="Last Year"
            fill={isDark ? '#475569' : '#cbd5e1'} radius={[4, 4, 0, 0]} maxBarSize={28}>
            {daywiseAreaData.length <= daywiseLabelMax && (
              <LabelList dataKey="prior"
                content={(props: any) => (
                  <SmartBarLabel {...props} value={props.value}
                    fill={isDark ? '#94a3b8' : '#64748b'} barKey="prior" idx={props.index} />
                )}
              />
            )}
          </Bar>
          <Bar dataKey="current" name="Current"
            fill="#5882ff" radius={[4, 4, 0, 0]} maxBarSize={28}>
            {daywiseAreaData.length <= daywiseLabelMax && (
              <LabelList dataKey="current"
                content={(props: any) => (
                  <SmartBarLabel {...props} value={props.value}
                    fill="#5882ff" barKey="current" idx={props.index} />
                )}
              />
            )}
          </Bar>
        </BarChart>
      </ResponsiveContainer>,
      daywiseAreaData.length, 48, 14,
      );
    }

    if (type === 'line') return (
      <div>
        <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
          {[['#5882ff','Current'],['#94a3b8','Last Year']].map(([c,n]) => (
            <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 16, height: 2, borderRadius: 1, background: c }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{n}</span>
            </div>
          ))}
        </div>
        {withHScroll(
          <ResponsiveContainer width="100%" height={daywiseLineHeight}>
            <AreaChart data={daywiseAreaData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="dgCurr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#5882ff" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#5882ff" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="dgPrior" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#94a3b8" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#94a3b8" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
              <XAxis dataKey="label" axisLine={false} tickLine={false} interval={interval}
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }} />
              <YAxis tickFormatter={fmtLakhsAxis} axisLine={false} tickLine={false}
                tick={{ fontSize: 10, fill: 'var(--text-muted)' }} width={48} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="prior" name="Last Year"
                stroke="#94a3b8" strokeWidth={1.5} fill="url(#dgPrior)"
                dot={daywiseAreaData.length <= 12 ? { fill: '#94a3b8', r: 3, strokeWidth: 0 } : false}
                activeDot={{ r: 4 }} />
              <Area type="monotone" dataKey="current" name="Current"
                stroke="#5882ff" strokeWidth={2} fill="url(#dgCurr)"
                dot={daywiseAreaData.length <= 12 ? { fill: '#5882ff', r: 3, strokeWidth: 0 } : false}
                activeDot={{ r: 5 }} />
            </AreaChart>
          </ResponsiveContainer>,
          daywiseAreaData.length, 48, 20,
        )}
      </div>
    );

    if (type === 'pie') {
      const topDays = daywiseAreaData.slice(0, 10).map(d => ({ name: d.label, value: d.current }));
      return (
        <div className={`flex items-center gap-3 md:gap-4 ${isMobile ? 'flex-col' : 'flex-row'}`}>
          <PieChart width={pieChartSize} height={pieChartSize} className="mx-auto shrink-0">
            <Pie data={topDays} dataKey="value" nameKey="name"
              cx="50%" cy="50%" innerRadius={isMobile ? 46 : 55} outerRadius={isMobile ? 72 : 85}
              paddingAngle={2} strokeWidth={0}>
              {topDays.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
            </Pie>
            <Tooltip
              formatter={(v: number, name) => [fmtLakhs(Number(v)), String(name)]}
              contentStyle={tooltipStyle} />
          </PieChart>
          <PieLegend items={topDays} isDark={isDark} className={isMobile ? 'max-h-[180px]' : 'flex-1 min-w-0'} />
        </div>
      );
    }
    return undefined;
  }

  return (
    <div className="space-y-5">

      {/* ── Header ── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold" style={{
            background: isDark
              ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)'
              : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>Sales Analytics</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            {data?.period_label ?? 'Select a period'} · All values in Lakhs (L)
          </p>
          {PERIOD_WINDOW_HINT[period] ? (
            <p className="text-xs mt-1 max-w-xl leading-relaxed" style={{ color: 'var(--text-muted)' }}>
              {PERIOD_WINDOW_HINT[period]}
            </p>
          ) : null}
        </div>
        <button type="button" onClick={handleRefresh}
          className="flex shrink-0 items-center justify-center gap-2 self-start px-3 py-2 rounded-xl text-xs font-medium transition-all sm:self-auto"
          style={{
            background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
            border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
            color: 'var(--text-secondary)',
          }}>
          <RefreshCw size={12} className={uiLoading || refreshSpinning ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* ── Period tabs ── */}
      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="flex min-w-0 items-center gap-1 overflow-x-auto p-1 rounded-xl scrollbar-none w-full sm:w-auto"
          style={{
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
            border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
          }}>
          {PERIOD_TABS.map((t) => (
            <button key={t.period} type="button"
              onMouseEnter={() => void prefetchAnalyticsPage(t.period)}
              onFocus={() => void prefetchAnalyticsPage(t.period)}
              onClick={() => setPeriod(t.period)}
              className="shrink-0 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all"
              style={{
                background: period === t.period
                  ? isDark ? 'rgba(88,130,255,0.18)' : 'rgba(88,130,255,0.12)'
                  : 'transparent',
                color: period === t.period ? '#5882ff' : 'var(--text-muted)',
                boxShadow: period === t.period ? '0 0 12px rgba(88,130,255,0.3)' : 'none',
              }}>
              {t.label}
            </button>
          ))}
        </div>

        {period === 'custom' && (
          <div className="flex flex-wrap gap-2 items-center">
            <input
              type="date" value={pendingStart}
              onChange={(e) => setPendingStart(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyCustom()}
              className="px-3 py-1.5 rounded-xl text-xs outline-none"
              style={{
                background: isDark ? 'rgba(255,255,255,0.05)' : 'white',
                border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.15)',
                color: 'var(--text-primary)',
              }}
            />
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>to</span>
            <input
              type="date" value={pendingEnd}
              onChange={(e) => setPendingEnd(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applyCustom()}
              className="px-3 py-1.5 rounded-xl text-xs outline-none"
              style={{
                background: isDark ? 'rgba(255,255,255,0.05)' : 'white',
                border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.15)',
                color: 'var(--text-primary)',
              }}
            />
            <button
              onClick={applyCustom} disabled={!canApplyCustom}
              className="px-3 py-1.5 rounded-xl text-xs font-semibold transition-all"
              style={{
                background: canApplyCustom
                  ? (customDirty ? '#5882ff' : (isDark ? 'rgba(88,130,255,0.18)' : 'rgba(88,130,255,0.12)'))
                  : (isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'),
                color: canApplyCustom ? (customDirty ? '#fff' : '#5882ff') : 'var(--text-muted)',
                border: `1px solid ${canApplyCustom ? 'rgba(88,130,255,0.4)' : 'transparent'}`,
                cursor: canApplyCustom ? 'pointer' : 'not-allowed',
              }}
            >{customDirty ? '▶ Apply' : '✓ Applied'}</button>
            <button
              type="button" onClick={handleClearCustomCache} disabled={clearingCache}
              title="Clear cached result for this custom range and refetch fresh data"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
              style={{
                background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
                color: clearCacheMsg
                  ? (clearCacheMsg.startsWith('Clear') ? '#f87171' : '#34d399')
                  : 'var(--text-muted)',
                cursor: clearingCache ? 'wait' : 'pointer',
                opacity: clearingCache ? 0.6 : 1,
              }}
            >
              <Trash2 size={11} className={clearingCache ? 'animate-pulse' : ''} />
              {clearCacheMsg ?? 'Clear Cache'}
            </button>
          </div>
        )}
      </div>

      {/* ── Reversed custom range warning ── */}
      <AnimatePresence>
        {isReversedRange && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="px-3.5 py-2.5 rounded-xl flex items-center gap-2.5 text-xs"
            style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.25)', color: '#f87171' }}>
            <AlertTriangle size={14} />
            <span className="font-semibold">Invalid date range —</span>
            <span style={{ color: 'var(--text-secondary)' }}>start date is after end date. Please pick an end date on or after the start date.</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Error banner ── */}
      <AnimatePresence>
        {isError && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="p-3.5 rounded-xl flex items-center gap-2.5 text-xs"
            style={{ background: 'rgba(255,184,0,0.08)', border: '1px solid rgba(255,184,0,0.2)', color: '#ffb800' }}>
            <AlertTriangle size={14} />
            <span className="font-semibold">Data unavailable —</span>
            <span style={{ color: 'var(--text-secondary)' }}>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {waitingForCustomDates ? (
        <Card className="p-12 flex flex-col items-center justify-center text-center gap-3">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
            style={{
              background: isDark ? 'rgba(88,130,255,0.12)' : 'rgba(88,130,255,0.08)',
              border: '1px solid rgba(88,130,255,0.2)',
            }}>
            <CalendarRange size={22} style={{ color: '#5882ff' }} />
          </div>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Select a custom date range to display the data
          </p>
          <p className="text-xs max-w-sm" style={{ color: 'var(--text-muted)' }}>
            Choose a start date and end date above, then analytics for that range will load here.
          </p>
        </Card>
      ) : customFetching ? (
        <Card className="p-12 flex flex-col items-center justify-center text-center gap-3">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
            style={{
              background: isDark ? 'rgba(88,130,255,0.12)' : 'rgba(88,130,255,0.08)',
              border: '1px solid rgba(88,130,255,0.2)',
            }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#5882ff"
              strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
              className="animate-spin">
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
          </div>
          <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Fetching data for {customStart} → {customEnd}
          </p>
          <p className="text-xs max-w-sm" style={{ color: 'var(--text-muted)' }}>
            Querying SQL Server for the selected date range. Large ranges may take a moment…
          </p>
        </Card>
      ) : (
      <>
      {/* ── Today: no-sales banner ── */}
      {period === 'today' && !uiLoading && s && (s.mtd_sales ?? 0) === 0 && (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-2xl text-sm"
          style={{
            background: isDark ? 'rgba(255,184,0,0.08)' : 'rgba(255,184,0,0.07)',
            border: '1px solid rgba(255,184,0,0.25)',
            color: '#ffb800',
          }}
        >
          <span style={{ fontSize: 16 }}>🌙</span>
          <span>
            <strong>No sales recorded today yet.</strong>{' '}
            The store may not have opened or transactions haven&apos;t been processed.
            Switch to <strong>MTD</strong> for the latest data, or check back once sales begin.
          </span>
        </div>
      )}
      {/* ── KPI cards ── */}
      <div className={`grid gap-3 ${
        extraCards.length > 0
          ? 'grid-cols-2 sm:grid-cols-3 xl:grid-cols-5'
          : 'grid-cols-2 lg:grid-cols-4'
      }`}>
        {uiLoading ? (
          [...Array(extraCards.length > 0 ? 5 : 4)].map((_, i) => (
            <Card key={i} className="p-4">
              <div className="animate-pulse space-y-2">
                <div className="h-2.5 rounded w-1/2" style={{ background: 'rgba(128,128,128,0.12)' }} />
                <div className="h-7 rounded w-3/4" style={{ background: 'rgba(128,128,128,0.1)' }} />
                <div className="h-2 rounded w-2/3" style={{ background: 'rgba(128,128,128,0.08)' }} />
              </div>
            </Card>
          ))
        ) : kpiCards.length > 0 ? (
          <>
          {kpiCards.map((k, i) => {
            const Icon = k.icon;
            return (
              <motion.div key={k.label}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.07, type: 'spring', stiffness: 280, damping: 26 }}>
                <Card className="p-3 sm:p-4 relative overflow-hidden">
                  <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
                    style={{ background: `linear-gradient(90deg, transparent, ${k.color}, transparent)` }} />
                  <div className="absolute top-0 right-0 w-24 h-24 pointer-events-none rounded-full"
                    style={{ background: `radial-gradient(circle, ${k.color}18 0%, transparent 70%)`, transform: 'translate(30%,-30%)' }} />
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-[11px] sm:text-xs font-medium leading-snug pr-1" style={{ color: 'var(--text-muted)' }}>{k.label}</p>
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: `${k.color}18`, border: `1px solid ${k.color}30` }}>
                      <Icon size={13} style={{ color: k.color }} />
                    </div>
                  </div>
                  <p className="text-lg sm:text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                    {k.value}
                  </p>
                  <p className="text-[11px] sm:text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{k.sub}</p>
                  {'growth' in k && k.growth != null && (
                    <div className="flex items-center gap-1 mt-1.5">
                      {k.growth >= 0
                        ? <TrendingUp size={11} style={{ color: '#00e67a' }} />
                        : <TrendingDown size={11} style={{ color: '#f87171' }} />}
                      <p className="text-[11px] sm:text-xs font-semibold"
                        style={{ color: k.growth >= 0 ? '#00e67a' : '#f87171' }}>
                        {k.growth >= 0 ? '+' : ''}{k.growth}% vs LY
                      </p>
                    </div>
                  )}
                </Card>
              </motion.div>
            );
          })}
          {extraCards.map((k, i) => {
            const Icon = k.icon;
            return (
              <motion.div key={k.label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: (kpiCards.length + i) * 0.06, type: 'spring', stiffness: 280, damping: 26 }}>
                <Card className="p-3 sm:p-4 relative overflow-hidden">
                  <div className="absolute top-0 left-0 right-0 h-0.5 rounded-t-2xl"
                    style={{ background: `linear-gradient(90deg, transparent, ${k.color}, transparent)` }} />
                  <div className="absolute top-0 right-0 w-20 h-20 pointer-events-none rounded-full"
                    style={{ background: `radial-gradient(circle, ${k.color}18 0%, transparent 70%)`, transform: 'translate(30%,-30%)' }} />
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-[11px] sm:text-xs font-medium leading-snug pr-1" style={{ color: 'var(--text-muted)' }}>{k.label}</p>
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: `${k.color}18`, border: `1px solid ${k.color}30` }}>
                      <Icon size={13} style={{ color: k.color }} />
                    </div>
                  </div>
                  <p className="text-lg sm:text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                    {k.value ?? '—'}
                  </p>
                  <p className="text-[11px] sm:text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{k.sub}</p>
                </Card>
              </motion.div>
            );
          })}
          </>
        ) : (
          !isError && (
            <div className="col-span-4 text-center py-4 text-sm" style={{ color: 'var(--text-muted)' }}>
              No data for this period
            </div>
          )
        )}
      </div>

      {/* ── Checksum strip ── */}
      {data?.checksum && !chartLoading && (
        <Card className="px-4 py-2.5 flex flex-wrap items-center gap-2.5">
          {data.checksum.match
            ? <CheckCircle2 size={14} style={{ color: '#00e67a', flexShrink: 0 }} />
            : <AlertTriangle size={14} style={{ color: '#f87171', flexShrink: 0 }} />}
          <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            <span className="font-semibold" style={{ color: data.checksum.match ? '#00e67a' : '#f87171' }}>
              Σ Checksum {data.checksum.match ? 'validated' : 'mismatch'}
            </span>
            {' — '}Trend total: <span className="font-mono">{fmtLakhs(data.checksum.trend_total)}</span>
            {' · '}Summary: <span className="font-mono">{fmtLakhs(data.checksum.summary_total)}</span>
          </span>
        </Card>
      )}

      {/* ── YoY Bar chart ── */}
      <Card className="p-3 sm:p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mb-1">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            {hasLyData ? 'Sales — Current vs Same Period Last Year' : 'Sales — Current Period'}
          </h2>
          <div className="flex flex-wrap items-center gap-3 sm:gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-2 rounded-sm" style={{ background: '#5882ff' }} />Current
            </div>
            {hasLyData && (
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-2 rounded-sm" style={{ background: '#94a3b8' }} />Last Year
              </div>
            )}
            {lyLoadingBadge && (
              <div className="flex items-center gap-1" style={{ color: 'var(--text-muted)', fontSize: 10, opacity: 0.7 }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="animate-spin">
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Loading last year…
              </div>
            )}
          </div>
        </div>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
          {period === 'today'
            ? 'Single day snapshot · Labels in Lakhs'
            : `${data?.granularity === 'month' ? 'Month-wise' : 'Day-wise'} · ${hasLyData ? 'YoY comparison · ' : ''}Labels in Lakhs`}
        </p>
        {chartLoading ? (
          <div className="animate-pulse rounded-xl"
            style={{ height: yoyChartHeight, background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
        ) : chartData.length === 0 ? (
          <p className="text-sm py-16 text-center" style={{ color: 'var(--text-muted)' }}>
            No data for this period
          </p>
        ) : withHScroll(
          <ResponsiveContainer width="100%" height={yoyChartHeight}>
            {(() => {
              _lblY.clear();
              const manyBars = chartData.length > 8;
              const xAngle = manyBars ? -38 : 0;
              const xAnchor = manyBars ? ('end' as const) : ('middle' as const);
              const xBottom = manyBars ? 44 : 4;
              return (
            <BarChart data={chartData}
              margin={{ top: showBarLabels ? 24 : 10, right: 12, left: 4, bottom: xBottom }}
              barCategoryGap="32%" barGap={4}>
              <CartesianGrid strokeDasharray="4 6"
                stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
              <XAxis dataKey="label"
                tick={{ fontSize: 10, fill: 'var(--text-muted)', angle: xAngle, textAnchor: xAnchor }}
                axisLine={false} tickLine={false} interval={0}
                height={manyBars ? 52 : 25} />
              <YAxis tickFormatter={fmtLakhsAxis} tick={{ fontSize: 10, fill: 'var(--text-muted)' }}
                axisLine={false} tickLine={false} width={52} />
              <Tooltip content={<ChartTooltip />}
                cursor={{ fill: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', radius: 4 }} />
              <Bar dataKey="current" name="Current" fill="#5882ff" radius={[4, 4, 0, 0]} maxBarSize={36}>
                {showBarLabels && (
                  <LabelList dataKey="current"
                    content={(props: any) => (
                      <SmartBarLabel {...props} value={props.value}
                        fill="#5882ff" barKey="current" idx={props.index} />
                    )}
                  />
                )}
              </Bar>
              {hasLyData && (
                <Bar dataKey="prior" name="Last Year"
                  fill={isDark ? '#475569' : '#cbd5e1'} radius={[4, 4, 0, 0]} maxBarSize={36}>
                  {showBarLabels && (
                    <LabelList dataKey="prior"
                      content={(props: any) => (
                        <SmartBarLabel {...props} value={props.value}
                          fill={isDark ? '#94a3b8' : '#64748b'} barKey="prior" idx={props.index} />
                      )}
                    />
                  )}
                </Bar>
              )}
            </BarChart>
              );
            })()}
          </ResponsiveContainer>,
          chartData.length, 56, 8,
        )}
      </Card>

      {/* ── Pie + Branch list ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Donut — Category % Contribution */}
        <Card className="p-3 sm:p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between mb-4">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Category % Contribution
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {allCategories.length} categories · hover slice to highlight
              </p>
            </div>
            <button type="button" onClick={() => setExpandCategories(!expandCategories)}
              className="flex shrink-0 items-center gap-1 self-start text-xs px-2.5 py-1 rounded-lg transition-all"
              style={{
                background: isDark ? 'rgba(88,130,255,0.1)' : 'rgba(88,130,255,0.08)',
                border: '1px solid rgba(88,130,255,0.2)', color: '#5882ff',
              }}>
              {expandCategories ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {expandCategories ? `Top 16` : `All ${allCategories.length}`}
            </button>
          </div>

          {pieData.length === 0 ? (
            <p className="text-sm text-center py-20" style={{ color: 'var(--text-muted)' }}>
              {uiLoading ? 'Loading…' : 'No category data'}
            </p>
          ) : (
            <div className={`flex gap-4 md:gap-5 items-center min-h-[220px] ${isMobile ? 'flex-col' : 'flex-row'}`}>

              {/* Donut */}
              <div className="shrink-0 mx-auto md:mx-0">
                <PieChart width={categoryPieSize} height={categoryPieSize}>
                  <Pie
                    data={pieData}
                    dataKey="percentage"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={isMobile ? 54 : 66}
                    outerRadius={isMobile ? 80 : 98}
                    paddingAngle={2}
                    strokeWidth={0}
                    activeIndex={activePieIndex}
                    activeShape={<ActiveShape />}
                    onMouseEnter={onPieEnter}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v: number, name: string) => [
                      `${Number(v).toFixed(2)}%  ·  ${fmtLakhs(pieData.find(c => c.name === name)?.revenue ?? 0)}`,
                      name,
                    ]}
                    contentStyle={{
                      background: isDark ? 'rgba(8,15,26,0.97)' : 'rgba(255,255,255,0.98)',
                      border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                      borderRadius: 10, fontSize: 11,
                    }}
                  />
                </PieChart>
              </div>

              {/* Legend */}
              <div className="w-full md:flex-1 overflow-y-auto max-h-[240px] md:max-h-[230px]">
                {pieData.map((cat, i) => {
                  const color = PIE_COLORS[i % PIE_COLORS.length];
                  const isActive = i === activePieIndex;
                  return (
                    <div
                      key={cat.name}
                      onMouseEnter={() => setActivePieIndex(i)}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '5px 8px', borderRadius: 8, cursor: 'default',
                        background: isActive ? (isDark ? `${color}18` : `${color}12`) : 'transparent',
                        transition: 'background 0.15s',
                        marginBottom: 2,
                      }}
                    >
                      {/* Color swatch */}
                      <div style={{
                        width: 10, height: 10, borderRadius: 3,
                        background: color, flexShrink: 0,
                        boxShadow: isActive ? `0 0 8px ${color}` : 'none',
                      }} />
                      {/* Name */}
                      <span style={{
                        fontSize: 11, flex: 1,
                        color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                        fontWeight: isActive ? 600 : 400,
                        whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      }}>
                        {cat.name}
                      </span>
                      {/* Revenue */}
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
                        {fmtLakhs(cat.revenue)}
                      </span>
                      {/* Percentage badge */}
                      <span style={{
                        fontSize: 11, fontWeight: 700, flexShrink: 0,
                        color: color,
                        minWidth: 40, textAlign: 'right',
                        fontVariantNumeric: 'tabular-nums',
                      }}>
                        {cat.percentage.toFixed(2)}%
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </Card>

        {/* Store-wise sales list */}
        <Card className="p-3 sm:p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between mb-4">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Store-wise Sales</h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {allBranches.length} stores · ranked by revenue
              </p>
            </div>
            <button type="button" onClick={() => setExpandBranches(!expandBranches)}
              className="flex shrink-0 items-center gap-1 self-start text-xs px-2.5 py-1 rounded-lg transition-all"
              style={{
                background: isDark ? 'rgba(88,130,255,0.1)' : 'rgba(88,130,255,0.08)',
                border: '1px solid rgba(88,130,255,0.2)', color: '#5882ff',
              }}>
              {expandBranches ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
              {expandBranches ? 'Top 20' : `All ${allBranches.length}`}
            </button>
          </div>
          {uiLoading ? (
            <div className="space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="flex items-center gap-3 animate-pulse">
                  <div className="h-2.5 flex-1 rounded" style={{ background: 'rgba(128,128,128,0.1)' }} />
                  <div className="h-2.5 w-20 rounded" style={{ background: 'rgba(128,128,128,0.08)' }} />
                </div>
              ))}
            </div>
          ) : branchList.length === 0 ? (
                <p className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>No branch data</p>
              ) : (
                <>
                {/* Mobile: card list */}
                <div className="space-y-2.5 max-h-[280px] overflow-y-auto sm:hidden">
                  {branchList.map((b, i) => {
                    const pct = Number(b.percentage ?? 0);
                    const maxPct = Number(branchList[0]?.percentage ?? 1);
                    return (
                      <div key={b.name + i} className="rounded-xl border px-3 py-2.5"
                        style={{
                          borderColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
                          background: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
                        }}>
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>#{i + 1}</p>
                            <p className="truncate text-xs font-medium mt-0.5" style={{ color: 'var(--text-primary)' }}>{b.name}</p>
                          </div>
                          <div className="shrink-0 text-right">
                            <p className="text-xs font-semibold tabular-nums" style={{ color: '#5882ff' }}>{fmtLakhs(b.revenue)}</p>
                            <p className="text-[10px] tabular-nums mt-0.5" style={{ color: 'var(--text-secondary)' }}>{pct.toFixed(2)}%</p>
                          </div>
                        </div>
                        <div className="mt-2 h-1.5 rounded-full overflow-hidden"
                          style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
                          <div className="h-full rounded-full"
                            style={{ width: `${Math.min(100, (pct / maxPct) * 100)}%`, background: 'linear-gradient(90deg, #5882ff, #00e67a)' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                {/* Tablet+: table */}
                <div className="hidden sm:block overflow-y-auto" style={{ maxHeight: 220 }}>
                <table className="w-full text-xs border-collapse min-w-[280px]">
                  <thead>
                    <tr style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
                      {['#','Store','Revenue','Share'].map(h => (
                        <th key={h}
                          className={`pb-2 font-semibold ${h==='Revenue'||h==='Share' ? 'text-right' : 'text-left'} ${h !== '#' ? 'pr-2' : ''}`}
                          style={{ color: 'var(--text-muted)' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {branchList.map((b, i) => {
                      const pct = Number(b.percentage ?? 0);
                      const maxPct = Number(branchList[0]?.percentage ?? 1);
                      return (
                        <tr key={b.name + i} className="transition-all"
                          style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.03)' : '1px solid rgba(0,0,0,0.04)' }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}>
                          <td className="py-2 pr-2 font-mono" style={{ color: 'var(--text-muted)', width: 24 }}>{i + 1}</td>
                          <td className="py-2 pr-3">
                            <div className="flex flex-col gap-1">
                              <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{b.name}</span>
                              <div className="h-1 rounded-full overflow-hidden"
                                style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
                                <div className="h-full rounded-full"
                                  style={{ width: `${Math.min(100, (pct / maxPct) * 100)}%`, background: 'linear-gradient(90deg, #5882ff, #00e67a)' }} />
                              </div>
                            </div>
                          </td>
                          <td className="py-2 text-right font-semibold tabular-nums" style={{ color: '#5882ff' }}>{fmtLakhs(b.revenue)}</td>
                          <td className="py-2 text-right tabular-nums" style={{ color: 'var(--text-secondary)' }}>{pct.toFixed(2)}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                </div>
                </>
              )}
        </Card>
      </div>

      {/* ── Detailed breakdown sections with Bar/Line/Pie toggle ── */}
      <div className="space-y-4">

        {/* Day-wise breakdown hidden for Today — single-day view makes row table redundant */}
        {period !== 'today' && (
          <>
            <BreakdownTable
              title="Day-wise Sales"
              subtitle={`${data?.daywise?.length ?? 0} ${periodUnit} · current vs last year`}
              loading={uiLoading}
              isDark={isDark}
              columns={['#', 'Date', 'Label', 'Sales', 'Qty', 'LY Sales']}
              rows={(data?.daywise ?? []).map((d, i) => [
                String(i + 1),
                d.date,
                formatChartLabel(d.label || d.date, gran),
                fmtLakhs(d.sales),
                fmtCount(d.quantity),
                d.prior > 0 ? fmtLakhs(d.prior) : '—',
              ])}
              renderChart={renderDaywise}
            />
            <BreakdownTable
              title="Day-wise Bills"
              subtitle={
                s
                  ? `${data?.daywise?.length ?? 0} days · daily sum ${fmtCount(daywiseBillsSum)} · KPI ${fmtCount(s.bills)}`
                  : `${data?.daywise?.length ?? 0} days · bill count per day`
              }
              loading={uiLoading}
              isDark={isDark}
              columns={['#', 'Date', 'Label', 'Bills']}
              rows={(data?.daywise ?? []).map((d, i) => [
                String(i + 1),
                d.date,
                formatChartLabel(d.label || d.date, gran),
                fmtCount(d.bills),
              ])}
              renderChart={renderDaywiseBills}
            />
          </>
        )}

        <BreakdownTable
          title="Category-wise Sales"
          subtitle={`${allCategories.length} categories · share % and bills`}
          loading={uiLoading}
          isDark={isDark}
          columns={['#', 'Category', 'Sales', 'Share %', 'Bills']}
          rows={allCategories.map((c, i) => [
            String(i + 1),
            c.name,
            fmtLakhs(c.revenue),
            c.percentage > 0 ? `${c.percentage.toFixed(2)}%` : '—',
            (c as any).transactions != null ? fmtCount((c as any).transactions) : '—',
          ])}
          renderChart={(type) => renderSingleSeries(type, topCategories)}
        />

        <BreakdownTable
          title="Branch-wise Sales"
          subtitle={`${allBranches.length} branches · ranked by revenue`}
          loading={uiLoading}
          isDark={isDark}
          columns={['#', 'Branch', 'Sales', 'Share %', 'Bills']}
          rows={allBranches.map((b, i) => [
            String(i + 1),
            b.name,
            fmtLakhs(b.revenue),
            `${b.percentage.toFixed(2)}%`,
            (b as any).transactions != null ? fmtCount((b as any).transactions) : '—',
          ])}
          renderChart={(type) => renderSingleSeries(type, topBranches)}
        />

        <BreakdownTable
          title="Department-wise Sales"
          subtitle={
            departmentRows.length > 0
              ? `${departmentRows.length} departments${deptChartLoading ? ' · loading…' : ''}`
              : deptChartLoading
                ? 'Loading department breakdown…'
                : 'No department data for this period'
          }
          loading={deptChartLoading}
          isDark={isDark}
          columns={['#', 'Department', 'Sales', 'Share %', 'Bills']}
          rows={departmentRows.map((d, i) => [
            String(i + 1),
            d.name || '—',
            fmtLakhs(d.revenue),
            `${d.percentage.toFixed(2)}%`,
            fmtCount((d as any).transactions ?? 0),
          ])}
          renderChart={(type) => renderSingleSeries(type, topDepts)}
        />
      </div>
      </>
      )}
    </div>
  );
}

// ─── Breakdown table with chart type toggle ────────────────────────────────────
function BreakdownTable({
  title,
  subtitle,
  columns,
  rows,
  loading,
  isDark,
  renderChart,
}: {
  title: string;
  subtitle: string;
  columns: string[];
  rows: string[][];
  loading: boolean;
  isDark: boolean;
  renderChart?: (type: 'bar' | 'line' | 'pie') => React.ReactNode;
}) {
  const [chartType, setChartType] = useState<'bar' | 'line' | 'pie'>('bar');

  return (
    <Card className="p-3 sm:p-5">
      {/* Header row */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{title}</h2>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{subtitle}</p>
        </div>

        {/* Chart type toggle */}
        {renderChart && !loading && (
          <div className="flex shrink-0 gap-1 self-start rounded-lg p-0.5"
            style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }}>
            {(['bar', 'line', 'pie'] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setChartType(t)}
                className="rounded-md px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wide transition-all sm:px-3"
                style={{
                  background: chartType === t
                    ? '#5882ff'
                    : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                  color: chartType === t
                    ? '#fff'
                    : 'var(--text-muted)',
                  border: chartType === t
                    ? 'none'
                    : `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}`,
                  boxShadow: chartType === t ? '0 0 10px rgba(0,184,230,0.35)' : 'none',
                  cursor: 'pointer',
                }}>
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Chart area */}
      {renderChart && !loading && (
        <div className="mb-5">
          {renderChart(chartType) ?? (
            <p className="text-xs text-center py-6" style={{ color: 'var(--text-muted)' }}>No chart data</p>
          )}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-3 rounded animate-pulse"
              style={{ background: 'rgba(128,128,128,0.1)', width: `${90 - i * 8}%` }} />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>No data</p>
      ) : (
        <div className="-mx-1 overflow-auto px-1" style={{ maxHeight: 360 }}>
          <table className="w-full min-w-[480px] text-xs border-collapse">
            <thead className="sticky top-0 z-10"
              style={{ background: isDark ? 'rgba(15,23,42,0.95)' : 'rgba(255,255,255,0.98)' }}>
              <tr style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)' }}>
                {columns.map((h) => (
                  <th key={h}
                    className={`pb-2 pr-3 font-semibold whitespace-nowrap ${
                      h === 'Sales' || h === 'Share %' || h === 'Bills' || h === 'Qty' || h === 'LY Sales'
                        ? 'text-right' : 'text-left'
                    }`}
                    style={{ color: 'var(--text-muted)' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri}
                  style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.03)' : '1px solid rgba(0,0,0,0.04)' }}>
                  {row.map((cell, ci) => (
                    <td key={ci}
                      className={`py-2 pr-3 tabular-nums ${ci >= 3 ? 'text-right' : ''}`}
                      style={{
                        color: ci === 3 && cell.startsWith('₹') ? '#5882ff'
                          : ci === 0 ? 'var(--text-muted)' : 'var(--text-primary)',
                        fontWeight: ci === 3 && cell.startsWith('₹') ? 600 : 400,
                      }}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
