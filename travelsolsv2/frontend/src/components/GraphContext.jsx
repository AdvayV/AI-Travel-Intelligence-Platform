import React, { useState } from 'react';
import GraphNetworkVisualizer from './GraphNetworkVisualizer';

export default function GraphContext({ context }) {
  const [isOpen, setIsOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('graph'); // 'graph' or 'facts'

  if (!context) return null;

  const { entities = {}, graph_facts = [] } = context;
  
  // Calculate total entities
  const entityCount = Object.values(entities).reduce((acc, curr) => acc + (curr ? curr.length : 0), 0);

  const highlightCodes = (text) => {
    const regex = /\b(BOM|DEL|BLR|MAA|HYD|DXB|SIN|LHR|JFK|CDG|NRT|BKK|KUL|DOH|SYD|AI|EK|QR|SQ|BA|6E|CP-\d{3}|WX-\d{4}-[A-Z]+|OPS-[A-Z]+-\d{4}-\d+|CORP-[A-Z]+-[A-Z]+|EMRG-\d{4})\b/g;
    const parts = text.split(regex);
    return parts.map((part, i) => {
      if (part.match(regex)) {
        return (
          <code key={i} className="font-mono bg-surface border border-border px-1.5 py-0.5 rounded text-[11px] font-semibold text-accent-text">
            {part}
          </code>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className="bg-surface-raised border border-border rounded-lg shadow-sm transition-all duration-200 overflow-hidden">
      {/* Panel Header */}
      <div className="w-full flex items-center justify-between px-4 py-3 bg-surface border-b border-border">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="flex items-center gap-2 hover:opacity-80 transition-all duration-150"
        >
          <span className="text-sm font-semibold text-text-primary">Knowledge graph context</span>
          {entityCount > 0 && (
            <span className="bg-accent-light text-accent text-[10px] font-bold px-2 py-0.5 rounded-full border border-accent/10">
              {entityCount} entities
            </span>
          )}
        </button>
        <div className="flex items-center gap-3">
          <svg
            onClick={() => setIsOpen(!isOpen)}
            className={`w-4 h-4 text-text-secondary cursor-pointer transition-transform duration-200 ${isOpen ? 'transform rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Collapsible Content */}
      {isOpen && (
        <div className="p-4 flex flex-col gap-4">
          {/* Tabs Navigation */}
          <div className="flex border-b border-border/60 pb-1 gap-2">
            <button
              onClick={() => setActiveTab('graph')}
              className={`pb-1 text-xs font-semibold px-2 border-b-2 transition-all duration-150
                ${activeTab === 'graph' 
                  ? 'border-accent text-accent' 
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'}`}
            >
              🌐 Visual Network
            </button>
            <button
              onClick={() => setActiveTab('facts')}
              className={`pb-1 text-xs font-semibold px-2 border-b-2 transition-all duration-150
                ${activeTab === 'facts' 
                  ? 'border-accent text-accent' 
                  : 'border-transparent text-text-tertiary hover:text-text-secondary'}`}
            >
              📜 Relational Facts ({graph_facts.length})
            </button>
          </div>

          {/* Section 1: Entities Detected (Shared) */}
          {entityCount > 0 && (
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Entities detected</span>
              <div className="flex flex-wrap gap-1.5">
                {entities.passengers?.map(item => (
                  <span key={item} className="bg-indigo-50 text-indigo-800 text-[11px] font-medium px-2 py-0.5 rounded-md border border-indigo-100">
                    👤 {item}
                  </span>
                ))}
                {entities.policies?.map(item => (
                  <span key={item} className="bg-amber-50 text-amber-800 text-[11px] font-medium px-2 py-0.5 rounded-md border border-amber-100 font-mono">
                    📜 {item}
                  </span>
                ))}
                {entities.airports?.map(item => (
                  <span key={item} className="bg-blue-50 text-blue-800 text-[11px] font-medium px-2 py-0.5 rounded-md border border-blue-100 font-mono">
                    ✈️ {item}
                  </span>
                ))}
                {entities.waivers?.map(item => (
                  <span key={item} className="bg-emerald-50 text-emerald-800 text-[11px] font-medium px-2 py-0.5 rounded-md border border-emerald-100 font-mono">
                    🎟️ {item}
                  </span>
                ))}
                {entities.airlines?.map(item => (
                  <span key={item} className="bg-purple-50 text-purple-800 text-[11px] font-medium px-2 py-0.5 rounded-md border border-purple-100 font-mono">
                    🛩️ {item}
                  </span>
                ))}
                {entities.fare_classes?.map(item => (
                  <span key={item} className="bg-pink-50 text-pink-800 text-[11px] font-medium px-2 py-0.5 rounded-md border border-pink-100 font-mono">
                    💺 Class {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Active Tab rendering */}
          {activeTab === 'graph' ? (
            <GraphNetworkVisualizer context={context} />
          ) : (
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold text-text-secondary uppercase tracking-wider">Graph facts retrieved</span>
              {graph_facts.length > 0 ? (
                <div className="flex flex-col gap-2 max-h-56 overflow-y-auto">
                  {graph_facts.map((fact, idx) => (
                    <div key={idx} className="text-xs text-text-primary p-2.5 bg-surface/50 border border-border rounded-md leading-relaxed">
                      {highlightCodes(fact)}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-text-tertiary italic">No relational facts retrieved from travel graph database.</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
