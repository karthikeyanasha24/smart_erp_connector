import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, BarChart3, MessageSquareCode, ArrowLeftRight,
  FileBarChart, GitBranch, Package, Database, Settings,
  ChevronLeft, ChevronRight, Zap, Activity, Table2, X,
} from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useNavigation } from '../../context/NavigationContext';
import { useTheme } from '../../context/ThemeContext';
import { useAuth } from '../../context/AuthContext';
import { ROUTES } from '../../lib/routes';
import type { Page } from '../../types';
import { prefetchTransactionsOnHover, prefetchAnalyticsPage, prefetchBranchesChart } from '../../hooks/useAnalytics';

const ALL_NAV_GROUPS = [
  {
    group: 'Core',
    items: [
      { id: 'dashboard' as Page, label: 'AI Dashboard', icon: LayoutDashboard, badge: null, roles: undefined },
      { id: 'analytics' as Page, label: 'Analytics', icon: BarChart3, badge: null, roles: undefined },
      { id: 'ai-query' as Page, label: 'AI Query', icon: MessageSquareCode, badge: 'AI', roles: ['admin', 'manager', 'analyst'] },
    ],
  },
  {
    group: 'Operations',
    items: [
      { id: 'transactions' as Page, label: 'Transactions', icon: ArrowLeftRight, badge: null, roles: undefined },
      { id: 'branch' as Page, label: 'Branch Intel', icon: GitBranch, badge: null, roles: undefined },
      { id: 'product' as Page, label: 'Products', icon: Package, badge: null, roles: undefined },
      { id: 'data' as Page, label: 'Data Explorer', icon: Database, badge: null, roles: undefined },
      { id: 'erp-views' as Page, label: 'ERP Views', icon: Table2, badge: '28', roles: undefined },
    ],
  },
  {
    group: 'Reporting',
    items: [
      { id: 'reports' as Page, label: 'Reports', icon: FileBarChart, badge: null, roles: undefined },
      { id: 'settings' as Page, label: 'Settings', icon: Settings, badge: null, roles: ['admin', 'manager'] },
    ],
  },
];

const ROLE_COLORS: Record<string, { bg: string; color: string }> = {
  admin:   { bg: 'rgba(245,158,11,0.15)',  color: '#f59e0b' },
  manager: { bg: 'rgba(99,102,241,0.15)',  color: '#818cf8' },
  analyst: { bg: 'rgba(34,197,94,0.15)',   color: '#4ade80' },
  viewer:  { bg: 'rgba(148,163,184,0.15)', color: '#94a3b8' },
};

