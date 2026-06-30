import React, { useState, useEffect } from 'react';
import SignalBadge from './SignalBadge';

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function StatCard({ label, value, sub, accent, small }) {
  return (
    <div style={{
      flex: 1,
      background: '#131D35',
      border: `1px solid ${accent || '#1E2D4A'}`,
      borderRadius: '10px',
      padding: '12px 14px',
      textAlign: 'center',
      minWidth: 120,
    }}>
      <div style={{ color: '#6B7FA3', fontSize: '10px', marginBottom: '5px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
      <div style={{ fontSize: small ? '16px' : '20px', fontWeight: 'bold', color: accent || 'white', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</div>
      {sub && <div style={{ color: '#6B7FA3', fontSize: '10px', marginTop: '4px' }}>{sub}</div>}
    </div>
  );
}

function ProgressBar({ label, color, percent, sub }) {
  return (
    <div style={{ marginBottom: '14px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
        <span style={{ color: '#A0B0CC', fontSize: '12px' }}>{label}</span>
        <span style={{ color: 'white', fontWeight: 'bold', fontSize: '12px' }}>{percent}%</span>
      </div>
      <div style={{ height: '6px', background: '#1E2D4A', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{
          width: `${Math.max(0, Math.min(100, percent))}%`,
          height: '100%',
          background: `linear-gradient(90deg, ${color}88, ${color})`,
          borderRadius: '3px',
          transition: 'width 0.7s ease',
        }} />
      </div>
      {sub && <div style={{ color: '#6B7FA3', fontSize: '11px', marginTop: '3px' }}>{sub}</div>}
    </div>
  );
}

function SurgeRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid #1A2640' }}>
      <span style={{ color: '#8A9BB8', fontSize: '12px' }}>{label}</span>
      <span style={{ color: color || 'white', fontWeight: 'bold', fontSize: '13px', fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}

/* ─── Interactive Calendar Component ─────────────────────────────────────── */

function InteractiveCalendar({ weather, selectedOffset, onSelect, optimalOffset }) {
  if (!weather || !weather.days || weather.days.length === 0) {
    return <div style={{ color: '#6B7FA3', fontSize: '12px' }}>Loading calendar data...</div>;
  }

  const days = weather.days;
  
  // Align calendar cells to actual weekday of the first forecast date
  const firstDate = new Date(days[0].date + 'T00:00:00');
  const startDayOfWeek = firstDate.getDay(); // 0 = Sun, 1 = Mon, ..., 6 = Sat
  
  const cells = [];
  
  // 1. Padding for past days in current week
  for (let i = 0; i < startDayOfWeek; i++) {
    cells.push({
      type: 'past',
      key: `past-${i}`
    });
  }
  
  // 2. Active forecast days (14 days)
  days.forEach((day, index) => {
    cells.push({
      type: 'forecast',
      dayData: day,
      offset: index,
      key: `day-${index}`
    });
  });
  
  // 3. Padding for empty cells to complete the grid
  const remainder = cells.length % 7;
  const paddingNeeded = remainder === 0 ? 0 : 7 - remainder;
  for (let i = 0; i < paddingNeeded; i++) {
    cells.push({
      type: 'empty',
      key: `empty-${i}`
    });
  }

  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div style={{ background: '#0D1428', border: '1px solid #1E2D4A', borderRadius: '12px', padding: '18px', marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
        <h3 style={{ margin: 0, fontSize: '14px', color: 'white', display: 'flex', alignItems: 'center', gap: '6px' }}>
          📅 Dynamic 14-Day Calendar Pricing
        </h3>
        <span style={{ fontSize: '11px', color: '#6B7FA3' }}>Click a date to recalculate score & weather surge</span>
      </div>

      {/* Weekday columns */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px', textAlign: 'center', marginBottom: '6px' }}>
        {weekdays.map((w, idx) => (
          <div key={idx} style={{ color: '#6B7FA3', fontSize: '10px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            {w}
          </div>
        ))}
      </div>

      {/* Calendar Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px' }}>
        {cells.map((cell) => {
          if (cell.type === 'past') {
            return (
              <div
                key={cell.key}
                style={{
                  background: '#070C1B',
                  border: '1px dashed #142038',
                  borderRadius: '8px',
                  height: '75px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#344563',
                  fontSize: '11px',
                  userSelect: 'none'
                }}
              >
                —
              </div>
            );
          }
          if (cell.type === 'empty') {
            return (
              <div
                key={cell.key}
                style={{
                  background: '#070C1B',
                  border: '1px solid #101B30',
                  borderRadius: '8px',
                  height: '75px',
                  opacity: 0.15
                }}
              />
            );
          }

          const { dayData, offset } = cell;
          const isSelected = offset === selectedOffset;
          const isOptimal = offset === optimalOffset;
          const dateObj = new Date(dayData.date + 'T00:00:00');
          const dayNum = dateObj.getDate();
          
          const appealColor = dayData.appeal >= 0.75 ? '#4CAF50'
                            : dayData.appeal >= 0.50 ? '#FF9B00'
                            : '#FF3B3B';

          // Show month shortname if it's the first card or day 1
          const showMonth = offset === 0 || dayNum === 1;
          const monthLabel = showMonth ? dateObj.toLocaleDateString('en-IN', { month: 'short' }) + ' ' : '';

          return (
            <div
              key={cell.key}
              onClick={() => onSelect(offset)}
              className={`calendar-card ${isSelected ? 'selected' : ''} ${isOptimal ? 'optimal' : ''}`}
            >
              {isOptimal && (
                <div style={{
                  position: 'absolute',
                  top: '-6px',
                  right: '-6px',
                  background: '#EAB308',
                  color: '#0D1428',
                  borderRadius: '50%',
                  width: '14px',
                  height: '14px',
                  fontSize: '9px',
                  fontWeight: 'bold',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
                  zIndex: 2
                }} title="Optimal Travel Date (Best Price & Weather)">
                  ★
                </div>
              )}
              {/* Date & Appeal Indicator */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                <span style={{ fontSize: '11px', fontWeight: 'bold', color: isSelected ? 'white' : '#A0B0CC' }}>
                  {monthLabel}{dayNum}
                </span>
                <span style={{ fontSize: '13px' }}>{dayData.emoji}</span>
              </div>

              {/* Temperatures */}
              <div style={{ textAlign: 'center', margin: '2px 0' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold', color: isSelected ? 'white' : '#FF9B00' }}>
                  {dayData.temp_max_c}°
                </span>
                <span style={{ fontSize: '9px', color: isSelected ? '#E0E7FF' : '#6B7FA3', marginLeft: '3px' }}>
                  {dayData.temp_min_c}°
                </span>
              </div>

              {/* Appeal dot */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                <span style={{ color: isSelected ? '#E0E7FF' : '#6B7FA3', fontSize: '8px' }}>
                  {offset === 0 ? 'Today' : `d+${offset}`}
                </span>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: appealColor }} title={`Appeal: ${Math.round(dayData.appeal * 100)}%`} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ─── Main Panel ─────────────────────────────────────────────────────────── */

function ForecastPanel({ route }) {
  const [routeDetail, setRouteDetail] = useState(null);
  const [weather, setWeather]         = useState(null);
  const [loadingRoute, setLoadingRoute]   = useState(false);
  const [loadingWeather, setLoadingWeather] = useState(false);
  const [selectedDayOffset, setSelectedDayOffset] = useState(0);
  const [advisorAnswer, setAdvisorAnswer] = useState('');
  const [advisorLoading, setAdvisorLoading] = useState(false);
  const [advisorQuestion, setAdvisorQuestion] = useState('');

  // Reset selected offset and advisor states when route changes
  useEffect(() => {
    setSelectedDayOffset(0);
    setAdvisorAnswer('');
    setAdvisorLoading(false);
  }, [route]);

  const handleAskAdvisor = async (e) => {
    if (e) e.preventDefault();
    if (!advisorQuestion.trim() || !route) return;

    const queryText = advisorQuestion;
    setAdvisorQuestion('');
    setAdvisorLoading(true);
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout
    
    try {
      const res = await fetch(`/api/advisor/${route.origin}/${route.destination}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: queryText }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      const data = await res.json();
      setAdvisorAnswer(data.answer || '');
    } catch (e) {
      console.error(e);
      setAdvisorAnswer('Failed to get a response from Qwen3. Please try another question.');
    } finally {
      setAdvisorLoading(false);
    }
  };

  const askPredefinedQuestion = async (questionText) => {
    if (!route) return;
    setAdvisorLoading(true);
    setAdvisorAnswer('');
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    
    try {
      const res = await fetch(`/api/advisor/${route.origin}/${route.destination}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: questionText }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      const data = await res.json();
      setAdvisorAnswer(data.answer || '');
    } catch (e) {
      console.error(e);
      setAdvisorAnswer('Failed to get a response from Qwen3. Please try again.');
    } finally {
      setAdvisorLoading(false);
    }
  };

  // Fetch dynamic route detail on route or selected date offset change
  useEffect(() => {
    if (!route) { setRouteDetail(null); return; }

    const fetchRoute = async () => {
      setLoadingRoute(true);
      try {
        const res = await fetch(`/api/forecast/${route.origin}/${route.destination}?day_offset=${selectedDayOffset}`);
        const data = await res.json();
        setRouteDetail(data);
      } catch (e) { console.error(e); }
      finally { setLoadingRoute(false); }
    };

    fetchRoute();
  }, [route, selectedDayOffset]);

  // Fetch weather forecast details (only when route destination changes)
  useEffect(() => {
    if (!route) { setWeather(null); return; }

    const fetchWeather = async () => {
      setLoadingWeather(true);
      setWeather(null);
      try {
        const res = await fetch(`/api/weather/${route.destination}`);
        const data = await res.json();
        setWeather(data);
      } catch (e) { console.error(e); }
      finally { setLoadingWeather(false); }
    };

    fetchWeather();
  }, [route]);

  if (!route) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#6B7FA3' }}>
        <div style={{ fontSize: '56px', marginBottom: '16px' }}>✈️</div>
        <div style={{ fontSize: '17px', marginBottom: '8px', color: '#A0B0CC' }}>Select a route to view its forecast</div>
        <div style={{ fontSize: '12px', color: '#4A6080' }}>TravelRoute Intelligence v2 · Surge Engine Active</div>
      </div>
    );
  }

  const d = routeDetail || route;

  const surgeColor = d.surge_multiplier >= 2.0 ? '#FF3B3B'
                   : d.surge_multiplier >= 1.5  ? '#FF9B00'
                   : d.surge_multiplier >= 1.2  ? '#FFD700'
                   : d.surge_multiplier < 1.0   ? '#4CAF50'
                   : '#A0B0CC';

  const tierColor = { PLATINUM: '#A855F7', HOT: '#FF3B3B', RISING: '#FF9B00', WATCH: '#4A9EFF', COLD: '#6B7FA3' }[d.tier] || '#4A9EFF';

  // Trends display: convert 0-1 float to readable %
  const trendsPct = d.trend_score != null ? Math.round(d.trend_score * 100) : 0;

  return (
    <div style={{ maxWidth: '880px', margin: '0 auto', width: '100%', paddingBottom: '30px' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '24px', margin: '0 0 8px 0', color: 'white', letterSpacing: '-0.5px' }}>
          {d.origin} → {d.destination}
          {d.surge_capped && (
            <span style={{ marginLeft: '10px', fontSize: '12px', color: '#FF3B3B', border: '1px solid #FF3B3B', padding: '2px 8px', borderRadius: '8px' }}>⚠ CAPPED 2.50×</span>
          )}
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '16px', color: '#E0E8FF' }}>{d.dest_city_name}</span>
          <SignalBadge tier={d.tier} score={d.score} />
          {d.surge_version === 'v2' && (
            <span style={{ fontSize: '11px', color: '#4A9EFF', border: '1px solid #1E2D4A', padding: '2px 7px', borderRadius: '5px' }}>ENGINE v2</span>
          )}
          {d.selected_date ? (
            <span style={{ fontSize: '12px', color: '#60A5FA', background: '#3B82F615', border: '1px solid #3B82F640', padding: '2px 8px', borderRadius: '8px', fontWeight: 'bold' }}>
              📅 {new Date(d.selected_date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
          ) : weather?.today_emoji ? (
            <span style={{ fontSize: '13px', color: '#A0B0CC' }}>
              {weather.today_emoji} {weather.today_condition} {weather.today_temp_max_c != null ? `· ${weather.today_temp_max_c}°C` : ''}
            </span>
          ) : null}
        </div>
      </div>

      {/* ── Price stat cards ── */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
        <StatCard label="Base Price" value={`$${d.base_price?.toFixed(0) || '---'}`} accent="#6B7FA3" />
        <StatCard label="Surge" value={`${d.surge_multiplier?.toFixed(3) || '1.000'}×`} accent={surgeColor}
          sub={d.surge_multiplier < 1.0 ? '💸 Discount applied' : d.surge_capped ? '⚠ CAPPED' : undefined} />
        <StatCard label="Dynamic Price" value={`$${d.current_price?.toFixed(0) || '---'}`} accent={surgeColor} />
        <StatCard label="Tier Score" value={`${d.score}/100`} accent={tierColor} sub={d.tier} />
      </div>

      {/* ── Dynamic 14-Day Calendar & Selected Weather Detail ── */}
      {loadingWeather ? (
        <div style={{ background: '#0D1428', border: '1px solid #1E2D4A', borderRadius: '12px', padding: '18px', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6B7FA3', fontSize: '13px', padding: '10px 0' }}>
            <div style={{ width: '14px', height: '14px', border: '2px solid #1E2D4A', borderTop: '2px solid #4A9EFF', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
            Fetching live weather & calendar signals…
          </div>
        </div>
      ) : weather ? (
        <>
          {/* Optimal Travel Date Alert Box */}
          {d.optimal_date && (
            <div style={{
              background: 'linear-gradient(90deg, rgba(234, 179, 8, 0.08), rgba(59, 130, 246, 0.08))',
              border: '1px solid rgba(234, 179, 8, 0.3)',
              borderRadius: '12px',
              padding: '12px 16px',
              marginBottom: '16px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
              boxShadow: '0 4px 20px rgba(0,0,0,0.15)'
            }}>
              <div style={{ fontSize: '13px', color: '#E0E7FF', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '18px' }}>💡</span>
                <span>
                  <span style={{ color: '#EAB308', fontWeight: 'bold' }}>Recommended Optimal Travel Date:</span>{' '}
                  <b style={{ color: 'white' }}>
                    {new Date(d.optimal_date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'short' })}
                  </b>{' '}
                  ({d.optimal_weather_emoji} {d.optimal_weather_condition}, ${d.optimal_price?.toFixed(0)}) offers the absolute best balance of weather comfort & lowest price!
                </span>
              </div>
              <button
                onClick={() => setSelectedDayOffset(d.optimal_day_offset)}
                style={{
                  background: '#EAB308',
                  color: '#0D1428',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '6px 14px',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: '0 2px 4px rgba(234, 179, 8, 0.2)'
                }}
                onMouseOver={(e) => { e.target.style.opacity = '0.88'; e.target.style.transform = 'scale(1.03)'; }}
                onMouseOut={(e) => { e.target.style.opacity = '1'; e.target.style.transform = 'scale(1)'; }}
              >
                Select Date
              </button>
            </div>
          )}

          {/* Calendar Widget */}
          <InteractiveCalendar
            weather={weather}
            selectedOffset={selectedDayOffset}
            onSelect={setSelectedDayOffset}
            optimalOffset={d.optimal_day_offset}
          />
          
          {/* Selected Day Weather details banner */}
          {weather.days && weather.days[selectedDayOffset] && (
            <div style={{
              background: '#0D1428',
              border: '1px solid #1E2D4A',
              borderRadius: '12px',
              padding: '16px',
              marginBottom: '16px'
            }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '13px', color: 'white' }}>🌤 Selected Date Weather Detail</h4>
              <div style={{
                background: '#131D35',
                border: '1px solid #1E2D4A',
                borderRadius: '8px',
                padding: '12px 14px',
                fontSize: '12px',
                color: '#A0B0CC',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px'
              }}>
                <div>
                  📅 <b style={{ color: 'white' }}>{new Date(weather.days[selectedDayOffset].date + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })}</b>
                  {selectedDayOffset === 0 && <span style={{ marginLeft: '6px', fontSize: '10px', color: '#4A9EFF', background: '#4A9EFF15', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold' }}>TODAY</span>}
                </div>
                <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                  <span>Weather: <b style={{ color: 'white' }}>{weather.days[selectedDayOffset].emoji} {weather.days[selectedDayOffset].condition} ({weather.days[selectedDayOffset].temp_max_c}°C / {weather.days[selectedDayOffset].temp_min_c}°C)</b></span>
                  <span>Rain: <b style={{ color: 'white' }}>💧 {weather.days[selectedDayOffset].precip_prob_pct}% ({weather.days[selectedDayOffset].precipitation_mm}mm)</b></span>
                  <span>Wind: <b style={{ color: 'white' }}>💨 {weather.days[selectedDayOffset].wind_kmh} km/h</b></span>
                  <span>Appeal: <b style={{ color: weather.days[selectedDayOffset].appeal >= 0.75 ? '#4CAF50' : weather.days[selectedDayOffset].appeal >= 0.50 ? '#FF9B00' : '#FF3B3B' }}>{Math.round(weather.days[selectedDayOffset].appeal * 100)}%</b></span>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        <div style={{ background: '#0D1428', border: '1px solid #1E2D4A', borderRadius: '12px', padding: '18px', marginBottom: '16px', color: '#6B7FA3', fontSize: '13px' }}>
          Weather data unavailable for this destination.
        </div>
      )}

      {/* ── Signal breakdown ── */}
      <div style={{ background: '#0D1428', border: '1px solid #1E2D4A', borderRadius: '12px', padding: '18px', marginBottom: '16px' }}>
        <h3 style={{ margin: '0 0 16px 0', fontSize: '14px', color: 'white' }}>📊 Signal Breakdown</h3>
        <ProgressBar
          label={`Google Trends · ${trendsPct}% search interest`}
          color="#9C27B0"
          percent={trendsPct}
          sub={trendsPct > 15 ? 'Strong consumer intent from India' : trendsPct > 5 ? 'Moderate search activity' : 'Low search activity'}
        />
        <ProgressBar
          label={`Weather Appeal · ${weather?.comfort_label || d.weather_label || ''}`}
          color="#4CAF50"
          percent={weather && weather.days && weather.days[selectedDayOffset] ? Math.round(weather.days[selectedDayOffset].appeal * 100) : Math.round((d.weather_score || 0) * 100)}
          sub={`Multiplier ×${d.weather_multiplier} · Decay factor ${d.temporal_decay}`}
        />
        <ProgressBar
          label={`Demand Score · ${Math.round(d.raw_base || 0)}%`}
          color="#3B82F6"
          percent={Math.round(d.raw_base || 0)}
          sub="Calculated from live Google Trends search interest"
        />
      </div>

      {/* ── Surge pricing breakdown ── */}
      <div style={{ background: '#0D1428', border: '1px solid #1E2D4A', borderRadius: '12px', padding: '18px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '14px' }}>
          <h3 style={{ margin: 0, fontSize: '14px', color: 'white' }}>⚡ Surge Breakdown (v2)</h3>
          <span style={{ color: '#4A6080', fontSize: '11px' }}>Hard cap: 2.50× · Floor: 0.75×</span>
        </div>
        <SurgeRow label="Opportunity Score"    value={`${d.score} / 100`}               color={tierColor} />
        <SurgeRow label="Raw Base Score"        value={`${d.raw_base} / 100`}             color="#6B7FA3" />
        <SurgeRow label="Temporal Decay"        value={`× ${d.temporal_decay}`}           color="#A0B0CC" />
        <SurgeRow label="Demand Base Surge"     value={`× ${d.base_surge?.toFixed(4)}`}   color="#FF9B00" />
        <SurgeRow label="Weather Boost"         value={`+ ${d.weather_boost?.toFixed(4)}`} color="#4CAF50" />
        <SurgeRow label="Alt-Route Adjustment"  value={`${(d.alt_route_delta || 0) >= 0 ? '+' : ''}${d.alt_route_delta?.toFixed(4)}`} color="#9C27B0" />
        <div style={{ marginTop: '14px', display: 'flex', gap: '10px' }}>
          <StatCard label="Final Multiplier" value={`${d.surge_multiplier?.toFixed(3)}×`} accent={surgeColor} />
          <StatCard label="Final Price (USD)" value={`$${d.current_price?.toFixed(0)}`} accent={surgeColor} />
        </div>
        {d.surge_multiplier < 1.0 && (
          <div style={{ marginTop: '10px', background: '#4CAF5015', border: '1px solid #4CAF5040', borderRadius: '8px', padding: '8px 12px', fontSize: '12px', color: '#4CAF50' }}>
            💸 Discount pricing active — low demand detected ({d.tier} tier). Multiplier below 1.00× reduces base fare.
          </div>
        )}
      </div>

      {/* ── Hugging Face AI Travel Advisor ── */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(20, 16, 50, 0.9), rgba(9, 11, 26, 0.98))',
        border: '1px solid rgba(129, 140, 248, 0.35)',
        borderRadius: '16px',
        padding: '22px',
        marginBottom: '20px',
        boxShadow: '0 10px 40px rgba(79, 70, 229, 0.15)',
        position: 'relative',
        overflow: 'hidden',
        backdropFilter: 'blur(8px)'
      }}>
        {/* Decorative subtle backdrop light */}
        <div style={{
          position: 'absolute',
          top: '-50%',
          left: '-50%',
          width: '200%',
          height: '200%',
          background: 'radial-gradient(circle, rgba(129, 140, 248, 0.12) 0%, transparent 60%)',
          pointerEvents: 'none',
          zIndex: 0
        }} />

        <div style={{ position: 'relative', zIndex: 1 }}>
          <h3 style={{ margin: '0 0 14px 0', fontSize: '15px', color: '#A5B4FC', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '10px', fontWeight: '800', letterSpacing: '0.3px' }}>
              🤖 AI Travel Advisor
            </span>
            {advisorAnswer && !advisorAnswer.includes('Hugging Face API Key is not configured') && (
              <span style={{
                fontSize: '9.5px',
                background: 'linear-gradient(90deg, #4F46E5, #7C3AED)',
                color: '#E0E7FF',
                padding: '3px 10px',
                borderRadius: '12px',
                fontWeight: 'bold',
                letterSpacing: '0.7px',
                boxShadow: '0 2px 8px rgba(79, 70, 229, 0.4)'
              }}>
                HF HUB LIVE
              </span>
            )}
          </h3>
          
          {advisorLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px 0', gap: '12px' }}>
              <div style={{
                width: '28px',
                height: '28px',
                border: '3px solid rgba(129, 140, 248, 0.15)',
                borderTop: '3px solid #818CF8',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
                boxShadow: '0 0 16px rgba(129, 140, 248, 0.3)'
              }} />
              <div style={{ color: '#C7D2FE', fontSize: '12.5px', fontWeight: '600', animation: 'pulse 1.5s ease-in-out infinite', letterSpacing: '0.2px' }}>
                Consulting Qwen3 travel pricing analyst…
              </div>
            </div>
          ) : !advisorAnswer ? (
            <div style={{ textAlign: 'center', padding: '12px 0' }}>
              <p style={{ margin: '0 0 16px 0', fontSize: '13px', color: '#94A3B8', lineHeight: '1.65' }}>
                Need expert routing advice? Let Qwen3 analyze weather comfort, Google Trends search interest, and alternate routes to summarize this opportunity.
              </p>
              <button
                type="button"
                onClick={() => askPredefinedQuestion('Summarize this route opportunity in 2 sentences for a travel agent.')}
                style={{
                  background: 'linear-gradient(135deg, #4F46E5, #7C3AED)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '10px',
                  padding: '10px 24px',
                  fontSize: '13px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  boxShadow: '0 4px 16px rgba(79, 70, 229, 0.4)'
                }}
                onMouseOver={(e) => { e.target.style.opacity = '0.9'; e.target.style.transform = 'scale(1.03)'; }}
                onMouseOut={(e) => { e.target.style.opacity = '1'; e.target.style.transform = 'scale(1)'; }}
              >
                🔮 Generate AI Analysis
              </button>
            </div>
          ) : (
            <>
              <p style={{
                margin: '0 0 16px 0',
                fontSize: '14px',
                fontFamily: "'Outfit', 'Inter', system-ui, sans-serif",
                color: '#E2E8F0',
                lineHeight: '1.7',
                background: 'rgba(255,255,255,0.015)',
                borderLeft: '3px solid #818CF8',
                padding: '8px 14px',
                borderRadius: '0 8px 8px 0',
                letterSpacing: '0.1px'
              }}>
                {advisorAnswer.replace(/\*\*/g, '').replace(/\*/g, '')}
              </p>
              
              {/* Predefined quick-query chips */}
              {!advisorAnswer.includes('Hugging Face API Key is not configured') && (
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                  {['Why this price?', 'Weather status?', 'Best travel day?'].map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => askPredefinedQuestion(q)}
                      style={{
                        background: 'rgba(79, 70, 229, 0.18)',
                        border: '1px solid rgba(129, 140, 248, 0.3)',
                        color: '#E0E7FF',
                        borderRadius: '14px',
                        padding: '4px 10px',
                        fontSize: '11px',
                        fontWeight: '600',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                      className="quick-chip"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
              
              <form onSubmit={handleAskAdvisor} style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  placeholder="Ask advisor a custom question..."
                  value={advisorQuestion}
                  onChange={(e) => setAdvisorQuestion(e.target.value)}
                  style={{
                    flex: 1,
                    background: '#0B0C18',
                    border: '1px solid #1E2D4A',
                    borderRadius: '8px',
                    padding: '9px 14px',
                    color: 'white',
                    fontSize: '13px',
                    outline: 'none',
                    transition: 'border-color 0.2s'
                  }}
                  onFocus={(e) => e.target.style.borderColor = '#4F46E5'}
                  onBlur={(e) => e.target.style.borderColor = '#1E2D4A'}
                />
                <button
                  type="submit"
                  disabled={!advisorQuestion.trim()}
                  style={{
                    background: '#4F46E5',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '9px 18px',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    cursor: advisorQuestion.trim() ? 'pointer' : 'default',
                    opacity: advisorQuestion.trim() ? 1 : 0.5,
                    transition: 'all 0.2s',
                    boxShadow: '0 2px 8px rgba(79, 70, 229, 0.3)'
                  }}
                  onMouseOver={(e) => { if (advisorQuestion.trim()) e.target.style.background = '#4338CA'; }}
                  onMouseOut={(e) => { e.target.style.background = '#4F46E5'; }}
                >
                  Ask
                </button>
              </form>
            </>
          )}
        </div>
      </div>

      {/* ── AI signal explanation ── */}
      <div style={{ background: '#0D142840', border: '1px solid #1A2840', borderRadius: '10px', padding: '14px', marginBottom: '20px' }}>
        <div style={{ color: '#4A9EFF', fontSize: '11px', fontWeight: 'bold', marginBottom: '5px' }}>🤖 Intelligence Summary</div>
        <div style={{ color: '#8A9BB8', fontSize: '12px', lineHeight: '1.7' }}>
          {d.signal_explanation || 'Loading signal intelligence…'}
        </div>
      </div>

      {/* ── CTA ── */}
      <button style={{
        background: 'linear-gradient(135deg, #4A9EFF, #7C5CFC)',
        color: 'white', border: 'none', padding: '15px 24px',
        borderRadius: '10px', cursor: 'pointer', fontWeight: 'bold',
        fontSize: '14px', width: '100%', transition: 'opacity 0.2s',
      }}
        onMouseOver={(e) => e.target.style.opacity = '0.88'}
        onMouseOut={(e)  => e.target.style.opacity = '1'}
      >
        Pre-negotiate rates for {d.origin} → {d.destination} on {d.selected_date ? new Date(d.selected_date + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Today'} →
      </button>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
        
        .quick-chip {
          transition: all 0.2s ease !important;
        }

        .quick-chip:hover {
          background: rgba(79, 70, 229, 0.3) !important;
          border-color: rgba(129, 140, 248, 0.65) !important;
          transform: translateY(-1px);
        }

        .quick-chip:active {
          transform: translateY(0);
        }

        /* ─── Calendar Styling ─── */
        .calendar-card {
          background: #131D35;
          border: 1px solid #1E2D4A;
          border-radius: 8px;
          padding: 6px;
          height: 75px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        
        .calendar-card:hover {
          background: #1C2A4E !important;
          border-color: #3B82F6 !important;
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        }
        
        .calendar-card.selected {
          background: linear-gradient(135deg, #2563EB, #7C3AED) !important;
          border-color: #60A5FA !important;
          box-shadow: 0 0 16px rgba(96, 165, 250, 0.4);
        }
        
        .calendar-card.selected:hover {
          background: linear-gradient(135deg, #1D4ED8, #6D28D9) !important;
          transform: translateY(-2px);
        }

        .calendar-card.optimal {
          border: 1.5px solid #EAB308 !important;
          position: relative;
        }

        .calendar-card.optimal:not(.selected) {
          box-shadow: 0 0 8px rgba(234, 179, 8, 0.15);
        }
      `}</style>
    </div>
  );
}

export default ForecastPanel;
