import React from 'react';

export default function StatusPill({ status, label }) {
  const getColors = () => {
    switch (status) {
      case 'success':
        return {
          bg: 'bg-success-light',
          text: 'text-success',
          dot: 'bg-success'
        };
      case 'warning':
        return {
          bg: 'bg-warning-light',
          text: 'text-warning',
          dot: 'bg-warning'
        };
      case 'error':
        return {
          bg: 'bg-danger-light',
          text: 'text-danger',
          dot: 'bg-danger'
        };
      case 'neutral':
      default:
        return {
          bg: 'bg-surface',
          text: 'text-text-secondary',
          dot: 'bg-text-tertiary'
        };
    }
  };

  const colors = getColors();

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${colors.bg} ${colors.text} border border-border`}>
      <span className={`w-1.5 h-1.5 rounded-full ${colors.dot}`} />
      <span>{label}</span>
    </div>
  );
}
