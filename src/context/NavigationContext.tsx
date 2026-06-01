import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { Page } from '../types';
import { ROUTES, pathToPage } from '../lib/routes';

interface NavigationContextValue {
  currentPage: Page;
  navigate: (page: Page) => void;
  sidebarExpanded: boolean;
  setSidebarExpanded: (v: boolean) => void;
  mobileSidebarOpen: boolean;
  setMobileSidebarOpen: (v: boolean) => void;
  isMobile: boolean;
}

const NavigationContext = createContext<NavigationContextValue>({
  currentPage: 'dashboard',
  navigate: () => {},
  sidebarExpanded: true,
  setSidebarExpanded: () => {},
  mobileSidebarOpen: false,
  setMobileSidebarOpen: () => {},
  isMobile: false,
});

export function NavigationProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const currentPage = pathToPage(location.pathname);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)');
    const handler = (e: MediaQueryListEvent) => {
      setIsMobile(e.matches);
      if (!e.matches) setMobileSidebarOpen(false); // close drawer when going desktop
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileSidebarOpen(false);
  }, [location.pathname]);

  return (
    <NavigationContext.Provider value={{
      currentPage,
      navigate: (page: Page) => navigate(ROUTES[page]),
      sidebarExpanded,
      setSidebarExpanded,
      mobileSidebarOpen,
      setMobileSidebarOpen,
      isMobile,
    }}>
      {children}
    </NavigationContext.Provider>
  );
}

export const useNavigation = () => useContext(NavigationContext);
