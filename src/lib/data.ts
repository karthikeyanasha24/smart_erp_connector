import type { KPIMetric, ChartDataPoint, AIInsight, Transaction, Branch } from '../types';

export const kpiMetrics: KPIMetric[] = [
  {
    id: 'revenue',
    label: 'Total Revenue',
    value: '4.82M',
    change: 18.4,
    changeLabel: 'vs last month',
    trend: 'up',
    sparkData: [32, 45, 38, 55, 48, 62, 58, 71, 65, 78, 82, 91],
    unit: '',
    prefix: '$',
    color: 'cyan',
  },
  {
    id: 'transactions',
    label: 'Transactions',
    value: '248.7K',
    change: 12.1,
    changeLabel: 'vs last month',
    trend: 'up',
    sparkData: [45, 52, 49, 58, 55, 63, 61, 68, 65, 72, 70, 78],
    color: 'green',
  },
  {
    id: 'ai-accuracy',
    label: 'AI Accuracy',
    value: '99.4',
    change: 0.8,
    changeLabel: 'vs last week',
    trend: 'up',
    sparkData: [96, 97, 96.5, 98, 98.2, 98.8, 99, 99.1, 99.3, 99.2, 99.4, 99.4],
    unit: '%',
    color: 'amber',
  },
  {
    id: 'fraud-prevented',
    label: 'Fraud Prevented',
    value: '1.24M',
    change: -23.5,
    changeLabel: 'fraud attempts blocked',
    trend: 'down',
    sparkData: [88, 76, 82, 71, 68, 62, 58, 55, 50, 48, 44, 40],
    unit: '',
    prefix: '$',
    color: 'red',
  },
];

export const revenueData: ChartDataPoint[] = [
  { label: 'Jan', value: 3200000, value2: 2800000 },
  { label: 'Feb', value: 3540000, value2: 3100000 },
  { label: 'Mar', value: 3280000, value2: 2950000 },
  { label: 'Apr', value: 3820000, value2: 3400000 },
  { label: 'May', value: 4100000, value2: 3700000 },
  { label: 'Jun', value: 3950000, value2: 3500000 },
  { label: 'Jul', value: 4400000, value2: 3900000 },
  { label: 'Aug', value: 4280000, value2: 3800000 },
  { label: 'Sep', value: 4680000, value2: 4100000 },
  { label: 'Oct', value: 4520000, value2: 4000000 },
  { label: 'Nov', value: 4820000, value2: 4300000 },
  { label: 'Dec', value: 5100000, value2: 4600000 },
];

export const transactionVolumeData: ChartDataPoint[] = Array.from({ length: 30 }, (_, i) => ({
  label: `Day ${i + 1}`,
  value: Math.floor(6000 + Math.random() * 4000 + Math.sin(i * 0.5) * 2000),
  value2: Math.floor(4000 + Math.random() * 3000 + Math.cos(i * 0.3) * 1500),
}));

export const categoryData: ChartDataPoint[] = [
  { label: 'Retail', value: 35 },
  { label: 'Digital', value: 28 },
  { label: 'Corporate', value: 18 },
  { label: 'SME', value: 12 },
  { label: 'Other', value: 7 },
];

export const hourlyData: ChartDataPoint[] = Array.from({ length: 24 }, (_, i) => ({
  label: `${i}:00`,
  value: Math.floor(200 + Math.sin((i - 9) * 0.4) * 180 + Math.random() * 60),
}));

export const aiInsights: AIInsight[] = [
  {
    id: '1',
    type: 'anomaly',
    title: 'Unusual transaction spike detected',
    description: 'Branch 14 (NYC Midtown) shows 340% above-baseline activity between 11PM–1AM. Pattern matches coordinated card-testing behavior.',
    confidence: 97.2,
    impact: 'high',
    timestamp: '2 min ago',
  },
  {
    id: '2',
    type: 'forecast',
    title: 'Q4 revenue trajectory exceeds projection',
    description: 'Current growth trajectory places Q4 revenue at $5.8M — 12% above the $5.2M projection. Key driver: digital channel adoption +41%.',
    confidence: 89.1,
    impact: 'high',
    timestamp: '8 min ago',
  },
  {
    id: '3',
    type: 'recommendation',
    title: 'Optimize weekend staffing model',
    description: 'Analysis of 90 days of transaction patterns suggests weekend peak shifted 2 hours earlier. Realigning staffing could reduce wait time by 31%.',
    confidence: 82.5,
    impact: 'medium',
    timestamp: '24 min ago',
  },
  {
    id: '4',
    type: 'alert',
    title: 'Merchant category drift in cards portfolio',
    description: 'Consumer spending shifted 8.4% from discretionary to essential merchants — indicator of macro stress. Monitoring credit risk exposure.',
    confidence: 76.8,
    impact: 'medium',
    timestamp: '1 hr ago',
  },
];

