import React, { useState } from 'react';

const QUICK_QUERIES = [
  { label: 'Book economy BOM→DXB tomorrow, policy CP-001', text: 'Book economy flight from BOM to DXB tomorrow for Aryan Mehta under policy CP-001' },
  { label: 'Check waivers for Aryan Mehta, BOM→LHR next week', text: 'Check active waivers and book flight BOM to LHR next week for Aryan Mehta' },
  { label: 'Business class DEL→JFK for Vikram Nair, CP-003', text: 'Book business class DEL to JFK for Vikram Nair under policy CP-003' },
  { label: 'Emergency rebook BOM→SIN, weather disruption', text: 'Emergency booking BOM to SIN for Anita Singh, weather disruption active' }
];

export default function QueryInput({ onSubmit, isLoading }) {
  const [text, setText] = useState('');
  const [passengerName, setPassengerName] = useState('Aryan Mehta');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim() || isLoading) return;
    onSubmit(text, passengerName);
  };

  const handleChipClick = (queryText) => {
    setText(queryText);
    
    // Auto-extract passenger name from suggestion text if matching known names
    const knownNames = ["Aryan Mehta", "Vikram Nair", "Anita Singh", "Priya Sharma", "Rajesh Kumar"];
    for (const name of knownNames) {
      if (queryText.includes(name)) {
        setPassengerName(name);
        break;
      }
    }
  };

  return (
    <div className="bg-surface-raised shadow-md rounded-lg border border-border p-6 flex flex-col gap-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        {/* Large Input Textarea */}
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe the trip you want to book..."
          rows={3}
          disabled={isLoading}
          className="w-full text-base font-normal text-text-primary placeholder-text-tertiary focus:outline-none resize-none disabled:bg-transparent"
        />

        {/* Passenger Name Input */}
        <div className="flex flex-col gap-1 border-t border-border/40 pt-3">
          <label className="text-[10px] uppercase font-bold text-text-secondary tracking-wider">Passenger Name</label>
          <input
            type="text"
            value={passengerName}
            onChange={(e) => setPassengerName(e.target.value)}
            placeholder="E.g., Aryan Mehta, Vikram Nair, John Doe"
            disabled={isLoading}
            className="w-full text-xs font-semibold text-text-primary placeholder-text-tertiary focus:outline-none bg-transparent border-b border-border/80 pb-1 focus:border-accent transition-colors"
          />
        </div>

        {/* Quick Fill Chips */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[10px] uppercase font-semibold text-text-secondary tracking-wider">Suggested queries</span>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_QUERIES.map((q, idx) => (
              <button
                key={idx}
                type="button"
                disabled={isLoading}
                onClick={() => handleChipClick(q.text)}
                className="bg-accent-light text-accent-text text-[11px] font-medium px-3 py-1 rounded-full border border-accent/10 hover:bg-accent hover:text-white transition-all duration-200 text-left"
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>

        {/* Bottom Actions Row */}
        <div className="flex items-center justify-between border-t border-border pt-4 mt-2">
          {/* Badge */}
          <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border border-accent text-accent">
            GraphRAG + MCP
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading || !text.trim()}
            className={`flex items-center gap-2 bg-accent text-white px-5 py-2 text-sm font-semibold rounded-[10px] shadow-sm transition-all duration-200
              ${(isLoading || !text.trim()) ? 'opacity-65 cursor-not-allowed' : 'hover:bg-accent-text'}`}
          >
            {isLoading ? (
              <>
                <svg className="animate-spin -ml-1 mr-1 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Running agent...
              </>
            ) : 'Run agent'}
          </button>
        </div>
      </form>
    </div>
  );
}
