import React, { useEffect, useState } from 'react';
import StatusPill from './StatusPill';


export default function TopBar({ onNewBooking, onRefreshForecasts, activeTab, setActiveTab }) {
  const [health, setHealth] = useState({
    neo4j: false,
    chroma: false,
    huggingface: false,
    agentMode: 'deterministic',
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
          agentMode: data.agent_mode || 'deterministic',
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
    <header className="sticky top-0 z-50 flex min-h-16 items-center justify-between gap-3 border-b border-border bg-white/90 px-4 py-2 shadow-sm backdrop-blur-xl transition-all duration-300 sm:px-6">
      {/* Left Wordmark */}
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo-600 to-sky-500 text-xs font-black text-white shadow-md shadow-indigo-200">TR</div>
        <div className="flex items-baseline">
          <span className="text-sm font-extrabold tracking-tight text-text-primary sm:text-base">TravelRoute</span>
          <span className="ml-1 hidden text-sm font-semibold text-text-secondary lg:inline">Intelligence</span>
        </div>
      </div>

      {/* Center Tabs Navigation */}
      <nav className="flex rounded-xl border border-border bg-surface p-1" aria-label="Primary navigation">
        <button
          onClick={() => setActiveTab('booking')}
          className={`flex items-center gap-2 px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 ${
            activeTab === 'booking'
              ? 'bg-surface-raised text-accent shadow-sm'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          Booking
        </button>
        <button
          onClick={() => setActiveTab('policy')}
          className={`flex items-center gap-2 px-4 py-1.5 text-xs font-semibold rounded-lg transition-all duration-300 ${
            activeTab === 'policy'
              ? 'bg-surface-raised text-accent shadow-sm'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          Policy graph
        </button>
      </nav>

      {/* Right Action & Status Indicators */}
      <div className="flex items-center gap-2 sm:gap-4">
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
            status={health.agentMode === 'deterministic' || health.huggingface ? 'success' : 'warning'}
            label={health.agentMode === 'deterministic' ? 'Policy Engine' : health.huggingface ? 'LLM Agent' : 'LLM Offline'}
          />
        </div>

        {/* Dynamic Context Button */}
        <div>
          {activeTab === 'booking' ? (
            <button
              onClick={onNewBooking}
              className="bg-accent text-white px-4 py-2 text-xs font-bold rounded-lg hover:bg-accent-text transition-all duration-200 shadow-sm"
            >
              <span className="sm:hidden">New</span><span className="hidden sm:inline">New booking</span>
            </button>
          ) : (
            <button
              onClick={() => fetch('/api/policy/ingest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })}
              className="bg-purple-600 text-white px-4 py-2 text-xs font-bold rounded-lg hover:bg-purple-500 transition-all duration-200 shadow-sm"
            >
              Refresh policy
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

