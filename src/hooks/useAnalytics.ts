/**
 * Analytics hooks — predefined cached analytics. NOT AI-generated.
 *
 * Architecture:
 *  - These hooks serve fixed backend endpoints (pre-aggregated SQL).
 *  - They are NOT connected to the AI/NLQ pipeline.
 *  - Cache is persisted to localStorage so data is available on reload
 *    before any network request fires → zero loading state on KPI cards.
 *
 * Cache layers:
 *  1. localStorage (survives reload) → data available on first paint
 *  2. In-memory Map (fastest, within session)
 *  3. Stale-while-revalidate: show cached, revalidate silently in bg
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  analytics,
  DashboardResponse,
  KPIsResponse,
  TrendPoint,
  CategoryPoint,
  BranchPoint,
  DeptPoint,
  SalespersonPoint,
  TransactionRecord,
  TransactionSummary,
  AnalyticsBundleResponse,
  DashboardPageResponse,
} from '../lib/api';

import { growthPct } from '../lib/format';

export {
  fmtLakhs,
  fmtCount,
  fmtLakhsAxis,
  formatChartLabel,
  growthPct,
  fmtRupees,
  fmtSmart,
  fmtLakhs as fmtRevenue,
} from '../lib/format';

export {
  hasLyTrendData,
  formatLySub,
  lyGrowthReady,
  lyChartSubtitle,
  bundleTrendHasLy,
  bundleHasCustomerCount,
  formatCustomerKpi,
} from '../lib/lyDisplay';

// ─── Persistent SWR Cache ───────────────────────────────────────────────────
// Layer 1: localStorage (survives reload — data on first paint)
// Layer 2: in-memory Map (zero-latency within session)

interface CacheEntry<T> {
  data: T;
  ts: number;
}

const _store = new Map<string, CacheEntry<unknown>>();
const LS_PREFIX = 'smerp_c:';
const LS_KEYS   = 'smerp_keys';

const FRESH_TTL  = 5  * 60 * 1000;   // 5 min — skip revalidation
const STALE_TTL  = 30 * 60 * 1000;   // 30 min — show stale + bg revalidate
const LS_MAX_TTL = 60 * 60 * 1000;   // 1 hr — evict from localStorage
const TODAY_FRESH_TTL = 60 * 1000;   // 1 min — today’s sales change intraday

const INTRADAY_CACHE_KEYS = new Set<string>([
  // Empty — today keys persist to localStorage for fast reload.
]);

/** Shorter revalidation window for today KPIs (still persisted to localStorage). */
const TODAY_CACHE_KEYS = new Set([
  'kpis:v2:today',
  'dashboard:v2:today::',
]);

/** Client cache keys that must roll over at local midnight. */
const ROLLING_CLIENT_KEYS = new Set([
  'dashboard:v2:mtd::',
  'dashboard:v2:today::',
  'kpis:mtd',
  'kpis:v2:today',
]);

const ROLLING_ANALYTICS_PERIODS = new Set(['today', 'yesterday', 'mtd', 'qtd', 'ytd', 'last_6m']);

function localTodayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function cacheEntryIsFromToday(key: string): boolean {
  const e = _store.get(key);
  if (!e) return false;
  const entryDay = new Date(e.ts).toLocaleDateString('en-CA');
  return entryDay === localTodayIso();
}

function dashboardAsOfDate(d: DashboardResponse | null | undefined): string | null {
  if (!d) return null;
  const end = d.date_range?.end;
  if (end) return end.slice(0, 10);
  const trend = d.trend ?? [];
  if (!trend.length) return null;
  const dates = trend
    .map((p) => p.date?.slice(0, 10))
    .filter((x): x is string => !!x);
  return dates.sort().pop() ?? null;
}

/** True when cached MTD/today dashboard belongs to a prior calendar day. */
function isRollingDashboardStale(
  d: DashboardResponse | null | undefined,
  period?: string,
): boolean {
  if (!d) return false;
  const p = period ?? d.period ?? 'mtd';
  if (!ROLLING_ANALYTICS_PERIODS.has(p) && p !== 'today') return false;
  const asOf = dashboardAsOfDate(d);
  if (!asOf) return false;
  if (p === 'today') return asOf !== localTodayIso();
  // MTD/QTD/YTD rolling windows end on today
  return asOf !== localTodayIso();
}

function isRollingClientCacheStale(key: string, entryTs?: number): boolean {
  const rollingKey =
    ROLLING_CLIENT_KEYS.has(key)
    || (key.startsWith('analytics-page:')
      && ROLLING_ANALYTICS_PERIODS.has(key.split(':')[2] ?? ''));
  if (!rollingKey) return false;
  const ts = entryTs ?? _store.get(key)?.ts;
  if (ts == null) return false;
  return new Date(ts).toLocaleDateString('en-CA') !== localTodayIso();
}

function purgeStaleClientCache(key: string): void {
  _store.delete(key);
  try {
    localStorage.removeItem(LS_PREFIX + key);
  } catch { /* ignore */ }
}

// ── Init: restore localStorage into _store on module load ──
;(function restoreFromLS() {
  try {
    const raw = localStorage.getItem(LS_KEYS);
    if (!raw) return;
    const keys: string[] = JSON.parse(raw);
    const now = Date.now();
    const legacyIntraday = new Set(['kpis:today', 'dashboard:today::']);
    for (const k of keys) {
      if (legacyIntraday.has(k)) {
        localStorage.removeItem(LS_PREFIX + k);
        continue;
      }
      const item = localStorage.getItem(LS_PREFIX + k);
      if (!item) continue;
      const entry: CacheEntry<unknown> = JSON.parse(item);
      if (now - entry.ts >= LS_MAX_TTL || isRollingClientCacheStale(k, entry.ts)) {
        localStorage.removeItem(LS_PREFIX + k);
        continue;
      }
      _store.set(k, entry);
    }
  } catch { /* localStorage unavailable */ }
})();

function cacheGet<T>(key: string): T | null {
  const e = _store.get(key);
  return e ? (e.data as T) : null;
}

/** Read an entry from the SWR cache. Returns null on miss. */
export function readCache<T>(key: string): T | null {
  return cacheGet<T>(key);
}

function cacheSet(key: string, data: unknown): void {
  const entry: CacheEntry<unknown> = { data, ts: Date.now() };
  _store.set(key, entry);
  // Intraday keys (empty set) skip localStorage — today/mtd both persist for fast reload.
  if (INTRADAY_CACHE_KEYS.has(key)) return;
  // Persist to localStorage for reload survival
  try {
    localStorage.setItem(LS_PREFIX + key, JSON.stringify(entry));
    const raw = localStorage.getItem(LS_KEYS);
    const keys: string[] = raw ? JSON.parse(raw) : [];
    if (!keys.includes(key)) {
      keys.push(key);
      localStorage.setItem(LS_KEYS, JSON.stringify(keys));
    }
  } catch { /* quota exceeded or unavailable */ }
}

function cacheTtl(key: string): number {
  if (TODAY_CACHE_KEYS.has(key)) return TODAY_FRESH_TTL;
  return INTRADAY_CACHE_KEYS.has(key) ? TODAY_FRESH_TTL : FRESH_TTL;
}

function isFresh(key: string)  {
  const e = _store.get(key);
  return !!e && Date.now() - e.ts < cacheTtl(key);
}

function isUsable(key: string) {
  const e = _store.get(key);
  const ttl = TODAY_CACHE_KEYS.has(key)
    ? TODAY_FRESH_TTL
    : INTRADAY_CACHE_KEYS.has(key)
      ? TODAY_FRESH_TTL
      : STALE_TTL;
  return !!e && Date.now() - e.ts < ttl;
}

/** Ignore poisoned cache entries from failed/empty API responses (shows as ₹0 everywhere). */
function isEmptyDashboard(d: DashboardResponse | null | undefined): boolean {
  if (!d?.summary) return !d?.trend?.length;
  const s = d.summary;
  const noSales = (s.mtd_sales ?? 0) === 0 && (s.bills ?? 0) === 0;
  return noSales && !(d.trend?.length);
}

/** Cron-era snapshots had KPI LY totals but trend points with prior always 0. */
function dashboardTrendMissingLy(d: DashboardResponse): boolean {
  const ly = d.summary?.ly_sales ?? 0;
  if (ly <= 0) return false;
  const trend = d.trend ?? [];
  if (!trend.length) return false;
  return trend.every((p) => (p.prior ?? 0) === 0);
}

function getDashboardCache(key: string): DashboardResponse | null {
  if (isRollingClientCacheStale(key)) {
    purgeStaleClientCache(key);
    return null;
  }
  const d = cacheGet<DashboardResponse>(key);
  if (!d || isEmptyDashboard(d)) return null;
  const period = key.includes('today') ? 'today' : 'mtd';
  if (isRollingDashboardStale(d, period)) {
    purgeStaleClientCache(key);
    return null;
  }
  return d;
}

/** Charts on Dashboard.tsx come from mtdRaw.trend / categories / branches. */
function dashboardHasCharts(d: DashboardResponse | null | undefined): boolean {
  if (!d) return false;
  return (d.trend?.length ?? 0) > 0 || (d.categories?.length ?? 0) > 0;
}

/** Call on logout — wipes in-memory and localStorage */
export function clearAnalyticsCache(): void {
  // Only wipe the in-memory store on logout — keep localStorage intact.
  // On the next login, pages will read stale data from localStorage (instant)
  // while silently revalidating in the background.  This means the first page
  // after re-login renders immediately instead of hitting SQL Server cold.
  _store.clear();
}

// ─── Core fetch hook ────────────────────────────────────────────────────────
// loading=false if ANY cached data exists — zero loading state on KPI cards.

