import React, { useEffect, useState } from 'react';
import QueryInput from '../components/QueryInput';
import AgentTrace from '../components/AgentTrace';
import GraphContext from '../components/GraphContext';
import VectorContext from '../components/VectorContext';
import FlightOptionsSelector from '../components/FlightOptionsSelector';
import BookingProposal from '../components/BookingProposal';
import ResizableSplit from '../components/ResizableSplit';

function BookingHistory({ bookings }) {
  return (
    <section className="bg-surface-raised shadow-sm rounded-2xl border border-border p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div>
          <h2 className="text-xs uppercase font-extrabold tracking-wider text-text-secondary">Booked ticket history</h2>
          <p className="text-[10px] text-text-tertiary">Session records synced to Neo4j</p>
        </div>
        <span className="text-[10px] bg-success-light text-success px-2.5 py-0.5 rounded-full font-bold border border-success/10">
          {bookings.length} booked
        </span>
      </div>
      <div className="flex flex-col gap-2 max-h-[280px] overflow-y-auto pr-1">
        {bookings.length === 0 ? (
          <div className="text-center py-6 text-xs text-text-secondary bg-surface rounded-xl border border-dashed border-border">No tickets booked yet in this session.</div>
        ) : bookings.map((booking, index) => (
          <article key={booking.pnr || index} className="bg-surface/50 border border-border rounded-xl p-3 flex flex-col gap-1.5 hover:border-accent/30 transition-colors shadow-sm">
            <div className="flex justify-between items-center gap-2 text-xs">
              <span className="font-bold text-text-primary truncate">{booking.passenger_name}</span>
              <span className="shrink-0 bg-accent-light text-accent-text text-[9px] font-extrabold px-2 py-0.5 rounded-full font-mono border border-accent/10">PNR: {booking.pnr}</span>
            </div>
            <div className="flex justify-between gap-2 text-[11px] text-text-secondary font-medium">
              <span>Flight {booking.flight_number} ({booking.fare_class})</span>
              <span className="text-text-primary font-extrabold">INR {booking.price_inr?.toLocaleString() || booking.price_inr}</span>
            </div>
            <div className="flex justify-between text-[10px] text-text-tertiary"><span>{booking.origin} → {booking.destination}</span><span>{booking.date}</span></div>
          </article>
        ))}
      </div>
    </section>
  );
}

function EmptyWorkspace({ icon, title, description }) {
  return (
    <div className="h-full min-h-[360px] rounded-xl border border-dashed border-border bg-surface-raised flex flex-col items-center justify-center text-center p-8">
      <span className="text-3xl mb-3">{icon}</span>
      <h3 className="text-sm font-bold text-text-primary">{title}</h3>
      <p className="mt-1 text-xs text-text-secondary max-w-xs">{description}</p>
    </div>
  );
}

