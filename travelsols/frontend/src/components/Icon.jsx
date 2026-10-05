import React from 'react';

const paths = {
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  plane: 'm22 2-7 20-4-9-9-4 20-7ZM22 2 11 13',
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  download: 'M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5',
  refresh: 'M20 7a8 8 0 0 0-14-2L3 8m0-5v5h5m-4 9a8 8 0 0 0 14 2l3-3m0 5v-5h-5',
  search: 'M21 21l-6-6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z',
  chevron: 'm9 5 7 7-7 7',
  sun: 'M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  cloud: 'M6 18a4 4 0 0 1-.5-8 6 6 0 0 1 11.5-1 4.5 4.5 0 0 1 1 9H6Z',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z',
  info: 'M12 11v6m0-10h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  check: 'm5 12 4 4L19 6',
  calendar: 'M8 2v4m8-4v4M3 10h18M3 4h18v18H3z',
  close: 'm6 6 12 12M6 18 18 6',
};
export default function Icon({ name, size = 18, className = '' }) {
  return <svg aria-hidden="true" className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name] || paths.activity}/></svg>;
}