interface UseFetchResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useFetch<T>(
  fetchFn: () => Promise<T>,
  deps: unknown[] = [],
  cacheKey?: string,
): UseFetchResult<T> {
  // Immediately resolve from cache (in-memory, restored from localStorage)
  const cached = cacheKey ? cacheGet<T>(cacheKey) : null;

  const [data,    setData]    = useState<T | null>(cached);
  const [loading, setLoading] = useState<boolean>(!cached); // false if cached
  const [error,   setError]   = useState<string | null>(null);

  const fetchRef = useRef(fetchFn);
  fetchRef.current = fetchFn;

  // When cache key changes (period switch) — instantly serve new key's cache.
  // Crucially: if the new key has NO cache yet, keep showing the old data (dimmed)
  // rather than nulling it out — this prevents the "loading forever blank" UX.
  const prevKeyRef = useRef<string | undefined>(cacheKey);
  useEffect(() => {
    if (prevKeyRef.current === cacheKey) return;
    prevKeyRef.current = cacheKey;
    const c = cacheKey ? cacheGet<T>(cacheKey) : null;
    if (c) {
      setData(c);
      setLoading(false);
    } else {
      // No cache for this key — show loading indicator but KEEP old data visible
      setLoading(true);
    }
    setError(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey]);

  const run = useCallback(async (silent = false) => {
    // Only block the UI with loading when we have nothing to show (stale-while-revalidate).
    // Otherwise a slow/hung refetch would blank Branch/Analytics-style pages forever.
    if (!silent) {
      const hasCached = !!(cacheKey && cacheGet<T>(cacheKey));
      if (!hasCached) setLoading(true);
    }
    setError(null);
    try {
      const result = await fetchRef.current();
      setData(result);
      if (cacheKey) cacheSet(cacheKey, result);
    } catch (err) {
      if (!silent) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        setError(msg.includes('abort') ? 'Request timed out — try a shorter period' : msg);
      }
      // On silent error, keep showing stale cached data — don't null out
    } finally {
      if (!silent) setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (cacheKey && isFresh(cacheKey)) return;   // fresh — skip fetch
    if (cacheKey && isUsable(cacheKey)) run(true); // stale — silent bg revalidate
    else run(false);                               // no cache — fetch (shows loading)
  }, [run, cacheKey]);

  useEffect(() => {
    if (!cacheKey) return;
    return subscribeCacheHydrate(() => {
      const c = cacheGet<T>(cacheKey);
      if (c) {
        setData(c);
        setLoading(false);
      }
    });
  }, [cacheKey]);

  return { data, loading, error, refetch: useCallback(() => run(false), [run]) };
}

// ─── Transactions warm cache (instant first open when user visited any app shell page) ─────────

function txnsCacheKey(period: string, page: number, pageSize: number, branch?: string, category?: string, search?: string): string {
  return `txns:${period}:${page}:${pageSize}:${branch}:${category}:${search}`;
}

/** Prefetch MTD page 1 transaction grid + summary into SWR cache (matches useTransactions key shape).
 *  page_size MUST match PAGE_SIZE in Transactions.tsx (12) so the cache key aligns. */
export function prefetchTransactionsSnapshots(): void {
  const period = 'mtd';
  const page = 1;
  const page_size = 12;   // matches PAGE_SIZE = 12 in Transactions.tsx
  const txnKey = txnsCacheKey(period, page, page_size, undefined, undefined, undefined);
  const sumKey = `txn_summary:${period}`;
  if (cacheGet(txnKey) && cacheGet(sumKey)) return;
  void Promise.all([
    analytics.transactions({ period, page, page_size }).then((d) => {
      cacheSet(txnKey, d);
    }),
    analytics.transactionSummary(period).then((d) => {
      cacheSet(sumKey, d);
    }),
  ]).catch(() => { /* offline — ignore */ });
}

export function prefetchTransactionsOnHover(period = 'mtd'): void {
  prefetchTransactionsSnapshots();
}

const KEY_DASH_MTD   = 'dashboard:v2:mtd::';
const KEY_DASH_TODAY = 'dashboard:v2:today::';
const KEY_KPIS_MTD   = 'kpis:mtd';
const KEY_KPIS_TODAY = 'kpis:v2:today';
const DASHBOARD_BUNDLE_TOP_N = 100;

// ─── Server-side Snapshot (instant, no SQL Server delay) ─────────────────────
// Fires once on login and on every Dashboard mount.
// Hydrates the SWR cache so useDashboardPage renders without any loading state.

let _snapshotInflight: Promise<void> | null = null;
const _dashboardHydrateListeners = new Set<() => void>();
const _cacheHydrateListeners = new Set<() => void>();

/** After snapshot writes SWR keys, useFetch hooks re-read their cache key. */
export function subscribeCacheHydrate(fn: () => void): () => void {
  _cacheHydrateListeners.add(fn);
  return () => {
    _cacheHydrateListeners.delete(fn);
  };
}

function notifyCacheHydrate(): void {
  _cacheHydrateListeners.forEach((fn) => {
    try {
      fn();
    } catch {
      /* ignore */
    }
  });
}

/** After snapshot/bundle writes cache, hooks re-read without a full refetch. */
export function subscribeDashboardHydrate(fn: () => void): () => void {
  _dashboardHydrateListeners.add(fn);
  return () => {
    _dashboardHydrateListeners.delete(fn);
  };
}

function notifyDashboardHydrate(): void {
  _dashboardHydrateListeners.forEach((fn) => {
    try {
      fn();
    } catch {
      /* ignore listener errors */
    }
  });
}

function summaryFromTrendPoint(pt: TrendPoint): DashboardResponse['summary'] {
  return {
    mtd_sales: pt.revenue ?? 0,
    ly_sales: 0,
    sales_growth_pct: null,
    bills: pt.transactions ?? 0,
    quantity: pt.quantity ?? 0,
    customers: null,
  };
}

function todaySummaryFromMtdDashboard(mtd: DashboardResponse | null): DashboardResponse['summary'] | null {
  if (!mtd?.trend?.length) return null;
  const todayIso = localTodayIso();
  const pt = mtd.trend.find((p) => p.date?.slice(0, 10) === todayIso);
  if (pt) {
    return {
      mtd_sales: pt.current,
      ly_sales: pt.prior ?? 0,
      sales_growth_pct: null,
      bills: pt.bills ?? 0,
      quantity: pt.quantity ?? 0,
      customers: null,
    };
  }
  // MTD trend is loaded but today has no row yet (no sales today) — show zero, not skeleton.
  return {
    mtd_sales: 0,
    ly_sales: 0,
    sales_growth_pct: null,
    bills: 0,
    quantity: 0,
    customers: null,
  };
}

function buildTodayDashboard(summary: DashboardResponse['summary']): DashboardResponse {
  return {
    success: true,
    period: 'today',
    period_label: 'Today',
    granularity: 'day',
    summary,
    trend: [],
    categories: [],
    branches: [],
    checksum: {
      trend_total: summary.mtd_sales,
      summary_total: summary.mtd_sales,
      match: true,
    },
  };
}

function applyTodayDashboard(
  summary: DashboardResponse['summary'],
  setToday?: (d: DashboardResponse | null) => void,
  setTodayLoading?: (v: boolean) => void,
): void {
  const dash = buildTodayDashboard(summary);
  cacheSet(KEY_DASH_TODAY, dash);
  setToday?.(dash);
  setTodayLoading?.(false);
  notifyDashboardHydrate();
}

/** Paint Today chips instantly from cached MTD trend (no extra SQL). */
function hydrateTodayFromMtd(
  mtd: DashboardResponse | null | undefined,
  handlers?: {
    setToday?: (d: DashboardResponse | null) => void;
    setTodayLoading?: (v: boolean) => void;
  },
): boolean {
  if (hasTodaySnapshot(getDashboardCache(KEY_DASH_TODAY), cacheGet(KEY_KPIS_TODAY))) {
    return true;
  }
  const summary = todaySummaryFromMtdDashboard(mtd ?? getDashboardCache(KEY_DASH_MTD));
  if (!summary) return false;
  applyTodayDashboard(summary, handlers?.setToday, handlers?.setTodayLoading);
  return true;
}

export async function fetchAndApplySnapshot(): Promise<void> {
  // Snapshot endpoint removed — cache is disabled, all data is live from SQL Server.
  // This function is kept as a no-op so call sites don't need to change.
  return Promise.resolve();
}

/** @deprecated kept for internal use only */
async function _fetchAndApplySnapshotLegacy(): Promise<void> {
  if (_snapshotInflight) return _snapshotInflight;

  _snapshotInflight = (async () => {
    try {
      const snap = await analytics.snapshot();
      if (!snap?.has_data) return;

      // ── Dashboard / KPI cache hydration ──────────────────────────────────
      if (snap.mtd_kpis?.revenue != null || snap.mtd_kpis?.transactions != null) {
        cacheSet(KEY_KPIS_MTD, snap.mtd_kpis);
      }
      if (snap.today_kpis?.revenue != null || snap.today_kpis?.transactions != null) {
        cacheSet(KEY_KPIS_TODAY, snap.today_kpis);
      }
      if (snap.mtd_dashboard && !isEmptyDashboard(snap.mtd_dashboard as DashboardResponse)) {
        cacheSet(KEY_DASH_MTD, snap.mtd_dashboard);
      }
      if (snap.today_dashboard?.summary != null) {
        cacheSet(KEY_DASH_TODAY, snap.today_dashboard);
      }

      // ── Transactions page 1 cache hydration ──────────────────────────────
      // Seed the exact cache keys that useTransactions / useTransactionSummary read,
      // so the Transactions page renders instantly without a loading state.
      const TXN_PAGE_SIZE = 12;  // must match PAGE_SIZE in Transactions.tsx
      if (snap.txn_list_mtd?.transactions?.length) {
        cacheSet(txnsCacheKey('mtd', 1, TXN_PAGE_SIZE, undefined, undefined, undefined), snap.txn_list_mtd);
      }
      if (snap.txn_list_today?.transactions?.length) {
        cacheSet(txnsCacheKey('today', 1, TXN_PAGE_SIZE, undefined, undefined, undefined), snap.txn_list_today);
      }
      if (snap.txn_summary_mtd?.total_revenue != null) {
        cacheSet('txn_summary:mtd', snap.txn_summary_mtd);
      }

      // ── Branch Intel page instant load ───────────────────────────────────
      // Seed branches:mtd so Branch.tsx renders immediately without a loading state.
      if (snap.branches_chart_mtd?.length) {
        cacheSet('branches:mtd', {
          success: true,
          period: 'mtd',
          branches: snap.branches_chart_mtd,
        });
      }

      // ── Products page instant load ────────────────────────────────────────
      // Seed categories:mtd:8 so the pie chart on Products.tsx renders immediately.
      if (snap.categories_chart_mtd?.length) {
        cacheSet('categories:mtd:8', {
          success: true,
          period: 'mtd',
          categories: snap.categories_chart_mtd.slice(0, 8),
        });
      }
      // Seed product catalog page 1 + top products MTD for instant Products page load.
      if (snap.product_catalog?.products?.length) {
        cacheSet('product_catalog:50:0', snap.product_catalog);
      }
      if (snap.top_products_mtd?.products?.length) {
        cacheSet('top_products:mtd:15', snap.top_products_mtd);
      }

      // KPI cache for all analytics tabs (customer count + revenue chips)
      const _kpiRows: Array<[string, KPIsResponse | null | undefined]> = [
        ['mtd', snap.mtd_kpis],
        ['today', snap.today_kpis],
        ['qtd', snap.qtd_kpis],
        ['ytd', snap.ytd_kpis],
        ['last_6m', snap.last6m_kpis],
      ];
      for (const [p, kpi] of _kpiRows) {
        if (!kpi) continue;
        if (
          kpi.revenue?.value != null
          || kpi.transactions?.value != null
          || kpi.customers?.value != null
        ) {
          cacheSet(`kpis:v2:${p}`, kpi);
          cacheSet(`kpis:${p}`, kpi);
        }
      }

      // ── Today: derive from MTD when snapshot has no intraday cache ──────────
      // today_kpis / today_dashboard are intraday keys not persisted to PG, so after
      // a server restart the snapshot returns null for them until warmup Phase 0+1
      // complete.  We derive today's numbers from the MTD data we DO have so the
      // Today tab renders immediately without a loading spinner.
      let todayDashForSeed = snap.today_dashboard as DashboardResponse | null;
      let todayKpisForSeed = snap.today_kpis as KPIsResponse | null;

      if (!todayDashForSeed?.summary) {
        // Path 1: MTD dashboard trend has a point for today
        const mtdDash = snap.mtd_dashboard as DashboardResponse | null;
        if (mtdDash?.trend?.length) {
          const summary = todaySummaryFromMtdDashboard(mtdDash);
          if (summary) {
            todayDashForSeed = buildTodayDashboard(summary);
          }
        }
      }

      if (!todayDashForSeed?.summary) {
        // Path 2: already-cached analytics-page:mtd:: has today's yoyTrend point
        const todayIso = localTodayIso();
        const mtdPage = cacheGet<AnalyticsPageData>(analyticsPageCacheKey('mtd'));
        if (mtdPage?.yoyTrend?.length) {
          const pt = mtdPage.yoyTrend.find((p) => p.date?.slice(0, 10) === todayIso);
          if (pt) {
            todayDashForSeed = buildTodayDashboard({
              mtd_sales: pt.current,
              ly_sales: pt.prior ?? 0,
              sales_growth_pct: null,
              bills: pt.bills ?? 0,
              quantity: pt.quantity ?? 0,
              customers: null,
            });
          }
        }
      }

      if (todayDashForSeed?.summary && !cacheGet<DashboardResponse>(KEY_DASH_TODAY)?.summary) {
        cacheSet(KEY_DASH_TODAY, todayDashForSeed);
      }

      // Synthesise today KPIs from derived dashboard when snapshot KPIs are null
      if (!todayKpisForSeed && todayDashForSeed?.summary) {
        const s = todayDashForSeed.summary;
        todayKpisForSeed = {
          revenue: { value: s.mtd_sales, prior: s.ly_sales ?? 0, growth: s.sales_growth_pct ?? null },
          transactions: { value: s.bills, prior: null, growth: null },
          customers: s.customers != null ? { value: s.customers, prior: null, growth: null } : null,
        } as KPIsResponse;
        if (!cacheGet(KEY_KPIS_TODAY)) {
          cacheSet(KEY_KPIS_TODAY, todayKpisForSeed);
          cacheSet('kpis:v2:today', todayKpisForSeed);
          cacheSet('kpis:today', todayKpisForSeed);
        }
      }

      // ── Analytics page cache hydration ──────────────────────────────────
      // Seed analytics-page:{period}:: so the Analytics page renders instantly
      // when the user navigates to it — no loading shimmer on any tab.
      const _snapPeriods: Array<{
        period: string;
        dash: DashboardResponse | null | undefined;
        kpi: KPIsResponse | null | undefined;
        departments: DeptPoint[] | null | undefined;
      }> = [
        { period: 'mtd', dash: snap.mtd_dashboard, kpi: snap.mtd_kpis, departments: snap.departments_mtd },
        { period: 'today', dash: todayDashForSeed, kpi: todayKpisForSeed, departments: snap.departments_today },
        { period: 'qtd', dash: snap.qtd_dashboard, kpi: snap.qtd_kpis, departments: snap.departments_qtd },
        { period: 'ytd', dash: snap.ytd_dashboard, kpi: snap.ytd_kpis, departments: snap.departments_ytd },
        { period: 'last_6m', dash: snap.last6m_dashboard, kpi: snap.last6m_kpis, departments: snap.departments_last6m },
      ];
      for (const row of _snapPeriods) {
        if (!row.dash) continue;
        const dash = row.dash as DashboardResponse;
        const hasContent =
          !isEmptyDashboard(dash)
          || (dash.trend?.length ?? 0) > 0
          || (row.departments?.length ?? 0) > 0;
        if (!hasContent) continue;
        seedAnalyticsPagePeriod(row.period, dash, row.kpi, row.departments ?? []);
      }
    } catch {
      // Server offline or cache cold — useDashboardPage falls back gracefully
    } finally {
      _snapshotInflight = null;
      notifyDashboardHydrate();
      notifyCacheHydrate();
    }
  })();

  return _snapshotInflight;
}

function enrichSummaryFromKpi(
  summary: DashboardResponse['summary'],
  kpi: KPIsResponse | null | undefined,
): DashboardResponse['summary'] {
  if (!kpi) return summary;
  const cust = kpi.distinct_clients?.value ?? kpi.customers?.value;
  return {
    ...summary,
    ly_sales: kpi.revenue?.prior ?? summary.ly_sales,
    sales_growth_pct: kpi.revenue?.growth ?? summary.sales_growth_pct,
    mtd_sales: summary.mtd_sales ?? kpi.revenue?.value ?? 0,
    bills: summary.bills ?? kpi.transactions?.value ?? 0,
    quantity: summary.quantity ?? kpi.quantity?.value ?? 0,
    customers:
      summary.customers != null
        ? summary.customers
        : cust != null && Number.isFinite(cust)
          ? Math.round(cust)
          : summary.customers,
  };
}

function seedAnalyticsPagePeriod(
  period: string,
  dash: DashboardResponse | null | undefined,
  kpi: KPIsResponse | null | undefined,
  departments: DeptPoint[] | null | undefined,
): void {
  if (!dash) return;
  const apKey = analyticsPageCacheKey(period);
  const existing = cacheGet<AnalyticsPageData>(apKey);
  if (
    existing
    && !isEmptyAnalyticsPage(existing)
    && isFresh(apKey)
    && isCompleteAnalyticsPage(existing, period)
    && cachedIsFullyMerged(existing, period)   // also require LY/customer data present
    && (existing.departments?.length || !departments?.length)
  ) {
    return;
  }

  const split: SplitBundle = {
    branches: (dash.branches ?? []).map((b) => ({
      branch: b.name,
      revenue: b.revenue,
      transactions: 0,
    })),
    trend: [],
    categories: (dash.categories ?? []).map((c) => ({
      category: c.name,
      revenue: c.revenue,
      percentage: c.percentage ?? 0,
    })),
    departments: departments ?? [],
    kpis: (kpi ?? {}) as KPIsResponse,
  };

  let built = buildAnalyticsPageData(split, dash as DashboardResponse, period);
  if (built.summary) {
    built = {
      ...built,
      summary: enrichSummaryFromKpi(built.summary, kpi),
    };
  } else if (kpi && hasUsableBundleKpis(kpi)) {
    built = {
      ...built,
      summary: enrichSummaryFromKpi(summaryFromKpis(kpi), kpi),
    };
  }
  if (existing && !isEmptyAnalyticsPage(existing)) {
    built = carryForwardAnalyticsPartial(built, existing);
  }
  if (!isEmptyAnalyticsPage(built)) {
    cacheSet(apKey, built);
    emitPageUpdate(period, built);
  }
}

/** Build DashboardResponse from fast /analytics/bundle (charts without YoY prior bars). */
function dashboardFromBundle(
  core: AnalyticsBundleResponse,
  kpis?: KPIsResponse | null,
): DashboardResponse | null {
  const trend = core.trend ?? [];
  const cats = core.categories ?? [];
  const branches = core.branches ?? [];
  if (!trend.length && !cats.length && !branches.length) return null;

  const branchTotal = branches.reduce((s, b) => s + b.revenue, 0);
  const yoyTrend = trend.map((t) => ({
    label: String(t.label || t.date).slice(0, 10),
    date: String(t.date).slice(0, 10),
    current: t.revenue,
    prior: typeof t.prior === 'number' ? t.prior : 0,
    bills: t.transactions ?? 0,
    quantity: t.quantity ?? 0,
  }));

  const lyFromTrend = yoyTrend.reduce((s, p) => s + (p.prior ?? 0), 0);
  const lyTrendReady = yoyTrend.some((p) => (p.prior ?? 0) > 0);

  const summary: DashboardResponse['summary'] =
    kpis && (kpis.revenue != null || kpis.transactions != null)
      ? {
          mtd_sales: kpis.revenue?.value ?? 0,
          ly_sales: lyTrendReady ? (lyFromTrend || kpis.revenue?.prior || 0) : 0,
          sales_growth_pct: lyTrendReady ? (kpis.revenue?.growth ?? null) : null,
          bills: kpis.transactions?.value ?? 0,
          quantity: kpis.quantity?.value ?? 0,
          customers:
            kpis.customers?.value != null && Number.isFinite(kpis.customers.value)
              ? Math.round(kpis.customers.value)
              : null,
        }
      : {
          mtd_sales: yoyTrend.reduce((s, p) => s + p.current, 0),
          ly_sales: lyTrendReady ? lyFromTrend : 0,
          sales_growth_pct: null,
          bills: yoyTrend.reduce((s, p) => s + p.bills, 0),
          quantity: yoyTrend.reduce((s, p) => s + p.quantity, 0),
          customers: null,
        };

  return {
    success: true,
    period: core.period || 'mtd',
    period_label: 'Month-to-Date',
    granularity: 'day',
    summary,
    trend: yoyTrend,
    categories: cats.map((c) => ({
      name: c.category,
      revenue: c.revenue,
      percentage: c.percentage ?? 0,
    })),
    branches: branches.map((b) => ({
      name: b.branch,
      revenue: b.revenue,
      percentage: branchTotal > 0 ? (b.revenue / branchTotal) * 100 : 0,
    })),
    checksum: {
      trend_total: summary.mtd_sales,
      summary_total: summary.mtd_sales,
      match: true,
    },
  };
}

function shouldKeepExistingMtd(prev: DashboardResponse | null, incoming: DashboardResponse): boolean {
  if (!prev || !dashboardHasCharts(prev)) return false;
  if (isRollingDashboardStale(prev, 'mtd')) return false;
  // Full dashboard with YoY bars beats bundle-only partial.
  if (!dashboardTrendMissingLy(prev) && dashboardTrendMissingLy(incoming)) return true;
  return false;
}

function applyMtdBundleCharts(
  core: AnalyticsBundleResponse,
  setMtd: (d: DashboardResponse | null) => void,
  kpis?: KPIsResponse | null,
  setToday?: (d: DashboardResponse | null) => void,
  setTodayLoading?: (v: boolean) => void,
): void {
  const partial = dashboardFromBundle(core, kpis);
  if (!partial) return;
  const prev = cacheGet<DashboardResponse>(KEY_DASH_MTD);
  if (shouldKeepExistingMtd(prev, partial)) return;
  cacheSet(KEY_DASH_MTD, partial);
  setMtd(partial);

  if (setToday && setTodayLoading) {
    hydrateTodayFromMtd(partial, { setToday, setTodayLoading });
  }
}

function fetchMtdBundleFast(
  setMtd: (d: DashboardResponse | null) => void,
  kpis?: KPIsResponse | null,
  setToday?: (d: DashboardResponse | null) => void,
  setTodayLoading?: (v: boolean) => void,
): void {
  void analytics
    .bundle('mtd', {
      topN: DASHBOARD_BUNDLE_TOP_N,
      includeDepartments: false,
      includeKpis: true,
    })
    .then((core) => {
      if (core.kpis) {
        cacheSet(KEY_KPIS_MTD, core.kpis);
      }
      applyMtdBundleCharts(core, setMtd, core.kpis ?? kpis, setToday, setTodayLoading);
    })
    .catch(() => {});
}

/** Apply /analytics/dashboard-page response to SWR cache + React state. */
function applyDashboardPagePayload(
  page: DashboardPageResponse,
  handlers: {
    setMtd: (d: DashboardResponse | null) => void;
    setToday: (d: DashboardResponse | null) => void;
    setKpis: (k: KPIsResponse | null) => void;
    setTodayKpis: (k: KPIsResponse | null) => void;
    setLoading: (v: boolean) => void;
    setTodayLoading: (v: boolean) => void;
  },
): void {
  const { mtd: mtdCore, today: todayCore } = page;

  if (mtdCore.kpis) {
    cacheSet(KEY_KPIS_MTD, mtdCore.kpis);
    handlers.setKpis(mtdCore.kpis);
    handlers.setLoading(false);
  }
  if (todayCore.kpis) {
    cacheSet(KEY_KPIS_TODAY, todayCore.kpis);
    handlers.setTodayKpis(todayCore.kpis);
    handlers.setTodayLoading(false);
  }

  applyMtdBundleCharts(
    mtdCore,
    handlers.setMtd,
    mtdCore.kpis,
    handlers.setToday,
    handlers.setTodayLoading,
  );

  const todayDash = dashboardFromBundle(todayCore, todayCore.kpis);
  if (todayDash?.summary) {
    cacheSet(KEY_DASH_TODAY, todayDash);
    handlers.setToday(todayDash);
    handlers.setTodayLoading(false);
  }

  notifyDashboardHydrate();
  notifyCacheHydrate();
}

/** Fastest today sales path — one cached trend query (not the heavy KPI scan). */
function fetchTodayTrendFast(
  setToday: (d: DashboardResponse | null) => void,
  setTodayLoading: (v: boolean) => void,
): void {
  void analytics
    .trend('today')
    .then(({ trend }) => {
      const pt = trend?.[0];
      if (!pt) return;
      applyTodayDashboard(summaryFromTrendPoint(pt), setToday, setTodayLoading);
    })
    .catch(() => {});
}

function fetchTodayBundleFast(
  setToday: (d: DashboardResponse | null) => void,
  setTodayLoading: (v: boolean) => void,
): void {
  void analytics
    .bundle('today', {
      topN: 30,
      includeDepartments: false,
      includeKpis: true,
    })
    .then((core) => {
      const partial = dashboardFromBundle(core);
      if (!partial?.summary) return;
      applyTodayDashboard(partial.summary, setToday, setTodayLoading);
    })
    .catch(() => {});
}

function clearIntradayClientCache(): void {
  for (const key of TODAY_CACHE_KEYS) {
    _store.delete(key);
    try {
      localStorage.removeItem(LS_PREFIX + key);
    } catch { /* ignore */ }
  }
}

function hasTodaySnapshot(todayRaw: DashboardResponse | null, todayKpis: KPIsResponse | null): boolean {
  if (isRollingClientCacheStale(KEY_KPIS_TODAY) || isRollingClientCacheStale(KEY_DASH_TODAY)) {
    return false;
  }
  if (todayRaw && isRollingDashboardStale(todayRaw, 'today')) return false;
  if (todayKpis?.revenue != null || todayKpis?.transactions != null) return true;
  if (todayRaw?.summary != null) return true;
  return false;
}

/**
 * Dashboard prefetch — today KPIs + today dashboard in parallel with MTD.
 * `/analytics/kpis?period=today` is one light SQL and paints Today/Bills chips fast.
 */
export async function fetchDashboardBundle(): Promise<{
  mtd: DashboardResponse;
  today: DashboardResponse;
  kpis: KPIsResponse;
}> {
  const page = await analytics.dashboardPage();
  const mtdDash = dashboardFromBundle(page.mtd, page.mtd.kpis)!;
  const todayDash = dashboardFromBundle(page.today, page.today.kpis)!;
  cacheSet(KEY_DASH_MTD, mtdDash);
  cacheSet(KEY_DASH_TODAY, todayDash);
  if (page.mtd.kpis) cacheSet(KEY_KPIS_MTD, page.mtd.kpis);
  if (page.today.kpis) cacheSet(KEY_KPIS_TODAY, page.today.kpis);
  return { mtd: mtdDash, today: todayDash, kpis: page.mtd.kpis! };
}

function bundleCacheReady(): boolean {
  return !!getDashboardCache(KEY_DASH_MTD)
    && !!getDashboardCache(KEY_DASH_TODAY)
    && isFresh(KEY_KPIS_MTD);
}

function bundleCacheUsable(): boolean {
  return !!getDashboardCache(KEY_DASH_MTD)
    && !!getDashboardCache(KEY_DASH_TODAY)
    && isUsable(KEY_KPIS_MTD);
}

/** MTD KPI cards can render — do not wait for /analytics/dashboard. */
function kpiCacheReady(): boolean {
  return isUsable(KEY_KPIS_MTD);
}

export interface DashboardPageResult {
  mtdRaw: DashboardResponse | null;
  todayRaw: DashboardResponse | null;
  kpis: KPIsResponse | null;
  todayKpis: KPIsResponse | null;
  loading: boolean;
  todayLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/** Single hook for Dashboard.tsx — one /dashboard-page request (MTD + Today). */
export function useDashboardPage(): DashboardPageResult {
  const cachedMtd      = getDashboardCache(KEY_DASH_MTD);
  const cachedToday    = getDashboardCache(KEY_DASH_TODAY);
  const cachedKpis     = cacheGet<KPIsResponse>(KEY_KPIS_MTD);
  const cachedTodayKpi = cacheGet<KPIsResponse>(KEY_KPIS_TODAY);

  const [mtdRaw,      setMtd]          = useState<DashboardResponse | null>(cachedMtd);
  const [todayRaw,    setToday]        = useState<DashboardResponse | null>(() => {
    if (cachedToday) return cachedToday;
    const s = todaySummaryFromMtdDashboard(cachedMtd);
    return s ? buildTodayDashboard(s) : null;
  });
  const [kpis,        setKpis]         = useState<KPIsResponse | null>(cachedKpis);
  const [todayKpis,   setTodayKpis]    = useState<KPIsResponse | null>(cachedTodayKpi);
  const [loading,     setLoading]      = useState<boolean>(!cachedKpis);
  const [todayLoading, setTodayLoading] = useState<boolean>(() => {
    if (hasTodaySnapshot(cachedToday, cachedTodayKpi)) return false;
    if (todaySummaryFromMtdDashboard(cachedMtd)) return false;
    return true;
  });
  const [error,       setError]        = useState<string | null>(null);

  const paintFromCache = useCallback(() => {
    const k = cacheGet<KPIsResponse>(KEY_KPIS_MTD);
    if (k) {
      setKpis(k);
      setLoading(false);
    }
    const tk = cacheGet<KPIsResponse>(KEY_KPIS_TODAY);
    if (tk) {
      setTodayKpis(tk);
      setTodayLoading(false);
    }
    const m = getDashboardCache(KEY_DASH_MTD);
    if (m) setMtd(m);
    const t = getDashboardCache(KEY_DASH_TODAY);
    if (t) setToday(t);
    if (hydrateTodayFromMtd(m, { setToday, setTodayLoading })) {
      /* today derived from MTD trend */
    } else if (!hasTodaySnapshot(t, tk)) {
      setTodayLoading(true);
    } else {
      setTodayLoading(false);
    }
  }, []);

  const run = useCallback(async (silent = false, clearToday = false) => {
    if (clearToday) clearIntradayClientCache();
    if (!silent) {
      setLoading(!cacheGet<KPIsResponse>(KEY_KPIS_MTD));
    }
    // Instant today from cached MTD trend while live SQL runs
    const hydrated = hydrateTodayFromMtd(getDashboardCache(KEY_DASH_MTD), { setToday, setTodayLoading });
    if (!hydrated && !hasTodaySnapshot(getDashboardCache(KEY_DASH_TODAY), cacheGet(KEY_KPIS_TODAY))) {
      if (!silent) setTodayLoading(true);
    }
    setError(null);

    try {
      const page = await analytics.dashboardPage();
      applyDashboardPagePayload(page, {
        setMtd,
        setToday,
        setKpis,
        setTodayKpis,
        setLoading,
        setTodayLoading,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Dashboard load failed';
      if (!silent && !cacheGet<KPIsResponse>(KEY_KPIS_MTD)) {
        setError(msg.includes('abort') ? 'Request timed out — try Refresh' : msg);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    paintFromCache();

    const hasKpis = kpiCacheReady();
    if (hasKpis) {
      setLoading(false);
      void run(true);
    } else {
      void run(false);
    }

    return subscribeDashboardHydrate(paintFromCache);
  }, [run, paintFromCache]);

  return {
    mtdRaw,
    todayRaw,
    kpis,
    todayKpis,
    loading,
    todayLoading,
    error,
    refetch: useCallback(() => {
      setTodayLoading(true);
      run(false, true);
    }, [run]),
  };
}

// ─── Prefetch (single dashboard-page call on login) ──────────────────────────

export async function prefetchAll(): Promise<void> {
  return prefetchCriticalDashboard();
}

export async function prefetchCriticalDashboard(): Promise<void> {
  try {
    const page = await analytics.dashboardPage();
    applyDashboardPagePayload(page, {
      setMtd: () => {},
      setToday: () => {},
      setKpis: () => {},
      setTodayKpis: () => {},
      setLoading: () => {},
      setTodayLoading: () => {},
    });
  } catch {
    // Keep dashboard functional; stale cache (localStorage) can still render.
  }
}

// ─── Analytics hooks ────────────────────────────────────────────────────────

export function useDashboard(
  period: string,
  startDate?: string,
  endDate?: string,
) {
  const key = `dashboard:${period}:${startDate ?? ''}:${endDate ?? ''}`;
  return useFetch(
    () => analytics.dashboard(period, startDate, endDate),
    [period, startDate, endDate],
    key,
  );
}

// ─── Analytics page bundle (split parallel — same as test/mtd_breakdown.py) ───

const API_TOP_N_MAX = 100;

export interface AnalyticsDayRow {
  date: string;
  label: string;
  sales: number;
  prior: number;
  bills: number;
  quantity: number;
}

export interface AnalyticsRankRow {
  name: string;
  revenue: number;
  percentage: number;
  transactions: number | null;
}

export interface AnalyticsPageData {
  period: string;
  period_label: string;
  granularity: 'day' | 'month';
  summary: DashboardResponse['summary'] | null;
  checksum: DashboardResponse['checksum'] | null;
  yoyTrend: DashboardResponse['trend'];
  daywise: AnalyticsDayRow[];
  categories: AnalyticsRankRow[];
  branches: AnalyticsRankRow[];
  departments: AnalyticsRankRow[];
}

interface SplitBundle {
  branches: BranchPoint[];
  trend: TrendPoint[];
  categories: CategoryPoint[];
  departments: DeptPoint[];
  kpis: KPIsResponse;
}

function pctOfTotal(revenue: number, total: number): number {
  return total > 0 ? (revenue / total) * 100 : 0;
}

/** True when bundle included real KPI rows (not `{}` from lean bundle). */
function hasUsableBundleKpis(kpis: KPIsResponse | undefined): boolean {
  return typeof kpis?.revenue?.value === 'number';
}

/** Same totals as /analytics/dashboard summary — used when dashboard is slow or empty. */
/** Today chips: live KPIs beat stale dashboard summary from an earlier fetch. */
export function resolveTodaySummary(
  todayRaw: DashboardResponse | null,
  todayKpis: KPIsResponse | null,
): DashboardResponse['summary'] | null {
  if (todayKpis?.revenue != null || todayKpis?.transactions != null) {
    return summaryFromKpis(todayKpis);
  }
  if (todayRaw?.summary != null) {
    return todayRaw.summary;
  }
  return null;
}

export function summaryFromKpis(kpis: KPIsResponse): DashboardResponse['summary'] {
  const rev = kpis.revenue;
  const custRaw = kpis.distinct_clients?.value ?? kpis.customers?.value;
  return {
    mtd_sales: rev?.value ?? 0,
    ly_sales: rev?.prior ?? 0,
    sales_growth_pct: rev?.growth ?? null,
    bills: kpis.transactions?.value ?? 0,
    quantity: kpis.quantity?.value ?? 0,
    customers:
      custRaw != null && Number.isFinite(custRaw) ? Math.round(custRaw) : null,
  };
}

function daywiseFromDashboard(trend: DashboardResponse['trend']): AnalyticsDayRow[] {
  return trend.map((p) => ({
    date: p.date,
    label: p.label ?? p.date,
    sales: p.current,
    prior: p.prior,
    bills: p.bills ?? 0,
    quantity: p.quantity ?? 0,
  }));
}

function granularityForPeriod(period: string): 'day' | 'month' {
  const p = period.toLowerCase();
  if (p === 'custom' || ['today', 'yesterday', 'mtd', 'last_7d', 'last_14d', 'last_30d'].includes(p)) {
    return 'day';
  }
  return 'month';
}

function trendLabel(t: TrendPoint): string {
  if (t.label) return t.label;
  const d = String(t.date);
  if (d.length >= 7 && d[4] === '-') {
    const [y, m] = d.split('-');
    const mo = Number(m);
    if (y && mo >= 1 && mo <= 12) {
      return new Date(Number(y), mo - 1, 1).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });
    }
  }
  return d.slice(0, 10);
}

function daywiseFromTrend(trend: TrendPoint[]): AnalyticsDayRow[] {
  return trend.map((t) => ({
    date: String(t.date).slice(0, 10),
    label: trendLabel(t),
    sales: t.revenue,
    prior: typeof t.prior === 'number' ? t.prior : 0,
    bills: t.transactions ?? 0,
    quantity: t.quantity ?? 0,
  }));
}

function trendToYoyPoints(trend: TrendPoint[]): DashboardResponse['trend'] {
  return trend.map((t) => ({
    label: trendLabel(t),
    date: String(t.date).slice(0, 10),
    current: t.revenue,
    prior: typeof t.prior === 'number' ? t.prior : 0,
    bills: t.transactions ?? 0,
    quantity: t.quantity ?? 0,
  }));
}

function mapCategories(rows: CategoryPoint[]): AnalyticsRankRow[] {
  return rows.map((c) => ({
    name: c.category,
    revenue: c.revenue,
    percentage: c.percentage ?? 0,
    transactions: c.transactions ?? null,
  }));
}

function mapBranches(rows: BranchPoint[], total: number): AnalyticsRankRow[] {
  return rows.map((b) => ({
    name: b.branch,
    revenue: b.revenue,
    percentage: pctOfTotal(b.revenue, total),
    transactions: b.transactions ?? null,
  }));
}

export function mergeDepartmentPoints(
  page: AnalyticsPageData,
  deptPoints: DeptPoint[],
): AnalyticsPageData {
  if (!deptPoints.length) return page;
  const total = deptPoints.reduce((s, d) => s + d.revenue, 0);
  return { ...page, departments: mapDepartments(deptPoints, total) };
}

function mapDepartments(rows: DeptPoint[], total: number): AnalyticsRankRow[] {
  const filtered = rows.filter((d) => (d.department ?? '').trim().length > 0);
  const denom = total > 0 ? total : filtered.reduce((s, d) => s + d.revenue, 0);
  return filtered.map((d) => ({
    name: d.department.trim(),
    revenue: d.revenue,
    percentage: pctOfTotal(d.revenue, denom),
    transactions: d.transactions ?? null,
  }));
}

export function buildAnalyticsPageData(
  split: SplitBundle | null,
  dashboard: DashboardResponse | null,
  period: string,
): AnalyticsPageData {
  const dashTrend = dashboard?.trend ?? [];
  const apiTrend = split?.trend ?? [];
  const daywise = dashTrend.length > 0 ? daywiseFromDashboard(dashTrend) : daywiseFromTrend(apiTrend);

  const catRows = split?.categories?.length
    ? mapCategories(split.categories)
    : (dashboard?.categories ?? []).map((c) => ({
        name: c.name,
        revenue: c.revenue,
        percentage: c.percentage ?? 0,
        transactions: null as number | null,
      }));

  const branchTotal = (split?.branches ?? []).reduce((s, b) => s + b.revenue, 0)
    || (dashboard?.branches ?? []).reduce((s, b) => s + b.revenue, 0);
  const branchRows = split?.branches?.length
    ? mapBranches(split.branches, branchTotal)
    : (dashboard?.branches ?? []).map((b) => ({
        name: b.name,
        revenue: b.revenue,
        percentage: b.percentage ?? 0,
        transactions: null as number | null,
      }));

  const deptTotal = (split?.departments ?? []).reduce((s, d) => s + d.revenue, 0);
  const deptRows = mapDepartments(split?.departments ?? [], deptTotal);

  let summary: DashboardResponse['summary'] | null =
    dashboard?.summary
    ?? (hasUsableBundleKpis(split?.kpis) ? summaryFromKpis(split!.kpis) : null);

  if (summary && !summary.mtd_sales && daywise.length) {
    summary = {
      ...summary,
      mtd_sales: daywise.reduce((s, d) => s + d.sales, 0),
      bills: summary.bills || daywise.reduce((s, d) => s + d.bills, 0),
      quantity: summary.quantity || daywise.reduce((s, d) => s + d.quantity, 0),
    };
  } else if (summary && !summary.quantity && daywise.length) {
    summary = { ...summary, quantity: daywise.reduce((s, d) => s + d.quantity, 0) };
  } else if (!summary && daywise.length) {
    summary = {
      mtd_sales: daywise.reduce((s, d) => s + d.sales, 0),
      ly_sales: 0,
      sales_growth_pct: null,
      bills: daywise.reduce((s, d) => s + d.bills, 0),
      quantity: daywise.reduce((s, d) => s + d.quantity, 0),
      customers: null,
    };
  }

  const lyFromDaywise = daywise.reduce((s, d) => s + (d.prior ?? 0), 0);
  const lyTrendReady = daywise.some((d) => (d.prior ?? 0) > 0);
  if (summary && lyTrendReady) {
    summary = {
      ...summary,
      ly_sales: lyFromDaywise || summary.ly_sales,
      sales_growth_pct:
        summary.sales_growth_pct ??
        (lyFromDaywise > 0 ? growthPct(summary.mtd_sales, lyFromDaywise) : null),
    };
  } else if (summary && !lyTrendReady) {
    summary = { ...summary, ly_sales: 0, sales_growth_pct: null };
  }

  const yoyTrend = dashTrend.length > 0 ? dashTrend : trendToYoyPoints(apiTrend);

  return {
    period,
    period_label: dashboard?.period_label ?? PERIOD_LABELS[period] ?? period,
    granularity: dashboard?.granularity ?? granularityForPeriod(period),
    summary,
    checksum: dashboard?.checksum ?? null,
    yoyTrend,
    daywise,
    categories: catRows.sort((a, b) => b.revenue - a.revenue),
    branches: branchRows.sort((a, b) => b.revenue - a.revenue),
    departments: deptRows.sort((a, b) => b.revenue - a.revenue),
  };
}

/**
 * Phase 1 carries `customers: null`. `null ?? prev.customers` was reviving stale
 * cached `0` — never treat that as trustworthy; positive carry is for UI smoothness only.
 */
function mergeCustomerCarryField(
  nextVal: number | null | undefined,
  prevVal: number | null | undefined,
): number | null | undefined {
  if (nextVal != null && Number.isFinite(nextVal)) return nextVal;
  if (prevVal != null && prevVal > 0 && Number.isFinite(prevVal)) return prevVal;
  return nextVal ?? null;
}

/**
 * While a refetch paints the fast lean bundle first, reuse the last fully merged
 * dashboard slice (YoY KPIs + departments) so UI does not flicker skeletons /
 * ₹0 / empty department rows until phase 2 finishes.
 */
function carryForwardAnalyticsPartial(next: AnalyticsPageData, prev: AnalyticsPageData): AnalyticsPageData {
  let merged = next;
  if (!next.departments.length && prev.departments.length) {
    merged = { ...merged, departments: prev.departments };
  }
  if (prev.checksum && !next.checksum && prev.summary && next.summary) {
    merged = {
      ...merged,
      summary: {
        ...next.summary,
        ly_sales: prev.summary.ly_sales,
        sales_growth_pct:
          prev.summary.sales_growth_pct ?? next.summary.sales_growth_pct,
        customers: mergeCustomerCarryField(next.summary.customers, prev.summary.customers),
      },
    };
  }
  return merged;
}

/** Fast bundle + departments — lean bundle first (same as test/breakdown_fetch.py). */
export async function fetchAnalyticsBundle(period: string, topN = API_TOP_N_MAX): Promise<SplitBundle> {
  const n = Math.min(Math.max(topN, 1), API_TOP_N_MAX);
  const core = await analytics.bundle(period, {
    topN: n,
    includeDepartments: false,
    includeKpis: true,
  });
  let departments: DeptPoint[] = [];
  try {
    const deptRes = await analytics.departments(period, n);
    departments = deptRes.departments ?? [];
  } catch {
    /* show branch/category/trend even if departments fail */
  }
  return {
    branches: core.branches ?? [],
    trend: core.trend ?? [],
    categories: core.categories ?? [],
    departments,
    kpis: (core.kpis ?? {}) as KPIsResponse,
  };
}

function analyticsPageCacheKey(period: string, startDate?: string, endDate?: string): string {
  const base = `analytics-page:${period}:${startDate ?? ''}:${endDate ?? ''}`;
  if (period !== 'custom' && ROLLING_ANALYTICS_PERIODS.has(period)) {
    return `${base}:${localTodayIso()}`;
  }
  return base;
}

function isEmptyAnalyticsPage(d: AnalyticsPageData | null | undefined): boolean {
  if (!d) return true;
  const s = d.summary;
  const hasTotals =
    (s?.mtd_sales ?? 0) > 0 || (s?.bills ?? 0) > 0 || (s?.quantity ?? 0) > 0;
  if (hasTotals) return false;
  return !(d.daywise?.length || d.categories?.length || d.branches?.length);
}

/**
 * Periods that need /analytics/dashboard for YoY trend bars.
 * Today/Yesterday are intentionally excluded: they show no multi-day trend chart
 * so the bundle + KPI response is sufficient for instant render.
 */
const PERIODS_WITH_YOY_DASHBOARD = new Set([
  'mtd', 'qtd', 'ytd', 'last_6m',
]);

function applyBundleCustomerCount(
  page: AnalyticsPageData,
  count: number | null | undefined,
): AnalyticsPageData {
  if (count == null || !Number.isFinite(count) || !page.summary) return page;
  return { ...page, summary: { ...page.summary, customers: Math.round(count) } };
}

function bundleNeedsDashboardMerge(period: string, core: AnalyticsBundleResponse): boolean {
  if (!bundleHasCustomerCount(core)) return true;
  if (PERIODS_FETCH_DASHBOARD_FOR_CUSTOMERS.has(period)) return true;
  if (PERIODS_WITH_YOY_DASHBOARD.has(period)) {
    return !bundleTrendHasLy(core);
  }
  return false;
}

/**
 * Periods that still need a background dashboard fetch even if they don't
 * require YoY bars — used to populate customer count and other dashboard-only fields.
 * Today's dashboard is warmed in Phase 1 so this fetch returns from cache quickly.
 */
const PERIODS_FETCH_DASHBOARD_FOR_CUSTOMERS = new Set(['today', 'yesterday']);

/** True when category/branch data exists but departments never loaded (stale partial cache). */
function needsDepartmentBackfill(d: AnalyticsPageData | null | undefined): boolean {
  if (!d || periodIsCustom(d.period)) return false;
  const hasOtherBreakdowns =
    (d.categories?.length ?? 0) > 0 || (d.branches?.length ?? 0) > 0;
  return hasOtherBreakdowns && (d.departments?.length ?? 0) === 0;
}

function periodIsCustom(period: string): boolean {
  return period === 'custom';
}

/**
 * True when the page has enough data to render KPI cards + charts.
 * Intentionally does NOT block on LY data — the chart renders with current-year
 * bars and updates automatically when the dashboard fetch brings in prior values.
 */
function isRenderableAnalyticsPage(d: AnalyticsPageData): boolean {
  if (needsDepartmentBackfill(d)) return false;
  const hasCharts =
    (d.yoyTrend?.length ?? 0) > 0
    || (d.categories?.length ?? 0) > 0
    || (d.branches?.length ?? 0) > 0;
  const hasTotals =
    (d.summary?.mtd_sales ?? 0) > 0
    || (d.summary?.bills ?? 0) > 0;
  return hasCharts && hasTotals;
}

/**
 * True when the page is *fully* complete (dashboard merged, LY present, checksum ok).
 * Used to decide whether to skip background dashboard re-fetch.
 * If false, prefetchAnalyticsPage will still fire a dashboard HTTP request in
 * the background — the component renders immediately via onPartial/subscribePageUpdate.
 */
function isCompleteAnalyticsPage(d: AnalyticsPageData, period: string): boolean {
  if (!isRenderableAnalyticsPage(d)) return false;
  // Dashboard checksum = fully merged response, nothing left to fetch.
  if (d.checksum != null) return true;
  // For YoY periods, still consider "complete enough" once we have trend data —
  // even if LY is 0.  The dashboard fetch fires anyway (in prefetchAnalyticsPage)
  // but we don't block the UI on it.
  return true;
}

const _prefetchInflight = new Map<string, Promise<AnalyticsPageData | null>>();
const _pageUpdateListeners = new Map<string, Set<(data: AnalyticsPageData) => void>>();

function subscribePageUpdate(period: string, cb: (data: AnalyticsPageData) => void): () => void {
  let set = _pageUpdateListeners.get(period);
  if (!set) {
    set = new Set();
    _pageUpdateListeners.set(period, set);
  }
  set.add(cb);
  return () => {
    set!.delete(cb);
    if (set!.size === 0) _pageUpdateListeners.delete(period);
  };
}

function emitPageUpdate(period: string, data: AnalyticsPageData): void {
  _pageUpdateListeners.get(period)?.forEach((cb) => cb(data));
}

/**
 * Load + cache full Analytics page data for a period.
 * Dedupes in-flight work so tab switches reuse the same promise.
 * Phase 1: bundle (fast when server cache warm) → paint immediately.
 * Phase 2: departments + dashboard YoY (dashboard HTTP starts in parallel with bundle).
 */
/** True when analytics page has a distinct-customer count (0 is valid). */
function pageHasCustomerCount(d: AnalyticsPageData | null | undefined): boolean {
  return d?.summary?.customers != null && Number.isFinite(d.summary.customers);
}

/** Sales/bills loaded but customer count never arrived — stale partial cache. */
function needsCustomerCountBackfill(d: AnalyticsPageData | null | undefined): boolean {
  if (!d?.summary || pageHasCustomerCount(d)) return false;
  return (d.summary.mtd_sales ?? 0) > 0 || (d.summary.bills ?? 0) > 0;
}

/** True when cached data is fully merged and no background dashboard fetch is needed. */
function cachedIsFullyMerged(d: AnalyticsPageData, period: string): boolean {
  if (needsCustomerCountBackfill(d)) return false;
  if (d.checksum != null && pageHasCustomerCount(d)) return true;
  if (PERIODS_WITH_YOY_DASHBOARD.has(period) || PERIODS_FETCH_DASHBOARD_FOR_CUSTOMERS.has(period)) {
    const hasLy = (d.yoyTrend ?? []).some((p) => (p.prior ?? 0) > 0);
    return hasLy && pageHasCustomerCount(d);
  }
  return pageHasCustomerCount(d) || !needsCustomerCountBackfill(d);
}

export function prefetchAnalyticsPage(
  period: string,
  onPartial?: (data: AnalyticsPageData) => void,
): Promise<AnalyticsPageData | null> {
  const key = analyticsPageCacheKey(period);
  const cached = cacheGet<AnalyticsPageData>(key);
  // Only skip the fetch job when data is fully complete AND has LY values.
  // If LY is missing for a YoY period, we still need to fire a dashboard fetch
  // in the background — but the component renders immediately with current data.
  if (
    cached
    && !isEmptyAnalyticsPage(cached)
    && isUsable(key)
    && isCompleteAnalyticsPage(cached, period)
    && !needsDepartmentBackfill(cached)
    && !needsCustomerCountBackfill(cached)
    && cachedIsFullyMerged(cached, period)
  ) {
    onPartial?.(cached);
    return Promise.resolve(cached);
  }

  const inflight = _prefetchInflight.get(period);
  if (inflight) {
    if (onPartial) {
      const partial = cacheGet<AnalyticsPageData>(key);
      if (partial && !isEmptyAnalyticsPage(partial)) {
        onPartial(partial);
      }
    }
    return inflight;
  }

  const job = (async (): Promise<AnalyticsPageData | null> => {
    try {
      const n = API_TOP_N_MAX;
      const bundleP = analytics.bundle(period, {
        topN: n,
        includeDepartments: false,
        includeKpis: true,
        includeCustomerCount: true,
      });
      const deptCached = cacheGet<{ departments: DeptPoint[] }>(`departments:${period}:${n}`);
      const deptP = deptCached
        ? Promise.resolve(deptCached)
        : analytics.departments(period, n).catch(() => ({ departments: [] as DeptPoint[] }));

      const [core] = await Promise.all([bundleP]);
      const kpiRes = core.kpis ?? null;
      if (kpiRes) {
        cacheSet(`kpis:v2:${period}`, kpiRes);
        cacheSet(`kpis:${period}`, kpiRes);
      }

      const leanSplit: SplitBundle = {
        branches: core.branches ?? [],
        trend: core.trend ?? [],
        categories: core.categories ?? [],
        departments: [],
        kpis: (kpiRes ?? {}) as KPIsResponse,
      };
      const prevSnap = cacheGet<AnalyticsPageData>(key);
      let built = buildAnalyticsPageData(leanSplit, null, period);
      built = applyBundleCustomerCount(built, core.customer_count);
      if (built.summary && kpiRes) {
        built = { ...built, summary: enrichSummaryFromKpi(built.summary, kpiRes) };
      }
      if (prevSnap && !isEmptyAnalyticsPage(prevSnap)) {
        built = carryForwardAnalyticsPartial(built, prevSnap);
      }
      if (!isEmptyAnalyticsPage(built)) {
        cacheSet(key, built);
        emitPageUpdate(period, built);
        onPartial?.(built);
      }

      const deptRes = await deptP;
      if (deptRes.departments?.length) {
        cacheSet(`departments:${period}:${n}`, deptRes);
      }
      const split: SplitBundle = {
        ...leanSplit,
        departments: deptRes.departments ?? [],
      };

      built = buildAnalyticsPageData(split, null, period);
      built = applyBundleCustomerCount(built, core.customer_count);
      if (built.summary && kpiRes) {
        built = { ...built, summary: enrichSummaryFromKpi(built.summary, kpiRes) };
      }
      if (prevSnap && !isEmptyAnalyticsPage(prevSnap)) {
        built = carryForwardAnalyticsPartial(built, prevSnap);
      }
      if (!isEmptyAnalyticsPage(built)) {
        cacheSet(key, built);
        emitPageUpdate(period, built);
        onPartial?.(built);
      }

      if (bundleNeedsDashboardMerge(period, core)) {
        void (async () => {
          try {
            const dash = await analytics.dashboard(period).catch(() => null);
            const dashOk =
              dash && typeof dash === 'object' && !isEmptyDashboard(dash as DashboardResponse)
                ? (dash as DashboardResponse)
                : null;
            if (!dashOk) return;
            let full = buildAnalyticsPageData(split, dashOk, period);
            const kpiHint = cacheGet<KPIsResponse>(`kpis:v2:${period}`) ?? cacheGet<KPIsResponse>(`kpis:${period}`);
            const baseSummary = full.summary ?? dashOk.summary;
            if (baseSummary) {
              full = {
                ...full,
                summary: enrichSummaryFromKpi(baseSummary, kpiHint),
              };
            }
            if (!isEmptyAnalyticsPage(full)) {
              cacheSet(key, full);
              emitPageUpdate(period, full);
              onPartial?.(full);
            }
          } catch {
            /* keep partial bundle visible */
          } finally {
            _prefetchInflight.delete(period);
          }
        })();
      } else {
        _prefetchInflight.delete(period);
      }

      return built;
    } catch {
      _prefetchInflight.delete(period);
      return cacheGet<AnalyticsPageData>(key);
    }
  })();

  _prefetchInflight.set(period, job);
  return job;
}

export function prefetchAnalyticsShell(): void {
  const tabs = ['mtd', 'today', 'qtd', 'ytd', 'last_6m'];
  for (const p of tabs) {
    void prefetchAnalyticsPage(p);
  }
}

/** Back-compat: prefetch a custom list (e.g. all period tabs minus custom). */
export async function prefetchAnalyticsTabs(periods: string[]): Promise<void> {
  await Promise.all(periods.map((p) => prefetchAnalyticsPage(p)));
}

const PERIOD_LABELS: Record<string, string> = {
  today: 'Today',
  yesterday: 'Yesterday',
  mtd: 'Month-to-Date',
  qtd: 'Quarter-to-Date',
  ytd: 'Year-to-Date',
  last_6m: 'Last 6 Months',
};

export interface AnalyticsPageResult {
  data: AnalyticsPageData | null;
  loading: boolean;
  chartLoading: boolean;
  error: string | null;
  refetch: () => void;
}

/** Analytics.tsx — /analytics/bundle (fast) + optional dashboard YoY for MTD/today. */
export function useAnalyticsPage(
  period: string,
  startDate?: string,
  endDate?: string,
): AnalyticsPageResult {
  const cacheKey = analyticsPageCacheKey(period, startDate, endDate);
  const cached = cacheGet<AnalyticsPageData>(cacheKey);

  // ── Stale-data guard ────────────────────────────────────────────────────────
  // Track which cacheKey the stored `data` belongs to. When the user switches
  // periods, cacheKey changes immediately on the next render but useState still
  // holds the old period's data — causing a flash of stale content.
  //
  // React's synchronous-update-during-render pattern: calling setState here
  // (not in an effect) makes React re-render immediately with the new values,
  // skipping the intermediate render that would show stale data.
  // ──────────────────────────────────────────────────────────────────────────
  const [dataCacheKey, setDataCacheKey] = useState(cacheKey);
  const [data, setData]         = useState<AnalyticsPageData | null>(cached);
  const [loading, setLoading]   = useState<boolean>(!cached);
  const [chartLoading, setChartLoading] = useState(false);
  const [error, setError]       = useState<string | null>(null);

  if (dataCacheKey !== cacheKey) {
    // Period switched — synchronously replace stale data so the render that
    // sees the new tab label also shows the right data (or empty/loading).
    const fresh = cacheGet<AnalyticsPageData>(cacheKey) ?? null;
    setDataCacheKey(cacheKey);
    setData(fresh);
    setLoading(!fresh);
    setError(null);
    setChartLoading(false);
  }

  const run = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    const needsYoy = PERIODS_WITH_YOY_DASHBOARD.has(period);
    if (!silent) {
      const peek = cacheGet<AnalyticsPageData>(cacheKey);
      const hasRenderableChart = (peek?.yoyTrend?.length ?? 0) > 0;
      setChartLoading(needsYoy && !hasRenderableChart);
    }

    const fail = (err: unknown, silentFail: boolean) => {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      const friendly = msg.includes('abort') ? 'Request timed out — try a shorter period' : msg;
      if (!silentFail) setError(friendly);
    };

    const applyPartial = (partial: AnalyticsPageData) => {
      setData(partial);
      setDataCacheKey(cacheKey);
      cacheSet(cacheKey, partial);
      if (!silent) setLoading(false);
      if (
        !PERIODS_WITH_YOY_DASHBOARD.has(period)
        || (partial.yoyTrend?.length ?? 0) > 0
      ) {
        setChartLoading(false);
      }
    };

    try {
      if (period === 'custom') {
        setChartLoading(false);
        const dash = await analytics.dashboard(period, startDate, endDate);
        const built = buildAnalyticsPageData(null, dash, period);
        setData(built);
        setDataCacheKey(cacheKey);
        cacheSet(cacheKey, built);
        return;
      }

      const built = await prefetchAnalyticsPage(period, applyPartial);
      if (built && !isEmptyAnalyticsPage(built)) {
        setData(built);
        setDataCacheKey(cacheKey);
        cacheSet(cacheKey, built);
      } else if (!cacheGet<AnalyticsPageData>(cacheKey)) {
        fail(new Error('No analytics data returned'), !silent);
      }
    } catch (err) {
      fail(err, silent);
    } finally {
      if (!silent) setLoading(false);
      setChartLoading(false);
    }
  }, [period, startDate, endDate, cacheKey]);

  useEffect(() => {
    // The synchronous guard above handles data reset immediately on period change.
    // This effect handles the __hold__ sentinel and syncs dataCacheKey for future renders.
    if (period === '__hold__') {
      setData(null);
      setLoading(false);
      setChartLoading(false);
      setError(null);
      setDataCacheKey(cacheKey);
    }
    // For normal periods: data was already set synchronously by the guard above;
    // the fetch-trigger effect (below) handles calling run() when cache is cold.
  }, [cacheKey, period]); // eslint-disable-line react-hooks/exhaustive-deps

  // If bundle/snapshot omitted departments, fetch them directly (MTD logs showed no /departments call).
  useEffect(() => {
    if (period === '__hold__' || period === 'custom' || !data) return;
    if (!needsDepartmentBackfill(data)) return;

    let cancelled = false;
    setChartLoading(true);
    void analytics
      .departments(period, API_TOP_N_MAX)
      .then((res) => {
        if (cancelled || !(res.departments?.length)) return;
        const merged = mergeDepartmentPoints(data, res.departments);
        setData(merged);
        cacheSet(cacheKey, merged);
        if (res.departments.length) {
          cacheSet(`departments:${period}:${API_TOP_N_MAX}`, res);
        }
      })
      .catch(() => { /* keep partial page */ })
      .finally(() => {
        if (!cancelled) setChartLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [period, cacheKey, data]);

  // Background dashboard merge (customers, LY, checksum) — keep UI in sync after lean bundle paint.
  useEffect(() => {
    if (period === '__hold__' || period === 'custom') return;
    return subscribePageUpdate(period, (partial) => {
      setData(partial);
      setDataCacheKey(cacheKey);
      cacheSet(cacheKey, partial);
      setLoading(false);
      setChartLoading(false);
    });
  }, [period, cacheKey]);

  useEffect(() => {
    if (period === '__hold__' || period === 'custom') return;
    return subscribeCacheHydrate(() => {
      const c = cacheGet<AnalyticsPageData>(cacheKey);
      if (c && !isEmptyAnalyticsPage(c)) {
        setData(c);
        setLoading(false);
        if (isCompleteAnalyticsPage(c, period) && !needsDepartmentBackfill(c)) setChartLoading(false);
      }
    });
  }, [cacheKey, period]);

  useEffect(() => {
    if (period === '__hold__') return;

    const cached = cacheGet<AnalyticsPageData>(cacheKey);
    if (cached && !isEmptyAnalyticsPage(cached)) {
      setData(cached);
      setDataCacheKey(cacheKey);
      setLoading(false);
      setChartLoading(false);
      const freshComplete =
        isFresh(cacheKey)
        && isCompleteAnalyticsPage(cached, period)
        && !needsCustomerCountBackfill(cached)
        && cachedIsFullyMerged(cached, period)
        && !needsDepartmentBackfill(cached);
      if (freshComplete) return;
      void run(true);
      return;
    }

    if (isUsable(cacheKey)) {
      void run(true);
    } else {
      void run(false);
    }
  }, [run, cacheKey, period]);

  return {
    data,
    loading,
    chartLoading,
    error,
    refetch: useCallback(() => run(false), [run]),
  };
}

export interface DashboardKPIs {
  revenue: { value: number; growth: number | null; prior: number };
  transactions: { value: number; growth: number | null };
  avgOrder: { value: number; growth: number | null };
  customers: { value: number | null; growth: number | null };
  period: string;
  fromApi: boolean;
}

export function useKPIs(period = 'mtd') {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.kpis(period),
    [period],
    `kpis:${period}`,
  );
  const kpis: DashboardKPIs = {
    revenue:      { value: data?.revenue?.value ?? 0, growth: data?.revenue?.growth ?? null, prior: data?.revenue?.prior ?? 0 },
    transactions: { value: data?.transactions?.value ?? 0, growth: data?.transactions?.growth ?? null },
    avgOrder:     { value: data?.avg_order_value?.value ?? 0, growth: data?.avg_order_value?.growth ?? null },
    customers:    { value: data?.customers?.value ?? null, growth: data?.customers?.growth ?? null },
    period: data?.period ?? period,
    fromApi: !!data,
  };
  return { kpis, loading, error, refetch };
}

export function useRevenueTrend(period = 'last_30d') {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.trend(period),
    [period],
    `trend:${period}`,
  );
  return { trend: data?.trend ?? [], loading, error, refetch, fromApi: !!data };
}

export function useCategories(period = 'mtd', topN = 8) {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.categories(period, topN),
    [period, topN],
    `categories:${period}:${topN}`,
  );
  return { categories: data?.categories ?? [], loading, error, refetch, fromApi: !!data };
}

/** Warm Branch Intel chart cache — same key as useBranches. */
export function prefetchBranchesChart(period = 'mtd'): void {
  const key = `branches:${period}`;
  if (isFresh(key)) return;
  void analytics.branches(period)
    .then((d) => cacheSet(key, d))
    .catch(() => { /* offline / warm miss */ });
}

export function useBranches(period = 'mtd') {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.branches(period),
    [period],
    `branches:${period}`,
  );
  return { branches: data?.branches ?? [], loading, error, refetch, fromApi: !!data };
}

export function useDepartments(period = 'mtd', topN = 8) {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.departments(period, topN),
    [period, topN],
    `departments:${period}:${topN}`,
  );
  return { departments: data?.departments ?? [], loading, error, refetch, fromApi: !!data };
}

