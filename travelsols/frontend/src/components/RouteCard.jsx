import React from 'react';
import SignalBadge from './SignalBadge';

const TIER_LEFT_BORDER = {
  PLATINUM: '#A855F7',
  HOT:      '#FF3B3B',
  RISING:   '#FF9B00',
  WATCH:    '#4A9EFF',
  COLD:     '#6B7FA3',
};

function RouteCard({ route, isSelected, onClick }) {
  const isRising = route.momentum_pct > 0;
  const isDiscount = route.surge_multiplier < 1.0;
  const tierBorder = TIER_LEFT_BORDER[route.tier] || '#1E2D4A';

  const getRankColor = (current, previous) => {
    if (current < previous) return '#4CAF50';
    if (current > previous) return '#FF3B3B';
    return '#6B7FA3';
  };

  const surgeColor = route.surge_multiplier >= 2.0 ? '#FF3B3B'
                   : route.surge_multiplier >= 1.5  ? '#FF9B00'
                   : route.surge_multiplier >= 1.2  ? '#FFD700'
                   : '#4CAF50';

  return (
    <div
      onClick={onClick}
      style={{
        background: '#0D1428',
        border: `1px solid ${isSelected ? '#4A9EFF' : '#1E2D4A'}`,
        borderLeft: `3px solid ${isSelected ? '#4A9EFF' : tierBorder}`,
        borderRadius: '10px',
        padding: '13px 14px',
        marginBottom: '8px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        backgroundColor: isSelected ? 'rgba(74, 158, 255, 0.12)' : '#0D1428',
      }}
      onMouseOver={(e) => {
        if (!isSelected) {
          e.currentTarget.style.borderColor = '#4A9EFF';
          e.currentTarget.style.backgroundColor = 'rgba(74, 158, 255, 0.08)';
        }
      }}
      onMouseOut={(e) => {
        if (!isSelected) {
          e.currentTarget.style.borderColor = '#1E2D4A';
          e.currentTarget.style.backgroundColor = '#0D1428';
        }
      }}
    >
      {/* Row 1: route + price + badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <div style={{ fontWeight: 'bold', fontSize: '14px', color: 'white' }}>
          {route.origin} → {route.destination}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isDiscount && (
            <span style={{ fontSize: '10px', color: '#4CAF50', border: '1px solid #4CAF50', padding: '1px 5px', borderRadius: '4px', fontWeight: 'bold' }}>DISC</span>
          )}
          <div style={{ color: surgeColor, fontWeight: 'bold', fontSize: '14px' }}>
            ${route.current_price?.toFixed(0) || '---'}
          </div>
          <SignalBadge tier={route.tier} score={route.score} />
        </div>
      </div>

      {/* Row 2: city name */}
      <div style={{ color: '#C0CCEA', fontSize: '13px', marginBottom: '5px' }}>
        {route.dest_city_name}
      </div>

      {/* Row 3: weather + momentum */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <div style={{ color: '#4CAF50', fontSize: '12px' }}>
          {route.weather_label || ''}
          {route.trend_score != null && (
            <span style={{ marginLeft: '8px', color: '#9C27B0', fontSize: '11px' }}>
              📈 {Math.round(route.trend_score * 100)}% interest
            </span>
          )}
        </div>
        <div style={{ color: isRising ? '#4CAF50' : '#FF9B00', fontSize: '12px', fontWeight: 'bold' }}>
          {isRising ? '↑' : '↓'} {route.momentum_pct > 0 ? '+' : ''}{route.momentum_pct}% demand
        </div>
      </div>

      {/* Row 4: surge + ranks */}
      <div style={{ display: 'flex', gap: '5px', fontSize: '11px', flexWrap: 'wrap' }}>
        <div style={{ background: '#1E2D4A', padding: '2px 7px', borderRadius: '4px', color: surgeColor, fontWeight: 'bold' }}>
          ×{route.surge_multiplier?.toFixed(2)} surge
        </div>
        <div style={{ background: '#1E2D4A', padding: '2px 7px', borderRadius: '4px', color: getRankColor(route.sabre_rank_2w, route.sabre_rank_8w) }}>
          2w #{route.sabre_rank_2w}
        </div>
        <div style={{ background: '#1E2D4A', padding: '2px 7px', borderRadius: '4px', color: getRankColor(route.sabre_rank_8w, route.sabre_rank_12w) }}>
          8w #{route.sabre_rank_8w}
        </div>
        <div style={{ background: '#1E2D4A', padding: '2px 7px', borderRadius: '4px', color: '#6B7FA3' }}>
          12w #{route.sabre_rank_12w}
        </div>
        {route.surge_capped && (
          <div style={{ background: '#FF3B3B20', border: '1px solid #FF3B3B', padding: '2px 7px', borderRadius: '4px', color: '#FF3B3B' }}>
            CAPPED
          </div>
        )}
      </div>
    </div>
  );
}

export default RouteCard;
