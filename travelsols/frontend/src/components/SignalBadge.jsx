import React from 'react';

const TIER_CONFIG = {
  PLATINUM: { bg: '#E8D5FF20', border: '#A855F7', color: '#A855F7', label: '💎 PLATINUM' },
  HOT:      { bg: '#FF3B3B20', border: '#FF3B3B', color: '#FF3B3B', label: '🔥 HOT' },
  RISING:   { bg: '#FF9B0020', border: '#FF9B00', color: '#FF9B00', label: '📈 RISING' },
  WATCH:    { bg: '#4A9EFF20', border: '#4A9EFF', color: '#4A9EFF', label: '👁 WATCH' },
  COLD:     { bg: '#6B7FA320', border: '#6B7FA3', color: '#6B7FA3', label: '❄️ COLD' },
};

function SignalBadge({ tier, score }) {
  const cfg = TIER_CONFIG[tier] || TIER_CONFIG['WATCH'];
  return (
    <div style={{
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      color: cfg.color,
      padding: '3px 10px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 'bold',
      whiteSpace: 'nowrap',
    }}>
      {cfg.label} {score != null ? `· ${score}` : ''}
    </div>
  );
}

export default SignalBadge;
export { TIER_CONFIG };
