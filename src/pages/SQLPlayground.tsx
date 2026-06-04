/**
 * SQL Playground — write and run custom SQL against the ERP database.
 * Results shown as: data table (paginated) + auto-generated bar chart.
 */

import { useState, useCallback, useMemo, useRef } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, LabelList,
} from 'recharts';
import { Play, Copy, Trash2, Download, ChevronLeft, ChevronRight, Terminal, Table2, BarChart2 } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { analytics } from '../lib/api';

// ── Colour palette for chart bars ────────────────────────────────────────────
const COLOURS = [
  '#5882ff','#00e67a','#ff6b6b','#ffc107','#26C6DA',
  '#ab47bc','#ff7043','#66bb6a','#42a5f5','#ef5350',
];

// ── Starter templates ─────────────────────────────────────────────────────────
const TEMPLATES = [
  {
    label: 'Top branches by MTD sales',
    sql: `SELECT TOP 10
    [BranchAlias]          AS Branch,
    SUM([SalesNetAmount])  AS Revenue,
    COUNT(DISTINCT [CashmemoNo]) AS Bills
FROM [dbo].[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] WITH (NOLOCK)
WHERE [CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
  AND [CashmemoDt] <  DATEADD(month, 1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1))
GROUP BY [BranchAlias]
ORDER BY Revenue DESC`,
  },
  {
    label: 'Category-wise QTD sales',
    sql: `SELECT TOP 20
    [CategoryShortName]    AS Category,
    SUM([SalesNetAmount])  AS Revenue,
    SUM([SalesQuantity])   AS Qty
FROM [dbo].[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] WITH (NOLOCK)
WHERE [CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), ((MONTH(GETDATE())-1)/3)*3+1, 1)
  AND [CashmemoDt] <  CAST(GETDATE() AS DATE)
GROUP BY [CategoryShortName]
ORDER BY Revenue DESC`,
  },
  {
    label: 'Daily sales last 30 days',
    sql: `SELECT
    CAST([CashmemoDt] AS DATE)         AS Date,
    SUM([SalesNetAmount])              AS Revenue,
    COUNT(DISTINCT [CashmemoNo])       AS Bills
FROM [dbo].[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] WITH (NOLOCK)
WHERE [CashmemoDt] >= CAST(DATEADD(day, -30, GETDATE()) AS DATE)
GROUP BY CAST([CashmemoDt] AS DATE)
ORDER BY Date ASC`,
  },
  {
    label: 'Top 10 salespersons MTD',
    sql: `SELECT TOP 10
    [SalesPersonName]      AS Salesperson,
    SUM([SalesNetAmount])  AS Revenue,
    COUNT(DISTINCT [CashmemoNo]) AS Bills
FROM [dbo].[VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID] WITH (NOLOCK)
WHERE [CashmemoDt] >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
GROUP BY [SalesPersonName]
ORDER BY Revenue DESC`,
  },
];

