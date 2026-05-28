import raw from './view_catalog.json';
import type { CatalogViewMeta } from '../lib/api';

type RawView = {
  fqn?: string;
  purpose?: string;
  grain?: string;
  column_count?: number;
  date_col?: string;
  amount_col?: string;
  branch_col?: string;
  note?: string;
  catalog_no?: number;
};

/** Static fallback — 28 ERP views (same as backend/data/view_catalog.json). */
export function getStaticViewCatalog(): {
  database: string;
  views: CatalogViewMeta[];
} {
  const viewsObj = (raw as { views?: Record<string, RawView> }).views ?? {};
  const database = (raw as { database?: string }).database ?? 'zRetailHQ0';
  const views: CatalogViewMeta[] = Object.entries(viewsObj)
    .map(([key, meta]) => {
      const fqn = String(meta.fqn ?? '');
      return {
        key,
        fqn,
        short_name: fqn.split('.').pop() ?? key,
        catalog_no: meta.catalog_no,
        purpose: meta.purpose ?? '',
        grain: meta.grain,
        column_count: meta.column_count,
        date_col: meta.date_col,
        amount_col: meta.amount_col,
        branch_col: meta.branch_col,
        note: meta.note,
      };
    })
    .sort((a, b) => (a.catalog_no ?? 999) - (b.catalog_no ?? 999));
  return { database, views };
}
