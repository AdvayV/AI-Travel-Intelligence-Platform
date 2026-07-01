import React, { useState } from 'react';
import TopBar from './components/TopBar';
import useAgent from './hooks/useAgent';
import BookingDashboard from './pages/BookingDashboard';
import PolicyGraphPage from './pages/PolicyGraphPage';

export default function App() {
  const [activeTab, setActiveTab] = useState('booking');
  const agentProps = useAgent();

  return (
    <div className="min-h-screen bg-bg flex flex-col text-text-primary antialiased">
      {/* Top Navigation */}
      <TopBar 
        onNewBooking={agentProps.reset} 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
      />
      
      {/* Dynamic Main Workspace Rendering */}
      {activeTab === 'booking' ? (
        <BookingDashboard {...agentProps} />
      ) : (
        <PolicyGraphPage />
      )}
    </div>
  );
}