const PAGE_SIZE = 50;

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtNum(v: string | number | null): string {
  if (v === null || v === undefined || v === '') return '—';
  const n = Number(v);
  if (isNaN(n)) return String(v);
  if (Math.abs(n) >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  if (Math.abs(n) >= 1_000) return n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function isNumericCol(rows: (string | number | null)[][], colIdx: number): boolean {
  const sample = rows.slice(0, 20).map(r => r[colIdx]).filter(v => v !== null);
  return sample.length > 0 && sample.every(v => !isNaN(Number(v)));
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function SQLPlayground() {
  const { isDark } = useTheme();

  const [sql, setSql] = useState(TEMPLATES[0].sql);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    columns: string[];
    rows: (string | number | null)[][];
    row_count: number;
    duration_ms: number;
  } | null>(null);
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<'table' | 'chart'>('table');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const card = {
    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.92)',
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`,
    borderRadius: 16,
  };

  // ── Run SQL ────────────────────────────────────────────────────────────────
  const runSql = useCallback(async () => {
    if (!sql.trim() || running) return;
    setRunning(true);
    setError(null);
    setResult(null);
    setPage(1);
    try {
      const res = await analytics.runSql(sql.trim(), 500);
      setResult(res);
      setTab('table');
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setRunning(false);
    }
  }, [sql, running]);

  // ── Keyboard shortcut: Ctrl+Enter ─────────────────────────────────────────
  const onKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runSql();
    }
  }, [runSql]);

  // ── Chart data: first text col = label, first numeric col = value ─────────
  const chartData = useMemo(() => {
    if (!result || result.rows.length === 0) return null;
    const { columns, rows } = result;
    const labelIdx = columns.findIndex((_, i) => !isNumericCol(rows, i));
    const valueIdx = columns.findIndex((_, i) => isNumericCol(rows, i));
    if (labelIdx === -1 || valueIdx === -1) return null;
    return rows.slice(0, 30).map(r => ({
      name: String(r[labelIdx] ?? ''),
      value: Number(r[valueIdx] ?? 0),
    }));
  }, [result]);

  // ── Paginated table rows ───────────────────────────────────────────────────
  const totalPages = result ? Math.ceil(result.rows.length / PAGE_SIZE) : 0;
  const pageRows = result ? result.rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE) : [];

  // ── Download CSV ──────────────────────────────────────────────────────────
  const downloadCsv = () => {
    if (!result) return;
    const header = result.columns.join(',');
    const body = result.rows.map(r =>
      r.map(v => (v === null ? '' : typeof v === 'string' && v.includes(',') ? `"${v}"` : String(v))).join(',')
    ).join('\n');
    const blob = new Blob([header + '\n' + body], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'query_results.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const muted = isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.45)';
  const text  = isDark ? '#fff' : '#111';

  return (
    <div className="space-y-4 pb-8">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{ ...card, padding: '20px 24px' }}>
        <div className="flex items-center gap-3 mb-1">
          <Terminal size={20} style={{ color: '#5882ff' }} />
          <h1 className="text-xl font-bold" style={{ color: text }}>SQL Playground</h1>
        </div>
        <p className="text-sm" style={{ color: muted }}>
          Write and run custom SQL against your ERP database · Read-only · Max 500 rows
        </p>
      </div>

      {/* ── Templates ──────────────────────────────────────────────────────── */}
      <div className="flex gap-2 flex-wrap">
        {TEMPLATES.map(t => (
          <button key={t.label} onClick={() => { setSql(t.sql); setResult(null); setError(null); }}
            className="text-xs px-3 py-1.5 rounded-lg transition-colors"
            style={{
              background: isDark ? 'rgba(88,130,255,0.1)' : 'rgba(88,130,255,0.08)',
              border: '1px solid rgba(88,130,255,0.25)',
              color: '#5882ff', cursor: 'pointer',
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── SQL Editor ─────────────────────────────────────────────────────── */}
      <div style={card}>
        <div className="flex items-center justify-between px-4 py-2.5"
          style={{ borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}` }}>
          <span className="text-xs font-semibold" style={{ color: muted }}>SQL EDITOR · Ctrl+Enter to run</span>
          <div className="flex gap-2">
            <button onClick={() => { setSql(''); setResult(null); setError(null); textareaRef.current?.focus(); }}
              title="Clear" className="p-1.5 rounded-lg hover:opacity-70" style={{ color: muted }}>
              <Trash2 size={14} />
            </button>
            <button onClick={() => navigator.clipboard.writeText(sql)}
              title="Copy SQL" className="p-1.5 rounded-lg hover:opacity-70" style={{ color: muted }}>
              <Copy size={14} />
            </button>
          </div>
        </div>
        <textarea
          ref={textareaRef}
          value={sql}
          onChange={e => setSql(e.target.value)}
          onKeyDown={onKeyDown}
          spellCheck={false}
          rows={10}
          className="w-full resize-y font-mono text-sm p-4 outline-none"
          style={{
            background: 'transparent',
            color: text,
            lineHeight: 1.65,
            minHeight: 200,
            maxHeight: 480,
          }}
          placeholder="SELECT TOP 20 * FROM dbo.VW_MB_POWERBI_SLS_DATA_WITHOUT_ITEMID WITH (NOLOCK) WHERE ..."
        />
        <div className="px-4 pb-3 flex items-center gap-3">
          <button onClick={runSql} disabled={running || !sql.trim()}
            className="flex items-center gap-2 px-5 py-2 rounded-xl font-semibold text-sm transition-all"
            style={{
              background: running ? 'rgba(88,130,255,0.4)' : '#5882ff',
              color: '#fff', cursor: running ? 'not-allowed' : 'pointer',
              boxShadow: running ? 'none' : '0 4px 16px rgba(88,130,255,0.35)',
            }}>
            <Play size={14} className={running ? 'animate-pulse' : ''} />
            {running ? 'Running…' : 'Run Query'}
          </button>
          {result && (
            <span className="text-xs" style={{ color: muted }}>
              {result.row_count} rows · {result.duration_ms}ms
            </span>
          )}
        </div>
      </div>

      {/* ── Error ──────────────────────────────────────────────────────────── */}
      {error && (
        <div className="rounded-xl px-4 py-3 text-sm" style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171',
        }}>
          <span className="font-semibold">Error: </span>{error}
        </div>
      )}

      {/* ── Results ────────────────────────────────────────────────────────── */}
      {result && result.row_count > 0 && (
        <div style={card}>
          {/* Tab bar */}
          <div className="flex items-center justify-between px-4 pt-3 pb-2"
            style={{ borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}` }}>
            <div className="flex gap-1">
              {(['table', 'chart'] as const).map(t => (
                <button key={t} onClick={() => setTab(t)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
                  style={{
                    background: tab === t ? (isDark ? 'rgba(88,130,255,0.2)' : 'rgba(88,130,255,0.12)') : 'transparent',
                    color: tab === t ? '#5882ff' : muted,
                  }}>
                  {t === 'table' ? <Table2 size={12} /> : <BarChart2 size={12} />}
                  {t === 'table' ? 'Table' : 'Chart'}
                </button>
              ))}
            </div>
            <button onClick={downloadCsv}
              className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg"
              style={{ color: muted, background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)', cursor: 'pointer' }}>
              <Download size={12} /> CSV
            </button>
          </div>

          {/* TABLE view */}
          {tab === 'table' && (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}` }}>
                      <th className="px-3 py-2 text-left font-semibold w-10" style={{ color: muted }}>#</th>
                      {result.columns.map(col => (
                        <th key={col} className="px-3 py-2 text-left font-semibold whitespace-nowrap"
                          style={{ color: muted }}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pageRows.map((row, ri) => (
                      <tr key={ri}
                        style={{ borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'}` }}
                        className="hover:bg-white/5 transition-colors">
                        <td className="px-3 py-2" style={{ color: muted }}>
                          {(page - 1) * PAGE_SIZE + ri + 1}
                        </td>
                        {row.map((cell, ci) => (
                          <td key={ci} className="px-3 py-2 whitespace-nowrap"
                            style={{
                              color: text,
                              textAlign: isNumericCol(result.rows, ci) ? 'right' : 'left',
                            }}>
                            {isNumericCol(result.rows, ci) ? fmtNum(cell) : String(cell ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-2.5"
                  style={{ borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}` }}>
                  <span className="text-xs" style={{ color: muted }}>
                    {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, result.row_count)} of {result.row_count}
                  </span>
                  <div className="flex gap-1">
                    <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
                      className="p-1.5 rounded-lg disabled:opacity-30" style={{ color: muted }}>
                      <ChevronLeft size={14} />
                    </button>
                    <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
                      className="p-1.5 rounded-lg disabled:opacity-30" style={{ color: muted }}>
                      <ChevronRight size={14} />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* CHART view */}
          {tab === 'chart' && chartData && (
            <div className="p-4">
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={chartData} margin={{ top: 20, right: 8, left: 0, bottom: chartData.length > 10 ? 60 : 8 }}>
                  <CartesianGrid strokeDasharray="3 3"
                    stroke={isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)'} vertical={false} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false}
                    tick={{ fontSize: 10, fill: muted }}
                    angle={chartData.length > 8 ? -40 : 0}
                    textAnchor={chartData.length > 8 ? 'end' : 'middle'}
                    interval={0} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: muted }}
                    tickFormatter={(v: number) =>
                      v >= 1_00_000 ? `${(v / 1_00_000).toFixed(1)}L` : v.toLocaleString('en-IN')} width={52} />
                  <Tooltip
                    contentStyle={{
                      background: isDark ? 'rgba(5,9,24,0.96)' : '#fff',
                      border: '1px solid rgba(88,130,255,0.2)',
                      borderRadius: 10, fontSize: 11,
                    }}
                    formatter={(v: number) => [fmtNum(v), result.columns.find((_, i) => isNumericCol(result.rows, i)) ?? 'Value']}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]} maxBarSize={48}>
                    {chartData.map((_, i) => <Cell key={i} fill={COLOURS[i % COLOURS.length]} />)}
                    {chartData.length <= 20 && (
                      <LabelList dataKey="value" position="top"
                        formatter={(v: number) => v >= 1_00_000 ? `${(v / 1_00_000).toFixed(1)}L` : v.toLocaleString('en-IN')}
                        style={{ fontSize: 9, fill: muted, fontWeight: 600 }} />
                    )}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {tab === 'chart' && !chartData && (
            <div className="p-8 text-center text-sm" style={{ color: muted }}>
              Chart requires at least one text column (label) and one numeric column (value).
            </div>
          )}
        </div>
      )}

      {result && result.row_count === 0 && (
        <div className="rounded-xl px-4 py-6 text-center text-sm" style={card}>
          <span style={{ color: muted }}>Query ran successfully — 0 rows returned</span>
        </div>
      )}
    </div>
  );
}
