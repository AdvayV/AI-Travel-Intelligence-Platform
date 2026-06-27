import React from 'react';
import QueryInput from '../components/QueryInput';
import AgentTrace from '../components/AgentTrace';
import GraphContext from '../components/GraphContext';
import VectorContext from '../components/VectorContext';
import FlightOptionsSelector from '../components/FlightOptionsSelector';
import BookingProposal from '../components/BookingProposal';

export default function BookingDashboard({
  query,
  isLoading,
  steps,
  graphContext,
  vectorContext,
  proposal,
  error,
  flightOptions,
  selectedFlight,
  setSelectedFlight,
  bookings,
  runAgent,
  confirmBooking,
  reset,
}) {
  const isBookingLoading = isLoading && steps.length > 0 && flightOptions.length > 0 && !proposal;

  return (
    <main className="flex-1 max-w-[1440px] w-full mx-auto px-6 py-6 grid grid-cols-1 lg:grid-cols-[440px_1fr] gap-6 animate-fade-in">
      
      {/* Left Control Column */}
      <div className="flex flex-col gap-4 h-fit">
        <QueryInput onSubmit={runAgent} isLoading={isLoading && steps.length === 0} />
        
        {graphContext && (
          <GraphContext context={graphContext} />
        )}
        
        {vectorContext && vectorContext.length > 0 && (
          <VectorContext chunks={vectorContext} />
        )}

        {/* Booked Ticket History */}
        <div className="bg-surface-raised shadow-md rounded-2xl border border-border p-5 flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <h2 className="text-xs uppercase font-extrabold tracking-wider text-text-secondary">Booked Ticket History</h2>
              <p className="text-[10px] text-text-tertiary">Real-time logs from Travel GDS & Neo4j</p>
            </div>
            <span className="text-[10px] bg-success-light text-success px-2.5 py-0.5 rounded-full font-bold border border-success/10">
              {bookings.length} Booked
            </span>
          </div>
          
          <div className="flex flex-col gap-2 max-h-[280px] overflow-y-auto pr-1">
            {bookings.length === 0 ? (
              <div className="text-center py-6 text-xs text-text-secondary bg-surface rounded-xl border border-dashed border-border">
                No tickets booked yet in this session.
              </div>
            ) : (
              bookings.map((b, idx) => (
                <div key={b.pnr || idx} className="bg-surface/50 border border-border rounded-xl p-3 flex flex-col gap-1.5 hover:border-accent/30 transition-all duration-200 shadow-sm">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-text-primary">{b.passenger_name}</span>
                    <span className="bg-accent-light text-accent-text text-[9px] font-extrabold px-2 py-0.5 rounded-full font-mono border border-accent/10">
                      PNR: {b.pnr}
                    </span>
                  </div>
                  <div className="flex justify-between text-[11px] text-text-secondary font-medium">
                    <span>Flight {b.flight_number} ({b.fare_class})</span>
                    <span className="text-text-primary font-extrabold">INR {b.price_inr?.toLocaleString() || b.price_inr}</span>
                  </div>
                  <div className="flex justify-between text-[10px] text-text-tertiary">
                    <span>{b.origin} → {b.destination}</span>
                    <span>{b.date}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
      
      {/* Right Intelligence Column */}
      <div className="flex flex-col gap-4 min-h-[600px] lg:h-[calc(100vh-100px)]">
        {/* Error Banner */}
        {error && (
          <div className="bg-danger-light text-danger border border-danger/10 px-4 py-3 rounded-md text-xs font-semibold flex items-center justify-between shadow-sm animate-fade-in-up">
            <div className="flex items-center gap-2">
              <span>⚠</span>
              <span>{error}</span>
            </div>
            <button 
              onClick={reset}
              className="hover:underline font-bold text-accent"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Reasoning trace takes main space */}
        <div className="flex-1 min-h-0">
          <AgentTrace steps={steps} isLoading={isLoading && flightOptions.length === 0} />
        </div>

        {/* Dynamic Flight Selector */}
        {flightOptions && flightOptions.length > 0 && (
          <div className="bg-surface border border-border p-4 rounded-lg shadow-sm max-h-[300px] overflow-y-auto">
            <FlightOptionsSelector 
              options={flightOptions}
              selected={selectedFlight}
              onSelect={setSelectedFlight}
            />
          </div>
        )}
        
        {/* Booking proposal attaches at the bottom */}
        {(selectedFlight || proposal) && (
          <BookingProposal 
            selectedFlight={selectedFlight}
            proposal={proposal} 
            onConfirm={confirmBooking}
            onRevise={reset} 
            isBookingLoading={isBookingLoading}
          />
        )}
      </div>
      
    </main>
  );
}
