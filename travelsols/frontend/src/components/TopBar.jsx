import React, { useState } from 'react';

function TierPill({ label, count, bg, border, color }) {
  if (!count) return null;
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, color, padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 'bold' }}>
      {label}: {count}
    </div>
  );
}

function TopBar({ hotCount, risingCount, platinumCount, coldCount, lastRefresh, onRefresh }) {
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await fetch('/api/refresh', { method: 'POST' });
      if (res.ok) {
        setTimeout(() => { onRefresh(); setRefreshing(false); }, 4000);
      }
    } catch (e) {
      console.error(e);
      setRefreshing(false);
    }
  };

  return (
    <div style={{
      background: '#0D1428',
      borderBottom: '1px solid #1E2D4A',
      padding: '10px 20px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '10px',
    }}>
      <div>
        <h1 style={{ margin: 0, fontSize: '18px', color: '#FFFFFF', letterSpacing: '-0.3px' }}>Route Intelligence</h1>
        <div style={{ color: '#4A9EFF', fontSize: '12px' }}>Demand Forecasting · Surge Engine v2</div>
      </div>

      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
        <TierPill label="💎 PLAT"   count={platinumCount} bg="#A855F720" border="#A855F7" color="#A855F7" />
        <TierPill label="🔥 HOT"    count={hotCount}      bg="#FF3B3B20" border="#FF3B3B" color="#FF3B3B" />
        <TierPill label="📈 RISING" count={risingCount}   bg="#FF9B0020" border="#FF9B00" color="#FF9B00" />
        <TierPill label="❄️ COLD"   count={coldCount}     bg="#6B7FA320" border="#6B7FA3" color="#6B7FA3" />
        <div style={{ color: '#4A6080', fontSize: '12px' }}>
          {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : 'Loading…'}
        </div>
      </div>

      <button
        onClick={handleRefresh}
        disabled={refreshing}
        style={{
          background: refreshing ? '#1E2D4A' : 'linear-gradient(135deg, #4A9EFF, #7C5CFC)',
          color: 'white',
          border: 'none',
          padding: '8px 18px',
          borderRadius: '8px',
          cursor: refreshing ? 'wait' : 'pointer',
          fontWeight: 'bold',
          fontSize: '13px',
          transition: 'opacity 0.2s',
        }}
      >
        {refreshing ? '⏳ Refreshing…' : '⟳ Refresh'}
      </button>
    </div>
  );
}

export default TopBar;