export function useSalespersons(period = 'mtd', topN = 10) {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.salespersons(period, topN),
    [period, topN],
    `salespersons:${period}:${topN}`,
  );
  return { salespersons: data?.salespersons ?? [], loading, error, refetch, fromApi: !!data };
}

export function useTransactionSummary(period = 'mtd') {
  const { data, loading, error, refetch } = useFetch(
    () => analytics.transactionSummary(period),
    [period],
    `txn_summary:${period}`,
  );
  const summary: TransactionSummary = data ?? {
    success: false, total_revenue: 0, total_transactions: 0,
    avg_ticket: 0, success_rate: 0, period, period_label: '',
  };
  return { summary, loading, error, refetch, fromApi: !!data };
}

export function useTransactions(params: {
  period?: string; page?: number; page_size?: number;
  branch?: string; category?: string; search?: string;
} = {}) {
  const key = txnsCacheKey(
    params.period ?? 'mtd',
    params.page ?? 1,
    params.page_size ?? 12,
    params.branch,
    params.category,
    params.search,
  );
  const { data, loading, error, refetch } = useFetch(
    () => analytics.transactions(params),
    [params.period, params.page, params.page_size, params.branch, params.category, params.search],
    key,
  );
  // dataPeriod lets the UI detect when cached data belongs to a *different* period
  // (e.g. MTD rows still showing after switching to Today). Show skeletons in that case.
  const dataPeriod: string | undefined = (data as any)?.period;
  return {
    transactions: data?.transactions ?? [],
    totalCount:   data?.total_count ?? 0,
    totalPages:   data?.total_pages ?? 1,
    dataPeriod,
    loading, error, refetch, fromApi: !!data,
  };
}

export function useBackendHealth() {
  const { data, loading } = useFetch(() => analytics.health(), [], 'health');
  const isConnected = data ? (data as Record<string, unknown>).status === 'healthy' : false;
  return { isConnected, loading, health: data };
}
