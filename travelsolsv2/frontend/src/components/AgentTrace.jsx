import React, { useEffect, useRef } from 'react';

export default function AgentTrace({ steps, isLoading }) {
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps]);

  const getToolStyle = (toolName) => {
    switch (toolName) {
      case 'check_active_waivers':
        return {
          bg: 'bg-amber-50 text-amber-700 border-amber-100',
          dot: 'bg-amber-500',
          icon: '🎟️',
          label: 'Active Waiver Check'
        };
      case 'get_weather_risk':
        return {
          bg: 'bg-teal-50 text-teal-700 border-teal-100',
          dot: 'bg-teal-500',
          icon: '🌤️',
          label: 'Weather Risk Check'
        };
      case 'search_flights':
        return {
          bg: 'bg-blue-50 text-blue-700 border-blue-100',
          dot: 'bg-blue-500',
          icon: '✈️',
          label: 'Flight Availability Search'
        };
      case 'check_policy_compliance':
        return {
          bg: 'bg-purple-50 text-purple-700 border-purple-100',
          dot: 'bg-purple-500',
          icon: '📜',
          label: 'Policy Compliance Check'
        };
      case 'create_pnr':
        return {
          bg: 'bg-emerald-50 text-emerald-700 border-emerald-100',
          dot: 'bg-emerald-500',
          icon: '💾',
          label: 'PNR Registry Creation'
        };
      case 'conclusion':
        return {
          bg: 'bg-accent-light text-accent-text border-accent/10',
          dot: 'bg-accent',
          icon: '🤖',
          label: 'Agent Conclusion'
        };
      default:
        return {
          bg: 'bg-surface text-text-secondary border-border',
          dot: 'bg-text-tertiary',
          icon: '⚙️',
          label: 'System Execution'
        };
    }
  };

  const getStepNumberText = () => {
    const regularSteps = steps.filter(s => s.tool_name !== 'conclusion');
    const totalCount = 5; // standard sequence is 5 tools
    if (isLoading) {
      return `${regularSteps.length} of ${totalCount} tools called...`;
    }
    return `${regularSteps.length} tool executions completed`;
  };

  return (
    <div className="bg-surface-raised border border-border shadow-lg rounded-lg h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border bg-surface flex items-center justify-between">
        <span className="text-sm font-semibold text-text-primary">Agent reasoning trace</span>
        {steps.length > 0 && (
          <span className="text-xs font-semibold text-text-secondary">
            {getStepNumberText()}
          </span>
        )}
      </div>

      {/* Scrollable Trace Body */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-5 flex flex-col gap-4 min-h-[450px]"
      >
        {steps.length === 0 ? (
          /* Empty State */
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center select-none py-12">
            <svg 
              className="w-16 h-16 text-text-tertiary animate-pulse" 
              fill="none" 
              viewBox="0 0 24 24" 
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
            </svg>
            <div className="flex flex-col gap-1">
              <h4 className="text-sm font-semibold text-text-primary">Awaiting booking request</h4>
              <p className="text-xs text-text-secondary max-w-[280px]">
                Run an agent query to see reasoning steps, weather logs, compliance audits, and graph facts.
              </p>
            </div>
          </div>
        ) : (
          /* Trace List */
          steps.map((step, idx) => {
            const style = getToolStyle(step.tool_name);
            const isConclusion = step.tool_name === 'conclusion';
            
            return (
              <div 
                key={idx}
                className={`flex flex-col gap-2 p-4 border rounded-md shadow-sm transform translate-y-2 opacity-0 animate-fade-in-up leading-relaxed
                  ${style.bg}`}
                style={{ animationDelay: '50ms', animationFillMode: 'forwards' }}
              >
                {/* Step Header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${style.dot} text-white`}>
                      {style.icon}
                    </span>
                    <span className="text-xs font-semibold uppercase tracking-wider">
                      {style.label}
                    </span>
                  </div>
                  <span className="text-[10px] text-text-tertiary">
                    {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>

                {/* Step Content */}
                <div className="text-xs mt-1">
                  {!isConclusion && (
                    <div className="mb-2">
                      <span className="text-[10px] font-bold uppercase text-text-secondary tracking-wide block mb-1">
                        Tool Input:
                      </span>
                      <code className="block font-mono bg-surface border border-border/60 p-2 rounded text-[11px] overflow-x-auto whitespace-pre-wrap select-all font-semibold">
                        {step.tool_input}
                      </code>
                    </div>
                  )}
                  
                  <div>
                    <span className="text-[10px] font-bold uppercase text-text-secondary tracking-wide block mb-1">
                      {isConclusion ? 'Response Content:' : 'Tool Output:'}
                    </span>
                    <p className={`whitespace-pre-line text-text-primary ${isConclusion ? 'text-sm font-medium' : ''}`}>
                      {step.tool_output.replace(/\*\*/g, '').replace(/\*/g, '')}
                    </p>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