export default function BookingDashboard({
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
  const [activePanel, setActivePanel] = useState('trace');
  const isBookingLoading = isLoading && steps.length > 0 && flightOptions.length > 0 && !proposal;

  useEffect(() => {
    if (proposal || selectedFlight) setActivePanel('proposal');
    else if (flightOptions?.length > 0) setActivePanel('flights');
  }, [flightOptions, proposal, selectedFlight]);

  const workspaceTabs = [
    { id: 'trace', label: 'Agent trace', count: steps.length },
    { id: 'flights', label: 'Flight options', count: flightOptions?.length || 0 },
    { id: 'proposal', label: 'Proposal', count: proposal || selectedFlight ? 1 : 0 },
  ];

  return (
    <main className="flex-1 max-w-[1680px] w-full mx-auto px-4 sm:px-6 py-4 sm:py-6 min-h-0 animate-fade-in">
      <ResizableSplit initialSize={440} minSize={340} maxSize={620} storageKey="travelroute-booking-context-width" sidebar={
        <div className="lg:h-[calc(100vh-112px)] lg:overflow-y-auto pr-1 flex flex-col gap-4 pb-1">
          <div className="flex items-center justify-between px-1">
            <div><p className="text-[10px] uppercase font-extrabold tracking-[0.14em] text-text-tertiary">Trip brief</p><h1 className="text-base font-bold tracking-tight text-text-primary">Build a compliant itinerary</h1></div>
            <span className="hidden lg:inline-flex text-[10px] text-text-tertiary bg-surface border border-border rounded-full px-2 py-1">Drag divider to resize</span>
          </div>
          <QueryInput onSubmit={runAgent} isLoading={isLoading && steps.length === 0} />
          {graphContext && <GraphContext context={graphContext} />}
          {vectorContext?.length > 0 && <VectorContext chunks={vectorContext} />}
          <BookingHistory bookings={bookings} />
        </div>
      }>
        <section className="lg:h-[calc(100vh-112px)] min-h-[620px] flex flex-col rounded-2xl border border-border bg-surface-raised shadow-md overflow-hidden">
          <header className="px-5 pt-4 border-b border-border bg-gradient-to-b from-white to-surface/70">
            <div className="flex items-start justify-between gap-4 mb-4">
              <div><p className="text-[10px] uppercase font-extrabold tracking-[0.14em] text-text-tertiary">Execution workspace</p><h2 className="text-lg font-bold tracking-tight text-text-primary">Booking intelligence</h2></div>
              <span className={`shrink-0 text-[10px] font-bold rounded-full px-2.5 py-1 border ${isLoading ? 'bg-accent-light text-accent border-accent/15' : 'bg-success-light text-success border-success/15'}`}>{isLoading ? 'Processing request' : 'Ready'}</span>
            </div>
            <div className="flex gap-1 overflow-x-auto -mb-px" role="tablist" aria-label="Booking workspace panels">
              {workspaceTabs.map((tab) => (
                <button key={tab.id} type="button" role="tab" aria-selected={activePanel === tab.id} onClick={() => setActivePanel(tab.id)} className={`inline-flex items-center gap-2 whitespace-nowrap px-3 py-2.5 text-xs font-semibold border-b-2 transition-colors ${activePanel === tab.id ? 'border-accent text-accent' : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border-strong'}`}>
                  {tab.label}
                  {tab.count > 0 && <span className={`rounded-full px-1.5 py-0.5 text-[9px] ${activePanel === tab.id ? 'bg-accent-light text-accent' : 'bg-surface text-text-tertiary'}`}>{tab.count}</span>}
                </button>
              ))}
            </div>
          </header>

          {error && <div className="mx-5 mt-4 bg-danger-light text-danger border border-danger/10 px-4 py-3 rounded-xl text-xs font-semibold flex items-center justify-between shadow-sm animate-fade-in-up"><span className="flex items-center gap-2"><span>⚠</span>{error}</span><button onClick={reset} className="hover:underline font-bold text-accent">Dismiss</button></div>}

          <div className="flex-1 min-h-0 p-4 sm:p-5 bg-surface/40">
            {activePanel === 'trace' && <AgentTrace steps={steps} isLoading={isLoading && flightOptions.length === 0} />}
            {activePanel === 'flights' && (flightOptions?.length > 0 ? <div className="h-full overflow-y-auto rounded-xl border border-border bg-surface-raised p-4 shadow-sm"><FlightOptionsSelector options={flightOptions} selected={selectedFlight} onSelect={setSelectedFlight} /></div> : <EmptyWorkspace icon="✈" title="Flight options will appear here" description="Run a trip request to compare policy-compliant routes, fares, and airline choices." />)}
            {activePanel === 'proposal' && ((selectedFlight || proposal) ? <div className="h-full overflow-y-auto pr-1"><BookingProposal selectedFlight={selectedFlight} proposal={proposal} onConfirm={confirmBooking} onRevise={reset} isBookingLoading={isBookingLoading} /></div> : <EmptyWorkspace icon="✓" title="Proposal ready when you are" description="Choose a flight option to review price, policy compliance, and booking approval before confirmation." />)}
          </div>
        </section>
      </ResizableSplit>
    </main>
  );
}
