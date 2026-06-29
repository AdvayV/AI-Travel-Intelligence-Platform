import React from 'react';

export default function BookingProposal({ selectedFlight, proposal, onConfirm, onRevise, isBookingLoading }) {
  const [isExpanded, setIsExpanded] = React.useState(true);

  if (!selectedFlight && !proposal) return null;

  // If already booked/ticketed (proposal exists with a PNR)
  if (proposal && proposal.pnr) {
    return (
      <div className="mt-4 border-t-2 border-emerald-500 bg-surface-raised shadow-lg rounded-b-lg p-5 animate-fade-in">
        <div className="bg-success-light border border-success/20 rounded-md p-5 flex flex-col gap-3 items-center text-center">
          <div className="w-12 h-12 rounded-full bg-success/15 flex items-center justify-center text-success text-2xl font-bold">
            ✓
          </div>
          <div className="flex flex-col gap-1">
            <h4 className="text-sm font-bold text-success">Booking Ticketed & Saved to Graph Database</h4>
            <p className="text-xs text-text-secondary max-w-sm">
              The flight itinerary has been registered. Passenger Name Record (PNR) code generated successfully via Travel:
            </p>
          </div>
          <span className="text-xl font-mono font-bold tracking-widest bg-success/10 text-success border border-success/20 px-6 py-2 rounded mt-2 select-all shadow-inner">
            {proposal.pnr}
          </span>
          <div className="text-[10px] text-text-tertiary mt-1 font-mono">
            Transaction node saved to corporate Travel Graph (Neo4j AuraDB).
          </div>
          <button
            onClick={onRevise}
            className="text-xs text-accent font-semibold hover:underline mt-3 px-4 py-1.5 border border-accent/20 rounded-full hover:bg-accent/5 transition-all duration-150"
          >
            Create another booking
          </button>
        </div>
      </div>
    );
  }

  const { flight_number, airline, origin, destination, departure_time, fare_class, price_inr, original_price_inr, discount_applied, compliant, requires_approval, compliance_details } = selectedFlight;

  const getAirlineName = (code) => {
    const names = {
      AI: 'Air India',
      EK: 'Emirates',
      QR: 'Qatar Airways',
      SQ: 'Singapore Airlines',
      BA: 'British Airways',
      '6E': 'IndiGo'
    };
    return names[code] || code;
  };

  const hasWaiverException = compliance_details && compliance_details.includes('Waiver Exception');
  const discountAmount = original_price_inr ? original_price_inr - price_inr : 0;

  const getAuditList = () => {
    const details = compliance_details || '';
    const hasFareViolation = details.includes('Fare class') || details.includes('restricted');
    const hasAdvanceViolation = details.includes('advance booking') || details.includes('Advance booking') || details.includes('Booked');
    const hasPriceViolation = details.includes('exceeds') || details.includes('price cap') || details.includes('fare limit');
    
    return [
      {
        name: 'Fare Class Access',
        passed: !hasFareViolation,
        msg: hasFareViolation ? 'Restricted class selected for passenger band/route' : (details.includes('Waiver Exception') && details.includes('Economy') ? 'Approved via Monsoon Waiver Exception' : 'Cabin class permitted')
      },
      {
        name: 'Advance Booking Window',
        passed: !hasAdvanceViolation,
        msg: hasAdvanceViolation ? 'Insufficient booking window' : (details.includes('Waiver Exception') && details.includes('Advance') ? 'Approved via Booking Window Exception' : 'Window compliance met')
      },
      {
        name: 'Maximum Fare Cap',
        passed: !hasPriceViolation,
        msg: hasPriceViolation ? 'Exceeds corporate limit' : 'Within budget threshold'
      },
      {
        name: 'Preferred Carrier Vendor',
        passed: !details.includes('Non-preferred airline'),
        msg: details.includes('Non-preferred airline') ? 'Non-preferred carrier selected' : 'Preferred carrier verified'
      }
    ];
  };

  return (
    <div className="mt-4 border-t-2 border-accent bg-surface-raised shadow-lg rounded-b-lg p-5 animate-slide-up transition-all duration-300">
      <div className="flex flex-col gap-4">
        {/* Click-to-Expand Header */}
        <div 
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center justify-between cursor-pointer select-none pb-1 hover:opacity-90"
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-text-primary uppercase tracking-wider">Itinerary Booking Proposal</span>
            <span className="text-[10px] text-accent font-semibold px-2 py-0.5 bg-accent/10 rounded">
              {isExpanded ? 'Collapse ▲' : 'Expand Details ▼'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-text-secondary">
              {origin} → {destination} | INR {price_inr.toLocaleString()}
            </span>
            <div>
              {!compliant ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                  ⚠ Non-Compliant
                </span>
              ) : hasWaiverException ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  🎟️ Waiver Applied
                </span>
              ) : requires_approval ? (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  📜 Approval Req.
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  ✓ Compliant
                </span>
              )}
            </div>
          </div>
        </div>

        {isExpanded && (
          <div className="flex flex-col gap-4 animate-fade-in">
            {/* Flight Summary */}
            <div className="bg-surface/40 border border-border/80 p-4 rounded-md flex justify-between items-center shadow-sm">
              <div className="flex flex-col gap-1">
                <span className="text-xl font-extrabold text-accent tracking-wide">{origin} → {destination}</span>
                <div className="flex items-center gap-2 text-xs text-text-secondary font-medium">
                  <span>{getAirlineName(airline)} ({flight_number})</span>
                  <span className="w-1 h-1 bg-text-tertiary rounded-full" />
                  <span className="font-mono bg-surface border px-1.5 py-0.5 rounded font-bold text-[9px] text-text-secondary">
                    {fare_class}
                  </span>
                </div>
              </div>
              {/* Waiver banner */}
              {hasWaiverException && (
                <span className="bg-amber-500/10 text-amber-400 text-[10px] font-bold px-2 py-1 rounded border border-amber-500/20 font-mono">
                  🎟️ MONSOON EXCEPTION APPLIED
                </span>
              )}
            </div>

            {/* Price Row */}
            <div className="flex items-center justify-between border-b border-border/60 pb-3.5">
              <span className="text-xs text-text-secondary font-semibold">Total Ticket Fare</span>
              <div className="flex flex-col items-end">
                <span className="text-xl font-bold text-text-primary">INR {price_inr.toLocaleString()}</span>
                {discountAmount > 0 && (
                  <span className="text-[10px] text-emerald-400 font-bold mt-0.5">
                    Saved INR {discountAmount.toLocaleString()} ({discount_applied})
                  </span>
                )}
              </div>
            </div>

            {/* Audit Details */}
            {compliance_details && (
              <div className="bg-surface/30 border border-border p-4 rounded-lg flex flex-col gap-3 shadow-inner">
                <span className="text-[10px] font-bold text-text-tertiary uppercase tracking-wider">Compliance Audit Logs</span>
                <div className="flex flex-col gap-2.5">
                  {getAuditList().map((item, idx) => (
                    <div key={idx} className="flex items-start gap-3 text-xs">
                      {item.passed ? (
                        <span className="text-emerald-500 font-bold text-base leading-none">✓</span>
                      ) : (
                        <span className="text-rose-500 font-bold text-base leading-none">✗</span>
                      )}
                      <div className="flex flex-col">
                        <span className={`font-semibold ${item.passed ? 'text-text-primary' : 'text-rose-400'}`}>
                          {item.name}
                        </span>
                        <span className="text-[10px] text-text-secondary mt-0.5">{item.msg}</span>
                      </div>
                    </div>
                  ))}
                </div>
                
                <div className="mt-2 pt-2.5 border-t border-border/40 text-[10px] font-mono text-text-tertiary leading-relaxed">
                  <span className="font-bold uppercase block mb-0.5 text-text-secondary">System Raw Trace:</span>
                  {compliance_details}
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3">
              {compliant ? (
                <button
                  onClick={onConfirm}
                  disabled={isBookingLoading}
                  className="flex-1 bg-accent text-white py-2 px-4 rounded-[10px] text-sm font-semibold hover:bg-accent-text transition-all duration-150 shadow-sm disabled:opacity-50"
                >
                  {isBookingLoading ? 'Creating PNR...' : requires_approval ? 'Confirm with Exception & Request Approval' : 'Approve & Create PNR'}
                </button>
              ) : (
                <button
                  onClick={onConfirm}
                  disabled={isBookingLoading}
                  className="flex-1 bg-rose-600 text-white py-2 px-4 rounded-[10px] text-sm font-semibold hover:bg-rose-700 transition-all duration-150 shadow-sm disabled:opacity-50"
                >
                  {isBookingLoading ? 'Registering Override...' : 'Request Policy Override & Create PNR'}
                </button>
              )}
              <button
                onClick={onRevise}
                className="px-4 py-2 border border-border rounded-[10px] text-xs font-semibold text-text-secondary hover:bg-surface hover:text-text-primary transition-all duration-150"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
