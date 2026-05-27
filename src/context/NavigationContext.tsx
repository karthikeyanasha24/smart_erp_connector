import { createContext, useContext, useState, type ReactNode } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { Page } from '../types';
import { ROUTES, pathToPage } from '../lib/routes';

interface NavigationContextValue {
  currentPage: Page;
  navigate: (page: Page) => void;
  sidebarExpanded: boolean;
  setSidebarExpanded: (v: boolean) => void;
}

const NavigationContext = createContext<NavigationContextValue>({
  currentPage: 'dashboard',
  navigate: () => {},
  sidebarExpanded: true,
  setSidebarExpanded: () => {},
});

export function NavigationProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const currentPage = pathToPage(location.pathname);

  return (
    <NavigationContext.Provider value={{
      currentPage,
      navigate: (page: Page) => navigate(ROUTES[page]),
      sidebarExpanded,
      setSidebarExpanded,
    }}>
      {children}
    </NavigationContext.Provider>
  );
}

export const useNavigation = () => useContext(NavigationContext);
