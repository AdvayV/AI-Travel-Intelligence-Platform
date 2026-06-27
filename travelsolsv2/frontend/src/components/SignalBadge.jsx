import React from 'react';

export default function SignalBadge({ tier, score }) {
  let classes = "";
  
  if (tier === 'HOT') {
    classes = "bg-danger-light border border-danger/20 text-danger";
  } else if (tier === 'RISING') {
    classes = "bg-warning-light border border-warning/20 text-warning";
  } else {
    classes = "bg-accent-light border border-accent/20 text-accent";
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase border ${classes}`}>
      {tier} {score.toFixed(1)}
    </span>
  );
}
