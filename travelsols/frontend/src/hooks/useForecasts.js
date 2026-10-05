import { useEffect, useRef, useState, useCallback } from 'react';

export default function useForecasts(origin) {
  const [forecasts, setForecasts] = useState([]);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshRequested, setRefreshRequested] = useState(false);
  const generation = useRef(0);
  useEffect(() => {
    const current = ++generation.current;
    const controller = new AbortController();
    let timer;
    setLoading(true); setForecasts([]); setError(null);
    async function poll() {
      try {
        const responses = await Promise.all([
          fetch('/api/health', { signal: controller.signal }),
          fetch('/api/forecasts?origin=' + origin + '&limit=100', { signal: controller.signal }),
        ]);
        if (responses.some(r => !r.ok)) throw new Error('Cannot reach the route service. Check that the backend is running on port 8000.');
        const [status, routes] = await Promise.all(responses.map(r => r.json()));
        if (current !== generation.current) return;
        setHealth(status); setForecasts(routes); setError(null); setLoading(false);
        if (!status.refresh?.running) setRefreshRequested(false);
        timer = setTimeout(poll, status.refresh?.running || !routes.length ? 2500 : 15000);
      } catch (e) {
        if (e.name === 'AbortError' || current !== generation.current) return;
        setError(e.message); setLoading(false); setRefreshRequested(false);
        timer = setTimeout(poll, 5000);
      }
    }
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [origin]);

  const refresh = useCallback(async () => {
    setRefreshRequested(true); setError(null);
    try {
      const response = await fetch('/api/refresh', { method: 'POST' });
      if (!response.ok) throw new Error('Refresh could not be started. Please retry.');
      setHealth(h => h ? { ...h, refresh: { ...h.refresh, running: true } } : h);
    } catch (e) { setError(e.message); setRefreshRequested(false); }
  }, []);
  return { forecasts, health, loading, error, refresh, refreshing: refreshRequested || health?.refresh?.running };
}
