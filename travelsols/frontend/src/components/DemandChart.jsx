import { ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from 'recharts';

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return <div className="chart-tooltip"><strong>{label>0?'+'+label:label} weeks</strong><span>{row.observed!=null?'Sample rank index: '+Math.round(row.observed*100):'Forecast index: '+Math.round(row.predicted*100)}</span>{row.band&&<span>Illustrative range: {Math.round(row.band[0]*100)}–{Math.round(row.band[1]*100)}</span>}</div>;
}
export default function DemandChart({ forecast }) {
  const history = forecast.history || {};
  const latestWeek = history['2w']!=null ? -2 : history['8w']!=null ? -8 : -12;
  const data = [
    ...[['12w',-12],['8w',-8],['2w',-2]].filter(([key])=>history[key]!=null).map(([key,week])=>({week,observed:history[key],predicted:week===latestWeek?history[key]:null})),
    ...forecast.weekly_forecast.map((v,i)=>({week:i+1,predicted:v,band:[forecast.forecast_lower[i],forecast.forecast_upper[i]]})),
  ];
  return <div className="chart-wrap" role="img" aria-label={'Four-week rank-index forecast, '+forecast.weekly_forecast.map(v=>Math.round(v*100)).join(', ')+'. Low confidence; simulated input data.'}>
    <ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:14,right:16,bottom:0,left:-22}}>
      <CartesianGrid vertical={false} stroke="#e9edf0" strokeDasharray="3 3"/>
      <XAxis dataKey="week" type="number" domain={[-12,4]} ticks={[-12,-8,-2,1,4]} tickFormatter={v=>(v>0?'+'+v:v)+' wk'} tickLine={false} axisLine={false} tick={{fontSize:11,fill:'#86909c'}} dy={10}/>
      <YAxis domain={[0,1]} tickCount={5} tickLine={false} axisLine={false} tickFormatter={v=>Math.round(v*100)} tick={{fontSize:11,fill:'#86909c'}}/>
      <Tooltip content={<ChartTooltip/>}/>
      <ReferenceLine x={0} stroke="#cbd5df" strokeDasharray="4 4"/>
      <Area dataKey="band" fill="#daeee8" stroke="none" isAnimationActive={false} connectNulls={false}/>
      <Line dataKey="observed" stroke="#657b90" strokeWidth={2.2} dot={{r:4,fill:'#fff',strokeWidth:2}} connectNulls={false} isAnimationActive={false}/>
      <Line dataKey="predicted" stroke="#197965" strokeWidth={2.5} strokeDasharray="5 3" dot={{r:3,fill:'#197965'}} isAnimationActive={false} connectNulls/>
    </ComposedChart></ResponsiveContainer>
  </div>;
}
