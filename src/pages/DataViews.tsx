import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Database,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Download,
  Loader2,
  Wifi,
  WifiOff,
  Table2,
  Layers,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { analytics, type CatalogViewMeta, type ViewQueryResponse } from '../lib/api';
import { fmtCount } from '../lib/format';

const stagger = { animate: { transition: { staggerChildren: 0.06 } } };
const item = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 28 } },
};

const PAGE_SIZES = [25, 50, 100, 200] as const;

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
  a.download = `${viewName}-page-${page}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function DataViews() {
  const { isDark } = useTheme();

  const [catalog, setCatalog] = useState<CatalogViewMeta[]>([]);
  const [catalogDb, setCatalogDb] = useState('');
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  const [selectedKey, setSelectedKey] = useState('');
  const [pageSize, setPageSize] = useState<number>(50);
  const [page, setPage] = useState(1);

  const [result, setResult] = useState<ViewQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const cardStyle = {
    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.92)',
    border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
  } as const;

  const thStyle = {
    color: 'var(--text-muted)',
    fontSize: 10,
    fontWeight: 600,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.04em',
  };

  const loadCatalog = useCallback(async () => {
    setCatalogLoading(true);
    setCatalogError(null);
    try {
      const res = await analytics.viewsCatalog();
      setCatalog(res.views ?? []);
      setCatalogDb(res.database ?? '');
      if (!selectedKey && res.views?.length) {
        setSelectedKey(res.views[0].key);
      }
    } catch (e) {
      setCatalog([]);
      setCatalogError(e instanceof Error ? e.message : 'Failed to load view catalog');
    } finally {
      setCatalogLoading(false);
    }
  }, [selectedKey]);

  useEffect(() => {
    void loadCatalog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedMeta = useMemo(
    () => catalog.find((v) => v.key === selectedKey),
    [catalog, selectedKey],
  );

  const runQuery = useCallback(
    async (targetPage: number) => {
      if (!selectedKey) return;
      setLoading(true);
      setLoadError(null);
      try {
        const res = await analytics.viewQuery({
          view: selectedKey,
          page: targetPage,
          page_size: pageSize,
        });
        setResult(res);
        setPage(targetPage);
      } catch (e) {
        setResult(null);
        setLoadError(e instanceof Error ? e.message : 'Failed to load view data');
      } finally {
        setLoading(false);
      }
    },
    [selectedKey, pageSize],
  );

  const handleLoad = () => {
    void runQuery(1);
  };

  const fromApi = result != null && !loadError;

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">
      <motion.div variants={item} className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Database size={18} style={{ color: '#5882ff' }} />
            <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
              Data Explorer
            </h2>
            <span
              className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5 rounded-full"
              style={{
                background: fromApi ? 'rgba(34,197,94,0.12)' : 'rgba(148,163,184,0.12)',
                color: fromApi ? '#4ade80' : 'var(--text-muted)',
              }}
            >
              {fromApi ? <Wifi size={10} /> : <WifiOff size={10} />}
              {fromApi ? 'Live' : 'Idle'}
            </span>
          </div>
          <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
            Browse all {catalog.length || 28} ERP views from the schema catalog. Load a view to paginate through every row.
            {catalogDb ? ` Database: ${catalogDb}.` : ''}
          </p>
        </div>
        <motion.button
          type="button"
          onClick={() => {
            void loadCatalog();
            if (result) void runQuery(page);
          }}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold"
          style={{
            background: isDark ? 'rgba(88,130,255,0.12)' : 'rgba(88,130,255,0.1)',
            color: '#5882ff',
            border: '1px solid rgba(88,130,255,0.25)',
          }}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          <RefreshCw size={14} className={catalogLoading || loading ? 'animate-spin' : ''} />
          Refresh
        </motion.button>
      </motion.div>

      {/* Load panel */}
      <motion.div variants={item} className="rounded-2xl p-5" style={cardStyle}>
        <div className="flex items-center gap-2 mb-4">
          <Table2 size={16} style={{ color: '#5882ff' }} />
          <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Load dataset
          </span>
        </div>

        {catalogError && (
          <p className="text-sm mb-3" style={{ color: '#f87171' }}>{catalogError}</p>
        )}

        <div className="grid gap-4 lg:grid-cols-[1fr_auto_auto] lg:items-end">
          <label className="block">
            <span className="text-2xs font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: 'var(--text-muted)' }}>
              View ({catalog.length} available)
            </span>
            <select
              value={selectedKey}
              onChange={(e) => {
                setSelectedKey(e.target.value);
                setResult(null);
                setPage(1);
              }}
              disabled={catalogLoading}
              className="w-full rounded-xl px-3 py-2.5 text-sm outline-none"
              style={{
                background: isDark ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.9)',
                border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                color: 'var(--text-primary)',
              }}
            >
              {catalog.map((v) => (
                <option key={v.key} value={v.key}>
                  {v.short_name} — {v.purpose.slice(0, 80)}
                  {v.purpose.length > 80 ? '…' : ''}
                </option>
              ))}
            </select>
            {selectedMeta?.note && (
              <p className="text-2xs mt-1.5" style={{ color: '#fb923c' }}>{selectedMeta.note}</p>
            )}
          </label>

          <label className="block lg:w-36">
            <span className="text-2xs font-semibold uppercase tracking-wider mb-1.5 block" style={{ color: 'var(--text-muted)' }}>
              Rows per page
            </span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setResult(null);
                setPage(1);
              }}
              className="w-full rounded-xl px-3 py-2.5 text-sm outline-none"
              style={{
                background: isDark ? 'rgba(0,0,0,0.25)' : 'rgba(255,255,255,0.9)',
                border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                color: 'var(--text-primary)',
              }}
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>{n} rows</option>
              ))}
            </select>
          </label>

          <motion.button
            type="button"
            onClick={handleLoad}
            disabled={!selectedKey || loading}
            className="flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold text-white disabled:opacity-50"
            style={{ background: 'linear-gradient(135deg, #4158D0 0%, #5882ff 100%)' }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Layers size={16} />}
            Load into view
          </motion.button>
        </div>

        {selectedMeta && (
          <p className="text-2xs mt-3" style={{ color: 'var(--text-muted)' }}>
            <span className="font-mono">{selectedMeta.fqn}</span>
            {selectedMeta.grain ? ` · ${selectedMeta.grain}` : ''}
            {selectedMeta.column_count ? ` · ~${selectedMeta.column_count} columns` : ''}
          </p>
        )}
      </motion.div>

      {loadError && (
        <motion.p variants={item} className="text-sm px-1" style={{ color: '#f87171' }}>
          {loadError}
        </motion.p>
      )}

      {/* Summary cards */}
      {result && (
        <motion.div variants={item} className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: 'Total rows', value: fmtCount(result.total_count), sub: result.capped ? `Capped at ${fmtCount(result.hard_cap)}` : undefined },
            { label: 'Columns', value: String(result.columns.length), sub: result.short_name },
            { label: 'Page', value: `${result.page} / ${result.total_pages}`, sub: `${result.page_size} per page · ${result.duration_ms}ms` },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="rounded-2xl p-4"
              style={{
                ...cardStyle,
                background: isDark
                  ? 'linear-gradient(135deg, rgba(88,130,255,0.12) 0%, rgba(139,92,246,0.08) 100%)'
                  : 'linear-gradient(135deg, rgba(88,130,255,0.08) 0%, rgba(255,255,255,0.95) 100%)',
              }}
            >
              <p className="text-2xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                {kpi.label}
              </p>
              <p className="text-2xl font-bold mt-1" style={{ color: 'var(--text-primary)' }}>
                {kpi.value}
              </p>
              {kpi.sub && (
                <p className="text-2xs mt-1 truncate" style={{ color: 'var(--text-tertiary)' }}>{kpi.sub}</p>
              )}
            </div>
          ))}
        </motion.div>
      )}

      {/* Data table */}
      {result && result.columns.length > 0 && (
        <motion.div variants={item} className="rounded-2xl overflow-hidden" style={cardStyle}>
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b" style={{ borderColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}>
            <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
              {fmtCount(result.rows.length)} row(s) on this page — {result.short_name}
            </span>
            <button
              type="button"
              onClick={() => downloadCsv(result.columns, result.rows, result.short_name, result.page)}
              className="flex items-center gap-1.5 text-2xs font-semibold px-3 py-1.5 rounded-lg"
              style={{
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                color: 'var(--text-secondary)',
              }}
            >
              <Download size={12} />
              CSV (this page)
            </button>
          </div>

          <div className="overflow-x-auto max-h-[min(70vh,640px)] overflow-y-auto">
            <table className="w-full text-left border-collapse min-w-max">
              <thead className="sticky top-0 z-10" style={{ background: isDark ? '#0c1228' : '#f8fafc' }}>
                <tr>
                  {result.columns.map((col) => (
                    <th key={col} className="px-3 py-2.5 whitespace-nowrap" style={thStyle}>
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr
                    key={i}
                    style={{
                      background: i % 2 === 0
                        ? 'transparent'
                        : isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
                    }}
                  >
                    {result.columns.map((col) => (
                      <td
                        key={col}
                        className="px-3 py-2 text-xs whitespace-nowrap max-w-[280px] truncate"
                        style={{ color: 'var(--text-secondary)' }}
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

          {/* Pagination */}
          <div
            className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-t"
            style={{ borderColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' }}
          >
            <span className="text-2xs" style={{ color: 'var(--text-muted)' }}>
              Showing {(result.page - 1) * result.page_size + 1}–
              {(result.page - 1) * result.page_size + result.rows.length} of {fmtCount(result.total_count)}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={result.page <= 1 || loading}
                onClick={() => void runQuery(result.page - 1)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-40"
                style={{
                  background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                  color: 'var(--text-primary)',
                }}
              >
                <ChevronLeft size={14} />
                Previous
              </button>
              <span className="text-xs font-medium px-2" style={{ color: 'var(--text-secondary)' }}>
                Page {result.page} / {result.total_pages}
              </span>
              <button
                type="button"
                disabled={result.page >= result.total_pages || loading}
                onClick={() => void runQuery(result.page + 1)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-40"
                style={{
                  background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
                  color: 'var(--text-primary)',
                }}
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        </motion.div>
      )}

      {result && result.columns.length === 0 && result.rows.length === 0 && (
        <motion.p variants={item} className="text-sm text-center py-8" style={{ color: 'var(--text-muted)' }}>
          View loaded but returned no rows.
        </motion.p>
      )}
    </motion.div>
  );
}
