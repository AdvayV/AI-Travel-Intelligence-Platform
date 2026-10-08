import React from 'react';
import { graphAnswerParagraphs, graphRecords } from '../utils/graphAnswer';

export default function GraphQueryResponse({ answer, results }) {
  const paragraphs = graphAnswerParagraphs(answer, results).split(/\n\s*\n/).filter(Boolean);
  const records = graphRecords(results);

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
        <h3 className="mb-2 text-xs font-bold text-indigo-900">Graph answer</h3>
        <div className="space-y-3 text-sm leading-relaxed text-slate-800" role="status" aria-live="polite">
          {paragraphs.length > 0 ? paragraphs.map((paragraph, index) => <p key={index} className="break-words">{paragraph.replace(/\*\*/g, '')}</p>)
            : <p>No readable answer was returned. Please try the query again.</p>}
        </div>
      </div>
      {results !== null && results !== undefined && (
        <details className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <summary className="cursor-pointer text-xs font-semibold text-slate-600">Show technical query data ({records.length} records)</summary>
          <pre className="mt-3 max-h-48 overflow-auto whitespace-pre-wrap break-words text-[11px] leading-relaxed text-slate-600">{JSON.stringify(records, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
