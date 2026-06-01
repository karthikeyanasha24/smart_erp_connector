import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User, Bell, Shield, Palette, Database, Brain, Globe,
  ChevronRight, Sun, Moon, Check, Lock, Key, Mail,
  Activity, Sparkles, Users, Plus, Trash2, Edit3, X, Loader2,
  RefreshCw, Server, Cpu, HardDrive, Wifi, WifiOff,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { auth, analytics, type ManagedUser } from '../lib/api';

const stagger = { animate: { transition: { staggerChildren: 0.06 } } };
const item = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 280, damping: 26 } },
};

type SectionId = 'profile' | 'appearance' | 'notifications' | 'security' | 'ai' | 'data' | 'users';

const BASE_SECTIONS: { id: SectionId; label: string; icon: any; desc: string; adminOnly?: boolean }[] = [
  { id: 'profile', label: 'Profile', icon: User, desc: 'Account information' },
  { id: 'appearance', label: 'Appearance', icon: Palette, desc: 'Theme & display' },
  { id: 'notifications', label: 'Notifications', icon: Bell, desc: 'Alert preferences' },
  { id: 'security', label: 'Security', icon: Shield, desc: 'Auth & permissions' },
  { id: 'ai', label: 'AI Settings', icon: Brain, desc: 'Model configuration' },
  { id: 'data', label: 'Data & APIs', icon: Database, desc: 'Integrations' },
  { id: 'users', label: 'User Management', icon: Users, desc: 'Add & manage users', adminOnly: true },
];

