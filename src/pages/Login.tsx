import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Eye, EyeOff, ArrowRight, Shield, BarChart3, Brain } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

/* ─── Role badge colours ─────────────────────────────────────────────────── */
const ROLES = [
  { label: 'Admin',   desc: 'Full access + user management', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  { label: 'Manager', desc: 'Dashboards + AI Query',          color: '#6366f1', bg: 'rgba(99,102,241,0.12)' },
  { label: 'Viewer',  desc: 'Read-only dashboards',           color: '#22c55e', bg: 'rgba(34,197,94,0.12)'  },
];

const STATS = [
  { icon: BarChart3, label: 'Live Analytics',  value: 'Real-time' },
  { icon: Brain,     label: 'AI Query',        value: 'NLQ → SQL' },
  { icon: Shield,    label: 'Role-based',      value: 'RBAC'      },
];

/* ─── Animated background dots ──────────────────────────────────────────── */
function GridDots() {
  return (
    <svg
      className="absolute inset-0 w-full h-full opacity-20 pointer-events-none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="dots" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="1.5" fill="rgba(255,255,255,0.4)" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#dots)" />
    </svg>
  );
}

export default function Login() {
  const { login } = useAuth();
  const navigate   = useNavigate();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [showPw,   setShowPw]   = useState(false);
  const [error,    setError]    = useState('');
  const [busy,     setBusy]     = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(email.trim().toLowerCase(), password.trim());
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid credentials. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ background: '#070c1a' }}>

      {/* ── LEFT BRAND PANEL (hidden on small screens) ─────────────────── */}
      <motion.div
        initial={{ opacity: 0, x: -40 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="hidden lg:flex flex-col justify-between relative overflow-hidden"
        style={{ width: '48%', background: '#0d1226', borderRight: '1px solid rgba(255,255,255,0.06)' }}
      >
        <GridDots />

        {/* Glow orbs */}
        <div className="absolute top-20 left-10 w-64 h-64 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.18) 0%, transparent 70%)' }} />
        <div className="absolute bottom-24 right-8 w-48 h-48 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(circle, rgba(34,197,94,0.12) 0%, transparent 70%)' }} />

        <div className="relative z-10 p-10 pt-12">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-12">
            <div className="w-11 h-11 rounded-2xl flex items-center justify-center flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #6366f1, #22c55e)' }}>
              <Zap size={22} className="text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-lg leading-tight">SmarterP</p>
              <p className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.4)' }}>ERP Connector</p>
            </div>
          </div>

          {/* Hero text */}
          <h2 className="text-3xl font-extrabold leading-tight mb-3">
            <span className="text-white">Your ERP data,</span>
            <br />
            <span style={{ background: 'linear-gradient(90deg,#6366f1,#22c55e)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              intelligently unified.
            </span>
          </h2>
          <p className="text-sm leading-relaxed mb-10" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Real-time dashboards, natural-language queries, and granular role-based access — all in one place.
          </p>

          {/* Stat chips */}
          <div className="flex flex-col gap-3 mb-10">
            {STATS.map(({ icon: Icon, label, value }) => (
              <div key={label} className="flex items-center gap-3 px-4 py-3 rounded-xl"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(99,102,241,0.2)' }}>
                  <Icon size={15} style={{ color: '#818cf8' }} />
                </div>
                <div>
                  <p className="text-xs font-semibold text-white">{label}</p>
                  <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>{value}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Role badges */}
        <div className="relative z-10 p-10 pb-12">
          <p className="text-xs font-semibold mb-3 uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.3)' }}>
            Access levels
          </p>
          <div className="flex flex-col gap-2">
            {ROLES.map(({ label, desc, color, bg }) => (
              <div key={label} className="flex items-center gap-3">
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold" style={{ background: bg, color }}>
                  {label}
                </span>
                <span className="text-xs" style={{ color: 'rgba(255,255,255,0.38)' }}>{desc}</span>
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* ── RIGHT FORM PANEL ────────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo (only on sm screens) */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-10 h-10 rounded-2xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #6366f1, #22c55e)' }}>
              <Zap size={20} className="text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-base">SmarterP Connector</p>
            </div>
          </div>

          <h1 className="text-2xl font-extrabold text-white mb-1">Welcome back</h1>
          <p className="text-sm mb-8" style={{ color: 'rgba(255,255,255,0.4)' }}>
            Sign in to access your dashboard
          </p>

          <form onSubmit={submit} className="space-y-5">
            {/* Email */}
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'rgba(255,255,255,0.55)' }}>
                Email address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                autoComplete="email"
                className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  color: 'white',
                }}
                onFocus={(e) => { e.currentTarget.style.border = '1px solid rgba(99,102,241,0.6)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'; }}
                onBlur={(e)  => { e.currentTarget.style.border = '1px solid rgba(255,255,255,0.1)'; e.currentTarget.style.boxShadow = 'none'; }}
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-xs font-semibold mb-1.5" style={{ color: 'rgba(255,255,255,0.55)' }}>
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  className="w-full px-4 py-3 pr-11 rounded-xl text-sm outline-none transition-all"
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: 'white',
                  }}
                  onFocus={(e) => { e.currentTarget.style.border = '1px solid rgba(99,102,241,0.6)'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(99,102,241,0.12)'; }}
                  onBlur={(e)  => { e.currentTarget.style.border = '1px solid rgba(255,255,255,0.1)'; e.currentTarget.style.boxShadow = 'none'; }}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded-lg transition-colors"
                  style={{ color: 'rgba(255,255,255,0.35)' }}
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Error */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  className="px-4 py-3 rounded-xl text-sm"
                  style={{ background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.25)', color: '#fca5a5' }}
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Submit */}
            <motion.button
              type="submit"
              disabled={busy}
              whileTap={{ scale: 0.98 }}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white relative overflow-hidden"
              style={{
                background: busy ? 'rgba(99,102,241,0.5)' : 'linear-gradient(135deg, #6366f1, #4f46e5)',
                boxShadow: busy ? 'none' : '0 4px 24px rgba(99,102,241,0.35)',
                cursor: busy ? 'not-allowed' : 'pointer',
              }}
            >
              {busy ? (
                <>
                  <svg className="animate-spin" width={16} height={16} viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="white" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight size={15} />
                </>
              )}
            </motion.button>
          </form>

          <p className="mt-6 text-xs text-center" style={{ color: 'rgba(255,255,255,0.25)' }}>
            Contact your administrator to get access
          </p>
        </motion.div>
      </div>
    </div>
  );
}
