/**
 * Map NLQ API records → chart / KPI cards / table (no mock data).
 */

export interface ChartPoint {
  label: string;
  value: number;
}

export interface KPICard {
  label: string;
  value: string;
  raw?: number;
}

export interface ResultTable {
  columns: string[];
  rows: string[][];
}

export interface NLQVisualization {
  chartType: 'bar' | 'area' | 'line' | 'pie' | 'none';
  chartData: ChartPoint[];
  valueKey: string;
  labelKey: string;
  kpiCards: KPICard[];
  table?: ResultTable;
}

const NUMERIC_HINTS = [
  'sales', 'revenue', 'amount', 'total', 'growth', 'margin', 'qty', 'quantity',
  'count', 'customers', 'invoices', 'ats', 'percent', 'pct', 'contribution',
  'bills', 'value', 'cost', 'profit', 'stock', 'turnover', 'rate',
];

const LABEL_HINTS = [
  'branch', 'store', 'category', 'department', 'supplier', 'product', 'article',
  'color', 'size', 'fabric', 'concept', 'month', 'label', 'name', 'region',
  'city', 'period', 'date', 'day', 'hour', 'season', 'group', 'segment',
];

const SKIP_COLS = new Set(['id', 'rownum', 'rn']);

function toNum(v: unknown): number | null {
  if (v == null || v === '') return null;
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  const n = Number(String(v).replace(/,/g, '').replace(/%/g, '').trim());
  return Number.isFinite(n) ? n : null;
}

function isNumericColumn(records: Record<string, unknown>[], col: string): boolean {
  let hits = 0;
  for (const row of records.slice(0, 12)) {
    if (toNum(row[col]) != null) hits += 1;
  }
  return hits > 0;
}

function scoreNumeric(col: string): number {
  const l = col.toLowerCase();
  if (SKIP_COLS.has(l)) return -100;
  let s = 0;
  for (const h of NUMERIC_HINTS) {
    if (l.includes(h)) s += 3;
  }
  if (l.endsWith('id')) s -= 5;
  return s;
}

function scoreLabel(col: string): number {
  const l = col.toLowerCase();
  if (SKIP_COLS.has(l)) return -100;
  let s = 0;
  for (const h of LABEL_HINTS) {
    if (l.includes(h)) s += 3;
  }
  if (l.includes('date') || l.includes('month')) s += 2;
  if (l.endsWith('id')) s -= 4;
  return s;
}

function pickColumns(records: Record<string, unknown>[]): { valueKey: string; labelKey: string } {
  const cols = Object.keys(records[0] ?? {});
  const numericCols = cols.filter(c => isNumericColumn(records, c));
  const labelCandidates = cols.filter(c => !numericCols.includes(c) || scoreLabel(c) > scoreNumeric(c));

  const valueKey =
    [...numericCols].sort((a, b) => scoreNumeric(b) - scoreNumeric(a))[0] ??
    cols.find(c => isNumericColumn(records, c)) ??
  cols[0] ??
    'value';

  const labelKey =
    [...labelCandidates].sort((a, b) => scoreLabel(b) - scoreLabel(a))[0] ??
    cols.find(c => c !== valueKey) ??
    cols[0] ??
    valueKey;

  return { valueKey, labelKey };
}

function formatCompact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 10_000) return `${(n / 1_000).toFixed(1)}K`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  if (Number.isInteger(n)) return n.toLocaleString('en-IN');
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
}

function formatCell(v: unknown): string {
  if (v == null) return '—';
  const n = toNum(v);
  if (n != null) return formatCompact(n);
  const s = String(v);
  return s.length > 28 ? `${s.slice(0, 26)}…` : s;
}

function isDateLikeLabel(label: string): boolean {
  return /^\d{4}-\d{2}-\d{2}/.test(label) || /jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec/i.test(label);
}

export function buildNLQVisualization(
  records: Record<string, unknown>[],
  chartTypeHint?: string,
): NLQVisualization {
  if (!records.length) {
    return { chartType: 'none', chartData: [], valueKey: '', labelKey: '', kpiCards: [] };
  }

  const { valueKey, labelKey } = pickColumns(records);
  const rowCount = records.length;

  // Single scalar row → KPI cards from all numeric columns
  if (rowCount === 1) {
    const cards: KPICard[] = [];
    for (const col of Object.keys(records[0])) {
      const n = toNum(records[0][col]);
      if (n == null) continue;
      cards.push({
        label: col.replace(/([A-Z])/g, ' $1').trim(),
        value: formatCompact(n),
        raw: n,
      });
    }
    return {
      chartType: 'none',
      chartData: [],
      valueKey,
      labelKey,
      kpiCards: cards.slice(0, 8),
    };
  }

  const chartData: ChartPoint[] = records.slice(0, 40).map((r, i) => {
    const labelRaw = r[labelKey] ?? r[Object.keys(r).find(k => k !== valueKey) ?? ''] ?? `#${i + 1}`;
    return {
      label: String(labelRaw).slice(0, 24),
      value: toNum(r[valueKey]) ?? 0,
    };
  });

  const firstLabel = chartData[0]?.label ?? '';
  const hint = (chartTypeHint ?? '').toLowerCase();

  let chartType: NLQVisualization['chartType'] = 'bar';
  if (hint === 'line' || hint === 'area') {
    chartType = hint === 'line' ? 'line' : 'area';
  } else if (hint === 'pie' || hint === 'donut') {
    chartType = 'pie';
  } else if (isDateLikeLabel(firstLabel) || /trend|daily|month/i.test(labelKey)) {
    chartType = rowCount > 14 ? 'area' : 'line';
  } else if (rowCount <= 6) {
    chartType = 'pie';
  } else if (rowCount > 20) {
    chartType = 'area';
  }

  const table: ResultTable = {
    columns: Object.keys(records[0]).slice(0, 8),
    rows: records.slice(0, 12).map(r =>
      Object.keys(records[0])
        .slice(0, 8)
        .map(c => formatCell(r[c])),
    ),
  };

  return {
    chartType,
    chartData,
    valueKey,
    labelKey,
    kpiCards: [],
    table: rowCount > 1 ? table : undefined,
  };
}

export function formatChartValue(n: number): string {
  return formatCompact(n);
}
