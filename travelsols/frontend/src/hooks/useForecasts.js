import { useState, useEffect } from 'react';

function useForecasts(selectedOrigin) {
  const [forecasts, setForecasts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchForecasts = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/forecasts?origin=${selectedOrigin}&limit=25`);
      if (!res.ok) throw new Error('Failed to fetch forecasts');
      const data = await res.json();
      setForecasts(data);
      setLastRefresh(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchForecasts();
    
    const interval = setInterval(fetchForecasts, 300000);
    return () => clearInterval(interval);
  }, [selectedOrigin]);

  return { forecasts, loading, error, lastRefresh, refetch: fetchForecasts };
}

export default useForecasts;
