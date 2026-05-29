/**
 * ERP Views Browser — all 28 SQL Server views with row-level pagination.
 * Click any view card → see all its rows, page by page.
 */
import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Table2, ChevronLeft, ChevronRight, Search,
  Layers, Database, RefreshCw, X, ArrowLeft,
  Download, Info, Loader2,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { analytics, type CatalogViewMeta, type ViewQueryResponse } from '../lib/api';
import { getStaticViewCatalog } from '../data/viewCatalog';
import { fmtCount } from '../lib/format';

const stagger = { animate: { transition: { staggerChildren: 0.04 } } };
const item = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 280, damping: 28 } },
};

const STATIC_CATALOG = getStaticViewCatalog();
const PAGE_SIZES = [25, 50, 100] as const;
type PageSize = typeof PAGE_SIZES[number];

function fmtCell(v: unknown): string {
  if (v == null) return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return fmtCount(v);
    return v.toLocaleString('en-IN', { maximumFractionDigits: 4 });
  }
  if (v instanceof Date) return v.toISOString().slice(0, 19).replace('T', ' ');
  const s = String(v);
  return s.length > 100 ? `${s.slice(0, 97)}…` : s;
}

function escapeCsvCell(s: string) {
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function downloadCsv(columns: string[], rows: Record<string, unknown>[], viewName: string, page: number) {
  const body = rows.map(r => columns.map(c => escapeCsvCell(fmtCell(r[c]))).join(','));
  const csv = [columns.join(','), ...body].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${viewName}-page-${page}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/** Group views by a loose category derived from their purpose */
function groupViews(views: CatalogViewMeta[]): { label: string; views: CatalogViewMeta[] }[] {
  const groups: Record<string, CatalogViewMeta[]> = {};
  for (const v of views) {
    const p = (v.purpose ?? '').toLowerCase();
    let group = 'Other';
    if (p.includes('sale') || p.includes('revenue') || p.includes('billing')) group = 'Sales & Revenue';
    else if (p.includes('product') || p.includes('item') || p.includes('catalog') || p.includes('stock')) group = 'Products & Inventory';
    else if (p.includes('customer') || p.includes('client')) group = 'Customers';
    else if (p.includes('branch') || p.includes('location') || p.includes('region')) group = 'Branches';
    else if (p.includes('purchase') || p.includes('vendor') || p.includes('supplier')) group = 'Purchasing';
    else if (p.includes('account') || p.includes('ledger') || p.includes('finance')) group = 'Finance';
    (groups[group] = groups[group] ?? []).push(v);
  }
  // Sort groups — put Sales first
  const order = ['Sales & Revenue', 'Products & Inventory', 'Customers', 'Branches', 'Purchasing', 'Finance', 'Other'];
  return order.filter(k => groups[k]?.length).map(k => ({ label: k, views: groups[k] }));
}

// ─── View Card ────────────────────────────────────────────────────────────────

function ViewCard({
  view,
  onOpen,
  isDark,
}: {
  view: CatalogViewMeta;
  onOpen: (v: CatalogViewMeta) => void;
  isDark: boolean;
}) {
  const cardBg = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.88)';
  const cardBorder = isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)';

  return (
    <motion.button
      onClick={() => onOpen(view)}
      className="w-full text-left rounded-2xl p-4 flex flex-col gap-2 relative overflow-hidden"
      style={{ background: cardBg, border: cardBorder, backdropFilter: 'blur(16px)' }}
      whileHover={{ y: -2, boxShadow: '0 8px 24px rgba(0,0,0,0.12)' }}
      whileTap={{ scale: 0.98 }}
    >
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(88,130,255,0.12)', border: '1px solid rgba(88,130,255,0.2)' }}>
          <Table2 size={16} style={{ color: '#5882ff' }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            {view.catalog_no != null && (
              <span className="text-2xs font-bold px-1.5 py-0.5 rounded"
                style={{ background: 'rgba(88,130,255,0.12)', color: '#5882ff' }}>
                #{view.catalog_no}
              </span>
            )}
            <span className="text-2xs font-mono truncate" style={{ color: 'var(--text-muted)' }}>
              {view.fqn.split('.').slice(-2).join('.')}
            </span>
          </div>
          <p className="text-sm font-semibold leading-snug" style={{ color: 'var(--text-primary)' }}>
            {view.short_name}
          </p>
        </div>
      </div>

      <p className="text-xs leading-relaxed line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
        {view.purpose || 'ERP view'}
      </p>

      <div className="flex items-center gap-2 flex-wrap mt-0.5">
        {view.grain && (
          <span className="text-2xs px-2 py-0.5 rounded-full"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: 'var(--text-muted)' }}>
            {view.grain}
          </span>
        )}
        {view.column_count != null && (
          <span className="text-2xs px-2 py-0.5 rounded-full"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: 'var(--text-muted)' }}>
            {view.column_count} cols
          </span>
        )}
        <span className="ml-auto text-2xs font-semibold" style={{ color: '#5882ff' }}>
          Browse rows →
        </span>
      </div>
    </motion.button>
  );
}

