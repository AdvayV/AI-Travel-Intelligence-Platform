import React, { lazy, Suspense, useEffect, useState } from 'react';
import SignalBadge from './SignalBadge';
const DemandChart = lazy(() => import('./DemandChart'));

const money = n => new Intl.NumberFormat('en-US', {style:'currency',currency:'USD',maximumFractionDigits:0}).format(n);
const dateName = text => new Date(text+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'});
function Metric({label,value,note}) {
  return <div className="rounded-xl border border-border bg-surface p-4"><p className="text-[11px] text-text-secondary">{label}</p><p className="mt-2 text-xl font-bold tracking-tight">{value}</p><p className="mt-1 text-[10px] text-text-tertiary">{note}</p></div>;
}
export default function ForecastPanel({ route }) {
  const [routeDetail,setRouteDetail] = useState(null);
  const [error,setError] = useState('');
  const [day,setDay] = useState(0);
  useEffect(()=>{
    if (!route) { setRouteDetail(null); return; }
    const abort = new AbortController();
    setRouteDetail(null); setError('');
    fetch('/api/forecast/'+route.origin+'/'+route.destination,{signal:abort.signal})
      .then(r=>{if(!r.ok)throw new Error('Route details could not be loaded. Please refresh.');return r.json();})
      .then(setRouteDetail).catch(e=>{if(e.name!=='AbortError')setError(e.message);});
    return ()=>abort.abort();
  },[route?.origin,route?.destination,route?.updated_at]);
  useEffect(()=>setDay(0),[route?.origin,route?.destination]);
  if(!route) return <div className="min-h-[400px] flex items-center justify-center text-text-secondary text-sm">Select a route to explore its local forecast.</div>;
  const detail = routeDetail?.origin === route.origin && routeDetail?.destination === route.destination ? routeDetail : route;
  const daily = detail.daily_forecast[day];
  const weather = daily.weather;
  return <div className="flex flex-col gap-5">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
      <div><p className="text-xs text-text-tertiary">{detail.origin} → {detail.destination} · planning analytics</p><h2 className="text-2xl font-bold mt-1">{detail.dest_city_name}</h2></div>
      <div className="flex gap-3 items-center"><SignalBadge tier={daily.tier} score={daily.score}/><a className="text-xs border border-border bg-white px-3 py-2 rounded-lg hover:bg-surface" href={'/api/forecast/'+detail.origin+'/'+detail.destination+'/export'}>Export CSV</a></div>
    </header>
    {error&&<p role="alert" className="text-danger text-xs">{error}</p>}
    <div className="rounded-xl border border-warning/20 bg-warning-light p-3 text-xs text-text-secondary leading-relaxed">
      Experimental planning forecast · {detail.observation_count} simulated rank snapshots · low confidence.
      These are not observed booking volumes, calibrated probabilities, or bookable airline fares.
    </div>
    <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
      <Metric label="Selected-day rank index" value={Math.round(daily.demand*100)+'/100'} note={'Illustrative range '+Math.round(daily.lower*100)+'–'+Math.round(daily.upper*100)}/>
      <Metric label="Illustrative fare" value={money(daily.price_usd)} note={'USD · '+daily.surge_multiplier.toFixed(2)+'× simulated base'}/>
      <Metric label="Weather adjustment" value={daily.weather_factor.toFixed(3)+'×'} note={daily.weather_source}/>
      <Metric label="Local model contribution" value={Math.round(detail.model_weight*100)+'%'} note={detail.fallback?'Damped-trend fallback':'Chronos Bolt + damped baseline'}/>
    </div>
    <section className="rounded-xl border border-border bg-surface-raised p-5">
      <div className="flex flex-wrap justify-between gap-2"><div><h3 className="text-sm font-bold">28-day demand outlook</h3><p className="mt-1 text-xs text-text-secondary">Simulated relative rank index, not passenger counts</p></div><span className="text-[10px] rounded-md bg-surface border border-border px-2 py-1 h-fit">Local CPU inference</span></div>
      <Suspense fallback={<div className="h-[240px] flex items-center justify-center text-xs text-text-tertiary">Loading chart…</div>}><DemandChart detail={detail}/></Suspense>
      <div className="flex flex-wrap gap-4 text-[10px] text-text-secondary mt-3"><span>● Sample history</span><span className="text-accent">● Weather-adjusted forecast</span><span>┄ Unadjusted baseline/model blend</span><span>▰ Uncalibrated range</span></div>
      <p className="text-[11px] leading-relaxed text-text-tertiary mt-4">{detail.forecast_note} Weather is a bounded post-processing heuristic, not an input covariate to Chronos.</p>
    </section>
    <section className="rounded-xl border border-border bg-surface-raised p-5">
      <div className="flex flex-wrap justify-between gap-3 mb-4"><div><h3 className="text-sm font-bold">Compare departure dates</h3><p className="text-xs text-text-secondary mt-1">Weather adjustments are neutral whenever no forecast is available.</p></div>
        <select value={day} onChange={e=>setDay(Number(e.target.value))} aria-label="Departure date" className="border border-border rounded-lg text-xs p-2 bg-surface">{detail.daily_forecast.map(d=><option key={d.day_offset} value={d.day_offset}>{dateName(d.date)}{detail.optimal_day?.day_offset===d.day_offset?' · best balance':''}</option>)}</select>
      </div>
      <div className="grid grid-cols-7 sm:grid-cols-14 gap-1.5">{detail.daily_forecast.map(d=><button key={d.day_offset} onClick={()=>setDay(d.day_offset)} aria-pressed={d.day_offset===day} aria-label={dateName(d.date)+', '+(d.weather?.condition||'weather unavailable')+', '+money(d.price_usd)} className={'rounded-lg border p-2 text-center text-[10px] '+(day===d.day_offset?'bg-accent text-white border-accent':'border-border bg-surface hover:border-accent')}>
        <span className="block">{new Date(d.date+'T12:00:00').getDate()}</span><span className="block mt-1">{d.weather_available?Math.round(d.weather_appeal*100):'—'}</span>{detail.optimal_day?.day_offset===d.day_offset&&<span aria-label="Best modeled balance">★</span>}
      </button>)}</div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 text-xs">{[['Conditions',weather?.condition||'Unavailable'],['High / low',weather?.temp_max_c!=null&&weather?.temp_min_c!=null?Math.round(weather.temp_max_c)+'° / '+Math.round(weather.temp_min_c)+'° C':'—'],['Rain chance',weather?.precip_prob_pct!=null?weather.precip_prob_pct+'%':'—'],['Wind',weather?.wind_kmh!=null?weather.wind_kmh+' km/h':'—']].map(([label,value])=><div key={label}><p className="text-text-tertiary">{label}</p><p className="font-semibold mt-1">{value}</p></div>)}</div>
      {detail.optimal_day&&<p className="text-xs text-success mt-5">Best modeled weather/cost balance: {dateName(detail.optimal_day.date)} · {money(detail.optimal_day.price_usd)} USD. This is a heuristic, not a guaranteed cheapest flight.</p>}
      <p className="text-[11px] text-text-tertiary mt-4">No weather data is invented after the feed horizon. Stale cached weather is labeled and receives half the adjustment strength.</p>
    </section>
    <section className="rounded-xl border border-border bg-surface-raised p-5 overflow-x-auto">
      <h3 className="text-sm font-bold mb-3">Weekly summary</h3>
      <table className="w-full text-xs text-left"><thead className="text-text-tertiary"><tr><th className="py-2 font-medium">Period</th><th className="font-medium">Mean index</th><th className="font-medium">Illustrative range</th><th className="font-medium">Weather coverage</th></tr></thead><tbody>{detail.weekly_forecast.map((v,i)=><tr key={i} className="border-t border-border"><td className="py-3">Days {i*7+1}–{i*7+7}</td><td>{Math.round(v*100)}/100</td><td>{Math.round(detail.forecast_lower[i]*100)}–{Math.round(detail.forecast_upper[i]*100)}</td><td>{detail.weekly_weather_coverage[i]}/7 days</td></tr>)}</tbody></table>
    </section>
    <p className="text-[11px] leading-relaxed text-text-secondary">Opportunity combines the weather-adjusted rank index (80%) and comfort (20%). The simulated fare multiplier is 0.75 + 1.25 × rank index. It never changes live observed airline prices.</p>
  </div>;
}
