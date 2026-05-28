import type { Page } from '../types';

export const ROUTES: Record<Page, string> = {
  dashboard: '/dashboard',
  analytics: '/analytics',
  'ai-query': '/ai-query',
  transactions: '/transactions',
  reports: '/reports',
  branch: '/branch',
  product: '/product',
  data: '/data',
  insights: '/insights',
  settings: '/settings',
};

export const PAGE_FROM_PATH: Record<string, Page> = Object.fromEntries(
  Object.entries(ROUTES).map(([page, path]) => [path, page as Page]),
) as Record<string, Page>;

export function pathToPage(pathname: string): Page {
  const p = pathname.replace(/\/$/, '') || '/dashboard';
  return PAGE_FROM_PATH[p] ?? 'dashboard';
}
