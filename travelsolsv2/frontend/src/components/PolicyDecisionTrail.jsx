import React from 'react';

const STATUS_STYLES = {
  pass: { label: 'Passed', className: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  fail: { label: 'Not compliant', className: 'border-rose-200 bg-rose-50 text-rose-800' },
  approval: { label: 'Approval needed', className: 'border-purple-200 bg-purple-50 text-purple-800' },
  waiver: { label: 'Exception applied', className: 'border-amber-200 bg-amber-50 text-amber-800' },
  warning: { label: 'Unverified', className: 'border-amber-200 bg-amber-50 text-amber-800' },
  adjusted: { label: 'Request adjusted', className: 'border-sky-200 bg-sky-50 text-sky-800' },
};

export default function PolicyDecisionTrail({ flight }) {
  if (!flight) return null;
  const trail = flight.decision_trail || [];
  const approvals = flight.approval_requirements || [];

  return (
    <section className="min-w-0 rounded-2xl border border-indigo-200 bg-white p-4 sm:p-5" aria-label="Policy decision trail">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-3">
        <div>
          <h3 className="text-sm font-bold text-text-primary">Why this flight was shown</h3>
          <p className="mt-1 text-xs text-text-secondary">Grade {flight.employee_grade} · {flight.policy_id} · {flight.origin} → {flight.destination}</p>
        </div>
        <span className="rounded-lg bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-800">
          {flight.policy_status?.replaceAll('_', ' ') || 'Audit unavailable'}
        </span>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-text-secondary">
        Search uses the resolved route, date and cabin. Returned options remain visible even when a rule fails.
        The initial selection is the first compliant option needing no approval, otherwise the first result—not necessarily the cheapest.
      </p>
      {trail.length === 0 ? (
        <p className="mt-4 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">No structured audit was returned. Run the request again with the updated backend.</p>
      ) : (
        <ol className="mt-4 space-y-3">
          {trail.map((check, index) => {
            const status = STATUS_STYLES[check.status] || STATUS_STYLES.warning;
            return (
              <li key={check.id} className="rounded-xl border border-border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-xs font-bold text-text-primary">{index + 1}. {check.title}</h4>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${status.className}`}>{status.label}</span>
                </div>
                <dl className="mt-2 space-y-1.5 break-words text-xs leading-relaxed">
                  <div><dt className="inline font-semibold text-text-primary">Rule: </dt><dd className="inline text-text-secondary">{check.rule}</dd></div>
                  <div><dt className="inline font-semibold text-text-primary">Actual: </dt><dd className="inline text-text-secondary">{check.observed}</dd></div>
                  <div><dt className="inline font-semibold text-text-primary">Result: </dt><dd className="inline text-text-secondary">{check.detail}</dd></div>
                </dl>
                <p className="mt-2 text-[10px] text-text-secondary">Source: {check.source}</p>
              </li>
            );
          })}
        </ol>
      )}
      <div className="mt-4 rounded-xl border border-purple-200 bg-purple-50 p-3 text-xs leading-relaxed text-purple-900">
        <h4 className="font-bold">Approval rules and demo limitation</h4>
        {approvals.length > 0 ? (
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {approvals.map((approval, index) => <li key={`${approval.role}-${index}`}><strong>{approval.role}:</strong> {approval.reason}</li>)}
          </ul>
        ) : <p className="mt-1">No approval requirement was identified by the returned policy checks.</p>}
        <p className="mt-2">These are rule flags, not approval decisions. Saving creates a demo reference only; no manager request is sent or stored, and no ticket is issued. Hard violations are not cleared by an approval flag.</p>
      </div>
      {flight.evaluated_at && <p className="mt-3 break-words text-[10px] text-text-secondary">Evaluated at: {flight.evaluated_at}</p>}
    </section>
  );
}
