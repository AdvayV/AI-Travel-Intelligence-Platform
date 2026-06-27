import React from 'react';

const CITIES = [
  { code: 'BOM', name: 'Mumbai' },
  { code: 'DEL', name: 'Delhi' },
  { code: 'BLR', name: 'Bengaluru' },
  { code: 'MAA', name: 'Chennai' },
  { code: 'HYD', name: 'Hyderabad' }
];

export default function OriginSelector({ selectedOrigin, onSelect }) {
  return (
    <div className="flex gap-2 pb-3 overflow-x-auto border-b border-border">
      {CITIES.map(city => {
        const isActive = city.code === selectedOrigin;
        return (
          <button
            key={city.code}
            onClick={() => onSelect(city.code)}
            className={`px-3 py-1.5 rounded-full border text-[11px] font-bold transition-all duration-300 whitespace-nowrap shadow-sm
              ${isActive 
                ? 'bg-accent border-accent text-white' 
                : 'bg-surface border-border text-text-secondary hover:bg-border'}`}
          >
            {city.name} ({city.code})
          </button>
        );
      })}
    </div>
  );
}
