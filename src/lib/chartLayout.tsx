import { useEffect, useRef, useState, type ReactElement, type ReactNode } from 'react';
import { ResponsiveContainer } from 'recharts';

/**
 * Cartesian charts (bar/line/area): fill the card width on large screens.
 * When items × slotPx exceeds the container, expand width and scroll horizontally
 * instead of squashing bars or clipping labels.
 */
export function ScrollableCartesian({
  itemCount,
  height,
  slotPx = 52,
  children,
  showScrollHint = true,
}: {
  itemCount: number;
  height: number;
  slotPx?: number;
  showScrollHint?: boolean;
  children: () => ReactElement;
}) {
  const outerRef = useRef<HTMLDivElement>(null);
  const [containerW, setContainerW] = useState(0);

  useEffect(() => {
    const el = outerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      setContainerW(entries[0]?.contentRect.width ?? 0);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const minContentW = itemCount * slotPx;
  const needsScroll = containerW > 0 && minContentW > containerW;

  return (
    <div ref={outerRef} className="w-full">
      <div
        className={needsScroll ? 'overflow-x-auto overflow-y-hidden -mx-1 px-1 touch-pan-x' : 'w-full'}
        style={needsScroll ? { WebkitOverflowScrolling: 'touch' } : undefined}
      >
        <div style={{ width: needsScroll ? minContentW : '100%' }}>
          <ResponsiveContainer width="100%" height={height}>
            {children()}
          </ResponsiveContainer>
        </div>
      </div>
      {showScrollHint && needsScroll && (
        <p className="text-[10px] mt-1 text-right tabular-nums" style={{ color: 'var(--text-muted)' }}>
          ← scroll chart · {itemCount} items →
        </p>
      )}
    </div>
  );
}

/** Pie graphic on the left, table/list on the right; stacks vertically on small screens. */
export function PieSideLayout({
  pie,
  side,
  stackBelow = 'md',
}: {
  pie: ReactNode;
  side: ReactNode;
  stackBelow?: 'sm' | 'md' | 'lg';
}) {
  const rowClass =
    stackBelow === 'sm' ? 'sm:flex-row sm:items-start' :
    stackBelow === 'lg' ? 'lg:flex-row lg:items-start' :
    'md:flex-row md:items-start';
  const pieAlign =
    stackBelow === 'sm' ? 'sm:mx-0' :
    stackBelow === 'lg' ? 'lg:mx-0' :
    'md:mx-0';

  return (
    <div className={`flex flex-col ${rowClass} gap-4 lg:gap-6`}>
      <div className={`shrink-0 mx-auto ${pieAlign}`}>{pie}</div>
      <div className="flex-1 min-w-0">{side}</div>
    </div>
  );
}
