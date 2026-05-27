import { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useTheme } from '../../context/ThemeContext';

export default function AnimatedBackground() {
  const { isDark } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let time = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const particles: Array<{ x: number; y: number; vx: number; vy: number; radius: number; alpha: number }> = [];

    for (let i = 0; i < 40; i++) {
      particles.push({
        x: Math.random() * window.innerWidth,
        y: Math.random() * window.innerHeight,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        radius: Math.random() * 1.5 + 0.5,
        alpha: Math.random() * 0.4 + 0.1,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      time += 0.005;

      // Atmospheric orbs — deep indigo/navy palette
      const orbs = [
        { x: canvas.width * 0.15 + Math.sin(time * 0.7) * 40, y: canvas.height * 0.25 + Math.cos(time * 0.5) * 30, r: 380, color: 'rgba(88,130,255,0.09)' },
        { x: canvas.width * 0.78 + Math.cos(time * 0.6) * 50, y: canvas.height * 0.18 + Math.sin(time * 0.8) * 35, r: 340, color: 'rgba(139,92,246,0.08)' },
        { x: canvas.width * 0.55 + Math.sin(time * 0.4) * 60, y: canvas.height * 0.80 + Math.cos(time * 0.6) * 40, r: 420, color: 'rgba(56,78,200,0.07)' },
        { x: canvas.width * 0.88 + Math.cos(time * 0.5) * 30, y: canvas.height * 0.65 + Math.sin(time * 0.4) * 45, r: 260, color: 'rgba(100,60,220,0.06)' },
        { x: canvas.width * 0.30 + Math.sin(time * 0.3) * 70, y: canvas.height * 0.85 + Math.cos(time * 0.7) * 35, r: 300, color: 'rgba(60,110,255,0.05)' },
      ];

      orbs.forEach(orb => {
        const grad = ctx.createRadialGradient(orb.x, orb.y, 0, orb.x, orb.y, orb.r);
        grad.addColorStop(0, orb.color);
        grad.addColorStop(1, 'transparent');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(orb.x, orb.y, orb.r, 0, Math.PI * 2);
        ctx.fill();
      });

      // Particles
      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(88,130,255,${p.alpha * (0.4 + Math.sin(time * 2 + p.x) * 0.2)})`;
        ctx.fill();
      });

      // Connect nearby particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            const alpha = (1 - dist / 120) * 0.06;
            ctx.strokeStyle = `rgba(88,130,255,${alpha})`;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }

      animId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, [isDark]);

  return (
    <>
      <canvas
        ref={canvasRef}
        className="fixed inset-0 pointer-events-none z-0"
        style={{ opacity: 0.8 }}
      />
      {/* Grid overlay */}
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          backgroundImage: `linear-gradient(rgba(88,130,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(88,130,255,0.025) 1px, transparent 1px)`,
          backgroundSize: '64px 64px',
        }}
      />
      {/* Noise texture */}
      <motion.div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
          opacity: isDark ? 0.025 : 0.015,
        }}
      />
    </>
  );
}
