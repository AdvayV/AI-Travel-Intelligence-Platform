import { useCallback, useEffect, useRef, useState } from 'react';

export default function useForecasts(selectedOrigin) {
  const [forecasts, setForecasts] = useState([]);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const fetchNow = useRef(null);
  useEffect(() => {
    const abort = new AbortController();
    let timer, disposed = false;
    let pending = false;
    setForecasts([]); setLoading(true); setError(null);
    async function poll() {
      if (pending || disposed) return;
      clearTimeout(timer); pending = true;
      try {
        const replies = await Promise.all([
          fetch('/api/forecasts?origin=' + selectedOrigin + '&limit=100', { signal: abort.signal }),
          fetch('/api/forecast/status', { signal: abort.signal }),
        ]);
        if (replies.some(r => !r.ok)) throw new Error('The forecasting service is unavailable. Check backend port 8001.');
        const [routes, health] = await Promise.all(replies.map(r => r.json()));
        if (disposed) return;
        setForecasts(routes); setStatus(health); setError(null); setLoading(false);
        setRefreshing(health.refresh.running);
        timer = setTimeout(poll, health.refresh.running || !routes.length ? 2500 : 15000);
      } catch (e) {
        if (disposed || e.name === 'AbortError') return;
        setError(e.message); setLoading(false); setRefreshing(false);
        timer = setTimeout(poll, 5000);
      } finally { pending = false; }
    }
    fetchNow.current = poll;
    poll();
    return () => { disposed = true; abort.abort(); clearTimeout(timer); fetchNow.current = null; };
  }, [selectedOrigin]);
  const refetch = useCallback(() => fetchNow.current?.(), []);
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const reply = await fetch('/api/refresh', { method: 'POST' });
      if (!reply.ok) throw new Error('Refresh could not be started.');
      await fetchNow.current?.();
    } catch (e) { setError(e.message); setRefreshing(false); }
  }, []);
  return { forecasts, status, loading, error, refreshing, refresh, refetch, lastRefresh: status?.last_refresh };
}
