import React, { useState } from 'react';

export default function VectorContext({ chunks }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!chunks || chunks.length === 0) return null;

  const getSourceStyle = (source) => {
    switch (source) {
      case 'FARE RULE':
        return 'bg-pink-50 text-pink-700 border-pink-100';
      case 'POLICY':
        return 'bg-amber-50 text-amber-700 border-amber-100';
      case 'IROPS':
      default:
        return 'bg-blue-50 text-blue-700 border-blue-100';
    }
  };

  return (
    <div className="bg-surface-raised border border-border rounded-lg shadow-sm transition-all duration-200 overflow-hidden">
      {/* Panel Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-surface border-b border-border hover:bg-border/20 transition-all duration-150"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary">Document chunks retrieved</span>
          <span className="bg-accent-light text-accent text-[10px] font-bold px-2 py-0.5 rounded-full border border-accent/10">
            {chunks.length} chunks
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-text-secondary transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Collapsible Content */}
      {isOpen && (
        <div className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[350px] overflow-y-auto pr-1">
            {chunks.slice(0, 6).map((chunk, idx) => (
              <div
                key={idx}
                className="bg-surface/30 border border-border rounded-md p-3 flex flex-col gap-2 shadow-sm"
              >
                {/* Source Badge */}
                <div className="flex items-center justify-between">
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded border ${getSourceStyle(chunk.source)}`}>
                    {chunk.source}
                  </span>
                  <span className="text-[9px] text-text-tertiary font-mono">
                    ID: {chunk.id}
                  </span>
                </div>
                {/* Excerpt */}
                <p className="text-[11px] text-text-secondary leading-relaxed">
                  {chunk.document}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
