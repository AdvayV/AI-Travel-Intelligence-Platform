import React, { useEffect, useState } from 'react';
import StatusPill from './StatusPill';


export default function TopBar({ onNewBooking, onRefreshForecasts, activeTab, setActiveTab }) {
  const [health, setHealth] = useState({
    neo4j: false,
    chroma: false,
    huggingface: false,
    forecastCacheSize: 0,
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchHealth = async () => {
    try {
      const resp = await fetch('/api/health');
      if (resp.ok) {
        const data = await resp.json();
        // parse chroma
        const chromaSeeded = data.chroma && !data.chroma.error && 
          Object.values(data.chroma).every(count => count > 0);
          
        setHealth({
          neo4j: data.neo4j === true,
          chroma: chromaSeeded,
          huggingface: data.huggingface === true,
          forecastCacheSize: data.forecast_cache_size || 0,
        });
      }
    } catch (err) {
      console.error('Failed to retrieve system health', err);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000); // refresh every 15s
    return () => clearInterval(interval);
  }, []);

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    try {
      const resp = await fetch('/api/refresh', { method: 'POST' });
      if (resp.ok) {
        if (onRefreshForecasts) onRefreshForecasts();
        setTimeout(fetchHealth, 3000); // refresh health shortly after
      }
    } catch (err) {
      console.error('Failed to trigger pipeline refresh', err);
    } finally {
      setTimeout(() => setIsRefreshing(false), 2000);
    }
  };

  return (
    <header className="h-16 px-6 bg-surface-raised border-b border-border flex items-center justify-between sticky top-0 z-50 shadow-sm transition-all duration-300">
      {/* Left Wordmark */}
      <div className="flex items-center gap-2">
        <div className="flex items-baseline">
          <span className="text-base font-bold text-accent">TravelRoute</span>
          <span className="text-base font-semibold text-text-secondary ml-1">Intelligence Portal</span>
          <span className="ml-2 align-super bg-accent-light text-accent-text text-[10px] px-2 py-0.5 rounded-full font-bold">
            Unified
          </span>
        </div>
      </div>

      {/* Center Tabs Navigation */}
      <div className="flex bg-surface p-1 rounded-xl border border-border">
        <button
          onClick={() => setActiveTab('booking')}
          className={`flex items-center gap-2 px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 ${
            activeTab === 'booking'
              ? 'bg-surface-raised text-accent shadow-sm'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          🤖 Booking Agent
        </button>
        <button
          onClick={() => setActiveTab('policy')}
          className={`flex items-center gap-2 px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 ${
            activeTab === 'policy'
              ? 'bg-surface-raised text-accent shadow-sm'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          🕸️ Policy Graph
        </button>
      </div>

      {/* Right Action & Status Indicators */}
      <div className="flex items-center gap-4">
        {/* Status Pills */}
        <div className="hidden xl:flex items-center gap-2">
          <StatusPill 
            status={health.neo4j ? 'success' : 'error'} 
            label={health.neo4j ? 'Neo4j Online' : 'Neo4j Offline'} 
          />
          <StatusPill 
            status={health.chroma ? 'success' : 'error'} 
            label={health.chroma ? 'ChromaDB Local' : 'ChromaDB Missing'} 
          />
          <StatusPill 
            status={health.huggingface ? 'success' : 'warning'} 
            label={health.huggingface ? 'HF Live Agent' : 'HF Mock (Offline)'} 
          />
        </div>

        {/* Dynamic Context Button */}
        <div>
          {activeTab === 'booking' ? (
            <button
              onClick={onNewBooking}
              className="bg-accent text-white px-4 py-2 text-xs font-bold rounded-lg hover:bg-accent-text transition-all duration-200 shadow-sm"
            >
              New Booking Session
            </button>
          ) : (
            <button
              onClick={() => fetch('/api/policy/ingest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })}
              className="bg-purple-600 text-white px-4 py-2 text-xs font-bold rounded-lg hover:bg-purple-500 transition-all duration-200 shadow-sm"
            >
              🔄 Re-Ingest PDF
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

