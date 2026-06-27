import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';

function DemandChart({ historical, forecast }) {
  const data = [
    { name: '12w ago', value: historical[0] },
    { name: '8w ago', value: historical[1] },
    { name: 'Now', value: historical[2] },
    { name: 'Wk 1', forecast: forecast[0] },
    { name: 'Wk 2', forecast: forecast[1] },
    { name: 'Wk 3', forecast: forecast[2] },
    { name: 'Wk 4', forecast: forecast[3] }
  ];

  data[2].forecast = historical[2];

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: '#0D1428', border: '1px solid #1E2D4A', padding: '10px', color: 'white', borderRadius: '4px' }}>
          <p style={{ margin: 0, marginBottom: '5px', color: '#6B7FA3' }}>{label}</p>
          {payload.map(entry => (
            <p key={entry.name} style={{ margin: 0, color: entry.color }}>
              Demand Score: {entry.value.toFixed(2)}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div style={{ height: '180px', width: '100%', marginTop: '20px' }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1E2D4A" vertical={false} />
          <XAxis dataKey="name" stroke="#6B7FA3" tick={{ fontSize: 12, fill: '#6B7FA3' }} axisLine={false} tickLine={false} />
          <YAxis stroke="#6B7FA3" domain={[0, 1]} tick={{ fontSize: 12, fill: '#6B7FA3' }} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine x="Now" stroke="#6B7FA3" strokeDasharray="3 3" label={{ position: 'top', value: 'Today', fill: '#6B7FA3', fontSize: 12 }} />
          <Line type="monotone" dataKey="value" stroke="#4A9EFF" strokeWidth={3} dot={{ r: 4, fill: '#4A9EFF' }} activeDot={{ r: 6 }} connectNulls />
          <Line type="monotone" dataKey="forecast" stroke="#FF9B00" strokeWidth={3} strokeDasharray="5 5" dot={{ r: 4, fill: '#FF9B00' }} activeDot={{ r: 6 }} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default DemandChart;
