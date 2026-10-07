import React, { useId, useMemo, useState } from 'react';

const QUICK_QUERIES = [
  { label: 'Grade 1 · Bombay to London', text: 'Bombay to London 21st August grade 1' },
  { label: 'Grade 6 · Mumbai to Dubai', text: 'Mumbai to Dubai next week grade 6' },
  { label: 'Grade 8 · Delhi to New York', text: 'Delhi to New York next week grade 8' },
  { label: 'Grade 9 · First to London', text: 'First class Mumbai to London next week grade 9' },
];

const GRADE_PATTERN = /\b(?:grade|band|level)\s*[-:]?\s*([1-9])\b/i;

const gradeSummary = (grade) => {
  if (grade <= 5) {
    return { policy: 'CP-001', cabin: 'Economy', detail: 'Economy-only travel on every route' };
  }
  if (grade <= 7) {
    return { policy: 'CP-002', cabin: 'Route-aware', detail: 'Business on long-haul; Economy otherwise' };
  }
  if (grade === 8) {
    return { policy: 'CP-002', cabin: 'Business', detail: 'Economy or Business on every route' };
  }
  return { policy: 'CP-003', cabin: 'Executive', detail: 'Business default; First when requested' };
};

export default function QueryInput({ onSubmit, isLoading }) {
  const fieldId = useId();
  const [text, setText] = useState('Bombay to London 21st August grade 1');
  const [passengerName, setPassengerName] = useState('Aryan Mehta');
  const [grade, setGrade] = useState(1);
  const policyPreview = useMemo(() => gradeSummary(grade), [grade]);

  const updateText = (value) => {
    setText(value);
    const match = value.match(GRADE_PATTERN);
    if (match) setGrade(Number(match[1]));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!text.trim() || isLoading) return;
    const normalizedQuery = GRADE_PATTERN.test(text) ? text.trim() : `${text.trim()} grade ${grade}`;
    onSubmit(normalizedQuery, passengerName.trim());
  };

  const handleGradeChange = (event) => {
    const nextGrade = Number(event.target.value);
    setGrade(nextGrade);
    if (GRADE_PATTERN.test(text)) {
      setText(text.replace(GRADE_PATTERN, `grade ${nextGrade}`));
    }
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-surface-raised shadow-md">
      <div className="border-b border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-sky-50 px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-extrabold uppercase tracking-[0.16em] text-accent">AI trip request</p>
            <h2 className="mt-1 text-base font-bold tracking-tight text-text-primary">Describe the journey naturally</h2>
            <p className="mt-1 text-[11px] leading-relaxed text-text-secondary">City names, flexible dates, employee grade and cabin requests are resolved automatically.</p>
          </div>
          <span className="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[10px] font-bold text-emerald-700">Live fares</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
        <label className="flex flex-col gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-secondary">Travel request</span>
          <textarea
            value={text}
            onChange={(event) => updateText(event.target.value)}
            placeholder="Example: Bombay to London 21st August grade 1"
            rows={3}
            disabled={isLoading}
            className="w-full resize-none rounded-[12px] border border-slate-300 bg-white px-3.5 py-3 text-sm font-medium leading-relaxed text-text-primary shadow-sm transition placeholder:text-slate-500 hover:border-slate-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:opacity-60"
          />
        </label>

        <div className="grid min-w-0 grid-cols-1 gap-4">
          <label htmlFor={`${fieldId}-passenger`} className="flex min-w-0 flex-col gap-2">
            <span className="text-xs font-semibold text-text-primary">Passenger name</span>
            <input
              id={`${fieldId}-passenger`}
              name="passengerName"
              type="text"
              autoComplete="name"
              maxLength={100}
              value={passengerName}
              onChange={(event) => setPassengerName(event.target.value)}
              placeholder="Enter the passenger's full name"
              disabled={isLoading}
              className="block min-h-12 w-full min-w-0 rounded-[12px] border border-slate-300 bg-white px-3.5 py-3 text-sm font-medium leading-5 text-slate-900 shadow-sm transition placeholder:text-slate-500 hover:border-slate-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
            />
          </label>
          <label htmlFor={`${fieldId}-grade`} className="flex min-w-0 flex-col gap-2">
            <span className="text-xs font-semibold text-text-primary">Employee grade</span>
            <select
              id={`${fieldId}-grade`}
              name="employeeGrade"
              value={grade}
              onChange={handleGradeChange}
              disabled={isLoading}
              className="block min-h-12 w-full min-w-0 rounded-[12px] border border-slate-300 bg-white px-3.5 py-3 text-sm font-medium leading-5 text-slate-900 shadow-sm transition hover:border-slate-400 focus:border-accent focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"
            >
              {Array.from({ length: 9 }, (_, index) => index + 1).map((value) => (
                <option key={value} value={value}>Grade {value}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="rounded-xl border border-indigo-100 bg-indigo-50/70 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md bg-indigo-600 px-2 py-1 text-[10px] font-extrabold text-white">GRADE {grade}</span>
            <span className="text-xs font-bold text-indigo-950">{policyPreview.policy}</span>
            <span className="text-[10px] font-semibold text-indigo-700">Recommended: {policyPreview.cabin}</span>
          </div>
          <p className="mt-1.5 text-[10px] leading-relaxed text-indigo-700">{policyPreview.detail}. Explicit grades override saved traveler defaults.</p>
        </div>

        <div className="order-5">
          <span className="text-[10px] font-bold uppercase tracking-[0.12em] text-text-secondary">Try an example</span>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {QUICK_QUERIES.map((query) => (
              <button
                key={query.label}
                type="button"
                disabled={isLoading}
                onClick={() => updateText(query.text)}
                className="rounded-full border border-border bg-white px-3 py-1.5 text-left text-[10px] font-semibold text-text-secondary transition hover:border-accent hover:bg-accent-light hover:text-accent"
              >
                {query.label}
              </button>
            ))}
          </div>
        </div>

        <div className="order-4 flex flex-col gap-3 border-t border-border pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-1.5">
            <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700">Hybrid GraphRAG</span>
            <span className="rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[10px] font-bold text-sky-700">Google Flights</span>
          </div>
          <button
            type="submit"
            disabled={isLoading || !text.trim()}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-200 transition hover:-translate-y-0.5 hover:bg-accent-text disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
          >
            {isLoading && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />}
            {isLoading ? 'Resolving policy and fares…' : 'Find compliant flights'}
          </button>
        </div>
      </form>
    </section>
  );
}