const ROLE_META: Record<string, { color: string; bg: string }> = {
  admin:   { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  manager: { color: '#818cf8', bg: 'rgba(99,102,241,0.12)' },
  analyst: { color: '#34d399', bg: 'rgba(52,211,153,0.12)' },
  viewer:  { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' },
};

function Toggle2({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <motion.button onClick={() => onChange(!checked)}
      className="w-10 h-5.5 rounded-full relative flex-shrink-0"
      style={{
        background: checked ? 'linear-gradient(135deg, #00b8e6, #00e67a)' : 'rgba(100,116,139,0.3)',
        boxShadow: checked ? '0 0 12px rgba(0,184,230,0.3)' : 'none',
        height: 22,
      }}
      animate={{ background: checked ? 'linear-gradient(135deg, #00b8e6, #00e67a)' : 'rgba(100,116,139,0.3)' }}
    >
      <motion.div className="w-4 h-4 bg-white rounded-full absolute top-[3px]"
        animate={{ left: checked ? 'calc(100% - 19px)' : 3 }}
        transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
    </motion.button>
  );
}

export default function Settings() {
  const { isDark, toggleTheme } = useTheme();
  const { isAdmin, user } = useAuth();
  const [activeSection, setActiveSection] = useState<SectionId>('appearance');

  // Sections filtered by role
  const sections = BASE_SECTIONS.filter((s) => !s.adminOnly || isAdmin);

  // ── User management state ─────────────────────────────────────────────────
  const [users, setUsers]           = useState<ManagedUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersError, setUsersError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingUser, setEditingUser] = useState<ManagedUser | null>(null);
  const [formData, setFormData] = useState({ name: '', email: '', password: '', role: 'viewer' });
  const [formBusy, setFormBusy] = useState(false);
  const [formError, setFormError] = useState('');

  const loadUsers = useCallback(async () => {
    if (!isAdmin) return;
    setUsersLoading(true);
    setUsersError('');
    try {
      const res = await auth.getUsers();
      setUsers(res.users ?? []);
    } catch (e) {
      setUsersError(e instanceof Error ? e.message : 'Failed to load users');
    } finally {
      setUsersLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (activeSection === 'users' && isAdmin) loadUsers();
  }, [activeSection, isAdmin, loadUsers]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormBusy(true);
    setFormError('');
    try {
      await auth.createUser(formData);
      setShowCreateForm(false);
      setFormData({ name: '', email: '', password: '', role: 'viewer' });
      await loadUsers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setFormBusy(false);
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setFormBusy(true);
    setFormError('');
    try {
      await auth.updateUser(editingUser.id, {
        name: formData.name,
        role: formData.role,
        ...(formData.password ? { password: formData.password } : {}),
      });
      setEditingUser(null);
      await loadUsers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to update user');
    } finally {
      setFormBusy(false);
    }
  };

  const handleToggleActive = async (u: ManagedUser) => {
    try {
      await auth.updateUser(u.id, { is_active: !u.is_active });
      await loadUsers();
    } catch { /* silent */ }
  };

  const handleDeleteUser = async (id: string) => {
    if (!confirm('Delete this user permanently?')) return;
    try {
      await auth.deleteUser(id);
      await loadUsers();
    } catch { /* silent */ }
  };

  // ── System health state ───────────────────────────────────────────────────
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState('');

  const loadHealth = useCallback(async () => {
    setHealthLoading(true);
    setHealthError('');
    try {
      const res = await analytics.health();
      setHealth(res);
    } catch (e) {
      setHealthError(e instanceof Error ? e.message : 'Health check failed');
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeSection === 'data') void loadHealth();
  }, [activeSection, loadHealth]);

  const [settings, setSettings] = useState({
    emailNotifs: true,
    pushNotifs: true,
    fraudAlerts: true,
    weeklyReport: false,
    aiInsights: true,
    darkMode: isDark,
    compactMode: false,
    animations: true,
    autoRefresh: true,
    aiSuggestions: true,
    predictiveMode: true,
    dataRetention: '90',
  });

  const toggle = (key: keyof typeof settings) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const sectionContent: Partial<Record<SectionId, React.ReactNode>> = {
    profile: (
      <div className="space-y-6">
        <div className="flex items-center gap-4 pb-5" style={{ borderBottom: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
          <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 20px rgba(0,184,230,0.3)' }}>
            {(user?.name ?? 'U').slice(0, 2).toUpperCase()}
          </div>
          <div>
            <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{user?.name ?? '—'}</h3>
            <p className="text-sm capitalize" style={{ color: 'var(--text-muted)' }}>{user?.role ?? 'viewer'}</p>
            <p className="text-xs mt-0.5" style={{ color: '#00b8e6' }}>{user?.email ?? ''}</p>
          </div>
          <div className="ml-auto">
            <span className="px-3 py-1 rounded-lg text-xs font-bold capitalize"
              style={{
                background: user?.role === 'admin' ? 'rgba(245,158,11,0.15)' : user?.role === 'manager' ? 'rgba(99,102,241,0.15)' : 'rgba(148,163,184,0.15)',
                color:      user?.role === 'admin' ? '#f59e0b'               : user?.role === 'manager' ? '#818cf8'               : '#94a3b8',
              }}>
              {user?.role ?? 'viewer'}
            </span>
          </div>
        </div>
        {[
          { label: 'Full Name', value: user?.name ?? '—', icon: User },
          { label: 'Email', value: user?.email ?? '—', icon: Mail },
          { label: 'Role', value: (user?.role ?? 'viewer').charAt(0).toUpperCase() + (user?.role ?? 'viewer').slice(1), icon: Key },
          { label: 'Organization', value: 'SmarterP Connector', icon: Globe },
        ].map(field => {
          const Icon = field.icon;
          return (
            <div key={field.label} className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }}>
                <Icon size={14} style={{ color: 'var(--text-muted)' }} />
              </div>
              <div className="flex-1">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{field.label}</p>
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{field.value}</p>
              </div>
              <ChevronRight size={13} style={{ color: 'var(--text-muted)' }} />
            </div>
          );
        })}
      </div>
    ),

    appearance: (
      <div className="space-y-5">
        <div>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Color Theme</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {[
              { label: 'Dark Mode', desc: 'Cinematic dark experience', icon: Moon, active: isDark },
              { label: 'Light Mode', desc: 'Premium minimal design', icon: Sun, active: !isDark },
            ].map(theme => {
              const Icon = theme.icon;
              return (
                <motion.button key={theme.label} onClick={toggleTheme}
                  className="p-4 rounded-2xl text-left relative overflow-hidden"
                  style={{
                    background: theme.active ? isDark ? 'rgba(0,184,230,0.1)' : 'rgba(0,184,230,0.08)' : isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)',
                    border: theme.active ? '1px solid rgba(0,184,230,0.3)' : isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
                  }}
                  whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  {theme.active && (
                    <div className="absolute top-2 right-2 w-4 h-4 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(0,184,230,0.2)' }}>
                      <Check size={9} style={{ color: '#00b8e6' }} />
                    </div>
                  )}
                  <Icon size={20} style={{ color: theme.active ? '#00b8e6' : 'var(--text-muted)' }} className="mb-3" />
                  <p className="text-sm font-semibold" style={{ color: theme.active ? '#00b8e6' : 'var(--text-primary)' }}>{theme.label}</p>
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{theme.desc}</p>
                </motion.button>
              );
            })}
          </div>
        </div>

        <div style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)', paddingTop: 20 }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>Display Options</h3>
          <div className="space-y-4">
            {[
              { key: 'compactMode' as const, label: 'Compact Mode', desc: 'Reduce padding and whitespace' },
              { key: 'animations' as const, label: 'Smooth Animations', desc: 'Framer Motion transitions and effects' },
            ].map(opt => (
              <div key={opt.key} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{opt.label}</p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{opt.desc}</p>
                </div>
                <Toggle2 checked={settings[opt.key] as boolean} onChange={() => toggle(opt.key)} />
              </div>
            ))}
          </div>
        </div>

        <div style={{ borderTop: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)', paddingTop: 20 }}>
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Accent Color</h3>
          <div className="flex items-center gap-2.5">
            {['#00b8e6', '#00e67a', '#a78bfa', '#f97316', '#ec4899'].map(color => (
              <motion.button key={color}
                className="w-8 h-8 rounded-xl border-2"
                style={{ background: color, borderColor: color === '#00b8e6' ? 'white' : 'transparent' }}
                whileHover={{ scale: 1.15 }} whileTap={{ scale: 0.9 }} />
            ))}
          </div>
        </div>
      </div>
    ),

    notifications: (
      <div className="space-y-5">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Notification Preferences</h3>
        {[
          { key: 'emailNotifs' as const, label: 'Email Notifications', desc: 'Receive reports and alerts via email', icon: Mail },
          { key: 'pushNotifs' as const, label: 'Push Notifications', desc: 'Real-time browser notifications', icon: Bell },
          { key: 'fraudAlerts' as const, label: 'Fraud Alerts', desc: 'Immediate alerts for suspicious activity', icon: Shield },
          { key: 'weeklyReport' as const, label: 'Weekly Digest', desc: 'Automated weekly performance report', icon: Activity },
          { key: 'aiInsights' as const, label: 'AI Insight Notifications', desc: 'New pattern detections and recommendations', icon: Brain },
        ].map(notif => {
          const Icon = notif.icon;
          return (
            <div key={notif.key} className="flex items-center gap-3 p-3.5 rounded-2xl"
              style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: settings[notif.key] ? 'rgba(0,184,230,0.1)' : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' }}>
                <Icon size={15} style={{ color: settings[notif.key] ? '#00b8e6' : 'var(--text-muted)' }} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{notif.label}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{notif.desc}</p>
              </div>
              <Toggle2 checked={settings[notif.key] as boolean} onChange={() => toggle(notif.key)} />
            </div>
          );
        })}
      </div>
    ),

    security: (
      <div className="space-y-5">
        <div className="p-4 rounded-2xl flex items-center gap-3"
          style={{ background: 'rgba(0,230,122,0.06)', border: '1px solid rgba(0,230,122,0.15)' }}>
          <Shield size={16} style={{ color: '#00e67a' }} />
          <div>
            <p className="text-sm font-semibold" style={{ color: '#00e67a' }}>Security Score: 94/100</p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Your account is well protected</p>
          </div>
        </div>
        {[
          { label: 'Two-Factor Authentication', desc: 'TOTP enabled via authenticator app', status: 'Enabled', color: '#00e67a', icon: Key },
          { label: 'Session Management', desc: '2 active sessions', status: 'Review', color: '#ffb800', icon: Globe },
          { label: 'API Access Keys', desc: '3 keys active, 1 expires soon', status: 'Manage', color: '#00b8e6', icon: Lock },
          { label: 'Audit Log', desc: 'All actions are logged', status: 'View', color: '#a78bfa', icon: Activity },
        ].map(item => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="flex items-center gap-3 p-3.5 rounded-2xl cursor-pointer group"
              style={{ border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}
            >
              <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                style={{ background: `${item.color}15` }}>
                <Icon size={15} style={{ color: item.color }} />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{item.label}</p>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{item.desc}</p>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-lg"
                style={{ background: `${item.color}18`, color: item.color }}>{item.status}</span>
            </div>
          );
        })}
      </div>
    ),

    ai: (
      <div className="space-y-5">
        <div className="p-4 rounded-2xl"
          style={{ background: 'linear-gradient(135deg, rgba(0,184,230,0.08), rgba(0,230,122,0.08))', border: '1px solid rgba(0,184,230,0.15)' }}>
          <div className="flex items-center gap-2 mb-1">
            <Sparkles size={14} style={{ color: '#00b8e6' }} />
            <p className="text-sm font-semibold" style={{ color: '#00b8e6' }}>AI Engine: GPT-4 Turbo Enhanced</p>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Fine-tuned on 18 months of financial transaction data</p>
        </div>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>AI Configuration</h3>
        {[
          { key: 'aiSuggestions' as const, label: 'AI Suggestions', desc: 'Contextual recommendations throughout the platform' },
          { key: 'predictiveMode' as const, label: 'Predictive Analytics', desc: 'Forward-looking forecasts and trend prediction' },
          { key: 'autoRefresh' as const, label: 'Auto-Refresh Insights', desc: 'Automatically update insights every 5 minutes' },
        ].map(opt => (
          <div key={opt.key} className="flex items-center justify-between p-3.5 rounded-2xl"
            style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', border: isDark ? '1px solid rgba(255,255,255,0.05)' : '1px solid rgba(0,0,0,0.05)' }}>
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{opt.label}</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{opt.desc}</p>
            </div>
            <Toggle2 checked={settings[opt.key] as boolean} onChange={() => toggle(opt.key)} />
          </div>
        ))}
        <div className="p-4 rounded-2xl"
          style={{ background: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)', border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
          <p className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Confidence Threshold</p>
          <div className="relative h-1.5 rounded-full" style={{ background: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)' }}>
            <div className="absolute left-0 top-0 h-full w-4/5 rounded-full"
              style={{ background: 'linear-gradient(90deg, #00b8e6, #00e67a)' }} />
            <div className="absolute top-1/2 -translate-y-1/2 w-4 h-4 rounded-full bg-white border-2 border-primary-500"
              style={{ left: 'calc(80% - 8px)', boxShadow: '0 0 8px rgba(0,184,230,0.5)' }} />
          </div>
          <div className="flex justify-between mt-1.5">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>60%</span>
            <span className="text-xs font-semibold" style={{ color: '#00b8e6' }}>80% (current)</span>
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>99%</span>
          </div>
        </div>
      </div>
    ),

    users: (
      <div className="space-y-5">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>User Management</h3>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {users.length} user{users.length !== 1 ? 's' : ''} in total
            </p>
          </div>
          <motion.button
            onClick={() => { setShowCreateForm(true); setEditingUser(null); setFormData({ name: '', email: '', password: '', role: 'viewer' }); setFormError(''); }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-white"
            style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)', boxShadow: '0 2px 12px rgba(99,102,241,0.3)' }}
            whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          >
            <Plus size={12} /> Add User
          </motion.button>
        </div>

        {/* Create / Edit form */}
        <AnimatePresence>
          {(showCreateForm || editingUser) && (
            <motion.form
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              onSubmit={editingUser ? handleUpdateUser : handleCreateUser}
              className="p-4 rounded-2xl space-y-3"
              style={{ background: isDark ? 'rgba(99,102,241,0.07)' : 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.2)' }}
            >
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs font-semibold" style={{ color: '#818cf8' }}>
                  {editingUser ? `Edit: ${editingUser.name}` : 'New User'}
                </p>
                <button type="button" onClick={() => { setShowCreateForm(false); setEditingUser(null); }}>
                  <X size={13} style={{ color: 'var(--text-muted)' }} />
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <div>
                  <label className="text-2xs font-medium" style={{ color: 'var(--text-muted)' }}>Full Name</label>
                  <input
                    required
                    type="text"
                    placeholder="Jane Smith"
                    value={formData.name}
                    onChange={(e) => setFormData(p => ({ ...p, name: e.target.value }))}
                    className="mt-0.5 w-full px-2.5 py-2 rounded-xl text-xs outline-none"
                    style={{ background: isDark ? 'rgba(0,0,0,0.3)' : 'white', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--text-primary)' }}
                  />
                </div>
                <div>
                  <label className="text-2xs font-medium" style={{ color: 'var(--text-muted)' }}>Email</label>
                  <input
                    required={!editingUser}
                    type="email"
                    placeholder="jane@example.com"
                    value={formData.email}
                    onChange={(e) => setFormData(p => ({ ...p, email: e.target.value }))}
                    disabled={!!editingUser}
                    className="mt-0.5 w-full px-2.5 py-2 rounded-xl text-xs outline-none"
                    style={{ background: isDark ? 'rgba(0,0,0,0.3)' : 'white', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--text-primary)', opacity: editingUser ? 0.5 : 1 }}
                  />
                </div>
                <div>
                  <label className="text-2xs font-medium" style={{ color: 'var(--text-muted)' }}>
                    {editingUser ? 'New Password (optional)' : 'Password'}
                  </label>
                  <input
                    required={!editingUser}
                    type="password"
                    placeholder={editingUser ? 'Leave blank to keep' : '••••••••'}
                    value={formData.password}
                    onChange={(e) => setFormData(p => ({ ...p, password: e.target.value }))}
                    className="mt-0.5 w-full px-2.5 py-2 rounded-xl text-xs outline-none"
                    style={{ background: isDark ? 'rgba(0,0,0,0.3)' : 'white', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--text-primary)' }}
                  />
                </div>
                <div>
                  <label className="text-2xs font-medium" style={{ color: 'var(--text-muted)' }}>Role</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData(p => ({ ...p, role: e.target.value }))}
                    className="mt-0.5 w-full px-2.5 py-2 rounded-xl text-xs outline-none"
                    style={{ background: isDark ? 'rgba(0,0,0,0.3)' : 'white', border: '1px solid rgba(99,102,241,0.25)', color: 'var(--text-primary)' }}
                  >
                    <option value="admin">Admin</option>
                    <option value="manager">Manager</option>
                    <option value="analyst">Analyst</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>
              </div>
              {formError && <p className="text-xs text-red-400">{formError}</p>}
              <motion.button
                type="submit"
                disabled={formBusy}
                className="w-full py-2 rounded-xl text-xs font-semibold text-white flex items-center justify-center gap-1.5"
                style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)', opacity: formBusy ? 0.6 : 1 }}
                whileTap={{ scale: 0.98 }}
              >
                {formBusy ? <Loader2 size={12} className="animate-spin" /> : null}
                {editingUser ? 'Save Changes' : 'Create User'}
              </motion.button>
            </motion.form>
          )}
        </AnimatePresence>

        {/* Error state */}
        {usersError && (
          <div className="p-3 rounded-xl text-xs" style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)', color: '#fca5a5' }}>
            {usersError}
          </div>
        )}

        {/* Loading spinner */}
        {usersLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        )}

        {/* User list */}
        {!usersLoading && users.map((u) => {
          const meta = ROLE_META[u.role] ?? ROLE_META.viewer;
          return (
            <div key={u.id} className="flex items-center gap-3 p-3.5 rounded-2xl"
              style={{
                border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)',
                opacity: u.is_active ? 1 : 0.5,
              }}>
              <div className="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                style={{ background: 'linear-gradient(135deg, #4158D0, #8B5CF6)' }}>
                {u.name.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>{u.name}</p>
                  <span className="text-2xs font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 capitalize"
                    style={{ background: meta.bg, color: meta.color }}>{u.role}</span>
                  {!u.is_active && (
                    <span className="text-2xs font-bold px-1.5 py-0.5 rounded-full flex-shrink-0"
                      style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171' }}>Inactive</span>
                  )}
                </div>
                <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{u.email}</p>
              </div>
              <div className="flex items-center gap-1.5 flex-shrink-0">
                <motion.button
                  onClick={() => { setEditingUser(u); setShowCreateForm(false); setFormData({ name: u.name, email: u.email, password: '', role: u.role }); setFormError(''); }}
                  className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' }}
                  whileHover={{ scale: 1.1 }}
                  title="Edit user"
                >
                  <Edit3 size={12} style={{ color: 'var(--text-muted)' }} />
                </motion.button>
                <motion.button
                  onClick={() => handleToggleActive(u)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: u.is_active ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)' }}
                  whileHover={{ scale: 1.1 }}
                  title={u.is_active ? 'Deactivate' : 'Activate'}
                >
                  <Shield size={12} style={{ color: u.is_active ? '#22c55e' : '#f87171' }} />
                </motion.button>
                <motion.button
                  onClick={() => handleDeleteUser(u.id)}
                  className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: 'rgba(239,68,68,0.08)' }}
                  whileHover={{ scale: 1.1 }}
                  title="Delete user"
                >
                  <Trash2 size={12} style={{ color: '#f87171' }} />
                </motion.button>
              </div>
            </div>
          );
        })}

        {!usersLoading && users.length === 0 && !usersError && (
          <div className="text-center py-8">
            <Users size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 8px' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No users found</p>
          </div>
        )}
      </div>
    ),

    data: (
      <div className="space-y-5">
        {/* Header with refresh */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>System Status</h3>
          <motion.button
            type="button"
            onClick={() => void loadHealth()}
            disabled={healthLoading}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-semibold"
            style={{ background: isDark ? 'rgba(0,184,230,0.08)' : 'rgba(0,184,230,0.06)', color: '#00b8e6', border: '1px solid rgba(0,184,230,0.2)' }}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.97 }}
          >
            <RefreshCw size={11} className={healthLoading ? 'animate-spin' : ''} />
            Refresh
          </motion.button>
        </div>

        {healthError && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#f87171' }}>
            <WifiOff size={12} />{healthError}
          </div>
        )}

        {healthLoading && !health && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
          </div>
        )}

        {/* Overall banner */}
        {health && (
          <div className="p-3.5 rounded-2xl flex items-center gap-3"
            style={{
              background: health.success ? 'rgba(0,230,122,0.06)' : 'rgba(239,68,68,0.06)',
              border: health.success ? '1px solid rgba(0,230,122,0.2)' : '1px solid rgba(239,68,68,0.2)',
            }}>
            {health.success
              ? <Wifi size={16} style={{ color: '#00e67a' }} />
              : <WifiOff size={16} style={{ color: '#f87171' }} />}
            <div>
              <p className="text-sm font-semibold" style={{ color: health.success ? '#00e67a' : '#f87171' }}>
                {health.success ? 'All systems operational' : 'Degraded — SQL Server offline'}
              </p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                ERP analytics pipeline status
              </p>
            </div>
          </div>
        )}

        {/* Data sources */}
        {health && (() => {
          const mssql = (health.mssql as Record<string, any>) ?? {};
          const pg    = (health.postgres as Record<string, any>) ?? {};
          const cacheStats = (health.cache as Record<string, any>) ?? {};

          const sources = [
            {
              name: 'SQL Server (ERP)',
              type: 'Primary data source',
              icon: Server,
              ok: !!mssql.connected,
              detail: mssql.connected
                ? `${mssql.database ?? 'connected'}`
                : (mssql.error ?? 'Offline'),
              color: '#00b8e6',
            },
            {
              name: 'PostgreSQL (Cache)',
              type: 'Cache persistence layer',
              icon: HardDrive,
              ok: !!pg.connected,
              detail: pg.connected
                ? `${pg.database ?? 'connected'}`
                : (pg.error ?? 'Offline'),
              color: '#336791',
            },
            {
              name: 'FastAPI Backend',
              type: 'Analytics API server',
              icon: Cpu,
              ok: true,
              detail: 'Responding normally',
              color: '#00e67a',
            },
            {
              name: 'AI Engine (Claude)',
              type: 'Natural language query & insights',
              icon: Brain,
              ok: true,
              detail: 'claude-3-5-sonnet',
              color: '#a78bfa',
            },
          ];

          return (
            <div className="space-y-2.5">
              {sources.map(src => {
                const Icon = src.icon;
                return (
                  <div key={src.name} className="flex items-center gap-3 p-3.5 rounded-2xl"
                    style={{ border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: `${src.color}18` }}>
                      <Icon size={15} style={{ color: src.color }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{src.name}</p>
                      <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{src.type} · {src.detail}</p>
                    </div>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
                      style={{
                        background: src.ok ? 'rgba(0,230,122,0.1)' : 'rgba(239,68,68,0.1)',
                        color: src.ok ? '#00e67a' : '#f87171',
                      }}>
                      {src.ok ? 'Connected' : 'Offline'}
                    </span>
                  </div>
                );
              })}
            </div>
          );
        })()}

        {/* Cache stats */}
        {health && (() => {
          const cs = (health.cache as Record<string, any>) ?? {};
          const entries  = cs.entries  ?? 0;
          const hits     = cs.hits     ?? 0;
          const misses   = cs.misses   ?? 0;
          const hitRate  = (hits + misses) > 0 ? Math.round(hits / (hits + misses) * 100) : 0;
          const memKb    = cs.memory_kb != null ? `${Math.round(cs.memory_kb / 1024 * 10) / 10} MB` : null;

          return (
            <div style={{ paddingTop: 16, borderTop: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.06)' }}>
              <p className="text-sm font-semibold mb-3" style={{ color: 'var(--text-primary)' }}>Cache Statistics</p>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Entries', value: String(entries) },
                  { label: 'Hit Rate', value: `${hitRate}%` },
                  { label: 'Hits', value: String(hits) },
                  { label: 'Memory', value: memKb ?? '—' },
                ].map(stat => (
                  <div key={stat.label} className="p-3 rounded-xl text-center"
                    style={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)', border: isDark ? '1px solid rgba(255,255,255,0.06)' : '1px solid rgba(0,0,0,0.05)' }}>
                    <p className="text-base font-bold tabular-nums" style={{ color: '#00b8e6' }}>{stat.value}</p>
                    <p className="text-2xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>
          );
        })()}
      </div>
    ),
  };

  return (
    <motion.div variants={stagger} initial="initial" animate="animate" className="space-y-5">

      {/* Header */}
      <motion.div variants={item} className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold" style={{
            background: isDark ? 'linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%)' : 'linear-gradient(135deg, #0f172a 0%, #334155 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
          }}>Settings</h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Configure your workspace and preferences</p>
        </div>
        <motion.button className="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white"
          style={{ background: 'linear-gradient(135deg, #00b8e6, #00e67a)', boxShadow: '0 0 20px rgba(0,184,230,0.3)' }}
          whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
          <Check size={12} /> Save Changes
        </motion.button>
      </motion.div>

      <div className="grid grid-cols-12 gap-4 items-start">
        {/* Sidebar nav */}
        <motion.div variants={item} className="col-span-12 md:col-span-3">
          <div className="rounded-2xl overflow-x-auto md:overflow-hidden flex flex-row md:flex-col scrollbar-none"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
            }}>
            {sections.map(sec => {
              const Icon = sec.icon;
              const isActive = activeSection === sec.id;
              return (
                <motion.button key={sec.id} onClick={() => setActiveSection(sec.id)}
                  className="flex-shrink-0 md:w-full flex items-center gap-3 px-3 md:px-4 py-3 md:py-3.5 relative"
                  style={{
                    background: isActive ? isDark ? 'rgba(0,184,230,0.08)' : 'rgba(0,184,230,0.06)' : 'transparent',
                    borderBottom: isDark ? '1px solid rgba(255,255,255,0.04)' : '1px solid rgba(0,0,0,0.04)',
                  }}
                  whileHover={{ background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.03)' }}>
                  {isActive && (
                    <motion.div layoutId="settingsActive" className="absolute left-0 top-0 bottom-0 w-0.5"
                      style={{ background: '#00b8e6' }} />
                  )}
                  <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                    style={{
                      background: isActive ? 'rgba(0,184,230,0.15)' : isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)',
                    }}>
                    <Icon size={13} style={{ color: isActive ? '#00b8e6' : 'var(--text-muted)' }} />
                  </div>
                  <div className="text-left">
                    <p className="text-xs font-semibold" style={{ color: isActive ? '#00b8e6' : 'var(--text-primary)' }}>{sec.label}</p>
                    <p className="text-2xs hidden md:block" style={{ color: 'var(--text-muted)' }}>{sec.desc}</p>
                  </div>
                </motion.button>
              );
            })}
          </div>
        </motion.div>

        {/* Content panel */}
        <motion.div variants={item} className="col-span-12 md:col-span-9">
          <div className="rounded-2xl p-4 md:p-6"
            style={{
              background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
            }}>
            <AnimatePresence mode="wait">
              <motion.div key={activeSection}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                transition={{ duration: 0.2 }}>
                {sectionContent[activeSection]}
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
