/** Indian Lakhs formatting — all currency values in ₹X.XX L */

const LAKH = 100_000;

export function toLakhs(amount: number): number {
  if (!Number.isFinite(amount)) return 0;
  return amount / LAKH;
}

/** Display: ₹12.45 L */
export function fmtLakhs(amount: number, decimals = 2): string {
  return `₹${toLakhs(amount).toFixed(decimals)} L`;
}

/** Compact count (bills, units, customers — never use Lakhs "L"; that is for ₹ only) */
export function fmtCount(n: number): string {
  if (!Number.isFinite(n)) return '—';
  if (n >= 10_000_000) return `${(n / 10_000_000).toFixed(2)} Cr`;
  if (n >= 100_000) return `${(n / 1000).toFixed(1)}K`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(Math.round(n));
}

/** Chart Y-axis tick */
export function fmtLakhsAxis(v: number): string {
  return `${toLakhs(v).toFixed(1)}L`;
}

/** Parse API date / ISO → readable label */
export function formatChartLabel(raw: string, granularity: 'day' | 'month'): string {
  if (!raw) return '';
  const s = raw.slice(0, 10);
  if (/^\d{4}-\d{2}$/.test(raw.slice(0, 7)) && granularity === 'month') {
    const [y, m] = raw.slice(0, 7).split('-');
    const d = new Date(Number(y), Number(m) - 1, 1);
    return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
  }
  const d = new Date(s.includes('T') ? raw : `${s}T00:00:00`);
  if (Number.isNaN(d.getTime())) return raw.slice(0, 10);
  return granularity === 'month'
    ? d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
    : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}

export function growthPct(current: number, prior: number): number | null {
  if (!prior) return null;
  return Math.round(((current - prior) / prior) * 10000) / 100;
}

/** Plain Indian-locale rupees — for avg bill / ticket values (not Lakhs scale) */
export function fmtRupees(n: number): string {
  if (!Number.isFinite(n) || n === 0) return '₹0';
  return `₹${Math.round(n).toLocaleString('en-IN')}`;
}

/** Smart revenue display: Lakhs for large, Rupees for small */
export function fmtSmart(n: number): string {
  if (!Number.isFinite(n)) return '₹0';
  if (n >= LAKH) return fmtLakhs(n);
  return fmtRupees(n);
}
