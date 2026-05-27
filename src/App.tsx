import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { NavigationProvider } from './context/NavigationContext';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import RoleRoute from './components/auth/RoleRoute';
import Layout from './components/layout/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Analytics from './pages/Analytics';
import AIQuery from './pages/AIQuery';
import Transactions from './pages/Transactions';
import Reports from './pages/Reports';
import Branch from './pages/Branch';
import Product from './pages/Product';
import Insights from './pages/Insights';
import Settings from './pages/Settings';
import { pathToPage } from './lib/routes';

function AppLayout() {
  const { pathname } = useLocation();
  const pageKey = pathToPage(pathname);
  return (
    <Layout pageKey={pageKey}>
      <Outlet />
    </Layout>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <NavigationProvider>
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route element={<ProtectedRoute><Outlet /></ProtectedRoute>}>
                <Route element={<AppLayout />}>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/analytics" element={<Analytics />} />
                  <Route path="/ai-query" element={
                    <RoleRoute allowed={['admin', 'manager', 'analyst']}>
                      <AIQuery />
                    </RoleRoute>
                  } />
                  <Route path="/transactions" element={<Transactions />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/branch" element={<Branch />} />
                  <Route path="/product" element={<Product />} />
                  <Route path="/insights" element={
                    <RoleRoute allowed={['admin', 'manager', 'analyst']}>
                      <Insights />
                    </RoleRoute>
                  } />
                  <Route path="/settings" element={
                    <RoleRoute allowed={['admin', 'manager']}>
                      <Settings />
                    </RoleRoute>
                  } />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </NavigationProvider>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
