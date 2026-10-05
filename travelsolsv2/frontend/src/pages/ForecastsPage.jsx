import React, { useState } from 'react';
import useForecasts from '../hooks/useForecasts';
import OriginSelector from '../components/OriginSelector';
import RouteCard from '../components/RouteCard';
import ForecastPanel from '../components/ForecastPanel';
import ResizableSplit from '../components/ResizableSplit';

export default function ForecastsPage() {
  const [origin,setOrigin] = useState('BOM');
  const [selected,setSelected] = useState(null);
  const [search,setSearch] = useState('');
  const {forecasts,status,loading,error,refreshing,refresh,lastRefresh} = useForecasts(origin);
  const active = forecasts.find(r=>r.destination===selected) || forecasts[0] || null;
  const visible = forecasts.filter(r=>(r.destination+' '+r.dest_city_name).toLowerCase().includes(search.toLowerCase()));
  return <main className="w-full max-w-[1600px] mx-auto p-4 sm:p-6">
    <div className="flex flex-wrap justify-between items-center gap-4 mb-5"><div><h1 className="text-2xl font-bold tracking-tight">Local route forecasting</h1><p className="text-xs text-text-secondary mt-2">Amazon Chronos Bolt + destination weather. No search API or hosted AI inference.</p></div><button disabled={refreshing} onClick={refresh} className="rounded-lg bg-accent text-white px-4 py-2 text-xs font-semibold disabled:opacity-50">{refreshing?'Refreshing…':'Refresh forecasts'}</button></div>
    <div className="flex flex-wrap gap-3 text-[11px] text-text-secondary mb-5"><span className="rounded-md bg-surface-raised border border-border px-3 py-2">Chronos: {status?.chronos?.status?.replaceAll('_',' ') || 'connecting'}</span><span className="rounded-md bg-surface-raised border border-border px-3 py-2">Weather: {status?.weather?.live_routes || 0}/{status?.cache_size || 0} live routes{status?.weather?.stale_routes>0?' · '+status.weather.stale_routes+' stale':''}</span><span className="rounded-md bg-surface-raised border border-border px-3 py-2">{forecasts.length} routes from {origin}</span><span className="rounded-md bg-surface-raised border border-border px-3 py-2">{lastRefresh?'Updated '+new Date(lastRefresh).toLocaleTimeString():'Initial refresh pending'}</span></div>
    {error&&<p role="alert" className="text-danger text-xs border border-danger/20 bg-danger-light p-3 rounded-lg mb-4">{error}</p>}
    {status?.refresh?.error&&<p role="alert" className="text-danger text-xs mb-4">Refresh failed ({status.refresh.error}); the previous complete forecast is retained.</p>}
    <ResizableSplit minSize={280} maxSize={440} initialSize={340} storageKey="travelroute-forecast-sidebar" sidebar={<div className="rounded-xl border border-border bg-surface-raised p-4 flex flex-col gap-3"><OriginSelector selectedOrigin={origin} onSelect={v=>{setOrigin(v);setSelected(null);setSearch('');}}/><input aria-label="Search forecast destinations" placeholder="Search city or airport…" value={search} onChange={e=>setSearch(e.target.value)} className="rounded-lg border border-border bg-surface px-3 py-2 text-xs"/><div className="flex flex-col gap-3 max-h-[740px] overflow-y-auto pr-1">{loading?<p className="text-xs text-text-tertiary p-5">Loading forecasts…</p>:visible.length?visible.map(r=><RouteCard key={r.destination} route={r} isSelected={r.destination===active?.destination} onClick={()=>setSelected(r.destination)}/>):<p className="text-xs text-text-tertiary p-5">{search?'No matching destinations.':refreshing?'The first forecast refresh is running.':'No routes available. Refresh to retry.'}</p>}</div><p className="text-[10px] text-text-tertiary">Simulated rank history · illustrative USD fares</p></div>}>
      <div className="rounded-xl border border-border bg-surface-raised p-4 sm:p-5"><ForecastPanel route={active}/></div>
    </ResizableSplit>
  </main>;
}
