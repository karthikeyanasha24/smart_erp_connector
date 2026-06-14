import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Sun, Moon, Sparkles, Command, TrendingUp,
  Calendar, Download, Menu, X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useNavigation } from '../../context/NavigationContext';
import { useTheme } from '../../context/ThemeContext';
import { useKPIs, useBranches } from '../../hooks/useAnalytics';

const pageLabels: Record<string, string> = {
  dashboard: 'AI Dashboard',
  analytics: 'Analytics',
  'ai-query': 'AI Query',
  transactions: 'Transactions',
  reports: 'Reports',
  branch: 'Branch Intel',
  product: 'Products',
  data: 'Data Explorer',
  insights: 'AI Insights',
  settings: 'Settings',
  'erp-views': 'ERP Views',
};

export default function Topbar() {
  const navigate = useNavigate();
  const { currentPage, sidebarExpanded, mobileSidebarOpen, setMobileSidebarOpen, isMobile } = useNavigation();
  const { isDark, toggleTheme } = useTheme();

  const sidebarW = isMobile ? 0 : (sidebarExpanded ? 240 : 72);

  const { kpis } = useKPIs('mtd');
  const { branches } = useBranches('mtd');

  const revGrowth = kpis.revenue.growth;
  const txnCount  = kpis.transactions.value;
  const branchCount = useMemo(() => branches?.length ?? 0, [branches]);

  const fmtGrowth = (g: number | null) => g !== null ? `${g >= 0 ? '+' : ''}${g.toFixed(1)}%` : '—';
  const fmtCount  = (n: number) => n >= 1e5 ? `${(n / 1e3).toFixed(1)}K` : n >= 1000 ? `${(n / 1e3).toFixed(0)}K` : String(n);


  return (
    <motion.header
      className="fixed top-0 right-0 z-40 flex items-center gap-2 md:gap-4 px-3 md:px-6"
      style={{
        left: sidebarW,
        height: 64,
        background: isDark ? 'rgba(5,9,24,0.88)' : 'rgba(248,250,255,0.92)',
        backdropFilter: 'blur(28px) saturate(200%)',
        borderBottom: isDark ? '1px solid rgba(88,130,255,0.1)' : '1px solid rgba(88,130,255,0.12)',
        boxShadow: isDark ? '0 1px 0 rgba(88,130,255,0.05), 0 4px 20px rgba(0,0,0,0.3)' : 'none',
        transition: 'left 0.3s cubic-bezier(0.4,0,0.2,1)',
      }}
    >
      {/* Hamburger — mobile only */}
      {isMobile && (
        <motion.button
          type="button"
          onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
            color: 'var(--text-secondary)',
          }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.92 }}
        >
          <AnimatePresence mode="wait">
            {mobileSidebarOpen ? (
              <motion.div key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}>
                <X size={16} />
              </motion.div>
            ) : (
              <motion.div key="menu" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }}>
                <Menu size={16} />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>
      )}

      {/* Page title */}
      <div className="flex items-center gap-2 flex-shrink-0 min-w-0">
        <motion.h1
          key={currentPage}
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-semibold truncate"
          style={{ color: 'var(--text-primary)', maxWidth: isMobile ? 120 : 'none' }}
        >
          {pageLabels[currentPage]}
        </motion.h1>

        <div className="flex items-center gap-1 px-2 py-1 rounded-full flex-shrink-0"
          style={{ background: 'rgba(88,130,255,0.08)', border: '1px solid rgba(88,130,255,0.18)' }}>
          <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#5882ff' }} />
          <span className="text-2xs font-semibold" style={{ color: '#5882ff' }}>LIVE</span>
        </div>
      </div>

      {/* Spacer — pushes actions to the right */}
      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-1 flex-shrink-0">
        {/* Transactions extras — sm+ only */}
        {currentPage === 'transactions' && (
          <>
            <motion.div
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold"
              style={{
                background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
                border: isDark ? '1px solid rgba(255,255,255,0.09)' : '1px solid rgba(0,0,0,0.08)',
                color: 'var(--text-secondary)',
              }}
            >
              <Calendar size={13} />
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

        {/* Ask AI */}
        <motion.button
          type="button"
          onClick={() => navigate('/ai-query')}
          className="flex items-center gap-2 px-2.5 md:px-3 py-1.5 rounded-xl text-xs font-semibold text-white flex-shrink-0"
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
    </motion.header>
  );
}
