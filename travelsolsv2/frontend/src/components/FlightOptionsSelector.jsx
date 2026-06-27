import React from 'react';

export default function FlightOptionsSelector({ options, selected, onSelect }) {
  if (!options || options.length === 0) return null;

  const standardFlights = options.filter(f => !f.is_alternative);
  const alternateFlights = options.filter(f => f.is_alternative);

  const getAirlineName = (code) => {
    const names = {
      AI: 'Air India',
      EK: 'Emirates',
      QR: 'Qatar Airways',
      SQ: 'Singapore Airlines',
      BA: 'British Airways',
      '6E': 'IndiGo'
    };
    return names[code] || code;
  };

  const renderFlightCard = (flight) => {
    const isSelected = selected && selected.flight_number === flight.flight_number && selected.fare_class === flight.fare_class;
    
    // Status style and label
    let statusBg = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    let statusLabel = 'Policy Compliant';
    if (!flight.compliant) {
      statusBg = 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      statusLabel = 'Non-Compliant';
    } else if (flight.compliance_details && flight.compliance_details.includes('Waiver Exception')) {
      statusBg = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      statusLabel = 'Compliant via Waiver';
    } else if (flight.requires_approval) {
      statusBg = 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      statusLabel = 'Requires Manager Approval';
    }

    // Weather risk badge
    let weatherRiskBadge = null;
    if (flight.disruption_risk === 'HIGH') {
      weatherRiskBadge = (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-400 animate-pulse border border-rose-500/20">
          ⛈️ High Risk Storm Delays
        </span>
      );
    } else if (flight.disruption_risk === 'MODERATE') {
      weatherRiskBadge = (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/20">
          ⚠️ Moderate Monsoon Risk
        </span>
      );
    } else {
      weatherRiskBadge = (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-teal-500/15 text-teal-400 border border-teal-500/20">
          ☀️ Low Weather Risk
        </span>
      );
    }

    return (
      <div
        key={`${flight.flight_number}-${flight.fare_class}`}
        onClick={() => onSelect(flight)}
        className={`relative border rounded-lg p-4 cursor-pointer transition-all duration-200 flex flex-col gap-3 group select-none
          ${isSelected 
            ? 'border-accent bg-accent/5 shadow-[0_0_15px_rgba(20,110,245,0.15)]' 
            : 'border-border bg-surface-raised hover:border-text-tertiary/50 hover:bg-surface-raised/80'
          }`}
      >
        {/* Selection Dot */}
        <div className={`absolute top-4 right-4 w-4 h-4 rounded-full border flex items-center justify-center
          ${isSelected ? 'border-accent bg-accent' : 'border-text-tertiary bg-transparent'}`}
        >
          {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
        </div>

        {/* Top Badges */}
        <div className="flex flex-wrap items-center gap-2 pr-6">
          <span className={`text-[10px] font-bold tracking-wide uppercase px-2 py-0.5 rounded border ${statusBg}`}>
            {statusLabel}
          </span>
          {weatherRiskBadge}
          {flight.surge_applied && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/15 text-orange-400 border border-orange-500/30 animate-pulse">
              ⚡ Surge {flight.surge_applied.multiplier}x
            </span>
          )}
          {flight.is_alternative && (
            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/20">
              🚁 Route Reroute
            </span>
          )}
        </div>

        {/* Flight Core Info */}
        <div className="flex justify-between items-center mt-1">
          <div className="flex flex-col">
            <span className="text-sm font-bold text-text-primary tracking-wide">{flight.flight_number}</span>
            <span className="text-xs text-text-secondary">{getAirlineName(flight.airline)}</span>
          </div>

          <div className="flex flex-col items-center px-4">
            <span className="text-xs font-semibold text-text-primary">
              {flight.departure_time.split(' ')[1]} → {flight.arrival_time.split(' ')[1]}
            </span>
            <span className="text-[10px] text-text-tertiary font-mono">{flight.duration} ({flight.stops === 0 ? 'Direct' : `${flight.stops} stop`})</span>
          </div>

          <div className="flex flex-col items-end">
            {flight.surge_applied ? (
              <>
                <span className="text-[10px] text-text-tertiary line-through">INR {flight.surge_applied.pre_surge_price_inr.toLocaleString()}</span>
                <span className="text-base font-bold text-orange-400">INR {flight.price_inr.toLocaleString()}</span>
                <span className="text-[9px] text-orange-400 font-bold bg-orange-500/10 px-1 py-0.5 rounded mt-0.5">⚡ {flight.surge_applied.reason}</span>
              </>
            ) : flight.discount_applied ? (
              <>
                <span className="text-[10px] text-text-tertiary line-through">INR {flight.original_price_inr.toLocaleString()}</span>
                <span className="text-base font-bold text-accent">INR {flight.price_inr.toLocaleString()}</span>
                <span className="text-[9px] text-emerald-400 font-bold bg-emerald-500/10 px-1 py-0.5 rounded mt-0.5">{flight.discount_applied}</span>
              </>
            ) : (
              <span className="text-base font-bold text-text-primary">INR {flight.price_inr.toLocaleString()}</span>
            )}
            <span className="text-[9px] font-semibold font-mono bg-surface border px-1.5 py-0.5 rounded mt-1">{flight.fare_class}</span>
            {flight.weather && (
              <span className="text-[10px] font-medium text-text-secondary mt-1 flex items-center gap-1 bg-surface/50 border px-1.5 py-0.5 rounded">
                🌤️ {flight.weather}
              </span>
            )}
          </div>
        </div>

        {/* Warnings or Waivers notes */}
        {(flight.disruption_warning || flight.compliance_details) && (
          <div className="border-t border-border/40 pt-2.5 flex flex-col gap-1.5">
            {flight.disruption_warning && (
              <span className="text-[10px] text-rose-400/90 font-medium flex items-center gap-1">
                ⚠️ {flight.disruption_warning}
              </span>
            )}
            {flight.compliance_details && (
              <span className="text-[10px] text-text-secondary/80 leading-relaxed">
                ℹ️ {flight.compliance_details}
              </span>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-5 mt-2 animate-fade-in-up">
      {/* Standard Flights Section */}
      <div className="flex flex-col gap-2.5">
        <h4 className="text-xs font-bold text-text-secondary uppercase tracking-wider flex items-center gap-1.5">
          <span>🎯 Available flights for requested sector</span>
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-ping" />
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {standardFlights.map(renderFlightCard)}
        </div>
      </div>

      {/* Alternative Hub Reroutes Section */}
      {alternateFlights.length > 0 && (
        <div className="flex flex-col gap-2.5 border-t border-border/80 pt-4">
          <h4 className="text-xs font-bold text-teal-400 uppercase tracking-wider flex items-center gap-1.5">
            <span>🛡️ Weather-resilient hub re-routing recommendations</span>
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {alternateFlights.map(renderFlightCard)}
          </div>
        </div>
      )}
    </div>
  );
}
