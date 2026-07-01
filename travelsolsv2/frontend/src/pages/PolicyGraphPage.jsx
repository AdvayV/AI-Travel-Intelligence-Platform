import React, { useEffect, useRef, useState, useCallback } from 'react';

const NODE_CONFIG = {
  document:  { color: '#1E1B4B', label: 'PolicyDocument', r: 28, text: '#ffffff' },
  section:   { color: '#0F172A', label: 'PolicySection',  r: 22, text: '#ffffff' },
  rule:      { color: '#451A03', label: 'PolicyRule',     r: 20, text: '#ffffff' },
  policy:    { color: '#022C22', label: 'CorporatePolicy',r: 24, text: '#ffffff' },
  fareclass: { color: '#4C0519', label: 'FareClass',      r: 18, text: '#ffffff' },
  airline:   { color: '#3B0764', label: 'Airline',        r: 22, text: '#ffffff' },
  tier:      { color: '#431407', label: 'EmployeeTier',   r: 18, text: '#ffffff' },
};

const LINK_COLORS = {
  HAS_SECTION:       '#1E40AF',
  CONTAINS_RULE:     '#9A3412',
  GOVERNS_POLICY:    '#065F46',
  PERMITS_FARE_CLASS:'#9F1239',
  PREFERRED_AIRLINE: '#6B21A8',
  GOVERNED_BY:       '#92400E',
};

function useForceSimulation(rawNodes, rawLinks, width, height) {
  const [simNodes, setSimNodes] = useState([]);
  const nodesRef = useRef([]);
  const tickRef = useRef(0);
  const rafRef = useRef(null);

  const reheat = useCallback(() => {
    tickRef.current = 0;
  }, []);

  useEffect(() => {
    if (!rawNodes.length) { setSimNodes([]); return; }

    const cx = width / 2;
    const cy = height / 2;

    // Preserve coordinates of existing nodes to keep layout stable during resize
    const existingNodesMap = new Map(nodesRef.current.map(n => [n.id, n]));

    const placed = rawNodes.map((n, i) => {
      const existing = existingNodesMap.get(n.id);
      if (existing) {
        return { ...n, ...existing };
      }
      
      const angle = (i / rawNodes.length) * 2 * Math.PI;
      const radius = 120 + Math.random() * 100;
      return {
        ...n,
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
        vx: 0,
        vy: 0,
        pinned: false,
      };
    });

    nodesRef.current = placed;
    setSimNodes([...placed]);
    tickRef.current = 0;

    const simulate = () => {
      const nodes = nodesRef.current;
      const alpha = Math.max(0.005, 0.3 * Math.exp(-tickRef.current * 0.005));
      tickRef.current++;

      // 1. Repulsion (inverse distance square force) - Increased strength for better spacing
      const strength = 3500;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[j].x - nodes[i].x || 0.1;
          const dy = nodes[j].y - nodes[i].y || 0.1;
          const d2 = dx * dx + dy * dy || 1;
          const d = Math.sqrt(d2);
          
          const f = (strength / d2) * alpha;
          const fx = (dx / d) * f;
          const fy = (dy / d) * f;
          
          if (!nodes[i].pinned) { nodes[i].vx -= fx; nodes[i].vy -= fy; }
          if (!nodes[j].pinned) { nodes[j].vx += fx; nodes[j].vy += fy; }
        }
      }

      // 2. Spring Attraction along links - Increased restLength for more space
      rawLinks.forEach(l => {
        const s = nodes.find(n => n.id === l.source);
        const t = nodes.find(n => n.id === l.target);
        if (!s || !t) return;
        const dx = t.x - s.x || 0.1;
        const dy = t.y - s.y || 0.1;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        
        const restLength = 220;
        const stiffness = 0.035;
        const f = stiffness * (d - restLength) * alpha;
        const fx = (dx / d) * f;
        const fy = (dy / d) * f;
        
        if (!s.pinned) { s.vx += fx; s.vy += fy; }
        if (!t.pinned) { t.vx -= fx; t.vy -= fy; }
      });

      // 3. Gravity and Damping
      nodes.forEach(n => {
        if (n.pinned) return;
        n.vx += (cx - n.x) * 0.002 * alpha;
        n.vy += (cy - n.y) * 0.002 * alpha;
        
        n.vx *= 0.88;
        n.vy *= 0.88;
        
        n.x += n.vx;
        n.y += n.vy;
      });

      setSimNodes([...nodes]);

      if (alpha > 0.006) {
        rafRef.current = requestAnimationFrame(simulate);
      } else {
        rafRef.current = null;
      }
    };

    rafRef.current = requestAnimationFrame(simulate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [rawNodes, rawLinks, width, height]);

  const pinNode = useCallback((id, x, y) => {
    nodesRef.current = nodesRef.current.map(n =>
      n.id === id ? { ...n, x, y, pinned: true, vx: 0, vy: 0 } : n
    );
    setSimNodes([...nodesRef.current]);
    reheat();
  }, [reheat]);

  const releaseNode = useCallback((id) => {
    nodesRef.current = nodesRef.current.map(n =>
      n.id === id ? { ...n, pinned: false } : n
    );
    reheat();
  }, [reheat]);

  return { simNodes, pinNode, releaseNode, reheat, setSimNodes };
}

