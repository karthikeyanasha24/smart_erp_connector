import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Database,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Download,
  Loader2,
  Wifi,
  WifiOff,
  Search,
  Table2,
  AlertTriangle,
  Play,
  X,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { analytics, type CatalogViewMeta, type ViewQueryResponse } from '../lib/api';
import { getStaticViewCatalog } from '../data/viewCatalog';
import { fmtCount } from '../lib/format';

const STATIC_CATALOG = getStaticViewCatalog();
const PAGE_SIZES = [25, 50, 100, 200] as const;
const ALL_ROWS_SIZE = 500; // "All rows" mode — 500 server rows per page

/* ─── RowsSelect ─────────────────────────────────────────────────────────────
   Custom rows-per-page dropdown — matches the premium dark dashboard theme.
   Replaces the native <select> which rendered with white browser chrome.
────────────────────────────────────────────────────────────────────────────── */
const ROW_OPTIONS: { value: string; label: string }[] = [
  { value: '25',  label: '25 rows' },
  { value: '50',  label: '50 rows' },
  { value: '100', label: '100 rows' },
  { value: '200', label: '200 rows' },
  { value: 'all', label: 'All rows (500/pg)' },
];

function RowsSelect({
  value,
  onChange,
  isDark,
}: {
  value: string;
  onChange: (v: string) => void;
  isDark: boolean;
}) {
  const [open, setOpen] = useState(false);
  const selected = ROW_OPTIONS.find(o => o.value === value) ?? ROW_OPTIONS[1];
  const isAll = value === 'all';

  return (
    <div className="relative" style={{ minWidth: 148 }}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(p => !p)}
        onBlur={(e) => {
          if (!e.currentTarget.parentElement?.contains(e.relatedTarget as Node)) setOpen(false);
        }}
        className="w-full flex items-center justify-between gap-2 px-3 rounded-xl text-sm font-semibold outline-none transition-all"
        style={{
          height: 44,
          background: isDark ? 'rgba(17,24,39,0.9)' : 'rgba(255,255,255,0.9)',
          border: open || isAll
            ? '1px solid rgba(6,182,212,0.5)'
            : isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.12)',
          color: isAll ? '#06B6D4' : isDark ? '#E5E7EB' : '#1E293B',
          boxShadow: open ? '0 0 0 3px rgba(6,182,212,0.12)' : 'none',
        }}
      >
        <span className="truncate">{selected.label}</span>
        <ChevronDown
          size={14}
          style={{
            color: isAll ? '#06B6D4' : isDark ? '#64748B' : '#94A3B8',
            flexShrink: 0,
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 150ms ease',
          }}
        />
      </button>

      {/* Dropdown menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.13, ease: 'easeOut' }}
            className="absolute left-0 right-0 z-50 mt-1 rounded-xl overflow-hidden"
            style={{
              background: isDark ? '#111827' : '#FFFFFF',
              border: '1px solid rgba(255,255,255,0.08)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4), 0 2px 8px rgba(0,0,0,0.2)',
              padding: '6px',
              backdropFilter: 'blur(12px)',
            }}
          >
            {ROW_OPTIONS.map(opt => {
              const isActive = opt.value === value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  tabIndex={0}
                  onClick={() => { onChange(opt.value); setOpen(false); }}
                  className="w-full text-left px-3 rounded-lg text-sm transition-all outline-none"
                  style={{
                    height: 38,
                    display: 'flex',
                    alignItems: 'center',
                    background: isActive ? 'rgba(6,182,212,0.18)' : 'transparent',
                    color: isActive ? '#06B6D4' : isDark ? '#CBD5E1' : '#334155',
                    fontWeight: isActive ? 600 : 400,
                  }}
                  onMouseEnter={e => {
                    if (!isActive) (e.currentTarget as HTMLElement).style.background = 'rgba(6,182,212,0.12)';
                    if (!isActive) (e.currentTarget as HTMLElement).style.color = '#06B6D4';
                  }}
                  onMouseLeave={e => {
                    if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent';
                    if (!isActive) (e.currentTarget as HTMLElement).style.color = isDark ? '#CBD5E1' : '#334155';
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── helpers ──────────────────────────────────────────────────────────────── */
function fmtCell(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return fmtCount(v);
    return v.toLocaleString('en-IN', { maximumFractionDigits: 4 });
  }
  if (v instanceof Date) return v.toISOString().slice(0, 19).replace('T', ' ');
  const s = String(v);
  return s.length > 120 ? `${s.slice(0, 117)}…` : s;
}

