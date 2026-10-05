import Icon from './Icon';
export default function TopBar({ tab, setTab, refreshing, refresh, health }) {
  const stamp = health?.last_refresh ? new Date(health.last_refresh).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : null;
  return <header className="topbar">
    <a className="brand" href="/" aria-label="TravelSols home"><span className="brand-mark"><Icon name="plane" size={21}/></span><span>travelsols<span className="brand-version">Workspace / v1</span></span></a>
    <nav className="primary-nav" aria-label="Workspace navigation">
      <button className={tab==='routes'?'active':''} onClick={()=>setTab('routes')}><Icon name="grid"/>Route intelligence</button>
      <button className={tab==='integrations'?'active':''} onClick={()=>setTab('integrations')}><Icon name="activity"/>Integrations</button>
    </nav>
    <div className="top-actions"><span className="sync-label">{refreshing ? 'Updating signals…' : stamp ? 'Updated '+stamp : 'Connecting…'}</span>
      <button className="button secondary small" onClick={refresh} disabled={refreshing}><Icon name="refresh" className={refreshing?'spin':''}/><span>{refreshing?'Refreshing':'Refresh data'}</span></button>
      <span className="avatar" title="Local workspace">TS</span>
    </div>
  </header>;
}
