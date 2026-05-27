import { Navigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

interface RoleRouteProps {
  children: React.ReactNode;
  /** Which roles are permitted. If the user's role is not in this list, redirect to /dashboard. */
  allowed: string[];
}

/**
 * Wraps a route element and only renders it when the authenticated user's role
 * is in the `allowed` list. Everyone else is redirected to /dashboard.
 * Must be used inside <ProtectedRoute> so `user` is guaranteed non-null.
 */
export default function RoleRoute({ children, allowed }: RoleRouteProps) {
  const { user } = useAuth();

  if (!user || !allowed.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
