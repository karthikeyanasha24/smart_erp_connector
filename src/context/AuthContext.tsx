import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import { auth, setAuthToken, clearAuthToken, getAuthToken } from '../lib/api';
import { prefetchAll, clearAnalyticsCache, prefetchCriticalDashboard, fetchAndApplySnapshot } from '../hooks/useAnalytics';

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  isManager: boolean;
  canUseAI: boolean;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
  isAdmin: false,
  isManager: false,
  canUseAI: false,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setLoading(false);
      return;
    }
    setAuthToken(token);
    auth.me()
      .then((r) => {
        setUser(r.user);
        // Snapshot first (< 20 ms, reads server cache) → then full refresh in background
        void fetchAndApplySnapshot().then(() => {
          void prefetchCriticalDashboard();
          void prefetchAll();
        });
      })
      .catch(() => {
        clearAuthToken();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await auth.login(email, password);
    setAuthToken(res.access_token);
    localStorage.setItem('smarterp_token', res.access_token);
    setUser(res.user);
    // Snapshot pre-warms the SWR cache so dashboard renders on first paint
    void fetchAndApplySnapshot().then(() => {
      void prefetchCriticalDashboard();
      void prefetchAll();
    });
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    clearAnalyticsCache();
    setUser(null);
  }, []);

  const isAdmin   = user?.role === 'admin';
  const isManager = user?.role === 'manager' || user?.role === 'admin';
  const canUseAI  = user?.role === 'admin' || user?.role === 'manager' || user?.role === 'analyst';

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin, isManager, canUseAI }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
