import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

/**
 * ProtectedRoute — renders children immediately if a user is present (optimistic).
 * Only blocks with a full-screen loader on the very first visit (no cached user yet).
 * Background JWT verification happens in AuthContext without blocking the UI.
 */
export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  // loading=true only when there's a token but NO cached user yet (first-ever login).
  // On subsequent reloads, user is set from the localStorage cache → loading=false → instant render.
  if (loading) {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center gap-4"
        style={{ background: 'var(--bg-base, #0b0e14)' }}
        role="status"
        aria-busy="true"
        aria-label="Loading"
      >
        <div className="w-8 h-8 rounded-full animate-spin border-2 border-cyan-400/30 border-t-cyan-400" />
        <p className="text-xs font-medium" style={{ color: 'rgba(148,163,184,0.6)' }}>
          SmarterPConnector
        </p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
