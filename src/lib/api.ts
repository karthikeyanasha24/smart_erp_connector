/**
 * SmarterPConnector — API Client
 * Dev: /api/* proxied to localhost:3000 (see vite.config.ts).
 * Prod: set VITE_API_URL to your Render backend (no /api prefix).
 */

const BASE = import.meta.env.VITE_API_URL ?? '/api';

// ── Auth token storage ────────────────────────────────────────────────────────
let _token: string | null = null;

export function setAuthToken(t: string) { _token = t; }
export function getAuthToken() { return _token ?? localStorage.getItem('smarterp_token'); }
export function clearAuthToken() { _token = null; localStorage.removeItem('smarterp_token'); }

// ── Base fetch ────────────────────────────────────────────────────────────────
async function apiFetch<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const token = getAuthToken();
  const timeoutMs = init?.timeoutMs ?? (path.includes('/analytics/') ? 600_000 : 60_000);
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(new DOMException(`Request timed out after ${Math.round(timeoutMs / 1000)}s`, 'TimeoutError')),
    timeoutMs,
  );
  const { timeoutMs: _t, ...rest } = init ?? {};

  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    signal: controller.signal,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...rest?.headers,
    },
  }).finally(() => clearTimeout(timer));
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const detail = err.detail;
    let message: string;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((d: { msg?: string }) => d.msg ?? JSON.stringify(d)).join('; ');
    } else {
      message = `HTTP ${res.status}`;
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

// ── In-flight GET deduplication ───────────────────────────────────────────────
// Prevents the same URL from being fetched concurrently multiple times.
// When useDashboardPage, fetchAndApplySnapshot, and prefetchAnalyticsShell all
// fire analytics.kpis('mtd') simultaneously, only ONE HTTP request goes out.
// The promise is shared; all callers get the same resolved value.
// The entry is deleted as soon as the request settles, so the next explicit
// re-fetch (e.g. Refresh button) goes through normally.
const _getInflight = new Map<string, Promise<unknown>>();

function apiFetchDeduped<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  // Only deduplicate GET requests (no body, idempotent).
  const method = (init?.method ?? 'GET').toUpperCase();
  if (method !== 'GET') return apiFetch<T>(path, init);

  const existing = _getInflight.get(path) as Promise<T> | undefined;
  if (existing) return existing;

  const p = apiFetch<T>(path, init).finally(() => _getInflight.delete(path));
  _getInflight.set(path, p as Promise<unknown>);
  return p;
}

// ── Types ─────────────────────────────────────────────────────────────────────
export interface KPIValue {
  value: number | null;
  prior: number | null;
  growth: number | null;
  period: string;
}

export interface KPISimple {
  value: number | null;
  period: string;
}

export interface KPIsResponse {
  success: boolean;
  period: string;
  revenue: KPIValue;
  transactions: KPIValue;
  avg_order_value: KPIValue;
  quantity?: KPIValue;
  customers: KPIValue;
  // PowerBI-equivalent extras: distinct buyers, suppliers, unique invoice count
  distinct_clients?:   KPISimple;
  distinct_suppliers?: KPISimple;
  unique_invoices?:    KPISimple;
}

export interface TrendPoint {
  date: string;
  label?: string;
  revenue: number;
  transactions: number;
  quantity?: number;
  /** Same-day / same-period last year revenue (YoY). */
  prior?: number;
}

export interface AnalyticsBundleResponse {
  success: boolean;
  period: string;
  branches: BranchPoint[];
  trend: TrendPoint[];
  categories: CategoryPoint[];
  departments?: DeptPoint[];
  kpis?: KPIsResponse;
  customer_count?: number | null;
  timings_ms?: Record<string, number>;
  errors?: Record<string, string>;
}

export interface DashboardPageResponse {
  success: boolean;
  mtd: AnalyticsBundleResponse;
  today: AnalyticsBundleResponse;
}

export interface CategoryPoint {
  category: string;
  revenue: number;
  transactions: number;
  percentage: number;
}

