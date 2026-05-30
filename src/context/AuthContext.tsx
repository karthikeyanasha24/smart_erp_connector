import { createContext, useContext, useState, useEffect, useCallback, useRef, type ReactNode } from 'react';
import { auth, setAuthToken, clearAuthToken, getAuthToken } from '../lib/api';
import { clearAnalyticsCache, prefetchCriticalDashboard } from '../hooks/useAnalytics';

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

const CACHED_USER_KEY = 'smarterp_user';

/** Read the last-known user from localStorage — used for optimistic instant render. */
function readCachedUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(CACHED_USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

function writeCachedUser(u: AuthUser) {
  try { localStorage.setItem(CACHED_USER_KEY, JSON.stringify(u)); } catch { /* ignore */ }
}

function clearCachedUser() {
  try { localStorage.removeItem(CACHED_USER_KEY); } catch { /* ignore */ }
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
  const token = getAuthToken();

  // ── Optimistic initial state ──────────────────────────────────────────────
  // If a JWT token exists we ASSUME the user is logged in using the last-cached
  // profile. The page renders immediately — no loading flash, no blank white screen.
  // We then verify the token with the backend in the background.
  const cachedUser = token ? readCachedUser() : null;

  const [user, setUser]       = useState<AuthUser | null>(cachedUser);
  const [loading, setLoading] = useState<boolean>(!cachedUser && !!token);
  // verifying = true means the silent background re-validation is in flight
  const verifying = useRef(false);

  useEffect(() => {
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }

    setAuthToken(token);

    // If we already have a cached user, skip the loading state entirely —
    // just verify silently in the background.
    if (cachedUser && !verifying.current) {
      verifying.current = true;
      auth.me()
        .then((r) => {
          setUser(r.user);
          writeCachedUser(r.user);
          // Background data prefetch (non-blocking)
          void prefetchCriticalDashboard();
        })
        .catch(() => {
          // Token is invalid — sign out silently
          clearAuthToken();
          clearCachedUser();
          setUser(null);
        })
        .finally(() => { verifying.current = false; });
      return;
    }

    // No cached user but token exists → show minimal loader while we verify
    if (!cachedUser) {
      setLoading(true);
      auth.me()
        .then((r) => {
          setUser(r.user);
          writeCachedUser(r.user);
          void prefetchCriticalDashboard();
        })
        .catch(() => {
          clearAuthToken();
          clearCachedUser();
          setUser(null);
        })
        .finally(() => setLoading(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await auth.login(email, password);
    setAuthToken(res.access_token);
    localStorage.setItem('smarterp_token', res.access_token);
    const u = res.user as AuthUser;
    setUser(u);
    writeCachedUser(u);
    void prefetchCriticalDashboard();
  }, []);

  const logout = useCallback(() => {
    clearAuthToken();
    clearCachedUser();
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

export function useAuth() {
  return useContext(AuthContext);
}
