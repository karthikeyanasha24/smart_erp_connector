/** Last-year (YoY) display helpers — never show flat zero while LY is still loading. */

import { fmtLakhs, fmtCount } from './format';

export type LyPoint = { prior?: number | null };

/** True when at least one trend point has real prior-year revenue (not placeholder 0). */
export function hasLyTrendData(points: LyPoint[] | undefined | null): boolean {
  if (!points?.length) return false;
  return points.some((p) => (p.prior ?? 0) > 0);
}

/** Sub-label for KPI cards, e.g. "LY: Loading…" */
export function formatLySub(lySales: number | null | undefined, lyReady: boolean): string {
  if (!lyReady) return 'LY: Loading…';
  if (lySales == null) return 'LY: —';
  return `LY: ${fmtLakhs(lySales)}`;
}

/** Growth % for KPI cards — null while LY loading (shows pending state in UI). */
export function lyGrowthReady(
  lyReady: boolean,
  growth: number | null | undefined,
): number | null {
  if (!lyReady) return null;
  return growth ?? null;
}

/** Chart subtitle when YoY comparison is pending. */
export function lyChartSubtitle(mtdLabel: string, lyReady: boolean): string {
  if (lyReady) return `Each day in ${mtdLabel} vs same day last year`;
  return `Each day in ${mtdLabel} · last year loading…`;
}

/** Bundle includes YoY trend points with real prior-year values. */
export function bundleTrendHasLy(core: AnalyticsBundleResponse | null | undefined): boolean {
  return (core?.trend ?? []).some((t) => (t.prior ?? 0) > 0);
}

export function bundleHasCustomerCount(core: AnalyticsBundleResponse | null | undefined): boolean {
  return typeof core?.customer_count === 'number';
}

/** Customer KPI label — never show fake zero while count is still loading. */
export function formatCustomerKpi(
  customers: number | null | undefined,
  opts: { loading?: boolean; hasSalesActivity?: boolean },
): string {
  if (opts.loading) return 'Loading…';
  if (customers == null) return '—';
  if (customers === 0 && opts.hasSalesActivity) return 'Loading…';
  return fmtCount(customers);
}