function escapeCsvCell(s: string) {
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function downloadCsv(columns: string[], rows: Record<string, unknown>[], viewName: string, page: number) {
  const header = columns.join(',');
  const body = rows.map((r) =>
    columns.map((c) => escapeCsvCell(fmtCell(r[c]))).join(','),
  );
  const csv = [header, ...body].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${viewName}-page${page}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ─── category colours ─────────────────────────────────────────────────────── */
const CATEGORY_COLORS: Record<string, string> = {
  'Sales & Revenue': '#5882ff',
  'Products & Inventory': '#00e67a',
  Customers: '#a78bfa',
  Branches: '#f472b6',
  Purchasing: '#fb923c',
  Finance: '#ffb800',
  Other: '#94a3b8',
};

function categoryOf(key: string): string {
  const k = key.toLowerCase();
  if (k.includes('sales') || k.includes('revenue') || k.includes('daily') || k.includes('invoice')) return 'Sales & Revenue';
  if (k.includes('product') || k.includes('stock') || k.includes('item') || k.includes('inventory')) return 'Products & Inventory';
  if (k.includes('customer') || k.includes('client') || k.includes('debtor')) return 'Customers';
  if (k.includes('branch') || k.includes('store')) return 'Branches';
  if (k.includes('purchase') || k.includes('supplier') || k.includes('vendor')) return 'Purchasing';
  if (k.includes('finance') || k.includes('payment') || k.includes('credit') || k.includes('ledger')) return 'Finance';
  return 'Other';
}

/* ─── component ─────────────────────────────────────────────────────────────── */
export default function DataViews() {
  const { isDark } = useTheme();
  const { user, loading: authLoading } = useAuth();

  const [catalog, setCatalog] = useState<CatalogViewMeta[]>(() => STATIC_CATALOG.views);
  const [catalogDb, setCatalogDb] = useState(() => STATIC_CATALOG.database);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [catalogFromApi, setCatalogFromApi] = useState(false);

  const [selectedKey, setSelectedKey] = useState(() => STATIC_CATALOG.views[0]?.key ?? '');
  const [pageSize, setPageSize] = useState<number>(50);
  const [allRowsMode, setAllRowsMode] = useState(false); // "All rows" = 500/page server pagination
  const [page, setPage] = useState(1);
  const [viewSearch, setViewSearch] = useState('');

  const [result, setResult] = useState<ViewQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  /* styles */
  const card = {
    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.92)',
    border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
  } as const;

  /* ── catalog ── */
  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const res = await analytics.viewsCatalog();
      if (res.views?.length) {
        setCatalog(res.views);
        setCatalogDb(res.database ?? STATIC_CATALOG.database);
        setCatalogFromApi(true);
        setSelectedKey((prev) => prev || res.views[0].key);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Catalog fetch failed';
      setCatalogError(`${msg}. Using offline catalog (${STATIC_CATALOG.views.length} views).`);
      setCatalog(STATIC_CATALOG.views);
      setCatalogDb(STATIC_CATALOG.database);
      setCatalogFromApi(false);
    } finally {
      setCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !user) return;
    void loadCatalog();
  }, [authLoading, user, loadCatalog]);

  /* ── selected view meta ── */
  const selectedMeta = useMemo(
    () => catalog.find((v) => v.key === selectedKey),
    [catalog, selectedKey],
  );

  /* ── filtered view list ── */
  const filteredViews = useMemo(() => {
    const q = viewSearch.trim().toLowerCase();
    if (!q) return catalog;
    return catalog.filter(
      (v) =>
        v.short_name.toLowerCase().includes(q) ||
        v.purpose.toLowerCase().includes(q) ||
        v.key.toLowerCase().includes(q),
    );
  }, [catalog, viewSearch]);

  /* ── data fetch ── */
  const effectivePageSize = allRowsMode ? ALL_ROWS_SIZE : pageSize;

  const runQuery = useCallback(
    async (targetPage: number) => {
      if (!selectedKey) return;
      setLoading(true);
      setLoadError(null);
      try {
        const res = await analytics.viewQuery({ view: selectedKey, page: targetPage, page_size: effectivePageSize });
        setResult(res);
        setPage(targetPage);
      } catch (e) {
        setResult(null);
        setLoadError(e instanceof Error ? e.message : 'Failed to load view data');
      } finally {
        setLoading(false);
      }
    },
    [selectedKey, effectivePageSize],
  );

  const handleLoad = () => void runQuery(1);

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-108px)]">

      {/* ── header ── */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, rgba(88,130,255,0.2), rgba(139,92,246,0.2))', border: '1px solid rgba(88,130,255,0.25)' }}
          >
            <Database size={16} style={{ color: '#5882ff' }} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>Data Explorer</h2>
              <span
                className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5 rounded-full"
                style={{
                  background: catalogFromApi ? 'rgba(34,197,94,0.12)' : 'rgba(148,163,184,0.12)',
                  color: catalogFromApi ? '#4ade80' : 'var(--text-muted)',
                }}
              >
                {catalogFromApi ? <Wifi size={9} /> : <WifiOff size={9} />}
                {catalogFromApi ? 'Live' : 'Offline'}
              </span>
            </div>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {catalog.length} ERP views{catalogDb ? ` · ${catalogDb}` : ''}
            </p>
          </div>
        </div>
        <motion.button
          type="button"
          onClick={() => { void loadCatalog(); if (result) void runQuery(page); }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold"
          style={{ background: isDark ? 'rgba(88,130,255,0.1)' : 'rgba(88,130,255,0.08)', color: '#5882ff', border: '1px solid rgba(88,130,255,0.2)' }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.97 }}
        >
          <RefreshCw size={12} className={catalogLoading || loading ? 'animate-spin' : ''} />
          Refresh
        </motion.button>
      </div>

      {catalogError && (
        <div className="flex items-start gap-2 px-3 py-2 rounded-xl text-xs flex-shrink-0"
          style={{ background: 'rgba(251,146,60,0.1)', border: '1px solid rgba(251,146,60,0.25)', color: '#fb923c' }}>
          <AlertTriangle size={12} className="flex-shrink-0 mt-0.5" />
          {catalogError}
        </div>
      )}

      {/* ── two-pane body ── */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* LEFT: view selector panel */}
        <div
          className="w-72 flex-shrink-0 flex flex-col rounded-2xl overflow-hidden"
          style={card}
        >
          {/* search */}
          <div className="p-3 flex-shrink-0" style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
            <div className="relative">
              <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
              <input
                type="search"
                placeholder="Search views…"
                value={viewSearch}
                onChange={(e) => setViewSearch(e.target.value)}
                className="w-full pl-7 pr-3 py-1.5 rounded-lg text-xs outline-none"
                style={{
                  background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                  border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
                  color: 'var(--text-primary)',
                }}
              />
              {viewSearch && (
                <button type="button" onClick={() => setViewSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2">
                  <X size={10} style={{ color: 'var(--text-muted)' }} />
                </button>
              )}
            </div>
            <p className="text-2xs mt-1.5" style={{ color: 'var(--text-muted)' }}>
              {filteredViews.length} of {catalog.length} views
            </p>
          </div>

          {/* view list */}
          <div className="flex-1 overflow-y-auto scrollbar-none p-2 space-y-0.5">
            {filteredViews.map((v) => {
              const cat = categoryOf(v.key);
              const color = CATEGORY_COLORS[cat] ?? '#94a3b8';
              const isActive = v.key === selectedKey;
              return (
                <motion.button
                  key={v.key}
                  type="button"
                  onClick={() => {
                    setSelectedKey(v.key);
                    setResult(null);
                    setPage(1);
                    setLoadError(null);
                    // Don't reset allRowsMode — user preference should persist across views
                  }}
                  className="w-full text-left px-2.5 py-2 rounded-xl flex items-start gap-2"
                  style={{
                    background: isActive
                      ? isDark ? 'rgba(88,130,255,0.12)' : 'rgba(88,130,255,0.09)'
                      : 'transparent',
                    border: isActive ? `1px solid rgba(88,130,255,0.25)` : '1px solid transparent',
                  }}
                  whileHover={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)' }}
                  whileTap={{ scale: 0.98 }}
                >
                  <div
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5"
                    style={{ background: color }}
                  />
                  <div className="min-w-0">
                    <p
                      className="text-xs font-semibold truncate"
                      style={{ color: isActive ? '#5882ff' : 'var(--text-primary)' }}
                    >
                      {v.short_name}
                    </p>
                    <p className="text-2xs truncate mt-0.5" style={{ color: 'var(--text-muted)' }}>
                      {v.purpose.slice(0, 60)}{v.purpose.length > 60 ? '…' : ''}
                    </p>
                  </div>
                </motion.button>
              );
            })}
          </div>
        </div>

        {/* RIGHT: data panel */}
        <div className="flex-1 flex flex-col min-w-0 gap-3">

          {/* controls bar */}
          <div className="rounded-2xl p-4 flex-shrink-0" style={card}>
            <div className="flex flex-wrap items-end gap-3">
              {/* view info */}
              <div className="flex-1 min-w-0">
                {selectedMeta ? (
                  <>
                    <div className="flex items-center gap-2 mb-0.5">
                      <Table2 size={13} style={{ color: '#5882ff' }} />
                      <span className="text-sm font-bold truncate" style={{ color: 'var(--text-primary)' }}>
                        {selectedMeta.short_name}
                      </span>
                      {selectedMeta.column_count && (
                        <span className="text-2xs px-1.5 py-0.5 rounded-full flex-shrink-0"
                          style={{ background: 'rgba(88,130,255,0.12)', color: '#5882ff' }}>
                          ~{selectedMeta.column_count} cols
                        </span>
                      )}
                    </div>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      <span className="font-mono text-2xs">{selectedMeta.fqn}</span>
                      {selectedMeta.grain ? <span> · {selectedMeta.grain}</span> : null}
                    </p>
                    {selectedMeta.note && (
                      <p className="text-2xs mt-1 flex items-center gap-1" style={{ color: '#fb923c' }}>
                        <AlertTriangle size={10} />{selectedMeta.note}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Select a view from the left panel</p>
                )}
              </div>

              {/* rows per page */}
              <div className="flex-shrink-0">
                <span className="text-2xs font-semibold uppercase tracking-wider block mb-1" style={{ color: 'var(--text-muted)' }}>
                  Rows / page
                </span>
                <RowsSelect
                  value={allRowsMode ? 'all' : String(pageSize)}
                  isDark={isDark}
                  onChange={(v) => {
                    if (v === 'all') {
                      setAllRowsMode(true);
                    } else {
                      setAllRowsMode(false);
                      setPageSize(Number(v));
                    }
                    setResult(null);
                    setPage(1);
                  }}
                />
              </div>

              {/* load button */}
              <motion.button
                type="button"
                onClick={handleLoad}
                disabled={!selectedKey || loading}
                className="flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-bold text-white disabled:opacity-50 flex-shrink-0"
                style={{ background: 'linear-gradient(135deg, #4158D0 0%, #5882ff 100%)' }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
              >
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                Load
              </motion.button>
            </div>
          </div>

          {/* error */}
          {loadError && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs flex-shrink-0"
              style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}>
              <AlertTriangle size={12} />{loadError}
            </div>
          )}

          {/* KPI strip */}
          <AnimatePresence>
            {result && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="grid grid-cols-3 gap-3 flex-shrink-0"
              >
                {[
                  {
                    label: 'Total rows',
                    value: result.count_skipped ? `${fmtCount(result.total_count)}+` : fmtCount(result.total_count),
                    sub: result.count_skipped
                      ? 'Fast mode — full count skipped'
                      : result.capped
                        ? `Capped at ${fmtCount(result.hard_cap)}`
                        : 'in view',
                    color: '#5882ff',
                  },
                  {
                    label: 'Columns',
                    value: String(result.columns.length),
                    sub: `${result.duration_ms}ms query`,
                    color: '#00e67a',
                  },
                  {
                    label: 'Page',
                    value: `${result.page} / ${result.total_pages}`,
                    sub: allRowsMode ? `${fmtCount(result.rows.length)} rows (500/pg)` : `${fmtCount(result.rows.length)} rows shown`,
                    color: allRowsMode ? '#5882ff' : '#a78bfa',
                  },
                ].map((kpi) => (
                  <div
                    key={kpi.label}
                    className="rounded-xl px-3 py-2.5"
                    style={{
                      background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.92)',
                      border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
                    }}
                  >
                    <p className="text-2xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                      {kpi.label}
                    </p>
                    <p className="text-xl font-bold mt-0.5 tabular-nums" style={{ color: kpi.color }}>{kpi.value}</p>
                    <p className="text-2xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{kpi.sub}</p>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {/* empty columns state — view returned no schema (view is empty or timed out) */}
          {result && result.columns.length === 0 && !loading && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 rounded-2xl" style={card}>
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(251,146,60,0.1)', border: '1px solid rgba(251,146,60,0.2)' }}
              >
                <AlertTriangle size={24} style={{ color: '#fb923c' }} />
              </div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                View returned no columns
              </p>
              <p className="text-xs text-center max-w-sm" style={{ color: 'var(--text-muted)' }}>
                This view appears to be empty, or the SQL Server query returned no schema.
                Try a different view, or use a smaller page size.
              </p>
              <button
                type="button"
                onClick={handleLoad}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-semibold"
                style={{ background: 'rgba(88,130,255,0.1)', color: '#5882ff', border: '1px solid rgba(88,130,255,0.2)' }}
              >
                <RefreshCw size={12} />
                Retry
              </button>
            </div>
          )}

          {/* data table — keep visible while paginating */}
          <AnimatePresence>
            {result && result.columns.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex-1 rounded-2xl overflow-hidden flex flex-col min-h-0"
                style={card}
              >
                {/* table header bar */}
                <div
                  className="flex items-center justify-between px-4 py-2.5 flex-shrink-0"
                  style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}
                >
                  <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                    {result.short_name} &mdash; {fmtCount(result.rows.length)} row(s) on page {result.page}
                  </span>
                  <button
                    type="button"
                    onClick={() => downloadCsv(result.columns, result.rows, result.short_name, result.page)}
                    className="flex items-center gap-1.5 text-2xs font-semibold px-2.5 py-1.5 rounded-lg"
                    style={{
                      background: isDark ? 'rgba(88,130,255,0.1)' : 'rgba(88,130,255,0.08)',
                      color: '#5882ff',
                      border: '1px solid rgba(88,130,255,0.2)',
                    }}
                  >
                    <Download size={11} />
                    CSV
                  </button>
                </div>

                {/* scrollable table */}
                <div className="flex-1 overflow-auto scrollbar-thin">
                  <table className="w-full text-left border-collapse min-w-max">
                    <thead
                      className="sticky top-0 z-10"
                      style={{ background: isDark ? '#0e1630' : '#f1f5f9' }}
                    >
                      <tr>
                        {result.columns.map((col, ci) => (
                          <th
                            key={col}
                            className="px-3 py-2.5 whitespace-nowrap text-left"
                            style={{
                              color: isDark ? '#8fa8d0' : '#64748b',
                              fontSize: 10,
                              fontWeight: 600,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                              borderRight: ci < result.columns.length - 1
                                ? isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)'
                                : undefined,
                            }}
                          >
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.rows.length === 0 ? (
                        <tr>
                          <td
                            colSpan={result.columns.length}
                            className="text-center py-10 text-xs"
                            style={{ color: 'var(--text-muted)' }}
                          >
                            No rows returned for page {result.page}.
                            {result.page > 1 ? ' Try going back to page 1.' : ' This view may be empty.'}
                          </td>
                        </tr>
                      ) : result.rows.map((row, ri) => (
                        <tr
                          key={ri}
                          style={{
                            background: ri % 2 === 0
                              ? 'transparent'
                              : isDark ? 'rgba(255,255,255,0.018)' : 'rgba(0,0,0,0.018)',
                          }}
                        >
                          {result.columns.map((col, ci) => (
                            <td
                              key={col}
                              className="px-3 py-1.5 text-xs whitespace-nowrap max-w-[260px] truncate"
                              style={{
                                color: ci === 0
                                ? (isDark ? '#e8eeff' : '#0f172a')
                                : (isDark ? '#b8c4e0' : '#334155'),
                                fontWeight: ci === 0 ? 500 : 400,
                                borderRight: ci < result.columns.length - 1
                                  ? isDark ? '1px solid rgba(255,255,255,0.03)' : '1px solid rgba(0,0,0,0.03)'
                                  : undefined,
                              }}
                              title={fmtCell(row[col])}
                            >
                              {fmtCell(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* pagination */}
                <div
                  className="flex items-center justify-between gap-3 px-4 py-2.5 flex-shrink-0"
                  style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}
                >
                  <span className="text-2xs" style={{ color: 'var(--text-muted)' }}>
                    Showing {(result.page - 1) * result.page_size + 1}–
                    {(result.page - 1) * result.page_size + result.rows.length} of {fmtCount(result.total_count)}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      disabled={result.page <= 1 || loading}
                      onClick={() => void runQuery(result.page - 1)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-40"
                      style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', color: 'var(--text-primary)' }}
                    >
                      <ChevronLeft size={13} />
                      Prev
                    </button>
                    <div className="flex items-center gap-1">
                      {Array.from({ length: Math.min(5, result.total_pages) }, (_, i) => {
                        let pageNum: number;
                        if (result.total_pages <= 5) {
                          pageNum = i + 1;
                        } else if (result.page <= 3) {
                          pageNum = i + 1;
                        } else if (result.page >= result.total_pages - 2) {
                          pageNum = result.total_pages - 4 + i;
                        } else {
                          pageNum = result.page - 2 + i;
                        }
                        return (
                          <button
                            key={pageNum}
                            type="button"
                            disabled={loading}
                            onClick={() => void runQuery(pageNum)}
                            className="w-7 h-7 rounded-lg text-xs font-medium"
                            style={{
                              background: pageNum === result.page
                                ? 'linear-gradient(135deg, #4158D0, #5882ff)'
                                : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                              color: pageNum === result.page ? 'white' : 'var(--text-secondary)',
                            }}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                    </div>
                    <button
                      type="button"
                      disabled={
                        loading
                        || (!(result.has_more ?? result.page < result.total_pages))
                      }
                      onClick={() => void runQuery(result.page + 1)}
                      className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-40"
                      style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)', color: 'var(--text-primary)' }}
                    >
                      Next
                      <ChevronRight size={13} />
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* empty / idle state */}
          {!result && !loading && !loadError && (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 rounded-2xl" style={card}>
              <div
                className="w-14 h-14 rounded-2xl flex items-center justify-center"
                style={{ background: 'rgba(88,130,255,0.1)', border: '1px solid rgba(88,130,255,0.2)' }}
              >
                <Table2 size={24} style={{ color: '#5882ff' }} />
              </div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                Select a view and press <strong>Load</strong>
              </p>
              <p className="text-xs text-center max-w-xs" style={{ color: 'var(--text-muted)' }}>
                Choose any of the {catalog.length} ERP views on the left, pick a page size (or <strong>All rows</strong> for 500/page), then click Load.
              </p>
            </div>
          )}

          {/* loading state — only full-screen when no data yet */}
          {loading && !result && (
            <div className="flex-1 flex items-center justify-center rounded-2xl" style={card}>
              <div className="flex flex-col items-center gap-3">
                <Loader2 size={28} className="animate-spin" style={{ color: '#5882ff' }} />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading page {page}…</p>
                <p className="text-xs text-center max-w-sm" style={{ color: 'var(--text-muted)' }}>
                  Branch and master views load without a full table scan. Large sales views may take longer.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
