import { useEffect, useRef, useState } from 'react';
import useForecasts from './hooks/useForecasts';
import TopBar from './components/TopBar';
import OriginSelector from './components/OriginSelector';
import RouteCard from './components/RouteCard';
import ForecastPanel from './components/ForecastPanel';
import Icon from './components/Icon';
import './styles.css';

function savedWidth() {
  try { return Math.max(280, Math.min(440, Number(localStorage.getItem('travelsols.rail')) || 330)); }
  catch { return 330; }
}
function IntegrationCard({ name, integration, description }) {
  const status = integration?.status || 'connecting';
  const positive = ['live','ready'].includes(status);
  const neutral = ['not_used','illustrative','simulated','not_checked'].includes(status);
  return <article className="integration-card">
    <div className="section-heading"><h3>{name}</h3><span className={'status-chip '+(positive?'good':neutral?'neutral':'warning')}><span className="dot"/>{status.replaceAll('_',' ')}</span></div>
    <p>{description}</p>
    {integration?.model && <code>{integration.model}</code>}
    {integration?.total_routes>0 && <div className="integration-detail">{integration.live_routes} of {integration.total_routes} routes with live data</div>}
    {integration?.error && <div className="integration-detail warning-text">Last check: {integration.error}</div>}
    {integration?.note && <div className="integration-detail">{integration.note}</div>}
  </article>;
}
export default function App() {
  const [origin, setOrigin] = useState('BOM');
  const [tab, setTab] = useState('routes');
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('score');
  const [width, setWidth] = useState(savedWidth);
  const workspace = useRef(null);
  const {forecasts, health, loading, error, refresh, refreshing} = useForecasts(origin);
  useEffect(()=>{ try { localStorage.setItem('travelsols.rail',String(width)); } catch {} },[width]);
  const active = forecasts.find(r=>r.destination===selected) || forecasts[0] || null;
  const visible = forecasts.filter(r=>(r.destination+' '+r.dest_city_name).toLowerCase().includes(search.toLowerCase())).sort((a,b)=>sort==='city'?a.dest_city_name.localeCompare(b.dest_city_name):sort==='price'?a.current_price-b.current_price:b.score-a.score);
  const rising = forecasts.filter(r=>r.trend==='rising').length;
  const high = forecasts.filter(r=>r.score>=65).length;
  const mean = forecasts.length ? (forecasts.reduce((v,r)=>v+r.score,0)/forecasts.length).toFixed(0) : '—';
  function changeOrigin(value) { setOrigin(value); setSelected(null); setSearch(''); }
  const integrations = health?.integrations || {};
  return <div className="app-shell">
    <TopBar tab={tab} setTab={setTab} health={health} refreshing={refreshing} refresh={refresh}/>
    <main className="main">
      <div className="page-heading"><div><div className="eyebrow">TRAVELSOLS / INTELLIGENCE WORKSPACE</div><h1>{tab==='routes'?'A clearer view of where to go.':'Connected signals, clearly explained.'}</h1><p>{tab==='routes'?'Explore route momentum, destination weather, and the days worth considering.':'See which providers are live, which are modeled, and what still needs attention.'}</p></div>
        <a className="button secondary export-all" href="/api/export/all-routes"><Icon name="download"/>Export workspace</a>
      </div>
      {error && <div className="notice error" role="alert"><Icon name="info"/><span>{error}</span></div>}
      {health?.refresh?.error && <div className="notice error" role="alert">Refresh failed ({health.refresh.error}). Previously fetched data is retained.</div>}
      <div className="metrics">
        {[['Routes monitored',forecasts.length || '—','From '+origin, 'plane'],['High-opportunity routes',forecasts.length?high:'—','Score of 65 or higher','spark'],['Average opportunity',mean,'Rank index + travel comfort','activity'],['Rising destinations',forecasts.length?rising:'—','Across sample snapshots','arrow']].map(([label,value,caption,icon])=><article className="metric" key={label}><div className="metric-label">{label}<Icon name={icon} size={16}/></div><div className="metric-value">{value}{label==='Average opportunity'&&<small>/100</small>}</div><span>{caption}</span></article>)}
      </div>
      {tab==='integrations'?<section className="integrations-view" aria-label="Integration status">
        <div className="integration-grid">
          <IntegrationCard name="Destination weather" integration={integrations.weather} description="Open-Meteo forecasts, cached for 30 minutes. No API key required."/>
          <IntegrationCard name="Amazon Chronos" integration={integrations.chronos} description="Local CPU inference, blended conservatively with a damped-trend baseline. Sparse sample data means low confidence."/>
          <IntegrationCard name="AI travel advisor" integration={integrations.advisor} description="Hugging Face hosted inference. Its status updates after an advisor request; a local fallback is explicitly labeled."/>
          <IntegrationCard name="Search interest" integration={integrations.trends} description="Google Trends via pytrends. Rate limits can trigger a labeled fallback, which is excluded from the demand blend."/>
          <IntegrationCard name="GDS route history" integration={integrations.gds} description="Three sample rank snapshots per route, not observed booking volumes."/>
          <IntegrationCard name="Fare estimates" integration={integrations.pricing} description="An explainable pricing simulation with bounded multipliers. Not connected to airline inventory."/>
          <IntegrationCard name="Neo4j" integration={integrations.neo4j} description="Architecture scope"/>
        </div><div className="notice"><Icon name="info"/><span>Route forecasts are experimental. To validate accuracy, connect real, regularly sampled booking history and evaluate against held-out periods.</span></div>
      </section>:<>
        <div className="workspace" ref={workspace} style={{'--rail-width':width+'px'}}>
          <aside className="route-rail" aria-label="Route explorer">
            <div className="rail-heading"><h2>Route explorer</h2><span className="count">{forecasts.length}</span></div>
            <OriginSelector selectedOrigin={origin} onOriginChange={changeOrigin}/>
            <div className="search-field"><Icon name="search" size={16}/><input aria-label="Search destinations" placeholder="Search city or airport…" value={search} onChange={e=>setSearch(e.target.value)}/>{search&&<button aria-label="Clear search" onClick={()=>setSearch('')}><Icon name="close" size={14}/></button>}</div>
            <div className="rail-sort"><span>{visible.length} destinations</span><select aria-label="Sort routes" value={sort} onChange={e=>setSort(e.target.value)}><option value="score">Opportunity</option><option value="city">City A–Z</option><option value="price">Lowest estimate</option></select></div>
            <div className="route-list">{loading?<div className="rail-empty"><span className="loader"/>Loading routes…</div>:visible.length?visible.map(route=><RouteCard key={route.destination} route={route} selected={active?.destination===route.destination} onClick={r=>setSelected(r.destination)}/>):<div className="rail-empty">{search?'No destinations match your search.':refreshing?'Preparing route forecasts…':'No routes available. Try Refresh data.'}</div>}</div>
            <div className="rail-footer"><span className="dot"/><span>Sample GDS · Illustrative USD fares</span></div>
          </aside>
          <div className="resize-handle" role="separator" aria-label="Resize route explorer" aria-orientation="vertical" aria-valuemin={280} aria-valuemax={440} aria-valuenow={width} tabIndex={0}
            onPointerDown={e=>{e.preventDefault();e.currentTarget.setPointerCapture(e.pointerId);}}
            onPointerMove={e=>{if(e.currentTarget.hasPointerCapture(e.pointerId))setWidth(Math.max(280,Math.min(440,e.clientX-workspace.current.getBoundingClientRect().left)));}}
            onPointerUp={e=>{if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);}}
            onKeyDown={e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();setWidth(w=>Math.max(280,Math.min(440,w+(e.key==='ArrowRight'?20:-20))));}}}><span/></div>
          <section className="route-detail" aria-label="Selected route">{active?<ForecastPanel key={origin+'-'+active.destination} forecast={active}/>:<div className="empty-state"><span className="empty-icon"><Icon name="plane" size={30}/></span><h2>{loading||refreshing?'Preparing your workspace':'No route selected'}</h2><p>{loading||refreshing?'Fetching destination signals and running route forecasts.':'Choose a departure airport to explore the available routes.'}</p></div>}</section>
        </div>
        <div className="workspace-footnote"><Icon name="info" size={14}/><span>Planning intelligence, not a booking engine. Demand uses simulated rank data; prices are illustrative USD estimates.</span><span className="footnote-right">TravelSols v1</span></div>
      </>}
    </main>
  </div>;
}
