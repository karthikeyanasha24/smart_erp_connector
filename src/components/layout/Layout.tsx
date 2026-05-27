import { type ReactNode, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigation } from '../../context/NavigationContext';
import { useTheme } from '../../context/ThemeContext';
import AnimatedBackground from './AnimatedBackground';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import { pageVariants } from '../../lib/motion';
import { prefetchTransactionsSnapshots } from '../../hooks/useAnalytics';

interface LayoutProps {
  children: ReactNode;
  pageKey: string;
}

export default function Layout({ children, pageKey }: LayoutProps) {
  const { sidebarExpanded } = useNavigation();
  const { isDark } = useTheme();
  const sidebarW = sidebarExpanded ? 240 : 72;

  useEffect(() => {
    prefetchTransactionsSnapshots();
    // Analytics tabs prefetch on sidebar hover only — not on every page mount.
  }, []);

  return (
    <div
      className="min-h-screen relative"
      style={{ background: isDark ? '#050918' : '#f0f4ff' }}
    >
      <AnimatedBackground />
      <Sidebar />
      <Topbar />

      <motion.main
        className="relative z-10"
        style={{
          marginLeft: sidebarW,
          paddingTop: 64,
          transition: 'margin-left 0.3s cubic-bezier(0.4,0,0.2,1)',
          minHeight: '100vh',
        }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={pageKey}
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            className="p-6"
            style={{ minHeight: 'calc(100vh - 64px)' }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </motion.main>
    </div>
  );
}
