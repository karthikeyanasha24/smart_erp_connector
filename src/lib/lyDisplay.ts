/** Last-year (YoY) display helpers — never show flat zero while LY is still loading. */

import { fmtLakhs } from './format';

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
