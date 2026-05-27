import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileBarChart, Download, Sparkles,
  Clock, FileText, Share2, Eye, Zap
} from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { useTheme } from '../context/ThemeContext';

const stagger = { animate: { transition: { staggerChildren: 0.06 } } };
const item = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 26 } },
};

const reports = [
  { id: 1, title: 'Monthly Financial Summary', period: 'November 2024', type: 'Financial', status: 'ready', size: '2.4 MB', updated: '2h ago', color: '#00b8e6' },
  { id: 2, title: 'AI Fraud Detection Report', period: 'Q4 2024', type: 'Security', status: 'ready', size: '1.8 MB', updated: '5h ago', color: '#ef4444' },
  { id: 3, title: 'Branch Performance Report', period: 'November 2024', type: 'Operations', status: 'generating', size: '—', updated: 'In progress', color: '#00e67a' },
  { id: 4, title: 'Product Revenue Breakdown', period: 'Q4 2024', type: 'Revenue', status: 'ready', size: '3.1 MB', updated: '1d ago', color: '#ffb800' },
  { id: 5, title: 'Customer Behaviour Analysis', period: 'October 2024', type: 'Analytics', status: 'ready', size: '5.6 MB', updated: '3d ago', color: '#a78bfa' },
  { id: 6, title: 'Regulatory Compliance Report', period: 'Q3 2024', type: 'Compliance', status: 'ready', size: '1.2 MB', updated: '2w ago', color: '#f87171' },
];

const quarterlyBar = [
  { label: 'Q1', revenue: 3.35, expenses: 2.1 },
  { label: 'Q2', revenue: 3.95, expenses: 2.3 },
  { label: 'Q3', revenue: 4.45, expenses: 2.5 },
  { label: 'Q4', revenue: 4.82, expenses: 2.7 },
];

export default function Reports() {
  const { isDark } = useTheme();
  const [selectedType, setSelectedType] = useState('All');
  const types = ['All', 'Financial', 'Security', 'Operations', 'Revenue', 'Analytics'];

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      {/* Header */}
      <motion.div variants={item} className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{
            background: isDark ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)' : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>Reports</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>AI-generated intelligence reports & exports</p>
        </div>
        <motion.button
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white"
          style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 20px rgba(0,184,230,0.3)' }}
          whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
          <Sparkles size={12} /> Generate AI Report
        </motion.button>
      </motion.div>

      {/* Charts row */}
      <div className="grid grid-cols-12 gap-4">
        <motion.div variants={item} className="col-span-7 rounded-2xl p-5"
          style={{
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(20px)',
            border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
          }}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Annual Revenue vs Expenses</h3>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Quarterly comparison (in $M)</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 rounded" style={{ background: '#00b8e6' }} /><span className="text-xs" style={{ color: 'var(--text-muted)' }}>Revenue</span></div>
              <div className="flex items-center gap-1.5"><div className="w-3 h-0.5 rounded" style={{ background: '#ef4444' }} /><span className="text-xs" style={{ color: 'var(--text-muted)' }}>Expenses</span></div>
            </div>
          </div>
          <div className="h-44">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={quarterlyBar} margin={{ top: 5, right: 10, left: -10, bottom: 5 }} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke={isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)'} vertical={false} />
                <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${v}M`} />
                <Tooltip formatter={(v: number) => [`$${v}M`, '']} />
                <Bar dataKey="revenue" fill="#00b8e6" radius={[4, 4, 0, 0]} barSize={28} opacity={0.85} />
                <Bar dataKey="expenses" fill="#ef4444" radius={[4, 4, 0, 0]} barSize={28} opacity={0.6} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </motion.div>

        <motion.div variants={item} className="col-span-5 rounded-2xl p-5"
          style={{
            background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
            backdropFilter: 'blur(20px)',
            border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
          }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Report Summary</h3>
          <div className="grid grid-cols-2 gap-3 mb-4">
            {[
              { label: 'Total Reports', value: '47', icon: FileText, color: '#00b8e6' },
              { label: 'AI Generated', value: '31', icon: Sparkles, color: '#00e67a' },
              { label: 'Scheduled', value: '12', icon: Clock, color: '#ffb800' },
              { label: 'Shared', value: '8', icon: Share2, color: '#a78bfa' },
            ].map(stat => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className="p-3 rounded-xl"
                  style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}>
                  <Icon size={14} style={{ color: stat.color }} className="mb-2" />
                  <p className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{stat.value}</p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
                </div>
              );
            })}
          </div>
          <div className="px-3 py-2.5 rounded-xl flex items-center gap-2"
            style={{ background: 'rgba(0,184,230,0.06)', border: '1px solid rgba(0,184,230,0.15)' }}>
            <Zap size={12} style={{ color: '#00b8e6' }} />
            <p className="text-xs" style={{ color: '#00b8e6' }}>Next scheduled report in <strong>2h 14m</strong></p>
          </div>
        </motion.div>
      </div>

      {/* Reports list */}
      <motion.div variants={item} className="rounded-2xl overflow-hidden"
        style={{
          background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
          backdropFilter: 'blur(20px)',
          border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
        }}>

        <div className="flex items-center justify-between p-4"
          style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Report Library</h3>
          <div className="flex items-center gap-1 p-1 rounded-xl"
            style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)' }}>
            {types.map(t => (
              <button key={t} onClick={() => setSelectedType(t)}
                className="px-3 py-1 rounded-lg text-xs font-medium transition-all"
                style={{
                  background: selectedType === t ? isDark ? 'rgba(0,184,230,0.15)' : 'rgba(0,184,230,0.1)' : 'transparent',
                  color: selectedType === t ? '#00b8e6' : 'var(--text-muted)',
                }}>{t}</button>
            ))}
          </div>
        </div>

        <div className="divide-y" style={{ borderColor: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }}>
          {reports
            .filter(r => selectedType === 'All' || r.type === selectedType)
            .map((report, i) => (
              <motion.div key={report.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.06 }}
                className="flex items-center gap-4 px-4 py-3.5 group cursor-pointer"
                whileHover={{ background: isDark ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.02)' }}>
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: `${report.color}18`, border: `1px solid ${report.color}30` }}>
                  <FileBarChart size={16} style={{ color: report.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{report.title}</p>
                    {report.status === 'generating' && (
                      <span className="px-2 py-0.5 rounded-full text-2xs font-bold animate-pulse"
                        style={{ background: 'rgba(255,184,0,0.1)', color: '#ffb800' }}>Generating…</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{report.period}</span>
                    <span className="px-1.5 py-0.5 rounded text-2xs font-semibold"
                      style={{ background: `${report.color}12`, color: report.color }}>{report.type}</span>
                    <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Updated {report.updated}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  {report.status === 'ready' && (
                    <>
                      <motion.button className="p-2 rounded-xl" whileHover={{ scale: 1.05 }}
                        style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', color: 'var(--text-muted)' }}>
                        <Eye size={13} />
                      </motion.button>
                      <motion.button className="p-2 rounded-xl" whileHover={{ scale: 1.05 }}
                        style={{ background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)', color: 'var(--text-muted)' }}>
                        <Download size={13} />
                      </motion.button>
                    </>
                  )}
                </div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{report.size}</div>
              </motion.div>
            ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
