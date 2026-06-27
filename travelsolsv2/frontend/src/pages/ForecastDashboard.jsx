import React, { useState } from 'react';
import OriginSelector from '../components/OriginSelector';
import RouteCard from '../components/RouteCard';
import ForecastPanel from '../components/ForecastPanel';
import useForecasts from '../hooks/useForecasts';

export default function ForecastDashboard() {
  const [selectedOrigin, setSelectedOrigin] = useState('BOM');
  const [selectedRoute, setSelectedRoute] = useState(null);
  const { forecasts, loading, error, refetch } = useForecasts(selectedOrigin);

  const handleOriginChange = (origin) => {
    setSelectedOrigin(origin);
    setSelectedRoute(null);
  };

  return (
    <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-6 grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-6 animate-fade-in">
      {/* Left Menu Panel */}
      <div className="flex flex-col gap-4 bg-surface-raised p-5 rounded-2xl border border-border lg:h-[calc(100vh-120px)] overflow-hidden shadow-sm">
        <div className="border-b border-border pb-3">
          <h2 className="text-sm font-bold text-text-primary">GDS Source Airport</h2>
          <p className="text-[10px] text-text-secondary mt-0.5">Select a hub to retrieve GDS forward demand</p>
        </div>
        
        <OriginSelector selectedOrigin={selectedOrigin} onSelect={handleOriginChange} />
        
        <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-2 mt-2">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-text-secondary gap-3">
              <span className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin"></span>
              <span className="text-xs font-semibold">Running Chronos Model...</span>
            </div>
          ) : error ? (
            <div className="text-center text-xs text-danger font-semibold p-4 bg-danger-light border border-danger/10 rounded-lg">
              {error}
            </div>
          ) : forecasts.length === 0 ? (
            <div className="text-center text-xs text-text-secondary p-4 bg-surface rounded-lg">
              No routes found. Select a source hub or refresh cache.
            </div>
          ) : (
            forecasts.map(route => (
              <RouteCard 
                key={`${route.origin}-${route.destination}`} 
                route={route} 
                isSelected={selectedRoute?.destination === route.destination}
                onClick={() => setSelectedRoute(route)} 
              />
            ))
          )}
        </div>
      </div>

      {/* Right Details Panel */}
      <div className="bg-surface-raised border border-border rounded-2xl p-6 lg:h-[calc(100vh-120px)] overflow-y-auto shadow-sm">
        <ForecastPanel route={selectedRoute} />
      </div>
    </main>
  );
}
