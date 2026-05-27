import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import type { KPIMetric } from '../../types';
import { useTheme } from '../../context/ThemeContext';
import { cardVariants } from '../../lib/motion';

interface KPICardProps extends KPIMetric {
  size?: 'sm' | 'md' | 'lg';
}

const colorMap = {
  cyan: { main: '#00b8e6', bg: 'rgba(0,184,230,0.08)', border: 'rgba(0,184,230,0.15)', glow: 'rgba(0,184,230,0.3)' },
  green: { main: '#00e67a', bg: 'rgba(0,230,122,0.08)', border: 'rgba(0,230,122,0.15)', glow: 'rgba(0,230,122,0.3)' },
  amber: { main: '#ffb800', bg: 'rgba(255,184,0,0.08)', border: 'rgba(255,184,0,0.15)', glow: 'rgba(255,184,0,0.3)' },
  red: { main: '#ef4444', bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.15)', glow: 'rgba(239,68,68,0.3)' },
};

export default function KPICard({ label, value, change, changeLabel, trend, sparkData, unit, prefix, color = 'cyan', size = 'md' }: KPICardProps) {
  const { isDark } = useTheme();
  const colors = colorMap[color];
  const isPositive = change > 0;

  const chartData = sparkData?.map((v, i) => ({ v, i })) ?? [];

  return (
    <motion.div
      variants={cardVariants}
      className="relative overflow-hidden rounded-2xl p-5 cursor-default"
      style={{
        background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.80)',
        backdropFilter: 'blur(20px)',
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.07)'}`,
      }}
      whileHover={{
        y: -2,
        borderColor: colors.border,
        boxShadow: `0 0 0 1px ${colors.border}, 0 20px 40px rgba(0,0,0,0.2)`,
      }}
      transition={{ duration: 0.25 }}
    >
      {/* Ambient corner glow */}
      <div
        className="absolute top-0 right-0 w-24 h-24 rounded-full pointer-events-none"
        style={{
          background: `radial-gradient(circle at top right, ${colors.glow} 0%, transparent 70%)`,
          transform: 'translate(30%, -30%)',
        }}
      />

      {/* Header */}
      <div className="flex items-start justify-between mb-4 relative z-10">
        <div>
          <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{label}</p>
          <div className="flex items-baseline gap-1.5">
            {prefix && (
              <span className="text-sm font-semibold" style={{ color: colors.main }}>{prefix}</span>
            )}
            <span
              className="text-3xl font-bold metric-value"
              style={{ color: 'var(--text-primary)', letterSpacing: '-0.03em' }}
            >
              {value}
            </span>
            {unit && (
              <span className="text-sm font-medium" style={{ color: 'var(--text-tertiary)' }}>{unit}</span>
            )}
          </div>
        </div>

        {/* Trend badge */}
        <div
          className="flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold"
          style={{
            background: isPositive ? 'rgba(0,230,122,0.12)' : trend === 'stable' ? 'rgba(100,116,139,0.12)' : 'rgba(239,68,68,0.12)',
            color: isPositive ? '#00e67a' : trend === 'stable' ? '#64748b' : '#ef4444',
          }}
        >
          {trend === 'up' ? <TrendingUp size={11} /> : trend === 'down' ? <TrendingDown size={11} /> : <Minus size={11} />}
          <span>{Math.abs(change)}%</span>
        </div>
      </div>

      {/* Spark chart */}
      {chartData.length > 0 && (
        <div className="h-12 -mx-1 mb-3 relative z-10">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
              <defs>
                <linearGradient id={`kg-${color}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors.main} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={colors.main} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={colors.main}
                strokeWidth={1.5}
                fill={`url(#kg-${color})`}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Change label */}
      <div className="flex items-center gap-1.5 relative z-10">
        <div
          className="w-1 h-1 rounded-full"
          style={{ background: colors.main }}
        />
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{changeLabel}</p>
      </div>

      {/* Bottom accent line */}
      <div
        className="absolute bottom-0 left-0 right-0 h-0.5"
        style={{
          background: `linear-gradient(90deg, transparent, ${colors.main}, transparent)`,
          opacity: 0.4,
        }}
      />
    </motion.div>
  );
}
