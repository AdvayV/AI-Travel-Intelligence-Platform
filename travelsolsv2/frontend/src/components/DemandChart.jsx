import React from 'react';
import { ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';

function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return <div className="rounded-lg border border-border bg-surface-raised p-3 text-xs shadow-md">
    <strong>{label < 0 ? Math.abs(label) + ' weeks ago' : 'Forecast day ' + Math.round(label * 7)}</strong>
    <p className="mt-1 text-text-secondary">Rank index: {Math.round((row.observed ?? row.forecast) * 100)}</p>
    {row.range && <p className="text-text-secondary">Illustrative range: {Math.round(row.range[0]*100)}–{Math.round(row.range[1]*100)}</p>}
    {row.weatherSource && <p className="mt-1 text-text-tertiary">{row.weatherSource}</p>}
  </div>;
}
export default function DemandChart({ detail }) {
  const data = [
    ...[['12w',-12],['8w',-8],['2w',-2]].filter(([key]) => detail.history[key] != null).map(([key,week]) => ({week,observed:detail.history[key]})),
    ...detail.daily_forecast.map(day => ({week:day.day_offset/7,forecast:day.demand,raw:day.raw_demand,range:[day.lower,day.upper],weatherSource:day.weather_source})),
  ];
  return <div className="h-[240px] w-full mt-4" role="img" aria-label="Simulated rank-index history and 28-day forecast with uncalibrated uncertainty ranges">
    <ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{top:15,right:10,left:-15,bottom:0}}>
      <CartesianGrid strokeDasharray="3 3" stroke="#e4eaf0" vertical={false}/>
      <XAxis dataKey="week" type="number" domain={[-12,4]} ticks={[-12,-8,-2,0,4]} tickFormatter={v=>v===0?'Today':(v>0?'+':'')+v+'w'} tick={{fontSize:11,fill:'#7a899c'}} tickLine={false} axisLine={false}/>
      <YAxis domain={[0,1]} tickFormatter={v=>Math.round(v*100)} tick={{fontSize:11,fill:'#7a899c'}} tickLine={false} axisLine={false}/>
      <Tooltip content={<ForecastTooltip/>}/>
      <ReferenceLine x={0} stroke="#97a4b5" strokeDasharray="3 3"/>
      <Area dataKey="range" fill="#dbeafe" stroke="none" isAnimationActive={false}/>
      <Line dataKey="observed" stroke="#8c9bae" strokeWidth={2} dot={{r:4}} isAnimationActive={false}/>
      <Line dataKey="raw" stroke="#a8b8d1" strokeWidth={1.5} dot={false} strokeDasharray="3 4" isAnimationActive={false}/>
      <Line dataKey="forecast" stroke="#4f46e5" strokeWidth={2.5} dot={false} isAnimationActive={false}/>
    </ComposedChart></ResponsiveContainer>
  </div>;
}
