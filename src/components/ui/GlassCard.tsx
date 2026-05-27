import { motion } from 'framer-motion';
import type { ReactNode, CSSProperties } from 'react';
import { useTheme } from '../../context/ThemeContext';
import { cardVariants } from '../../lib/motion';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  animate?: boolean;
  hover?: boolean;
  glow?: 'cyan' | 'green' | 'amber' | 'red' | 'none';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
}

const glowColors = {
  cyan: { shadow: '0 0 0 1px rgba(0,184,230,0.2), 0 20px 40px rgba(0,0,0,0.2)', border: 'rgba(0,184,230,0.25)' },
  green: { shadow: '0 0 0 1px rgba(0,230,122,0.2), 0 20px 40px rgba(0,0,0,0.2)', border: 'rgba(0,230,122,0.25)' },
  amber: { shadow: '0 0 0 1px rgba(255,184,0,0.2), 0 20px 40px rgba(0,0,0,0.2)', border: 'rgba(255,184,0,0.25)' },
  red: { shadow: '0 0 0 1px rgba(239,68,68,0.2), 0 20px 40px rgba(0,0,0,0.2)', border: 'rgba(239,68,68,0.25)' },
  none: { shadow: '', border: '' },
};

const paddings = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
};

export default function GlassCard({
  children,
  className = '',
  style,
  animate = true,
  hover = true,
  glow = 'none',
  padding = 'md',
  onClick,
}: GlassCardProps) {
  const { isDark } = useTheme();

  const baseStyle: CSSProperties = {
    background: isDark ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.75)',
    backdropFilter: 'blur(16px) saturate(180%)',
    WebkitBackdropFilter: 'blur(16px) saturate(180%)',
    border: isDark ? '1px solid rgba(255,255,255,0.07)' : '1px solid rgba(0,0,0,0.07)',
    borderRadius: '16px',
    ...style,
  };

  const hoverStyle = hover ? {
    borderColor: glow !== 'none' ? glowColors[glow].border : isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)',
    boxShadow: glow !== 'none' ? glowColors[glow].shadow : '0 20px 40px rgba(0,0,0,0.15)',
    y: -1,
  } : {};

  if (!animate) {
    return (
      <div
        className={`${paddings[padding]} ${className}`}
        style={baseStyle}
        onClick={onClick}
      >
        {children}
      </div>
    );
  }

  return (
    <motion.div
      variants={cardVariants}
      className={`${paddings[padding]} ${className} ${onClick ? 'cursor-pointer' : ''}`}
      style={baseStyle}
      whileHover={hoverStyle}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      onClick={onClick}
    >
      {children}
    </motion.div>
  );
}
