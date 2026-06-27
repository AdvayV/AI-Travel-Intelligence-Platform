import { useState } from 'react';
import TopBar from './components/TopBar';
import OriginSelector from './components/OriginSelector';
import RouteCard from './components/RouteCard';
import ForecastPanel from './components/ForecastPanel';
import useForecasts from './hooks/useForecasts';

function App() {
  const [selectedOrigin, setSelectedOrigin] = useState('BOM');
  const [selectedRoute, setSelectedRoute] = useState(null);

  const { forecasts, loading, error, lastRefresh, refetch } = useForecasts(selectedOrigin);

  const platinumCount = forecasts.filter(f => f.tier === 'PLATINUM').length;
  const hotCount      = forecasts.filter(f => f.tier === 'HOT').length;
  const risingCount   = forecasts.filter(f => f.tier === 'RISING').length;
  const coldCount     = forecasts.filter(f => f.tier === 'COLD').length;

  const handleOriginChange = (origin) => {
    setSelectedOrigin(origin);
    setSelectedRoute(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      <TopBar
        platinumCount={platinumCount}
        hotCount={hotCount}
        risingCount={risingCount}
        coldCount={coldCount}
        lastRefresh={lastRefresh}
        onRefresh={refetch}
      />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }} className="main-layout">
        <div style={{ width: '340px', display: 'flex', flexDirection: 'column', borderRight: '1px solid #1E2D4A', flexShrink: 0 }} className="left-panel">
          <OriginSelector selectedOrigin={selectedOrigin} onSelect={handleOriginChange} />
          <div style={{ overflowY: 'auto', flex: 1, padding: '10px' }}>
            {loading ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#6B7FA3' }}>Loading forecasts…</div>
            ) : error ? (
              <div style={{ padding: '20px', textAlign: 'center', color: '#FF3B3B' }}>{error}</div>
            ) : forecasts.map(route => (
              <RouteCard
                key={`${route.origin}-${route.destination}`}
                route={route}
                isSelected={selectedRoute?.destination === route.destination}
                onClick={() => setSelectedRoute(route)}
              />
            ))}
          </div>
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto', padding: '20px' }}>
          <ForecastPanel route={selectedRoute} />
        </div>
      </div>
      <style>{`
        @media (max-width: 768px) {
          .main-layout { flex-direction: column !important; overflow-y: auto !important; }
          .left-panel { width: 100% !important; border-right: none !important; border-bottom: 1px solid #1E2D4A; }
        }
      `}</style>
    </div>
  );
}

export default App;
