import React, { useEffect, useRef, useState } from 'react';

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

/** A responsive, keyboard-accessible workspace split. */
export default function ResizableSplit({
  sidebar,
  children,
  initialSize = 420,
  minSize = 320,
  maxSize = 600,
  storageKey = 'travelroute-sidebar-width',
}) {
  const rootRef = useRef(null);
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    try {
      const item = localStorage.getItem(storageKey);
      const saved = item == null ? NaN : Number(item);
      return Number.isFinite(saved) ? clamp(saved, minSize, maxSize) : initialSize;
    } catch { return initialSize; }
  });
  const [isResizing, setIsResizing] = useState(false);

  useEffect(() => {
    try { localStorage.setItem(storageKey, String(sidebarWidth)); } catch {}
  }, [sidebarWidth, storageKey]);

  useEffect(() => {
    if (!isResizing) return undefined;
    const updateWidth = (event) => {
      const root = rootRef.current;
      if (!root) return;
      const next = event.clientX - root.getBoundingClientRect().left;
      setSidebarWidth(clamp(next, minSize, Math.min(maxSize, root.clientWidth - 360)));
    };
    const stopResize = () => setIsResizing(false);
    window.addEventListener('pointermove', updateWidth);
    window.addEventListener('pointerup', stopResize);
    return () => {
      window.removeEventListener('pointermove', updateWidth);
      window.removeEventListener('pointerup', stopResize);
    };
  }, [isResizing, maxSize, minSize]);

  const adjustWidth = (amount) => setSidebarWidth((current) => clamp(current + amount, minSize, maxSize));

  return (
    <div ref={rootRef} className={`resizable-split ${isResizing ? 'resizable-split--dragging' : ''}`} style={{ '--sidebar-width': `${sidebarWidth}px` }}>
      <aside className="min-w-0 min-h-0">{sidebar}</aside>
      <button
        type="button"
        role="slider"
        className="resizable-split__divider"
        aria-label="Resize context panel"
        aria-orientation="vertical"
        aria-valuemin={minSize}
        aria-valuemax={maxSize}
        aria-valuenow={sidebarWidth}
        aria-valuetext={`${sidebarWidth} pixel context panel width`}
        onPointerDown={(event) => { event.preventDefault(); setIsResizing(true); }}
        onKeyDown={(event) => {
          if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) event.preventDefault();
          if (event.key === 'ArrowLeft') adjustWidth(-24);
          if (event.key === 'ArrowRight') adjustWidth(24);
          if (event.key === 'Home') setSidebarWidth(minSize);
          if (event.key === 'End') setSidebarWidth(maxSize);
        }}
      >
        <span />
      </button>
      <section className="min-w-0 min-h-0">{children}</section>
    </div>
  );
}
