import Icon from './Icon';
export default function RouteCard({ route, selected, onClick }) {
  const values = Object.values(route.history || {}).filter(v=>v!=null);
  const points = values.map((v,i)=>(i*27+2)+','+(28-v*23)).join(' ');
  return <button className={'route-card'+(selected?' selected':'')} onClick={()=>onClick(route)} aria-pressed={selected}>
    <div className="destination-mark">{route.destination}</div>
    <div className="route-card-main"><strong>{route.dest_city_name}</strong><span>{route.origin}<span className="tiny-arrow">→</span>{route.destination} · <span className={'direction '+route.trend}>{route.trend}</span></span></div>
    <div className="route-card-score"><strong>{Number(route.score).toFixed(0)}<small>/100</small></strong><svg width="60" height="30" viewBox="0 0 60 30" aria-hidden="true"><polyline points={points} fill="none" stroke={route.trend==='falling'?'#8b9caa':'#298a7b'} strokeWidth="1.8"/></svg></div>
    <Icon name="chevron" size={14}/>
  </button>;
}
