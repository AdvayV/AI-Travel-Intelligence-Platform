import React, { useState, useEffect } from 'react';
import SignalBadge from './SignalBadge';
import DemandChart from './DemandChart';

function ProgressBar({ label, color, percent }) {
  return (
    <div className="flex items-center mb-3">
      <div className="w-44 text-text-secondary text-xs font-semibold">{label}</div>
      <div className="flex-1 h-2 bg-surface border border-border rounded-full overflow-hidden mx-4">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${percent}%`, backgroundColor: color }}></div>
      </div>
      <div className="w-10 text-right font-extrabold text-xs text-text-primary">
        {percent}%
      </div>
    </div>
  );
}

export default function ForecastPanel({ route }) {
  const [routeDetail, setRouteDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!route) {
      setRouteDetail(null);
      return;
    }
    
    const fetchDetail = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/forecast/${route.origin}/${route.destination}`);
        const data = await res.json();
        setRouteDetail(data);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    
    fetchDetail();
  }, [route]);

  if (!route) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[400px] text-text-tertiary">
        <div className="text-5xl mb-4 animate-bounce">✈️</div>
        <div className="text-sm font-semibold">Select a route forecast card to view analytical metrics</div>
      </div>
    );
  }

  const detail = routeDetail || route;

  return (
    <div className="max-w-[800px] mx-auto w-full flex flex-col gap-6">
      {/* Title Header */}
      <div className="border-b border-border pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-extrabold text-text-primary tracking-tight">
            {detail.origin} → {detail.destination}
          </h2>
          <span className="text-sm text-text-secondary font-medium">{detail.dest_city_name} Hub</span>
        </div>
        <div>
          <SignalBadge tier={detail.tier} score={detail.score} />
        </div>
      </div>

      {/* Grid: Indicators & Pricing */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Signal Breakdown */}
        <div className="bg-surface-raised border border-border rounded-xl p-5 shadow-sm">
          <h3 className="text-xs uppercase font-extrabold tracking-wider text-text-secondary mb-4">Signal Breakdown</h3>
          <ProgressBar label="Travel GDS Momentum" color="#3B82F6" percent={Math.round(((51 - detail.travel_rank_2w) / 50) * 100)} />
          <ProgressBar label="Google Trends Signal" color="#8B5CF6" percent={detail.trend_score > 0 ? 100 : 0} />
          <ProgressBar label="Weather Appeal" color="#10B981" percent={Math.round(detail.weather_score * 100)} />
          <ProgressBar label="Chronos Confidence" color="#F59E0B" percent={Math.min(100, Math.max(0, 50 + detail.momentum_pct))} />
        </div>

        {/* Pricing Model */}
        <div className="bg-surface-raised border border-border rounded-xl p-5 shadow-sm flex flex-col justify-between">
          <h3 className="text-xs uppercase font-extrabold tracking-wider text-text-secondary mb-3">Surge Pricing Model</h3>
          <div className="flex gap-2 items-center">
            <div className="flex-1 bg-surface border border-border p-3 rounded-lg text-center">
              <div className="text-[10px] uppercase font-bold text-text-tertiary mb-1">Base Price</div>
              <div className="text-base font-extrabold text-text-primary">${detail.base_price?.toFixed(0) || '---'}</div>
            </div>
            <div className="text-text-tertiary text-sm font-bold">×</div>
            <div className="flex-1 bg-surface border border-border p-3 rounded-lg text-center">
              <div className="text-[10px] uppercase font-bold text-text-tertiary mb-1">Surge</div>
              <div className="text-base font-extrabold text-warning">{detail.surge_multiplier?.toFixed(2) || '1.00'}x</div>
            </div>
            <div className="text-text-tertiary text-sm font-bold">=</div>
            <div className="flex-1 bg-danger-light border border-danger/10 p-3 rounded-lg text-center">
              <div className="text-[10px] uppercase font-bold text-danger/80 mb-1">Dynamic</div>
              <div className="text-base font-extrabold text-danger">${detail.current_price?.toFixed(0) || '---'}</div>
            </div>
          </div>
          <div className="text-[10px] text-text-secondary text-center mt-2.5 italic">
            Dynamically computed via Chronos demand surge factors
          </div>
        </div>
      </div>

      {/* Demand Forecast Chart */}
      <div className="bg-surface-raised border border-border rounded-xl p-5 shadow-sm">
        <h3 className="text-xs uppercase font-extrabold tracking-wider text-text-secondary mb-2">Demand Forecast (30 Days)</h3>
        {loading ? (
          <div className="h-[180px] flex items-center justify-center text-text-secondary text-xs">
            <span className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin mr-2"></span>
            Recalculating predictions...
          </div>
        ) : (
          <DemandChart 
            historical={[(51 - detail.travel_rank_12w)/50, (51 - detail.travel_rank_8w)/50, (51 - detail.travel_rank_2w)/50]} 
            forecast={detail.weekly_forecast} 
          />
        )}
      </div>

      {/* AI explanation and advice */}
      <div className="bg-accent-light border border-accent/15 rounded-xl p-4 shadow-sm flex items-start gap-3">
        <span className="text-lg">💡</span>
        <div className="text-xs text-accent-text font-medium leading-relaxed">
          <span className="font-bold block mb-1">Forecast Analysis Insight:</span>
          {detail.signal_explanation || 'Loading AI insights from GDS and search trends...'}
        </div>
      </div>

      {/* Direct Booking call to action */}
      <button 
        className="w-full bg-accent text-white font-bold py-3 px-4 rounded-xl shadow-md hover:bg-accent-text transition-all duration-300 text-xs uppercase tracking-wider"
      >
        Lock In & Pre-negotiate Corporate Rates
      </button>
    </div>
  );
}
