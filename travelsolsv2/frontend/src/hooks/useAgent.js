import { useState, useRef, useEffect } from 'react';

export default function useAgent() {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [steps, setSteps] = useState([]);
  const [graphContext, setGraphContext] = useState(null);
  const [vectorContext, setVectorContext] = useState([]);
  const [proposal, setProposal] = useState(null);
  const [error, setError] = useState(null);
  const [flightOptions, setFlightOptions] = useState([]);
  const [selectedFlight, setSelectedFlight] = useState(null);
  const [bookings, setBookings] = useState([]);
  
  const [passengerName, setPassengerName] = useState('Aryan Mehta');
  
  const timerRef = useRef([]);

  const fetchBookings = async () => {
    try {
      const response = await fetch('/api/booking/history');
      if (response.ok) {
        const data = await response.json();
        setBookings(data);
      }
    } catch (err) {
      console.error("Failed to load booking history:", err);
    }
  };

  useEffect(() => {
    fetchBookings();
  }, []);

  const reset = () => {
    // Clear any active timers
    timerRef.current.forEach(clearTimeout);
    timerRef.current = [];

    
    setSteps([]);
    setGraphContext(null);
    setVectorContext([]);
    setProposal(null);
    setError(null);
    setFlightOptions([]);
    setSelectedFlight(null);
  };

  const runAgent = async (queryText, pName) => {
    reset();
    setQuery(queryText);
    setPassengerName(pName);
    setIsLoading(true);

    try {
      const response = await fetch('/api/agent/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: queryText, passenger_id: pName }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to execute agent query');
      }

      const data = await response.json();
      
      // Immediately set the contexts so they are visible right away
      if (data.graph_context) {
        setGraphContext(data.graph_context);
        if (data.graph_context.semantic_chunks) {
          setVectorContext(data.graph_context.semantic_chunks);
        }
      }

      // Animate steps appearing sequentially with 450ms delay between each
      const rawSteps = data.steps || [];
      
      rawSteps.forEach((step, index) => {
        const t = setTimeout(() => {
          setSteps(prev => [...prev, step]);
          
          // If this is the last step, render the final conclusion and proposal
          if (index === rawSteps.length - 1) {
            setSteps(prev => [
              ...prev,
              {
                tool_name: 'conclusion',
                tool_input: 'final_answer',
                tool_output: data.answer
              }
            ]);
            
            if (data.flight_options && data.flight_options.length > 0) {
              setFlightOptions(data.flight_options);
              const firstCompliant = data.flight_options.find(f => f.compliant && !f.requires_approval);
              setSelectedFlight(firstCompliant || data.flight_options[0]);
            }
            
            setIsLoading(false);
          }
        }, (index + 1) * 450);
        
        timerRef.current.push(t);
      });
      
      // If there are NO intermediate steps, show conclusion immediately
      if (rawSteps.length === 0) {
        setSteps([
          {
            tool_name: 'conclusion',
            tool_input: 'final_answer',
            tool_output: data.answer
          }
        ]);
        if (data.flight_options && data.flight_options.length > 0) {
          setFlightOptions(data.flight_options);
          const firstCompliant = data.flight_options.find(f => f.compliant && !f.requires_approval);
          setSelectedFlight(firstCompliant || data.flight_options[0]);
        }
        setIsLoading(false);
      }

    } catch (err) {
      console.error(err);
      setError(err.message || 'An unexpected error occurred during execution.');
      setIsLoading(false);
    }
  };

  const confirmBooking = async () => {
    if (!selectedFlight) return;
    setIsLoading(true);
    setError(null);
    try {
      let finalPassengerName = passengerName || "Aryan Mehta";
      if (graphContext && graphContext.entities && graphContext.entities.passengers && graphContext.entities.passengers.length > 0) {
        finalPassengerName = graphContext.entities.passengers[0];
      }
      
      const response = await fetch('/api/booking/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          passenger_name: finalPassengerName,
          flight_number: selectedFlight.flight_number,
          origin: selectedFlight.origin,
          destination: selectedFlight.destination,
          date: selectedFlight.departure_time.split(' ')[0],
          fare_class: selectedFlight.fare_class,
          price: selectedFlight.price_inr
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to complete booking');
      }

      const booking = await response.json();
      
      setProposal({
        pnr: booking.pnr,
        route: `${selectedFlight.origin} → ${selectedFlight.destination}`,
        airline: selectedFlight.airline,
        fareClass: selectedFlight.fare_class,
        price: selectedFlight.price_inr,
        compliant: selectedFlight.compliant,
        discountApplied: selectedFlight.discount_applied,
        rawAnswer: `PNR registration complete: ${booking.pnr}`
      });
      
      // Refresh booking history
      await fetchBookings();
      
    } catch (err) {
      console.error(err);
      setError(err.message || 'Booking transaction failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return {
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
  };
}
