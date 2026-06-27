import React from 'react';

const CITIES = [
  { code: 'BOM', name: 'Mumbai' },
  { code: 'DEL', name: 'Delhi' },
  { code: 'BLR', name: 'Bengaluru' },
  { code: 'MAA', name: 'Chennai' },
  { code: 'HYD', name: 'Hyderabad' }
];

function OriginSelector({ selectedOrigin, onSelect }) {
  return (
    <div style={{ display: 'flex', overflowX: 'auto', padding: '10px', borderBottom: '1px solid #1E2D4A', gap: '8px' }}>
      {CITIES.map(city => {
        const isActive = city.code === selectedOrigin;
        return (
          <button
            key={city.code}
            onClick={() => onSelect(city.code)}
            style={{
              padding: '6px 12px',
              borderRadius: '16px',
              border: `1px solid ${isActive ? '#4A9EFF' : '#4A9EFF'}`,
              background: isActive ? '#4A9EFF' : 'transparent',
              color: isActive ? '#FFFFFF' : '#4A9EFF',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              fontWeight: 'bold',
              fontSize: '13px'
            }}
          >
            {city.name} ({city.code})
          </button>
        );
      })}
    </div>
  );
}

export default OriginSelector;
