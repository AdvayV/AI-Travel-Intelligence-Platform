import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import SignalBadge from './SignalBadge';
const DemandChart = lazy(() => import('./DemandChart'));

const money = value => value==null?'—':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(value);
const dateLabel = (date, options={month:'short',day:'numeric'}) => date ? new Date(date+'T12:00:00').toLocaleDateString('en-US',options) : '—';
const decimal = value => value==null?'—':Number(value).toFixed(2);
function SignalRow({label,value,source}) {
  return <div className="signal-row"><div><span>{label}</span><small>{source}</small></div><div className="signal-bar"><span style={{width:Math.max(0,Math.min(100,(value||0)*100))+'%'}}/></div><strong>{value==null?'—':Math.round(value*100)}</strong></div>;
}
export default function ForecastPanel({ forecast }) {
  const [detail,setDetail]=useState(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const [view,setView]=useState('overview');
  const [day,setDay]=useState(0);
  const [question,setQuestion]=useState('');
  const [messages,setMessages]=useState([]);
  const [asking,setAsking]=useState(false);
  const advisorAbort=useRef(null);
  const advisorEnd=useRef(null);
  useEffect(()=>{
    const abort = new AbortController();
    setLoading(true);setError('');
    fetch('/api/forecast/'+forecast.origin+'/'+forecast.destination,{signal:abort.signal})
      .then(r=>{if(!r.ok)throw new Error('Route details could not be loaded. Please retry after refreshing.');return r.json();})
      .then(data=>{setDetail(data);setLoading(false);})
      .catch(e=>{if(e.name!=='AbortError'){setError(e.message);setLoading(false);}});
    return ()=>abort.abort();
  },[forecast.origin,forecast.destination,forecast.updated_at]);
  useEffect(()=>()=>advisorAbort.current?.abort(),[]);
  useEffect(()=>{advisorEnd.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[messages,asking]);
  const base=detail||forecast;
  const schedule=detail?.daily_schedules||[];
  const current=schedule[day]||base;
  const selectedWeather=current.selected_weather;
  const price=current.price_usd??base.current_price;
  const score=current.score??base.score;
  const multiplier=current.surge_multiplier??base.surge_multiplier;
  const best=detail?.optimal_day_offset;
  async function ask(prompt) {
    if(asking||!prompt.trim())return;
    const text=prompt.trim();
    setQuestion('');setAsking(true);
    setMessages(m=>[...m,{role:'user',text}]);
    advisorAbort.current=new AbortController();
    try {
      const res=await fetch('/api/advisor/'+forecast.origin+'/'+forecast.destination,{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:text,day_offset:day}),signal:advisorAbort.current.signal});
      if(!res.ok)throw new Error('The advisor service could not complete this request.');
      const answer=await res.json();
      setMessages(m=>[...m,{role:'assistant',text:answer.answer,mode:answer.mode,model:answer.model,error:answer.error}]);
    } catch(e) {if(e.name!=='AbortError')setMessages(m=>[...m,{role:'assistant',text:e.message,mode:'error'}]);}
    finally {setAsking(false);}
  }
  return <div className="forecast-panel">
    <header className="detail-heading"><div><div className="route-kicker">{forecast.origin}<Icon name="arrow" size={14}/>{forecast.destination}<span>International route</span></div><h2>{forecast.dest_city_name}<SignalBadge tier={current.tier||base.tier}/></h2><p>{base.trend==='rising'?'Gaining momentum':base.trend==='falling'?'Demand easing':'A steady outlook'}<span className="inline-divider">/</span>{base.observation_count} sample observations</p></div>
      <a className="icon-button" href={'/api/export/forecast/'+forecast.origin+'/'+forecast.destination} title="Export this route as CSV" aria-label="Export this route as CSV"><Icon name="download"/></a>
    </header>
    <div className="detail-tabs" role="tablist" aria-label="Route views">{[['overview','Overview'],['weather','Weather & dates'],['advisor','AI advisor']].map(([id,label])=><button key={id} id={'tab-'+id} role="tab" aria-selected={view===id} aria-controls={'panel-'+id} onClick={()=>setView(id)} className={view===id?'active':''}>{id==='advisor'&&<Icon name="spark" size={15}/>} {label}</button>)}</div>
    {error&&<div className="notice error" role="alert">{error}</div>}
    <div className="route-summary">
      <div><span className="label">Opportunity score</span><strong>{Number(score).toFixed(0)}<small>/100</small></strong><span className="summary-caption">Rank index & weather appeal</span></div>
      <div><span className="label">Illustrative fare <span className="unit-tag">USD</span></span><strong>{money(price)}</strong><span className="summary-caption">{decimal(multiplier)}× modeled multiplier</span></div>
      <div className="date-summary"><span className="label">Departure date</span><select aria-label="Selected departure day" value={day} onChange={e=>setDay(Number(e.target.value))} disabled={!schedule.length}>{schedule.length?schedule.map(s=><option value={s.day_offset} key={s.day_offset}>{dateLabel(s.date,{weekday:'short',month:'short',day:'numeric'})}{s.day_offset===best?' · best balance':''}</option>):<option value={0}>{loading?'Loading dates…':'Today'}</option>}</select><span className="summary-caption">{selectedWeather?.condition || 'Weather unavailable'}</span></div>
    </div>
    {view==='overview'&&<div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview" className="view-content">
      <div className="overview-grid">
        <article className="card forecast-card"><div className="section-heading"><div><h3>Demand outlook</h3><p>Relative rank index · next 4 weeks</p></div><span className="status-chip neutral">Low confidence</span></div>
          <Suspense fallback={<div className="chart-wrap loading-state">Loading chart…</div>}><DemandChart forecast={base}/></Suspense>
          <div className="chart-legend"><span><i className="legend-sample"/>Sample history</span><span><i className="legend-forecast"/>Blended forecast</span><span><i className="legend-band"/>Illustrative range</span></div>
          <div className="model-note"><Icon name="info" size={15}/><span>{base.forecast_method==='chronos_bolt_blend'?'Chronos Bolt + damped trend':'Damped-trend baseline'} · {Math.round((base.forecast_model_weight||0)*100)}% model weight. Sparse, simulated inputs; uncalibrated ranges.</span></div>
        </article>
        <article className="card pricing-card"><div className="section-heading"><div><h3>Behind the estimate</h3><p>Transparent pricing signals</p></div><Icon name="activity" size={17}/></div>
          <div className="price-lines"><div><span>Simulated base fare</span><strong>{money(base.base_price)}</strong></div><div><span>Demand factor</span><strong>{decimal(current.base_surge)}×</strong></div><div><span>Weather factor</span><strong>{decimal(current.weather_boost)}×</strong></div><div><span>Alternative adjustment</span><strong>{Number(current.alt_route_delta||0)>=0?'+':''}{((current.alt_route_delta||0)*100).toFixed(1)}%</strong></div><div><span>Signal strength</span><strong>{Math.round((current.temporal_decay||1)*100)}%</strong></div><div className="price-total"><span>Modeled fare</span><strong>{money(price)}<small> USD</small></strong></div></div>
          <p className="fine-print">Signals shrink toward neutral further out. This estimate is not an airline quote.</p>
        </article>
      </div>
      <div className="bottom-grid">
        <article className="card signals-card"><div className="section-heading"><h3>Signal composition</h3><span className="label">Index / 100</span></div>
          <SignalRow label="Route demand" value={base.mean_demand} source="Simulated GDS rank forecast"/>
          <SignalRow label="Search interest" value={base.trend_score} source={base.trend_source==='live'?'Google Trends · relative keyword index':'Fallback · excluded from demand blend'}/>
          <SignalRow label="Travel comfort" value={current.weather_appeal} source={current.weather_available?'Open-Meteo · live forecast':'Unavailable · neutral pricing factor'}/>
        </article>
        <article className="best-day-card"><span className="best-day-icon"><Icon name="calendar" size={21}/></span><div className="eyebrow">PLAN WITH CONTEXT</div><h3>{best!=null?dateLabel(detail.optimal_date,{weekday:'long',month:'short',day:'numeric'}):'Explore the next two weeks'}</h3><p>{best!=null?'The best modeled balance of travel comfort and cost. '+detail.optimal_weather_condition+'.':'Compare daily weather and illustrative fares. No recommendation is made when weather is unavailable or severe.'}</p><button className="text-button" onClick={()=>setView('weather')}>Explore travel dates<Icon name="arrow" size={16}/></button></article>
      </div>
    </div>}
    {view==='weather'&&<div role="tabpanel" id="panel-weather" aria-labelledby="tab-weather" className="view-content">
      <article className="card calendar-card"><div className="section-heading"><div><h3>Your next 14 days</h3><p>Select a date to compare conditions and estimates.</p></div>{best!=null&&<span className="status-chip good">Best balance marked</span>}</div>
        {loading?<div className="loading-state"><span className="loader"/>Loading daily signals…</div>:<div className="day-grid">{schedule.map(s=><button key={s.day_offset} onClick={()=>setDay(s.day_offset)} aria-pressed={s.day_offset===day} className={'day-card'+(day===s.day_offset?' selected':'')+(best===s.day_offset?' best':'')}>
          <span className="day-name">{dateLabel(s.date,{weekday:'short'})}{best===s.day_offset&&<Icon name="spark" size={12}/>}</span><strong>{dateLabel(s.date)}</strong><Icon name={s.selected_weather?.wmo_code<=2?'sun':'cloud'} size={24}/><span>{s.temp_max_c==null?'—':Math.round(s.temp_max_c)+'°'}</span><small>{money(s.price_usd)}</small></button>)}</div>}
      </article>
      <div className="weather-detail-grid"><article className="card"><div className="section-heading"><div><h3>{dateLabel(current.date,{weekday:'long',month:'short',day:'numeric'})}</h3><p>{selectedWeather?.condition || 'Weather data unavailable'}</p></div><Icon name="cloud" size={24}/></div>
        <div className="weather-stats">{[['High / low',selectedWeather?.temp_max_c!=null?Math.round(selectedWeather.temp_max_c)+'° / '+Math.round(selectedWeather.temp_min_c)+'° C':'—'],['Rain chance',selectedWeather?.precip_prob_pct!=null?selectedWeather.precip_prob_pct+'%':'—'],['Precipitation',selectedWeather?.precipitation_mm!=null?selectedWeather.precipitation_mm+' mm':'—'],['Wind speed',selectedWeather?.wind_kmh!=null?selectedWeather.wind_kmh+' km/h':'—']].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
        <p className="fine-print">{current.weather_available?'Open-Meteo daily forecast · temperatures in °C · weather forecasts may change.':'No live weather for this date. Neutral weather is used in the pricing simulation; conditions are not assumed.'}</p></article>
        <article className="card"><div className="section-heading"><h3>Day-specific estimate</h3><span className="unit-tag">USD</span></div><div className="large-price">{money(price)}</div><p className="muted">{decimal(multiplier)}× base fare of {money(base.base_price)}</p><p className="fine-print">{current.surge_reasoning||base.signal_explanation}</p><button className="button secondary" onClick={()=>setView('advisor')}><Icon name="spark" size={16}/>Ask about this date</button></article></div>
    </div>}
    {view==='advisor'&&<div role="tabpanel" id="panel-advisor" aria-labelledby="tab-advisor" className="view-content">
      <article className="card advisor-card"><div className="section-heading"><div><h3><Icon name="spark" size={18}/>Your route, explained.</h3><p>Ask about {forecast.dest_city_name}, travel dates, or the signals behind an estimate.</p></div><span className="status-chip neutral">HF-powered</span></div>
        {!messages.length&&<div className="advisor-intro"><span className="advisor-symbol"><Icon name="spark" size={28}/></span><h3>Make sense of the signals.</h3><p>Grounded in this route's data. Live model responses and local fallbacks are labeled.</p><div className="prompt-grid">{['Summarize this route opportunity.','Which date balances weather and cost?','What are the limitations of this forecast?'].map(p=><button key={p} onClick={()=>ask(p)} disabled={asking}>{p}<Icon name="arrow" size={14}/></button>)}</div></div>}
        <div className="advisor-messages" aria-live="polite">{messages.map((m,i)=><div key={i} className={'message '+m.role}><span className="message-label">{m.role==='user'?'You':m.mode==='live'?'AI advisor · live':'Local fallback'}{m.error&&' · '+m.error}</span><p>{m.text}</p>{m.model&&<small>{m.model}</small>}</div>)}{asking&&<div className="advisor-thinking"><span className="loader"/>Analyzing route signals…</div>}<div ref={advisorEnd}/></div>
        <form className="advisor-form" onSubmit={e=>{e.preventDefault();ask(question);}}><input aria-label="Ask the travel advisor" placeholder="Ask a question about this route…" value={question} onChange={e=>setQuestion(e.target.value)} maxLength={2000} disabled={asking}/><button className="button primary" type="submit" disabled={asking||!question.trim()}><Icon name="arrow" size={18}/><span>Ask advisor</span></button></form><p className="fine-print">Selected date: {dateLabel(current.date)}. AI may make mistakes. Sample demand and fare estimates are not booking advice.</p>
      </article>
    </div>}
  </div>;
}