function SidebarContent({
  expanded,
  onClose,
}: {
  expanded: boolean;
  onClose?: () => void;
}) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { isDark } = useTheme();

  const navGroups = ALL_NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) =>
      !item.roles || (user?.role && item.roles.includes(user.role))
    ),
  })).filter((group) => group.items.length > 0);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <>
      {/* Logo row */}
      <div className="flex items-center px-4 h-16 flex-shrink-0 relative">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <motion.div
            className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 relative"
            style={{ background: 'linear-gradient(135deg, #4158D0 0%, #8B5CF6 100%)' }}
            whileHover={{ scale: 1.05, rotate: 5 }}
          >
            <Zap size={16} className="text-white" />
            <div className="absolute inset-0 rounded-xl" style={{ boxShadow: '0 0 20px rgba(88,130,255,0.7)' }} />
          </motion.div>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}
                className="flex flex-col min-w-0"
              >
                <span className="text-sm font-bold tracking-tight truncate" style={{ color: 'var(--text-primary)' }}>
                  SmarterP
                </span>
                <span className="text-xs font-medium" style={{
                  background: 'linear-gradient(90deg, #5882ff, #8B5CF6)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}>
                  Connector
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Close button on mobile drawer */}
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{
              background: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
              color: 'var(--text-muted)',
            }}
          >
            <X size={15} />
          </button>
        )}

        {/* Desktop collapse toggle */}
        {!onClose && (
          <motion.button
            className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center z-10"
            style={{
              background: isDark ? '#1e293b' : '#f1f5f9',
              border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
              color: 'var(--text-tertiary)',
            }}
            onClick={() => {/* handled by parent */}}
            whileHover={{ scale: 1.1, color: '#5882ff' }}
            whileTap={{ scale: 0.9 }}
          >
            {expanded ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
          </motion.button>
        )}
      </div>

      {/* Live status */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mx-3 mb-3 rounded-xl px-3 py-2 flex items-center gap-2"
            style={{ background: 'rgba(88,130,255,0.08)', border: '1px solid rgba(88,130,255,0.18)' }}
          >
            <Activity size={12} style={{ color: '#5882ff' }} />
            <span className="text-xs font-medium" style={{ color: '#5882ff' }}>Systems Operational</span>
            <div className="ml-auto w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#5882ff' }} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-none px-2 pb-4 space-y-1">
        {navGroups.map((group) => (
          <div key={group.group} className="mb-4">
            <AnimatePresence>
              {expanded && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="px-3 mb-1"
                >
                  <span className="text-2xs font-semibold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                    {group.group}
                  </span>
                </motion.div>
              )}
            </AnimatePresence>

            {group.items.map((item) => {
              const Icon = item.icon;
              const path = ROUTES[item.id];
              return (
                <NavLink
                  key={item.id}
                  to={path}
                  className="block mb-0.5"
                  onMouseEnter={() => {
                    if (item.id === 'transactions') prefetchTransactionsOnHover();
                    if (item.id === 'analytics') void prefetchAnalyticsPage('mtd');
                    if (item.id === 'branch') prefetchBranchesChart('mtd');
                  }}
                >
                  {({ isActive }) => (
                    <motion.div
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl relative group"
                      style={{
                        background: isActive
                          ? isDark ? 'rgba(88,130,255,0.14)' : 'rgba(88,130,255,0.10)'
                          : 'transparent',
                        color: isActive ? '#5882ff' : 'var(--text-tertiary)',
                      }}
                      whileHover={{
                        background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
                        color: isActive ? '#5882ff' : 'var(--text-primary)',
                      }}
                      whileTap={{ scale: 0.97 }}
                      transition={{ duration: 0.15 }}
                    >
                      {isActive && (
                        <motion.div
                          layoutId="activeIndicator"
                          className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full"
                          style={{ background: '#5882ff', boxShadow: '0 0 8px rgba(0,184,230,0.8)' }}
                          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                        />
                      )}
                      <Icon size={16} className="flex-shrink-0" style={{ color: isActive ? '#5882ff' : undefined }} />
                      <AnimatePresence>
                        {expanded && (
                          <motion.span
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -8 }}
                            transition={{ duration: 0.15 }}
                            className="text-sm font-medium flex-1 text-left truncate"
                          >
                            {item.label}
                          </motion.span>
                        )}
                      </AnimatePresence>
                      {item.badge && expanded && (
                        <motion.span
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          className="text-2xs font-bold px-1.5 py-0.5 rounded-full flex-shrink-0"
                          style={{
                            background: item.badge === 'AI'
                              ? 'linear-gradient(135deg, #4158D0, #8B5CF6)'
                              : 'rgba(88,130,255,0.18)',
                            color: item.badge === 'AI' ? 'white' : '#5882ff',
                          }}
                        >
                          {item.badge}
                        </motion.span>
                      )}
                      {!expanded && !onClose && (
                        <motion.div
                          className="absolute left-full ml-2 px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap pointer-events-none z-50"
                          style={{
                            background: isDark ? '#1e293b' : 'white',
                            border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
                            color: 'var(--text-primary)',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                          }}
                          initial={{ opacity: 0, x: -4 }}
                          whileHover={{ opacity: 1, x: 0 }}
                        >
                          {item.label}
                        </motion.div>
                      )}
                    </motion.div>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User profile */}
      <div className="p-3 flex-shrink-0" style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}>
        <motion.div
          className="flex items-center gap-3 p-2 rounded-xl cursor-pointer"
          whileHover={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' }}
        >
          <div
            className="w-7 h-7 rounded-lg flex-shrink-0 flex items-center justify-center text-xs font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #4158D0, #8B5CF6)' }}
          >
            {(user?.name ?? 'U').slice(0, 2).toUpperCase()}
          </div>
          <AnimatePresence>
            {expanded && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col min-w-0 flex-1"
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{user?.name ?? 'User'}</span>
                  {user?.role && (
                    <span
                      className="text-2xs font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 capitalize"
                      style={{
                        background: ROLE_COLORS[user.role]?.bg ?? 'rgba(148,163,184,0.15)',
                        color: ROLE_COLORS[user.role]?.color ?? '#94a3b8',
                      }}
                    >
                      {user.role}
                    </span>
                  )}
                </div>
                <span className="text-2xs truncate" style={{ color: 'var(--text-muted)' }}>{user?.email ?? ''}</span>
              </motion.div>
            )}
          </AnimatePresence>
          {expanded && (
            <button
              type="button"
              onClick={handleLogout}
              className="text-2xs font-semibold px-2 py-1 rounded-lg flex-shrink-0"
              style={{ color: '#f87171', border: '1px solid rgba(248,113,113,0.3)' }}
            >
              Logout
            </button>
          )}
        </motion.div>
      </div>
    </>
  );
}

export default function Sidebar() {
  const { sidebarExpanded, setSidebarExpanded, mobileSidebarOpen, setMobileSidebarOpen, isMobile } = useNavigation();
  const { isDark } = useTheme();

  const sidebarBg = isDark
    ? 'linear-gradient(180deg, rgba(5,9,24,0.97) 0%, rgba(7,11,28,0.97) 50%, rgba(5,9,24,0.97) 100%)'
    : 'linear-gradient(180deg, rgba(255,255,255,0.97) 0%, rgba(240,244,255,0.97) 100%)';
  const sidebarBorder = isDark ? '1px solid rgba(88,130,255,0.1)' : '1px solid rgba(88,130,255,0.12)';
  const sidebarShadow = isDark ? '4px 0 32px rgba(0,0,0,0.4)' : '4px 0 16px rgba(0,0,0,0.06)';

  /* ── Mobile: full-screen drawer with backdrop ── */
  if (isMobile) {
    return (
      <AnimatePresence>
        {mobileSidebarOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              key="backdrop"
              className="fixed inset-0 z-40"
              style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileSidebarOpen(false)}
            />
            {/* Drawer */}
            <motion.aside
              key="drawer"
              className="fixed left-0 top-0 h-full z-50 flex flex-col w-72"
              style={{
                background: sidebarBg,
                backdropFilter: 'blur(32px) saturate(200%)',
                borderRight: sidebarBorder,
                boxShadow: sidebarShadow,
              }}
              initial={{ x: -288 }}
              animate={{ x: 0 }}
              exit={{ x: -288 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            >
              <SidebarContent expanded={true} onClose={() => setMobileSidebarOpen(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    );
  }

  /* ── Desktop: fixed collapsible sidebar ── */
  return (
    <motion.aside
      className="fixed left-0 top-0 h-full z-50 flex flex-col"
      animate={{ width: sidebarExpanded ? 240 : 72 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      style={{
        background: sidebarBg,
        backdropFilter: 'blur(32px) saturate(200%)',
        borderRight: sidebarBorder,
        boxShadow: sidebarShadow,
      }}
    >
      <div
        className="flex flex-col h-full"
        onClick={(e) => {
          // Click on the toggle button (the -right-3 button)
          const btn = (e.target as HTMLElement).closest('button[data-collapse]');
          if (btn) setSidebarExpanded(!sidebarExpanded);
        }}
      >
        {/* Render content — pass a fake onClose=undefined to show collapse toggle */}
        <SidebarContent
          expanded={sidebarExpanded}
          onClose={undefined}
        />
      </div>

      {/* Collapse toggle floats outside the scroll area */}
      <motion.button
        data-collapse
        className="absolute -right-3 top-8 w-6 h-6 rounded-full flex items-center justify-center z-10"
        style={{
          background: isDark ? '#1e293b' : '#f1f5f9',
          border: isDark ? '1px solid rgba(255,255,255,0.1)' : '1px solid rgba(0,0,0,0.1)',
          color: 'var(--text-tertiary)',
        }}
        onClick={() => setSidebarExpanded(!sidebarExpanded)}
        whileHover={{ scale: 1.1, color: '#5882ff' }}
        whileTap={{ scale: 0.9 }}
      >
        {sidebarExpanded ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
      </motion.button>
    </motion.aside>
  );
}
