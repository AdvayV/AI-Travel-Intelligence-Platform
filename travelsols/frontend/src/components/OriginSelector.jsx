const origins = [{code:'BOM',name:'Mumbai'},{code:'DEL',name:'Delhi'},{code:'BLR',name:'Bengaluru'},{code:'MAA',name:'Chennai'},{code:'HYD',name:'Hyderabad'}];
export default function OriginSelector({ selectedOrigin, onOriginChange }) {
  return <label className="origin-select"><span>Departure airport</span><select value={selectedOrigin} onChange={e=>onOriginChange(e.target.value)}>{origins.map(o=><option key={o.code} value={o.code}>{o.name} · {o.code}</option>)}</select></label>;
}
