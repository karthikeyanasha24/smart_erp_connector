import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Bell, Sun, Moon, Sparkles, Command, TrendingUp,
  Calendar, Download,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useNavigation } from '../../context/NavigationContext';
import { useTheme } from '../../context/ThemeContext';

const pageLabels: Record<string, string> = {
  dashboard: 'AI Dashboard',
  analytics: 'Analytics',
  'ai-query': 'AI Query Workspace',
  transactions: 'Transactions',
  reports: 'Reports',
  branch: 'Branch Intelligence',
  product: 'Product Analytics',
  data: 'Data Explorer',
  insights: 'AI Insights',
  settings: 'Settings',
};

export default function Topbar() {
  const navigate = useNavigate();
  const { currentPage, sidebarExpanded } = useNavigation();
  const { isDark, toggleTheme } = useTheme();
  const [searchFocused, setSearchFocused] = useState(false);
  const [searchValue, setSearchValue] = useState('');
  const [notifOpen, setNotifOpen] = useState(false);

  const sidebarW = sidebarExpanded ? 240 : 72;

  return (
    <motion.header
      className="fixed top-0 right-0 z-40 flex items-center gap-4 px-6"
      style={{
        left: sidebarW,
        height: 64,
        background: isDark
          ? 'rgba(5,9,24,0.88)'
          : 'rgba(248,250,255,0.92)',
        backdropFilter: 'blur(28px) saturate(200%)',
        borderBottom: isDark ? '1px solid rgba(88,130,255,0.1)' : '1px solid rgba(88,130,255,0.12)',
        boxShadow: isDark ? '0 1px 0 rgba(88,130,255,0.05), 0 4px 20px rgba(0,0,0,0.3)' : 'none',
        transition: 'left 0.3s cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      {/* Page title */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <motion.h1
          key={currentPage}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-semibold"
          style={{ color: 'var(--text-primary)' }}
        >
          {pageLabels[currentPage]}
        </motion.h1>

        {/* Live pulse indicator */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full"
          style={{
            background: 'rgba(88,130,255,0.08)',
            border: '1px solid rgba(88,130,255,0.18)',
          }}>
          <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#5882ff' }} />
          <span className="text-2xs font-semibold" style={{ color: '#5882ff' }}>LIVE</span>
        </div>
      </div>

      {/* AI Pulse ticker */}
      <div
        className="flex-1 mx-4 hidden md:flex items-center gap-3 px-4 py-2 rounded-xl overflow-hidden"
        style={{
          background: isDark ? 'rgba(88,130,255,0.04)' : 'rgba(88,130,255,0.04)',
          border: isDark ? '1px solid rgba(88,130,255,0.1)' : '1px solid rgba(88,130,255,0.1)',
          maxWidth: 480,
        }}
      >
        <TrendingUp size={12} className="text-primary-400 flex-shrink-0" />
        <div className="overflow-hidden flex-1">
          <motion.div
            animate={{ x: ['0%', '-50%'] }}
            transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
            className="flex gap-8 whitespace-nowrap text-xs"
            style={{ color: 'var(--text-muted)' }}
          >
            <span><span className="text-accent-400 font-medium">+18.4%</span> Revenue MoM</span>
            <span><span className="text-primary-400 font-medium">248.7K</span> Active Transactions</span>
            <span><span className="text-warning-400 font-medium">99.4%</span> AI Accuracy</span>
            <span><span className="text-error-400 font-medium">$1.24M</span> Fraud Blocked Today</span>
            <span><span className="text-accent-400 font-medium">6</span> Branches Online</span>
            <span><span className="text-primary-400 font-medium">+18.4%</span> Revenue MoM</span>
            <span><span className="text-accent-400 font-medium">248.7K</span> Active Transactions</span>
            <span><span className="text-warning-400 font-medium">99.4%</span> AI Accuracy</span>
          </motion.div>
        </div>
      </div>

      {/* Search */}
      <motion.div
        className="relative hidden lg:flex items-center"
        animate={{ width: searchFocused ? 240 : 180 }}
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      >
        <Search size={13} className="absolute left-3" style={{ color: 'var(--text-muted)' }} />
        <input
          value={searchValue}
          onChange={e => setSearchValue(e.target.value)}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setSearchFocused(false)}
          placeholder="Search metrics, branches, products..."
          className="w-full pl-8 pr-9 py-2 text-xs rounded-xl outline-none transition-all"
          style={{
            background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
            border: searchFocused
              ? '1px solid rgba(88,130,255,0.4)'
              : isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.08)',
            color: 'var(--text-primary)',
          }}
        />
        <div
          className="absolute right-2.5 flex items-center gap-0.5 px-1 py-0.5 rounded"
          style={{
            background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
          }}
        >
          <Command size={9} style={{ color: 'var(--text-muted)' }} />
          <span className="text-2xs" style={{ color: 'var(--text-muted)' }}>K</span>
        </div>
      </motion.div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        {/* Transactions-focused chrome (dashboard mock parity) */}
        {currentPage === 'transactions' && (
          <>
            <motion.div
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold"
              style={{
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                border: isDark ? '1px solid rgba(255,255,255,0.09)' : '1px solid rgba(0,0,0,0.08)',
                color: 'var(--text-secondary)',
              }}
              title="Period is driven from the Transactions page"
            >
              <Calendar size={13} style={{ opacity: 0.85 }} />
              MTD
            </motion.div>
            <motion.button
              type="button"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold"
              style={{
                background: 'transparent',
                border: isDark ? '1px solid rgba(255,255,255,0.12)' : '1px solid rgba(0,0,0,0.1)',
                color: 'var(--text-secondary)',
              }}
              title="Export from the Transactions table actions below"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => document.getElementById('transactions-export-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            >
              <Download size={13} />
              Export
            </motion.button>
          </>
        )}
        {/* Theme toggle */}
        <motion.button
          onClick={toggleTheme}
          className="w-8 h-8 rounded-xl flex items-center justify-center"
          style={{
            background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
            color: 'var(--text-tertiary)',
          }}
          whileHover={{ scale: 1.05, color: '#5882ff' }}
          whileTap={{ scale: 0.92 }}
        >
          <AnimatePresence mode="wait">
            {isDark ? (
              <motion.div key="sun" initial={{ rotate: -30, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 30, opacity: 0 }}>
                <Sun size={14} />
              </motion.div>
            ) : (
              <motion.div key="moon" initial={{ rotate: 30, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -30, opacity: 0 }}>
                <Moon size={14} />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>

        {/* Notifications */}
        <motion.button
          onClick={() => setNotifOpen(v => !v)}
          className="relative w-8 h-8 rounded-xl flex items-center justify-center"
          style={{
            background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
            color: 'var(--text-tertiary)',
          }}
          whileHover={{ scale: 1.05, color: '#5882ff' }}
          whileTap={{ scale: 0.92 }}
        >
          <Bell size={14} />
          <span
            className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-error-500"
            style={{ boxShadow: '0 0 6px rgba(239,68,68,0.8)' }}
          />
        </motion.button>

        {/* AI Assistant button */}
        <motion.button
          type="button"
          onClick={() => navigate('/ai-query')}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold text-white flex-shrink-0"
          style={{
            background: 'linear-gradient(135deg, #4158D0 0%, #8B5CF6 100%)',
            boxShadow: '0 0 16px rgba(88,130,255,0.35)',
          }}
          whileHover={{ scale: 1.02, boxShadow: '0 0 28px rgba(88,130,255,0.6)' }}
          whileTap={{ scale: 0.97 }}
        >
          <Sparkles size={11} />
          <span className="hidden sm:inline">Ask AI</span>
        </motion.button>
      </div>

      {/* Notification dropdown */}
      <AnimatePresence>
        {notifOpen && (
          <motion.div
            className="absolute top-full right-4 mt-2 w-80 rounded-2xl p-4 z-50"
            style={{
              background: isDark ? 'rgba(8,15,26,0.95)' : 'rgba(255,255,255,0.95)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.08)' : '1px solid rgba(0,0,0,0.08)',
              boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
            }}
            initial={{ opacity: 0, y: -8, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.96 }}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Notifications</span>
              <span className="badge-info">4 new</span>
            </div>
            {[
              { title: 'Anomaly Detected', desc: 'Branch NYC-01 shows unusual activity', time: '2m', color: 'error' },
              { title: 'Revenue Milestone', desc: 'Q4 projections exceeded by 12%', time: '8m', color: 'success' },
              { title: 'AI Model Updated', desc: 'Fraud detection accuracy improved', time: '1h', color: 'info' },
            ].map((n, i) => (
              <motion.div
                key={i}
                className="flex items-start gap-3 p-2.5 rounded-xl mb-1.5 cursor-pointer"
                whileHover={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }}
              >
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0 ${
                  n.color === 'error' ? 'bg-error-500' : n.color === 'success' ? 'bg-accent-500' : 'bg-primary-500'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>{n.title}</p>
                  <p className="text-2xs mt-0.5 truncate" style={{ color: 'var(--text-muted)' }}>{n.desc}</p>
                </div>
                <span className="text-2xs flex-shrink-0" style={{ color: 'var(--text-muted)' }}>{n.time}</span>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}