export interface BranchPoint {
  branch: string;
  revenue: number;
  transactions: number;
}

export interface DeptPoint {
  department: string;
  revenue: number;
  transactions: number;
}

export interface SalespersonPoint {
  name: string;
  branch: string;
  revenue: number;
  transactions: number;
}

export interface TransactionRecord {
  id: string;
  date: string;
  branch: string;
  category: string;
  department: string;
  amount: number;
  salesperson: string;
  /** Line-level fields (aligned with test/list_transactions_db.py extended). */
  xn_id?: string | null;
  xn_no?: string | null;
  itemcode?: string | null;
  quantity?: number | null;
  status: 'completed' | 'pending' | 'failed';
}

export interface TransactionsResponse {
  success: boolean;
  transactions: TransactionRecord[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  period: string;
  period_label: string;
}

export interface TransactionSummary {
  success: boolean;
  total_revenue: number;
  total_transactions: number;
  avg_ticket: number;
  success_rate: number;
  period: string;
  period_label: string;
}

/** Product master row — mirrors VW_MB_POWERBI_PRODUCT_MASTER minimal columns. */
export interface ProductMasterRow {
  ItemId?: string | null;
  Itemcode?: string | null;
  DepartmentShortName?: string | null;
  CategoryShortName?: string | null;
  ArticleNo?: string | null;
  SupplierAlias?: string | null;
  SupplierName?: string | null;
  ItemMRP?: number | null;
  PurchasePrice?: number | null;
}

export interface CatalogViewMeta {
  key: string;
  fqn: string;
  short_name: string;
  catalog_no?: number;
  purpose: string;
  grain?: string;
  column_count?: number;
  date_col?: string;
  amount_col?: string;
  branch_col?: string;
  note?: string;
}

export interface ViewsCatalogResponse {
  success: boolean;
  database: string;
  view_count: number;
  views: CatalogViewMeta[];
  categories: Record<string, string[]>;
}

export interface ViewQueryResponse {
  success: boolean;
  view_key: string;
  fqn: string;
  short_name: string;
  purpose: string;
  page: number;
  page_size: number;
  total_count: number;
  total_raw: number | null;
  total_pages: number;
  capped: boolean;
  hard_cap: number;
  columns: string[];
  rows: Record<string, unknown>[];
  duration_ms: number;
  /** True when COUNT(*) was skipped for speed (dimension views). */
  count_skipped?: boolean;
  /** True when another page of rows may exist. */
  has_more?: boolean;
}

export interface ProductCatalogResponse {
  success: boolean;
  total_count: number;
  distinct_departments: number;
  distinct_categories: number;
  distinct_suppliers: number;
  offset: number;
  limit: number;
  products: ProductMasterRow[];
}

export interface TopProductRow {
  item_id: string;
  label: string;
  revenue: number;
  quantity: number;
  growth_pct: number | null;
  share_pct: number;
}

export interface TopProductsResponse {
  success: boolean;
  period: string;
  products: TopProductRow[];
}

export interface HeatmapPoint {
  hour: number;
  day: string;
  day_num: number;
  revenue: number;
  transactions: number;
}

export interface NLQRequest {
  query: string;
  conversation_id?: string;
  top_n?: number;
  provider?: 'claude' | 'openai';
}

export interface NLQResponse {
  success: boolean;
  query: string;
  sql: string;
  records: Record<string, unknown>[];
  record_count: number;
  intent: Record<string, unknown>;
  chart_type: string;
  period: string;
  period_label: string;
  description: string;
  summary: string | null;
  insights: Record<string, unknown>[];
  conversation_id: string;
  duration_ms: number;
  from_template: boolean;
  corrected: boolean;
  warnings: string[];
  faq_template_id?: string | null;
}

export interface VerifiedSuggestionsResponse {
  success: boolean;
  queries: string[];
  count: number;
  source: string;
  faq_loader: {
    faq_engine_ready: boolean;
    source_dir: string;
    load_error: string | null;
  };
}

export interface LoginResponse {
  success: boolean;
  access_token: string;
  user: { id: string; email: string; name: string; role: string; branch_ids: string[] };
}

// ── Auth ──────────────────────────────────────────────────────────────────────
export interface DashboardTrendPoint {
  label: string;
  date: string;
  current: number;
  prior: number;
  bills: number;
  quantity: number;
}

export interface DashboardResponse {
  success: boolean;
  period: string;
  period_label: string;
  granularity: 'day' | 'month';
  summary: {
    mtd_sales: number;
    ly_sales: number;
    sales_growth_pct: number | null;
    quantity: number;
    bills: number;
    customers: number | null;
  };
  trend: DashboardTrendPoint[];
  categories: { name: string; revenue: number; percentage: number }[];
  branches: { name: string; revenue: number; percentage: number }[];
  date_range?: { start: string; end: string };
  checksum: { trend_total: number; summary_total: number; match: boolean };
}

export interface ManagedUser {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
  created_at?: string;
}

export interface UsersListResponse {
  success: boolean;
  users: ManagedUser[];
}

export const auth = {
  login: (email: string, password: string) =>
    apiFetch<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => apiFetch<{ success: boolean; user: LoginResponse['user'] }>('/auth/me'),
  logout: () => apiFetch<{ success: boolean }>('/auth/logout', { method: 'POST' }),

  // ── User management (admin only) ─────────────────────────────────────────
  getUsers: () => apiFetch<UsersListResponse>('/auth/users'),
  createUser: (data: { email: string; name: string; password: string; role: string }) =>
    apiFetch<{ success: boolean; user: ManagedUser }>('/auth/users', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateUser: (id: string, data: Partial<{ name: string; role: string; is_active: boolean; password: string }>) =>
    apiFetch<{ success: boolean; user: ManagedUser }>(`/auth/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  deleteUser: (id: string) =>
    apiFetch<{ success: boolean }>(`/auth/users/${id}`, { method: 'DELETE' }),
};

// ── Analytics ─────────────────────────────────────────────────────────────────
export const analytics = {
  // Note: all GET endpoints below use apiFetchDeduped — concurrent identical
  // calls (e.g. from useDashboardPage + fetchAndApplySnapshot + prefetchAnalyticsShell)
  // share a single in-flight HTTP request instead of firing N copies.

  dashboard: (period = 'mtd', startDate?: string, endDate?: string) => {
    const qs = new URLSearchParams({ period });
    if (startDate) qs.set('start_date', startDate);
    if (endDate) qs.set('end_date', endDate);
    return apiFetchDeduped<DashboardResponse>(`/analytics/dashboard?${qs}`, { timeoutMs: 600_000 });
  },

  kpis: (period = 'mtd') =>
    apiFetchDeduped<KPIsResponse>(`/analytics/kpis?period=${period}`, { timeoutMs: 600_000 }),

  trend: (period = 'last_30d') =>
    apiFetchDeduped<{ success: boolean; period: string; trend: TrendPoint[] }>(
      `/analytics/trend?period=${period}`
    ),

  categories: (period = 'mtd', topN = 10) =>
    apiFetchDeduped<{ success: boolean; period: string; categories: CategoryPoint[] }>(
      `/analytics/categories?period=${period}&top_n=${topN}`
    ),

  branches: (period = 'mtd') =>
    apiFetchDeduped<{ success: boolean; period: string; branches: BranchPoint[] }>(
      `/analytics/branches?period=${period}`
    ),

  /** Fast path — server parallel SQL + cache (see test/qtd_breakdown.py). */
  bundle: (
    period = 'mtd',
    opts?: { topN?: number; includeDepartments?: boolean; includeKpis?: boolean; includeCustomerCount?: boolean },
  ) => {
    const qs = new URLSearchParams({ period });
    const topN = opts?.topN ?? 100;
    qs.set('top_n', String(topN));
    qs.set('include_departments', opts?.includeDepartments ? 'true' : 'false');
    qs.set('include_kpis', opts?.includeKpis ? 'true' : 'false');
    qs.set('include_customer_count', opts?.includeCustomerCount !== false ? 'true' : 'false');
    return apiFetchDeduped<AnalyticsBundleResponse>(`/analytics/bundle?${qs}`, { timeoutMs: 600_000 });
  },

  /** One HTTP call: MTD + Today bundles with KPIs (home dashboard). */
  dashboardPage: () =>
    apiFetchDeduped<DashboardPageResponse>('/analytics/dashboard-page', { timeoutMs: 600_000 }),

  departments: (period = 'mtd', topN = 10) =>
    apiFetchDeduped<{ success: boolean; period: string; departments: DeptPoint[] }>(
      `/analytics/departments?period=${period}&top_n=${topN}`
    ),

  salespersons: (period = 'mtd', topN = 10) =>
    apiFetchDeduped<{ success: boolean; period: string; salespersons: SalespersonPoint[] }>(
      `/analytics/salespersons?period=${period}&top_n=${topN}`
    ),

  heatmap: (period = 'last_30d') =>
    apiFetchDeduped<{ success: boolean; period: string; heatmap: HeatmapPoint[] }>(
      `/analytics/heatmap?period=${period}`
    ),

  branchDetail: (alias: string, period = 'last_14d') =>
    apiFetchDeduped<Record<string, unknown>>(
      `/analytics/branches/${encodeURIComponent(alias)}?period=${encodeURIComponent(period)}`,
    ),

  health: () => apiFetchDeduped<Record<string, unknown>>('/analytics/health'),

  /**
   * Instant snapshot — reads ONLY from server-side cache (PostgreSQL / memory).
   * Never waits for SQL Server. Responds in < 20 ms.
   * Use this to paint the dashboard on every page load, then refresh in background.
   */
  snapshot: () => apiFetchDeduped<{
    success: boolean;
    has_data: boolean;
    source: string;
    mtd_dashboard: DashboardResponse | null;
    mtd_kpis: KPIsResponse | null;
    today_kpis: KPIsResponse | null;
    today_dashboard: DashboardResponse | null;
    // Analytics page tabs — seeded so period tabs render without loading state
    qtd_dashboard: DashboardResponse | null;
    ytd_dashboard: DashboardResponse | null;
    last6m_dashboard: DashboardResponse | null;
    qtd_kpis?: KPIsResponse | null;
    ytd_kpis?: KPIsResponse | null;
    last6m_kpis?: KPIsResponse | null;
    departments_mtd?: DeptPoint[] | null;
    departments_today?: DeptPoint[] | null;
    departments_qtd?: DeptPoint[] | null;
    departments_ytd?: DeptPoint[] | null;
    departments_last6m?: DeptPoint[] | null;
    // Branch Intel page — seeds branches:mtd SWR key (plain list from chart cache)
    branches_chart_mtd?: BranchPoint[] | null;
    // Products page — seeds categories:mtd:8 SWR key (plain list from chart cache)
    categories_chart_mtd?: CategoryPoint[] | null;
    // Transactions page 1 — seeded into SWR cache so Transactions page loads instantly
    txn_list_mtd: TransactionsResponse | null;
    txn_list_today: TransactionsResponse | null;
    txn_summary_mtd: TransactionSummary | null;
    // Products page — product master catalog + top products MTD
    product_catalog?: ProductCatalogResponse | null;
    top_products_mtd?: TopProductsResponse | null;
  }>('/analytics/snapshot', { timeoutMs: 8_000 }),

  transactionSummary: (period = 'mtd') =>
    apiFetch<TransactionSummary>(`/analytics/transactions/summary?period=${period}`),

  transactions: (params: {
    period?: string;
    page?: number;
    page_size?: number;
    branch?: string;
    category?: string;
    search?: string;
  } = {}) => {
    const qs = new URLSearchParams();
    if (params.period) qs.set('period', params.period);
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    if (params.branch) qs.set('branch', params.branch);
    if (params.category) qs.set('category', params.category);
    if (params.search) qs.set('search', params.search);
    return apiFetch<TransactionsResponse>(`/analytics/transactions?${qs.toString()}`);
  },

  /** Paginated item master (same source as test/list_products_db.py). */
  productCatalog: (params: { search?: string; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.search) qs.set('search', params.search);
    if (params.limit != null) qs.set('limit', String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    return apiFetch<ProductCatalogResponse>(
      `/analytics/products/catalog?${qs}`,
      { timeoutMs: 120_000 },
    );
  },

  topProducts: (period = 'mtd', topN = 15) =>
    apiFetch<TopProductsResponse>(
      `/analytics/products/top?period=${encodeURIComponent(period)}&top_n=${topN}`,
      { timeoutMs: 600_000 },
    ),

  viewsCatalog: () =>
    apiFetch<ViewsCatalogResponse>('/analytics/views', { timeoutMs: 120_000 }),

  viewQuery: (params: { view: string; page?: number; page_size?: number; skip_count?: boolean }) => {
    const qs = new URLSearchParams();
    qs.set('view', params.view);
    if (params.page != null) qs.set('page', String(params.page));
    if (params.page_size != null) qs.set('page_size', String(params.page_size));
    if (params.skip_count) qs.set('skip_count', 'true');
    return apiFetch<ViewQueryResponse>(`/analytics/views/query?${qs}`, { timeoutMs: 120_000 });
  },
};

// ── AI / NLQ ──────────────────────────────────────────────────────────────────
export const ai = {
  query: (body: NLQRequest) =>
    apiFetch<NLQResponse>('/ai/query', {
      method: 'POST',
      body: JSON.stringify(body),
      // Verified FAQ SQL can run for several minutes on large ERP views.
      timeoutMs: 900_000,
    }),

  verifiedSuggestions: (limit = 50) =>
    apiFetchDeduped<VerifiedSuggestionsResponse>(
      `/ai/verified-suggestions?limit=${encodeURIComponent(String(limit))}`,
    ),

  conversations: () =>
    apiFetch<{ success: boolean; conversations: unknown[] }>('/ai/conversations'),

  explainSql: (sql: string) =>
    apiFetch<{ success: boolean; explanation: string }>('/ai/explain-sql', {
      method: 'POST',
      body: JSON.stringify({ sql }),
    }),

  pageInsights: (period = 'mtd') =>
    apiFetch<PageInsightsResponse>(`/ai/page-insights?period=${encodeURIComponent(period)}`, { timeoutMs: 45_000 }),
};

export interface PageInsight {
  id: string;
  type: 'anomaly' | 'forecast' | 'recommendation' | 'alert';
  title: string;
  description: string;
  confidence: number;
  impact: 'high' | 'medium' | 'low';
  severity: 'info' | 'warning' | 'critical';
}

export interface PageInsightsResponse {
  success: boolean;
  period: string;
  insights: PageInsight[];
  executive_summary: string | null;
  data_available: boolean;
  from_cache: boolean;
}

// ── Public health (no JWT; boot loader) ─────────────────────────────────────────
const PUBLIC_FETCH_MS = 12_000;

export interface PublicHealthResponse {
  status: string;
  mssql?: {
    connected?: boolean;
    latency_ms?: number | null;
    busy?: boolean;
    error?: string;
    note?: string;
  };
  warmup?: { running?: boolean; complete?: boolean };
  warehouse?: {
    erp_database: string;
    analytics_line_table: string;
    sales_ai_table: string;
    sales_view: string;
    transactions_view: string;
    schema_catalog_objects: number;
  };
}

/** Best-effort; returns null if backend is unreachable */
export async function fetchPublicHealth(): Promise<PublicHealthResponse | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PUBLIC_FETCH_MS);
  try {
    const res = await fetch(`${BASE}/health`, {
      method: 'GET',
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return null;
    return (await res.json()) as PublicHealthResponse;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
