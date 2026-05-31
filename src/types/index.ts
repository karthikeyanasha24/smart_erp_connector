export type Theme = 'dark' | 'light';

export type Page =
  | 'dashboard'
  | 'analytics'
  | 'ai-query'
  | 'transactions'
  | 'reports'
  | 'branch'
  | 'product'
  | 'data'
  | 'erp-views'
  | 'settings';

export interface KPIMetric {
  id: string;
  label: string;
  value: string | number;
  change: number;
  changeLabel: string;
  trend: 'up' | 'down' | 'stable';
  sparkData?: number[];
  unit?: string;
  prefix?: string;
  color?: 'cyan' | 'green' | 'amber' | 'red';
}

export interface ChartDataPoint {
  label: string;
  value: number;
  value2?: number;
  value3?: number;
}

export interface AIInsight {
  id: string;
  type: 'anomaly' | 'recommendation' | 'forecast' | 'alert';
  title: string;
  description: string;
  confidence: number;
  impact: 'high' | 'medium' | 'low';
  timestamp: string;
}

export interface Transaction {
  id: string;
  merchant: string;
  category: string;
  amount: number;
  currency: string;
  status: 'completed' | 'pending' | 'failed';
  timestamp: string;
  branch: string;
  channel: string;
  risk: 'low' | 'medium' | 'high';
}

export interface Branch {
  id: string;
  name: string;
  city: string;
  revenue: number;
  transactions: number;
  growth: number;
  status: 'active' | 'alert' | 'offline';
  lat: number;
  lng: number;
}

export interface NavItem {
  id: Page;
  label: string;
  icon: string;
  badge?: string | number;
  group?: string;
}