// ─── Row Browser ──────────────────────────────────────────────────────────────

function RowBrowser({
  view,
  onBack,
  isDark,
}: {
  view: CatalogViewMeta;
  onBack: () => void;
  isDark: boolean;
}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(50);
  const [result, setResult] = useState<ViewQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cardBg = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.88)';
  const cardBorder = isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)';
  const innerBg = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)';
  const innerBorder = isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)';
  const headerBg = isDark ? 'rgba(88,130,255,0.08)' : 'rgba(88,130,255,0.06)';

  const load = useCallback(async (p: number, ps: PageSize) => {
    setLoading(true);
    setError(null);
    try {
      const data = await analytics.viewQuery({ view: view.key, page: p, page_size: ps });
      setResult(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load view';
      setError(msg.includes('abort') ? 'Query timed out — try a smaller page size' : msg);
    } finally {
      setLoading(false);
    }
  }, [view.key]);

  // Load on open — backend skips COUNT(*) for dimension views (e.g. VwAIBranch).
  useEffect(() => {
    void load(1, pageSize);
  }, [load, pageSize]);

  const goToPage = (p: number) => {
    setPage(p);
    void load(p, pageSize);
  };

  const changePageSize = (ps: PageSize) => {
    setPageSize(ps);
    setPage(1);
  };

  const columns = result?.columns ?? [];
  const rows = result?.rows ?? [];
  const totalPages = result?.total_pages ?? 1;
  const totalCount = result?.total_count ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.25 }}
      className="space-y-4"
    >
      {/* Browser header */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <motion.button onClick={onBack}
            className="p-2 rounded-xl"
            style={{ background: innerBg, border: cardBorder, color: 'var(--text-muted)' }}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <ArrowLeft size={15} />
          </motion.button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
                {view.short_name}
              </h2>
              {view.catalog_no != null && (
                <span className="text-xs font-bold px-2 py-0.5 rounded"
                  style={{ background: 'rgba(88,130,255,0.12)', color: '#5882ff' }}>
                  #{view.catalog_no}
                </span>
              )}
            </div>
            <p className="text-xs mt-0.5 font-mono" style={{ color: 'var(--text-muted)' }}>
              {view.fqn}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {result && (
            <span className="text-xs px-3 py-1.5 rounded-full"
              style={{ background: 'rgba(0,230,122,0.1)', border: '1px solid rgba(0,230,122,0.2)', color: '#00e67a' }}>
              {result.count_skipped ? `${fmtCount(totalCount)}+ rows` : `${fmtCount(totalCount)} rows`}
            </span>
          )}
          {/* Page size picker */}
          <div className="flex items-center rounded-xl p-1 gap-0.5"
            style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', border: cardBorder }}>
            {PAGE_SIZES.map(ps => (
              <button key={ps}
                onClick={() => changePageSize(ps)}
                className="px-2.5 py-1 rounded-lg text-xs font-semibold"
                style={{
                  background: pageSize === ps
                    ? isDark ? 'rgba(88,130,255,0.18)' : 'rgba(88,130,255,0.12)'
                    : 'transparent',
                  color: pageSize === ps ? '#5882ff' : 'var(--text-muted)',
                  border: pageSize === ps ? '1px solid rgba(88,130,255,0.3)' : '1px solid transparent',
                }}>
                {ps}
              </button>
            ))}
          </div>

          {result && columns.length > 0 && rows.length > 0 && (
            <motion.button
              onClick={() => downloadCsv(columns, rows, view.short_name, page)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold"
              style={{ background: 'rgba(88,130,255,0.1)', border: '1px solid rgba(88,130,255,0.2)', color: '#5882ff' }}
              whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Download size={12} /> CSV
            </motion.button>
          )}

          <motion.button
            onClick={() => void load(page, pageSize)}
            className="p-2 rounded-xl"
            style={{ background: innerBg, border: cardBorder, color: 'var(--text-muted)' }}
            whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
          </motion.button>
        </div>
      </div>

      {/* Purpose strip */}
      {view.purpose && (
        <div className="flex items-start gap-2 px-4 py-2.5 rounded-xl"
          style={{ background: headerBg, border: '1px solid rgba(88,130,255,0.15)' }}>
          <Info size={13} style={{ color: '#5882ff', flexShrink: 0, marginTop: 1 }} />
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{view.purpose}</p>
        </div>
      )}

      {/* Table area */}
      <div className="rounded-2xl overflow-hidden"
        style={{ background: cardBg, border: cardBorder, backdropFilter: 'blur(16px)' }}>
        {loading && !result ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 size={28} className="animate-spin" style={{ color: '#5882ff' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              Loading {view.short_name}…
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              This may take a moment for large views
            </p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)' }}>
              <X size={18} style={{ color: '#f87171' }} />
            </div>
            <p className="text-sm font-semibold" style={{ color: '#f87171' }}>Failed to load</p>
            <p className="text-xs text-center max-w-xs" style={{ color: 'var(--text-muted)' }}>{error}</p>
            <motion.button
              onClick={() => void load(page, pageSize)}
              className="px-4 py-2 rounded-xl text-xs font-semibold mt-1"
              style={{ background: 'rgba(88,130,255,0.1)', border: '1px solid rgba(88,130,255,0.2)', color: '#5882ff' }}
              whileHover={{ scale: 1.03 }}>
              Retry
            </motion.button>
          </div>
        ) : columns.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <Table2 size={24} style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No data returned</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr style={{ background: headerBg, borderBottom: `1px solid rgba(88,130,255,0.12)` }}>
                  <th className="px-3 py-2.5 text-left font-semibold sticky left-0 z-10"
                    style={{ background: headerBg, color: 'var(--text-muted)', width: 48, minWidth: 48 }}>
                    #
                  </th>
                  {columns.map(col => (
                    <th key={col} className="px-3 py-2.5 text-left font-semibold whitespace-nowrap"
                      style={{ color: 'var(--text-secondary)', minWidth: 100 }}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, ri) => (
                  <motion.tr
                    key={ri}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(ri * 0.008, 0.3) }}
                    style={{
                      borderBottom: innerBorder,
                      background: ri % 2 === 0 ? 'transparent' : innerBg,
                    }}
                  >
                    <td className="px-3 py-2 tabular-nums sticky left-0"
                      style={{ color: 'var(--text-muted)', background: ri % 2 === 0 ? (isDark ? 'rgba(10,14,33,0.6)' : 'rgba(255,255,255,0.9)') : (isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)') }}>
                      {(page - 1) * pageSize + ri + 1}
                    </td>
                    {columns.map(col => (
                      <td key={col} className="px-3 py-2 max-w-xs truncate"
                        style={{ color: 'var(--text-primary)' }}
                        title={fmtCell(row[col])}>
                        {fmtCell(row[col])}
                      </td>
                    ))}
                  </motion.tr>
                ))}
              </tbody>
            </table>

            {/* Loading overlay for page changes */}
            {loading && (
              <div className="flex items-center justify-center py-6 gap-2"
                style={{ borderTop: innerBorder }}>
                <Loader2 size={16} className="animate-spin" style={{ color: '#5882ff' }} />
                <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Loading page {page}…</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Pagination controls */}
      {result && totalPages > 1 && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Showing rows {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, totalCount)} of {fmtCount(totalCount)}
          </p>
          <div className="flex items-center gap-1">
            <motion.button
              disabled={page <= 1 || loading}
              onClick={() => goToPage(page - 1)}
              className="p-2 rounded-lg disabled:opacity-40"
              style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: 'var(--text-muted)' }}
              whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <ChevronLeft size={14} />
            </motion.button>

            {/* Page number pills */}
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let p: number;
              if (totalPages <= 7) {
                p = i + 1;
              } else if (page <= 4) {
                p = i < 5 ? i + 1 : i === 5 ? -1 : totalPages;
              } else if (page >= totalPages - 3) {
                p = i === 0 ? 1 : i === 1 ? -1 : totalPages - (6 - i);
              } else {
                p = i === 0 ? 1 : i === 1 ? -1 : i === 5 ? -2 : i === 6 ? totalPages : page + (i - 3);
              }
              if (p < 0) return (
                <span key={`ellipsis-${i}`} className="px-1 text-xs" style={{ color: 'var(--text-muted)' }}>…</span>
              );
              return (
                <motion.button key={p}
                  onClick={() => goToPage(p)}
                  disabled={loading}
                  className="w-8 h-8 rounded-lg text-xs font-semibold"
                  style={{
                    background: p === page
                      ? isDark ? 'rgba(88,130,255,0.18)' : 'rgba(88,130,255,0.12)'
                      : isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
                    color: p === page ? '#5882ff' : 'var(--text-muted)',
                    border: p === page ? '1px solid rgba(88,130,255,0.3)' : '1px solid transparent',
                  }}
                  whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
                  {p}
                </motion.button>
              );
            })}

            <motion.button
              disabled={loading || !(result?.has_more ?? page < totalPages)}
              onClick={() => goToPage(page + 1)}
              className="p-2 rounded-lg disabled:opacity-40"
              style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)', color: 'var(--text-muted)' }}
              whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}>
              <ChevronRight size={14} />
            </motion.button>
          </div>
        </div>
      )}
    </motion.div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function ERPViews() {
  const { isDark } = useTheme();
  const [search, setSearch] = useState('');
  const [activeView, setActiveView] = useState<CatalogViewMeta | null>(null);
  const [catalog, setCatalog] = useState<CatalogViewMeta[]>(STATIC_CATALOG.views);
  const [catalogDb, setCatalogDb] = useState(STATIC_CATALOG.database);
  const [catalogLoading, setCatalogLoading] = useState(false);

  const cardBg = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.88)';
  const cardBorder = isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)';
  const innerBg = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)';

  // Try to load live catalog from API
  useEffect(() => {
    setCatalogLoading(true);
    analytics.viewsCatalog()
      .then(res => {
        if (res?.views?.length) {
          setCatalog(res.views);
          setCatalogDb(res.database ?? STATIC_CATALOG.database);
        }
      })
      .catch(() => { /* keep static fallback */ })
      .finally(() => setCatalogLoading(false));
  }, []);

  const filtered = search.trim()
    ? catalog.filter(v =>
        v.short_name.toLowerCase().includes(search.toLowerCase()) ||
        v.purpose.toLowerCase().includes(search.toLowerCase()) ||
        (v.grain ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : catalog;

  const groups = groupViews(filtered);

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      <AnimatePresence mode="wait">
        {activeView ? (
          <motion.div key="browser"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <RowBrowser view={activeView} onBack={() => setActiveView(null)} isDark={isDark} />
          </motion.div>
        ) : (
          <motion.div key="catalog"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="space-y-5">

            {/* ── Header ── */}
            <motion.div variants={item} className="flex items-start justify-between gap-4 flex-wrap">
              <div>
                <h1 className="text-2xl font-bold" style={{
                  background: isDark
                    ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)'
                    : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
                  WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
                }}>ERP Views</h1>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                  Browse all {catalog.length} SQL Server views from {catalogDb}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
                  style={{ background: 'rgba(88,130,255,0.10)', border: '1px solid rgba(88,130,255,0.2)', color: '#5882ff' }}>
                  <Database size={10} />
                  {catalogLoading ? 'Loading…' : `${catalog.length} views`}
                </span>
              </div>
            </motion.div>

            {/* ── Search ── */}
            <motion.div variants={item}>
              <div className="relative">
                <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2"
                  style={{ color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search views by name or purpose…"
                  className="w-full pl-9 pr-9 py-2.5 rounded-xl text-sm outline-none"
                  style={{
                    background: cardBg,
                    border: cardBorder,
                    color: 'var(--text-primary)',
                    backdropFilter: 'blur(16px)',
                  }}
                />
                {search && (
                  <button onClick={() => setSearch('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded"
                    style={{ color: 'var(--text-muted)' }}>
                    <X size={13} />
                  </button>
                )}
              </div>
            </motion.div>

            {/* ── Summary stat row ── */}
            <motion.div variants={item}
              className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Total Views', value: catalog.length, icon: Layers, color: '#5882ff' },
                { label: 'Filtered', value: filtered.length, icon: Search, color: '#00b8e6' },
                { label: 'Categories', value: groups.length, icon: Database, color: '#00e67a' },
                { label: 'Database', value: catalogDb.slice(0, 12), icon: Table2, color: '#ffb800' },
              ].map(s => {
                const Icon = s.icon;
                return (
                  <div key={s.label} className="rounded-2xl p-4 flex items-center gap-3"
                    style={{ background: cardBg, border: cardBorder, backdropFilter: 'blur(16px)' }}>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                      style={{ background: `${s.color}18`, border: `1px solid ${s.color}30` }}>
                      <Icon size={15} style={{ color: s.color }} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-bold truncate" style={{ color: s.color }}>
                        {typeof s.value === 'number' ? fmtCount(s.value) : s.value}
                      </p>
                      <p className="text-2xs" style={{ color: 'var(--text-muted)' }}>{s.label}</p>
                    </div>
                  </div>
                );
              })}
            </motion.div>

            {/* ── View cards by group ── */}
            {groups.length === 0 ? (
              <motion.div variants={item}
                className="rounded-2xl p-12 flex flex-col items-center justify-center gap-3"
                style={{ background: cardBg, border: cardBorder }}>
                <Search size={28} style={{ color: 'var(--text-muted)' }} />
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  No views match "{search}"
                </p>
                <button onClick={() => setSearch('')}
                  className="text-xs font-semibold" style={{ color: '#5882ff' }}>
                  Clear search
                </button>
              </motion.div>
            ) : (
              groups.map(group => (
                <motion.div key={group.label} variants={item} className="space-y-3">
                  <div className="flex items-center gap-2">
                    <h2 className="text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-muted)' }}>
                      {group.label}
                    </h2>
                    <span className="text-2xs px-2 py-0.5 rounded-full"
                      style={{ background: innerBg, color: 'var(--text-muted)' }}>
                      {group.views.length}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {group.views.map(view => (
                      <ViewCard key={view.key} view={view} onOpen={setActiveView} isDark={isDark} />
                    ))}
                  </div>
                </motion.div>
              ))
            )}

          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
