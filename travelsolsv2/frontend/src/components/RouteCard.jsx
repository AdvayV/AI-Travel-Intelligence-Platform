import React from 'react';
import SignalBadge from './SignalBadge';

export default function RouteCard({ route, isSelected, onClick }) {
  const isRising = route.momentum_pct > 0;
  
  const getRankColorClass = (current, previous) => {
    if (current < previous) return 'text-success font-semibold'; // Improved (lower rank is better)
    if (current > previous) return 'text-danger font-semibold'; // Worsened
    return 'text-text-secondary'; // Stable
  };

  return (
    <div 
      onClick={onClick}
      className={`border rounded-xl p-4 cursor-pointer transition-all duration-300 shadow-sm flex flex-col gap-2.5
        ${isSelected 
          ? 'bg-accent-light/65 border-accent/60 ring-1 ring-accent/10' 
          : 'bg-surface-raised border-border hover:border-accent/40 hover:bg-accent-light/20'}`}
    >
      <div className="flex justify-between items-center">
        <div className="font-bold text-sm text-text-primary">
          {route.origin} → {route.destination}
        </div>
        <div className="flex items-center gap-2">
          <div className="text-text-primary font-extrabold text-sm">${route.current_price?.toFixed(0) || '---'}</div>
          <SignalBadge tier={route.tier} score={route.score} />
        </div>
      </div>
      
      <div className="text-xs text-text-secondary font-medium">
        {route.dest_city_name}
      </div>
      
      <div className={`text-xs font-semibold flex items-center gap-1
        ${isRising ? 'text-success' : 'text-danger'}`}>
        <span>{isRising ? '📈' : '📉'}</span>
        <span>{route.momentum_pct > 0 ? '+' : ''}{route.momentum_pct}% GDS demand swing</span>
      </div>
      
      <div className="flex gap-1.5 mt-1 text-[9px] uppercase font-bold tracking-wider text-text-secondary">
        <div className="bg-surface px-2 py-0.5 rounded border border-border">
          2w rank: <span className={getRankColorClass(route.travel_rank_2w, route.travel_rank_8w)}>#{route.travel_rank_2w}</span>
        </div>
        <div className="bg-surface px-2 py-0.5 rounded border border-border">
          8w rank: <span className={getRankColorClass(route.travel_rank_8w, route.travel_rank_12w)}>#{route.travel_rank_8w}</span>
        </div>
        <div className="bg-surface px-2 py-0.5 rounded border border-border text-[8px] text-text-tertiary">
          12w: #{route.travel_rank_12w}
        </div>
      </div>
    </div>
  );
}