export default function PolicyGraphPage() {
  const containerRef = useRef(null);
  const [dimensions, setDimensions]   = useState({ width: 1000, height: 700 });
  const [rawNodes, setRawNodes]        = useState([]);
  const [rawLinks, setRawLinks]        = useState([]);
  const [stats, setStats]              = useState(null);
  const [loading, setLoading]          = useState(true);
  const [error, setError]              = useState(null);
  const [hovered, setHovered]          = useState(null);
  const [selected, setSelected]        = useState(null);
  const [filterType, setFilterType]    = useState('all');
  const [dragId, setDragId]            = useState(null);
  const [searchQ, setSearchQ]          = useState('');
  const [ingestStatus, setIngestStatus]= useState(null);

  // Custom Graph Query States
  const [nlPrompt, setNlPrompt]        = useState('');
  const [geminiKey, setGeminiKey]      = useState(() => localStorage.getItem('gemini_api_key') || '');
  const [cypherQuery, setCypherQuery]  = useState('MATCH (d:PolicyDocument)-[r]->(n) RETURN d, r, n LIMIT 100');
  const [queryAnswer, setQueryAnswer]  = useState('');
  const [queryResults, setQueryResults]= useState(null);
  const [queryLoading, setQueryLoading]= useState(false);
  const [showConsole, setShowConsole]  = useState(false);

  const handleNLSubmit = async (e) => {
    e.preventDefault();
    if (!nlPrompt.trim()) return;
    setQueryLoading(true);
    setQueryAnswer('');
    setQueryResults(null);
    try {
      const res = await fetch('/api/graph/query/nl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: nlPrompt,
          api_key: geminiKey || undefined
        })
      });
      if (res.ok) {
        const data = await res.json();
        setCypherQuery(data.cypher);
        setQueryAnswer(data.answer);
        setQueryResults(data.results);
        setShowConsole(true);
      } else {
        const errText = await res.text();
        setQueryAnswer(`Error translating prompt: ${errText}`);
        setShowConsole(true);
      }
    } catch (err) {
      setQueryAnswer(`Error: ${err.message}`);
      setShowConsole(true);
    } finally {
      setQueryLoading(false);
    }
  };

  const handleCypherSubmit = async (e) => {
    e?.preventDefault();
    if (!cypherQuery.trim()) return;
    setQueryLoading(true);
    setQueryAnswer('');
    setQueryResults(null);
    try {
      const res = await fetch('/api/graph/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: cypherQuery })
      });
      if (res.ok) {
        const data = await res.json();
        setQueryResults(data.results);
        setQueryAnswer(`Successfully executed Cypher query. Found ${data.results?.length || 0} rows.`);
        setShowConsole(true);
      } else {
        const errText = await res.text();
        setQueryAnswer(`Query execution error: ${errText}`);
        setShowConsole(true);
      }
    } catch (err) {
      setQueryAnswer(`Error executing Cypher: ${err.message}`);
      setShowConsole(true);
    } finally {
      setQueryLoading(false);
    }
  };

  // Pan and Zoom State
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [isDraggingCanvas, setIsDraggingCanvas] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const { simNodes, pinNode, releaseNode, reheat } = useForceSimulation(
    rawNodes, rawLinks, dimensions.width, dimensions.height
  );

  // Measure container
  useEffect(() => {
    const measure = () => {
      if (containerRef.current) {
        setDimensions({
          width:  containerRef.current.clientWidth  || 1000,
          height: containerRef.current.clientHeight || 700,
        });
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  // Listen to wheel zoom with non-passive options
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const handleWheelDOM = (e) => {
      e.preventDefault();
      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      const zoomFactor = 1.08;
      setZoom((prevZoom) => {
        let newZoom = e.deltaY < 0 ? prevZoom * zoomFactor : prevZoom / zoomFactor;
        newZoom = Math.max(0.15, Math.min(4, newZoom));
        
        setPan((prevPan) => ({
          x: mouseX - (newZoom / prevZoom) * (mouseX - prevPan.x),
          y: mouseY - (newZoom / prevZoom) * (mouseY - prevPan.y)
        }));

        return newZoom;
      });
      reheat();
    };
    container.addEventListener('wheel', handleWheelDOM, { passive: false });
    return () => {
      container.removeEventListener('wheel', handleWheelDOM);
    };
  }, [reheat]);

  // Load graph data
  const loadGraph = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch('/api/policy/graph');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRawNodes(data.nodes || []);
      setRawLinks(data.links || []);
      setStats(data.stats);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const triggerIngest = async () => {
    setIngestStatus('ingesting');
    try {
      const res = await fetch('/api/policy/ingest', { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({}) 
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setIngestStatus('done');
      setTimeout(() => { setIngestStatus(null); loadGraph(); }, 1500);
    } catch (e) {
      setIngestStatus('error');
      setTimeout(() => setIngestStatus(null), 3000);
    }
  };

  useEffect(() => { loadGraph(); }, [loadGraph]);

  // Canvas Drag/Pan Handlers
  const handleCanvasMouseDown = (e) => {
    if (e.target.tagName === 'svg' || e.target.id === 'grid-rect') {
      setIsDraggingCanvas(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleCanvasMouseMove = (e) => {
    if (isDraggingCanvas) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    } else if (dragId) {
      const rect = containerRef.current.getBoundingClientRect();
      // Translate client coordinate back to graph coordinate
      const mouseX = (e.clientX - rect.left - pan.x) / zoom;
      const mouseY = (e.clientY - rect.top - pan.y) / zoom;
      pinNode(dragId, mouseX, mouseY);
    }
  };

  const handleCanvasMouseUp = () => {
    setIsDraggingCanvas(false);
    if (dragId) releaseNode(dragId);
    setDragId(null);
  };

  // Node Drag Trigger
  const handleNodeMouseDown = (e, id) => {
    e.stopPropagation();
    setDragId(id);
  };


  // Short name formatter for rendering inside circles
  const getShortLabel = (node) => {
    const label = node.label || node.id || '';
    if (node.type === 'document') return 'Policy Doc';
    if (node.type === 'rule') {
      return label.replace('Rule ', ''); // e.g. "p.5"
    }
    if (node.type === 'fareclass') {
      return label.replace('Class ', ''); // e.g. "Y"
    }
    if (node.type === 'policy') {
      return label; // e.g. "CP-001"
    }
    if (node.type === 'airline') {
      return node.id; // e.g. "AI", "QR"
    }
    return label.length > 9 ? label.slice(0, 7) + '..' : label;
  };

  // Calculate Node Label counts for Legend
  const typeCounts = simNodes.reduce((acc, n) => {
    acc[n.type] = (acc[n.type] || 0) + 1;
    return acc;
  }, {});

  // Filters logic
  const searchNormalized = searchQ.trim().toLowerCase();
  const visibleNodeIds = new Set(
    simNodes
      .filter(n => filterType === 'all' || n.type === filterType)
      .filter(n => !searchNormalized || (n.label || '').toLowerCase().includes(searchNormalized) || n.id.toLowerCase().includes(searchNormalized))
      .map(n => n.id)
  );
  const visibleLinks = rawLinks.filter(l => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target));
  const visibleNodes = simNodes.filter(n => visibleNodeIds.has(n.id));

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] bg-[#F8FAFC] overflow-hidden text-slate-800 select-none">
      
      {/* Top control bar (Faux Neo4j Aura Header) */}
      <div className="flex items-center gap-4 px-6 py-3 bg-[#FFFFFF] border-b border-[#E2E8F0] flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.4)]" />
          <span className="text-xs font-bold text-slate-700 tracking-wide font-mono">Instance: travel-policy-db</span>
          <span className="text-[10px] text-slate-600 font-mono bg-[#F1F5F9] px-2 py-0.5 rounded border border-[#E2E8F0] select-none">
            Neo4j v5.x
          </span>
        </div>

        {/* Search Input */}
        <div className="relative ml-4">
          <input
            type="text"
            placeholder="Search nodes by label or ID..."
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            className="bg-[#F1F5F9] border border-[#CBD5E1] rounded px-3 py-1 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-indigo-600 w-56 font-sans transition-all"
          />
          {searchQ && (
            <button onClick={() => setSearchQ('')} className="absolute right-2 top-1.5 text-slate-400 hover:text-slate-600 text-xs">×</button>
          )}
        </div>

        {/* Admin Commands */}
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={triggerIngest}
            disabled={ingestStatus === 'ingesting'}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded bg-[#FFFFFF] border border-[#CBD5E1] text-slate-700 hover:border-emerald-600 hover:text-emerald-600 transition-all disabled:opacity-50"
          >
            {ingestStatus === 'ingesting' ? (
              <><span className="w-2.5 h-2.5 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />Running...</>
            ) : ingestStatus === 'done' ? '✅ Ingestion Success' : ingestStatus === 'error' ? '❌ Ingestion Failed' : '⚡ Parse PDF & Build Graph'}
          </button>
          
          <button
            onClick={loadGraph}
            className="flex items-center gap-1 px-3 py-1 text-xs font-semibold rounded bg-indigo-600 text-white hover:bg-indigo-500 transition-all shadow-md"
          >
            ↻ Refresh DB
          </button>
        </div>
      </div>

      {/* Interactive Graph Query Console */}
      <div className="bg-[#FFFFFF] border-b border-[#E2E8F0] p-4 flex flex-col gap-3 flex-shrink-0 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Natural Language Prompt Form */}
          <form onSubmit={handleNLSubmit} className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center flex-wrap gap-2">
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">Ask Graph in Natural Language</label>
              <input
                type="password"
                placeholder="Paste Gemini API Key (Optional)..."
                value={geminiKey}
                onChange={e => {
                  setGeminiKey(e.target.value);
                  localStorage.setItem('gemini_api_key', e.target.value);
                }}
                className="bg-[#F1F5F9] border border-[#CBD5E1] rounded px-2.5 py-0.5 text-[9px] text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-indigo-500 font-mono w-44"
              />
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={nlPrompt}
                onChange={e => setNlPrompt(e.target.value)}
                placeholder="E.g., What are the rules governed by standard travel policy? or Which airlines are preferred?"
                className="flex-1 bg-[#F1F5F9] border border-[#CBD5E1] rounded px-3 py-1.5 text-xs text-slate-800 focus:outline-none focus:border-indigo-600 font-sans"
              />
              <button
                type="submit"
                disabled={queryLoading || !nlPrompt.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-1.5 rounded transition-all shadow"
              >
                {queryLoading ? 'Translating...' : 'Generate Cypher'}
              </button>
            </div>
          </form>

          {/* Raw Cypher Query Form */}
          <form onSubmit={handleCypherSubmit} className="flex flex-col gap-1.5">
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider font-mono">Execute custom Cypher query</label>
            <div className="flex gap-2">
              <span className="text-teal-600 font-mono font-bold text-xs self-center select-none">neo4j$</span>
              <input
                type="text"
                value={cypherQuery}
                onChange={e => setCypherQuery(e.target.value)}
                placeholder="MATCH (n) RETURN n LIMIT 10"
                className="flex-1 bg-[#F1F5F9] border border-[#CBD5E1] rounded px-3 py-1.5 text-xs font-mono text-slate-800 focus:outline-none focus:border-emerald-600"
              />
              <button
                type="submit"
                disabled={queryLoading || !cypherQuery.trim()}
                className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold px-4 py-1.5 rounded transition-all shadow"
              >
                {queryLoading ? 'Executing...' : 'Run Cypher'}
              </button>
            </div>
          </form>
        </div>

        {/* Collapsible Console Output for Query Answers / JSON Results */}
        {showConsole && (
          <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-3 flex flex-col gap-2.5 max-h-[160px] overflow-y-auto font-mono text-[11px] text-slate-300 relative animate-fade-in-up">
            <button
              onClick={() => setShowConsole(false)}
              className="absolute right-2 top-2 text-slate-500 hover:text-slate-300 text-xs font-bold font-sans"
            >
              Close ×
            </button>
            
            {/* Model Generated Summary Answer */}
            {queryAnswer && (
              <div className="border-b border-[#1E293B] pb-3 mb-2">
                <span className="text-[10px] uppercase font-bold text-[#38BDF8] tracking-wider flex items-center gap-2 mb-2">
                  <span className="text-base">🤖</span> AI Summary Analysis
                </span>
                <div className="text-white leading-relaxed font-sans text-sm bg-slate-800/50 p-3 rounded border border-slate-700/50 shadow-inner">
                  {queryAnswer.split('\n').map((line, idx) => (
                    <div key={idx} className={line.trim().startsWith('-') || line.trim().startsWith('*') ? 'ml-4 mb-1 text-slate-300' : 'mb-2 text-slate-200'}>
                      {line.replace(/\*\*/g, '').replace(/\*/g, '')}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Cypher Result JSON Rows */}
            {queryResults && (
              <div>
                <span className="text-[9px] uppercase font-bold text-[#E2E8F0]/60 tracking-wider block mb-1">📊 Raw Database Results ({queryResults.length} rows)</span>
                <pre className="text-slate-400 text-[10px] leading-tight select-all break-all overflow-x-auto whitespace-pre-wrap">{JSON.stringify(queryResults, null, 2)}</pre>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Workspace layout */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Graph canvas container */}
        <div
          ref={containerRef}
          className="flex-1 relative bg-[#F8FAFC] overflow-hidden"
          onMouseMove={handleCanvasMouseMove}
          onMouseUp={handleCanvasMouseUp}
          onMouseLeave={handleCanvasMouseUp}
        >
          {/* Loading panel */}
          {loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#F8FAFC]/90 z-20">
              <div className="w-8 h-8 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin" />
              <span className="text-slate-500 text-xs font-medium">Fetching graph database metadata...</span>
            </div>
          )}

          {/* Error panel */}
          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#F8FAFC]/95 z-20 px-6 text-center">
              <span className="text-3xl">⚠️</span>
              <p className="text-rose-600 text-xs font-bold font-mono">{error}</p>
              <p className="text-slate-500 text-xs max-w-sm">Make sure the PDF has been ingested and your Neo4j service credentials are correct.</p>
              <button onClick={triggerIngest} className="mt-2 px-4 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded">Ingest PDF</button>
            </div>
          )}

          {/* Empty state panel */}
          {!loading && !error && rawNodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-[#F8FAFC] z-20">
              <div className="text-5xl">🕸️</div>
              <p className="text-slate-700 text-sm font-semibold">Graph database is empty</p>
              <p className="text-slate-500 text-xs max-w-xs text-center">The system detected no extracted node relationships in the current Neo4j schema.</p>
              <button onClick={triggerIngest} className="mt-1 px-5 py-2 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded shadow-lg transition-all">
                ⚡ Parse & Index Policy PDF
              </button>
            </div>
          )}

          {/* Legend floating banner */}
          <div className="absolute top-4 left-4 right-4 bg-[#FFFFFF]/90 border border-[#E2E8F0] rounded p-2 z-10 flex items-center gap-2 overflow-x-auto shadow-lg backdrop-blur-sm">
            <span className="text-[9px] uppercase font-mono tracking-widest text-slate-400 font-bold border-r border-[#E2E8F0] pr-3 mr-1 select-none">
              Node Labels
            </span>
            
            <button
              onClick={() => setFilterType('all')}
              className={`px-2.5 py-0.5 text-[10px] font-bold rounded transition-all font-mono ${filterType === 'all' ? 'bg-[#E2E8F0] text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
            >
              * ({simNodes.length})
            </button>
            
            {Object.entries(NODE_CONFIG).map(([type, cfg]) => {
              const count = typeCounts[type] || 0;
              if (count === 0) return null;
              const isActive = filterType === type;
              
              return (
                <button
                  key={type}
                  onClick={() => setFilterType(isActive ? 'all' : type)}
                  className="flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold rounded transition-all border font-mono select-none"
                  style={{
                    backgroundColor: isActive ? `${cfg.color}15` : 'transparent',
                    borderColor: isActive ? cfg.color : '#E2E8F0',
                    color: isActive ? cfg.color : '#64748b'
                  }}
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cfg.color }} />
                  <span>{cfg.label}</span>
                  <span className="text-slate-500 text-[9px] font-normal">({count})</span>
                </button>
              );
            })}
          </div>

          {/* Canvas SVG */}
          <svg
            width="100%"
            height="100%"
            className="select-none absolute inset-0 outline-none"
            onMouseDown={handleCanvasMouseDown}
            onMouseMove={handleCanvasMouseMove}
            onMouseUp={handleCanvasMouseUp}
            onMouseLeave={handleCanvasMouseUp}
            onClick={() => setSelected(null)}
            style={{ cursor: isDraggingCanvas ? 'grabbing' : dragId ? 'grabbing' : 'grab' }}
          >
            <defs>
              {/* Arrow Head markers representing direct relationships */}
              <marker id="arr" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0,2 L8,5 L0,8 z" fill="#64748b" />
              </marker>
            </defs>

            {/* Grid Pattern Background */}
            <pattern id="neo-grid" width="32" height="32" patternUnits="userSpaceOnUse">
              <circle cx="16" cy="16" r="0.8" fill="rgba(100, 116, 139, 0.25)" />
            </pattern>
            <rect id="grid-rect" width="100%" height="100%" fill="url(#neo-grid)" />

            {/* Zoom & Pan Group Container */}
            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              
              {/* Links Render */}
              {visibleLinks.map((link, i) => {
                const s = visibleNodes.find(n => n.id === link.source);
                const t = visibleNodes.find(n => n.id === link.target);
                if (!s || !t) return null;

                const color = LINK_COLORS[link.label] || '#475569';
                const dx = t.x - s.x;
                const dy = t.y - s.y;
                const d = Math.sqrt(dx * dx + dy * dy) || 1;
                
                const sRadius = (NODE_CONFIG[s.type] || { r: 20 }).r;
                const tRadius = (NODE_CONFIG[t.type] || { r: 20 }).r + (hovered?.id === t.id || selected?.id === t.id ? 4 : 0);

                // Precise coordinate trimming to prevent arrowheads from rendering behind node boundaries
                const startX = s.x + (dx / d) * sRadius;
                const startY = s.y + (dy / d) * sRadius;
                const endX = t.x - (dx / d) * (tRadius + 7);
                const endY = t.y - (dy / d) * (tRadius + 7);

                const mx = (startX + endX) / 2;
                const my = (startY + endY) / 2;
                const isConnectedToSelected = selected && (link.source === selected.id || link.target === selected.id);
                const isNodeHovered = hovered && (link.source === hovered.id || link.target === hovered.id);
                const showLabel = isConnectedToSelected || isNodeHovered;

                const textWidth = link.label.length * 5 + 8;

                return (
                  <g key={i}>
                    <line
                      x1={startX} y1={startY} x2={endX} y2={endY}
                      stroke={color}
                      strokeOpacity={showLabel ? 0.95 : selected ? 0.08 : 0.4}
                      strokeWidth={showLabel ? 2 : 1.2}
                      markerEnd="url(#arr)"
                    />
                    
                    {/* Floating relationship pill label */}
                    <g transform={`translate(${mx}, ${my})`} opacity={showLabel ? 1 : selected ? 0.08 : 0.6}>
                      <rect
                        x={-textWidth / 2}
                        y={-6}
                        width={textWidth}
                        height={12}
                        rx={3}
                        fill="#FFFFFF"
                        stroke={color}
                        strokeWidth={0.5}
                      />
                      <text
                        textAnchor="middle"
                        y={3}
                        fontSize="7"
                        fill="#475569"
                        fontWeight="bold"
                        className="font-mono pointer-events-none"
                      >
                        {link.label}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Nodes Render */}
              {visibleNodes.map(node => {
                const cfg = NODE_CONFIG[node.type] || { color: '#64748b', text: '#ffffff', r: 20 };
                const isHov = hovered?.id === node.id;
                const isSel = selected?.id === node.id;
                const isDragged = dragId === node.id;
                
                // Highlight connected nodes when a node is selected
                const isConnected = selected && rawLinks.some(
                  l => (l.source === selected.id && l.target === node.id) || (l.target === selected.id && l.source === node.id)
                );

                const r = cfg.r + (isHov || isSel ? 4 : 0);
                const opacity = selected && !isSel && !isConnected ? 0.15 : 1;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x},${node.y})`}
                    style={{ cursor: isDragged ? 'grabbing' : 'pointer', opacity }}
                    onMouseEnter={() => setHovered(node)}
                    onMouseLeave={() => setHovered(null)}
                    onMouseDown={e => handleNodeMouseDown(e, node.id)}
                    onClick={e => { e.stopPropagation(); setSelected(selected?.id === node.id ? null : node); }}
                  >
                    {/* Selection halo ring */}
                    {isSel && (
                      <circle r={r + 6} fill="none" stroke="#0F172A" strokeWidth="2.5" opacity="0.9" className="animate-pulse" />
                    )}

                    {/* Hover border glow */}
                    {isHov && !isSel && (
                      <circle r={r + 5} fill="none" stroke={cfg.color} strokeWidth="1.5" opacity="0.5" />
                    )}

                    {/* Main Circle node */}
                    <circle
                      r={r}
                      fill={cfg.color}
                      stroke="rgba(0, 0, 0, 0.15)"
                      strokeWidth={isSel ? 3.5 : isHov ? 2.5 : 1.5}
                      className="transition-all"
                    />

                    {/* Node Text Label inside the circle */}
                    <text
                      textAnchor="middle"
                      y={3.5}
                      fontSize={r > 20 ? "9" : "8"}
                      fontWeight="bold"
                      fill={cfg.text || '#ffffff'}
                      className="pointer-events-none select-none font-sans"
                    >
                      {getShortLabel(node)}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>

          {/* Hover tooltip panel */}
          {hovered && (
            <div className="absolute top-20 left-4 bg-[#FFFFFF]/95 border border-[#E2E8F0] rounded-lg p-3 shadow-2xl pointer-events-none max-w-[280px] z-10 backdrop-blur-sm font-sans animate-fade-in text-slate-800">
              <div className="flex items-center gap-1.5 mb-1">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: (NODE_CONFIG[hovered.type] || {}).color }} />
                <span className="text-[10px] font-bold font-mono uppercase tracking-widest text-slate-400">
                  {(NODE_CONFIG[hovered.type] || {}).label}
                </span>
              </div>
              <p className="text-xs font-bold text-slate-800 leading-tight break-words">{hovered.label || hovered.id}</p>
              <p className="text-[9px] text-slate-400 font-mono mt-1 select-all pointer-events-auto break-all">ID: {hovered.id}</p>
            </div>
          )}

          {/* Zoom/Pan/Simulation Floating controls (Neo4j Aura Style overlay) */}
          <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 z-10">
            <button
              onClick={() => setZoom(z => Math.min(4, z * 1.15))}
              title="Zoom In"
              className="w-8 h-8 rounded bg-white/90 border border-[#E2E8F0] flex items-center justify-center text-slate-700 hover:text-slate-900 hover:bg-slate-100 transition-all font-bold text-sm select-none"
            >
              +
            </button>
            <button
              onClick={() => setZoom(z => Math.max(0.15, z / 1.15))}
              title="Zoom Out"
              className="w-8 h-8 rounded bg-white/90 border border-[#E2E8F0] flex items-center justify-center text-slate-700 hover:text-slate-900 hover:bg-slate-100 transition-all font-bold text-sm select-none"
            >
              -
            </button>
            <button
              onClick={() => { setPan({ x: 0, y: 0 }); setZoom(1); reheat(); }}
              title="Center View"
              className="w-8 h-8 rounded bg-white/90 border border-[#E2E8F0] flex items-center justify-center text-slate-700 hover:text-slate-900 hover:bg-slate-100 transition-all text-[11px] font-bold select-none"
            >
              ⛶
            </button>
            <button
              onClick={loadGraph}
              title="Re-run Simulation"
              className="w-8 h-8 rounded bg-white/90 border border-[#E2E8F0] flex items-center justify-center text-slate-700 hover:text-slate-900 hover:bg-slate-100 transition-all text-xs select-none"
            >
              ⚙
            </button>
          </div>
        </div>

        {/* Right drawer — selected node detail (Highlights properties like Neo4j console) */}
        <div className={`transition-all duration-300 bg-[#FFFFFF] border-l border-[#E2E8F0] overflow-y-auto flex-shrink-0 flex flex-col ${selected ? 'w-80' : 'w-0'}`}>
          {selected && (() => {
            const cfg = NODE_CONFIG[selected.type] || { color: '#94a3b8', label: selected.type };
            const connectedLinks = rawLinks.filter(l => l.source === selected.id || l.target === selected.id);
            const connectedNodes = connectedLinks.map(l => {
              const peerId = l.source === selected.id ? l.target : l.source;
              const dir = l.source === selected.id ? '→' : '←';
              const peer = simNodes.find(n => n.id === peerId);
              return { peer, dir, rel: l.label };
            });
            return (
              <div className="flex-1 flex flex-col min-w-[320px]">
                
                {/* Drawer Header */}
                <div className="p-4 border-b border-[#E2E8F0] bg-[#F1F5F9] flex items-center justify-between flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: cfg.color }} />
                    <div className="min-w-0">
                      <span className="text-[10px] font-bold font-mono tracking-wide text-slate-500 block">{cfg.label}</span>
                      <span className="text-xs font-bold text-slate-800 break-all">{selected.label || selected.id}</span>
                    </div>
                  </div>
                  <button onClick={() => setSelected(null)} className="text-slate-500 hover:text-slate-800 text-lg font-bold p-1">×</button>
                </div>

                {/* Drawer Scrollable Content */}
                <div className="p-4 flex-1 flex flex-col gap-4 overflow-y-auto font-sans">
                  
                  {/* ID Field */}
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5 font-mono">Node ID</span>
                    <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2.5 font-mono text-[11px] text-indigo-700 break-all select-all">
                      {selected.id}
                    </div>
                  </div>

                  {/* Properties Table */}
                  <div>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5 font-mono">Properties</span>
                    <div className="flex flex-col gap-1">
                      
                      {/* labels array */}
                      <div className="bg-[#F8FAFC] border border-[#E2E8F0]/50 rounded px-2.5 py-1.5 flex items-start text-[11px] font-mono">
                        <span className="text-slate-400 w-24 flex-shrink-0 select-none">_labels:</span>
                        <span className="text-emerald-700 font-semibold">["{cfg.label}"]</span>
                      </div>
                      
                      {selected.props && Object.entries(selected.props).filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => (
                        <div key={k} className="bg-[#F8FAFC] border border-[#E2E8F0]/50 rounded px-2.5 py-1.5 flex items-start text-[11px] font-mono">
                          <span className="text-slate-400 w-24 flex-shrink-0 select-none truncate" title={k}>{k}:</span>
                          <span className="text-slate-800 flex-1 break-all">
                            {typeof v === 'boolean' ? (
                              <span className="text-purple-700">{String(v)}</span>
                            ) : typeof v === 'number' ? (
                              <span className="text-amber-700">{v}</span>
                            ) : (
                              <span className="text-emerald-700">"{String(v)}"</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Connected peer nodes */}
                  {connectedNodes.length > 0 && (
                    <div className="mt-2">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5 font-mono">
                        Relationships ({connectedNodes.length})
                      </span>
                      <div className="flex flex-col gap-1.5 max-h-56 overflow-y-auto pr-1">
                        {connectedNodes.map((c, i) => {
                          if (!c.peer) return null;
                          const peerCfg = NODE_CONFIG[c.peer.type] || { color: '#64748b', label: c.peer.type };
                          return (
                            <div
                              key={i}
                              onClick={() => setSelected(c.peer)}
                              className="bg-[#F8FAFC] border border-[#E2E8F0] rounded p-2 flex items-center gap-2 cursor-pointer hover:border-indigo-500/50 hover:bg-[#F1F5F9] transition-all"
                            >
                              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: peerCfg.color }} />
                              <div className="flex-1 min-w-0 font-mono text-[10px]">
                                <span className="text-slate-500 font-semibold">{c.dir} {c.rel}</span>
                                <span className="text-slate-800 block truncate font-sans text-xs mt-0.5">
                                  {c.peer.label || c.peer.id}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })()}
        </div>
      </div>

      {/* Bottom stats info bar (Neo4j Status Bar) */}
      <div className="flex items-center gap-6 px-6 py-2 bg-[#FFFFFF] border-t border-[#E2E8F0] flex-shrink-0 text-[10px] text-slate-500 font-mono select-none">
        <div className="flex items-center gap-4">
          <span className="text-slate-600 font-bold select-none">Database:</span>
          {Object.entries(NODE_CONFIG).map(([type, cfg]) => {
            const count = typeCounts[type] || 0;
            return (
              <span key={type} className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cfg.color }} />
                <span>{cfg.label}:</span>
                <span className="text-slate-800 font-bold">{count}</span>
              </span>
            );
          })}
        </div>
        {visibleNodes.length !== simNodes.length && (
          <span className="ml-auto text-indigo-600 font-bold">Showing {visibleNodes.length} / {simNodes.length} nodes (filters active)</span>
        )}
      </div>
    </div>
  );
}