export const transactions: Transaction[] = [
  { id: 'TXN-8821', merchant: 'Amazon Web Services', category: 'Technology', amount: 12450.00, currency: 'USD', status: 'completed', timestamp: '2024-11-25 14:32:18', branch: 'NYC-01', channel: 'API', risk: 'low' },
  { id: 'TXN-8820', merchant: 'Whole Foods Market', category: 'Retail', amount: 284.50, currency: 'USD', status: 'completed', timestamp: '2024-11-25 14:28:44', branch: 'LA-03', channel: 'POS', risk: 'low' },
  { id: 'TXN-8819', merchant: 'Marriott Hotels', category: 'Hospitality', amount: 3200.00, currency: 'USD', status: 'pending', timestamp: '2024-11-25 14:24:01', branch: 'CHI-02', channel: 'Web', risk: 'medium' },
  { id: 'TXN-8818', merchant: 'Shell Gas Station', category: 'Transport', amount: 87.40, currency: 'USD', status: 'completed', timestamp: '2024-11-25 14:19:33', branch: 'HOU-01', channel: 'POS', risk: 'low' },
  { id: 'TXN-8817', merchant: 'Unknown Merchant', category: 'Other', amount: 5500.00, currency: 'USD', status: 'failed', timestamp: '2024-11-25 14:15:22', branch: 'NYC-01', channel: 'ATM', risk: 'high' },
  { id: 'TXN-8816', merchant: 'Apple Store', category: 'Electronics', amount: 1299.99, currency: 'USD', status: 'completed', timestamp: '2024-11-25 14:12:08', branch: 'SF-01', channel: 'POS', risk: 'low' },
  { id: 'TXN-8815', merchant: 'Netflix Inc', category: 'Entertainment', amount: 22.99, currency: 'USD', status: 'completed', timestamp: '2024-11-25 14:08:45', branch: 'DIGITAL', channel: 'API', risk: 'low' },
  { id: 'TXN-8814', merchant: 'Goldman Sachs', category: 'Finance', amount: 250000.00, currency: 'USD', status: 'pending', timestamp: '2024-11-25 14:02:17', branch: 'NYC-01', channel: 'Wire', risk: 'medium' },
];

export const branches: Branch[] = [
  { id: 'NYC-01', name: 'New York Midtown', city: 'New York', revenue: 1240000, transactions: 48200, growth: 22.4, status: 'active', lat: 40.758, lng: -73.985 },
  { id: 'LA-03', name: 'Los Angeles Beverly', city: 'Los Angeles', revenue: 890000, transactions: 34100, growth: 15.2, status: 'active', lat: 34.073, lng: -118.400 },
  { id: 'CHI-02', name: 'Chicago Loop', city: 'Chicago', revenue: 720000, transactions: 28800, growth: 8.7, status: 'alert', lat: 41.882, lng: -87.630 },
  { id: 'SF-01', name: 'San Francisco FiDi', city: 'San Francisco', revenue: 1080000, transactions: 41600, growth: 31.8, status: 'active', lat: 37.790, lng: -122.399 },
  { id: 'HOU-01', name: 'Houston Energy', city: 'Houston', revenue: 560000, transactions: 22400, growth: 5.1, status: 'active', lat: 29.760, lng: -95.370 },
  { id: 'MIA-01', name: 'Miami Brickell', city: 'Miami', revenue: 640000, transactions: 25600, growth: 18.9, status: 'active', lat: 25.758, lng: -80.191 },
];

export const productData = [
  { name: 'Premium Card', revenue: 1820000, users: 48200, growth: 24.5, color: '#00b8e6' },
  { name: 'Business Account', revenue: 1240000, users: 12800, growth: 18.2, color: '#00e67a' },
  { name: 'Digital Wallet', revenue: 880000, users: 124000, growth: 41.8, color: '#ffb800' },
  { name: 'Investment Suite', revenue: 620000, users: 6200, growth: 12.4, color: '#ff6b6b' },
  { name: 'Savings Plus', revenue: 380000, users: 84000, growth: 8.9, color: '#a78bfa' },
];
