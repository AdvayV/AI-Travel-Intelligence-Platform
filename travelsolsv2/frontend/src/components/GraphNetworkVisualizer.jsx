import React, { useEffect, useState, useRef } from 'react';

export default function GraphNetworkVisualizer({ context }) {
  const containerRef = useRef(null);
  const [nodes, setNodes] = useState([]);
  const [links, setLinks] = useState([]);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [draggedNodeId, setDraggedNodeId] = useState(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 260 });

  // Update canvas size on mount
  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth || 400,
        height: 260
      });
    }
  }, []);

  // Construct Nodes & Links from retrieved entities
  useEffect(() => {
    if (!context || !context.entities) return;
    const { entities } = context;
    
    const extractedNodes = [];
    const extractedLinks = [];
    const seenNodes = new Set();

    const addNode = (id, label, type) => {
      if (!id || seenNodes.has(id)) return;
      seenNodes.add(id);
      
      // Initial positions in circular layout
      const angle = (extractedNodes.length / 5) * 2 * Math.PI;
      const radius = 80;
      extractedNodes.push({
        id,
        label,
        type,
        x: dimensions.width / 2 + radius * Math.cos(angle) + (Math.random() - 0.5) * 10,
        y: dimensions.height / 2 + radius * Math.sin(angle) + (Math.random() - 0.5) * 10,
        vx: 0,
        vy: 0
      });
    };

    const addLink = (source, target, label) => {
      if (!source || !target) return;
      extractedLinks.push({ source, target, label });
    };

    // 1. Build Nodes
    if (entities.passengers) {
      entities.passengers.forEach(p => addNode(p, p, 'passenger'));
    }
    if (entities.policies) {
      entities.policies.forEach(pol => addNode(pol, pol, 'policy'));
    }
    if (entities.airports) {
      entities.airports.forEach(air => addNode(air, air, 'airport'));
    }
    if (entities.waivers) {
      entities.waivers.forEach(w => addNode(w, w, 'waiver'));
    }
    if (entities.airlines) {
      entities.airlines.forEach(airl => addNode(airl, airl, 'airline'));
    }

    // 2. Build Links based on travel logic
    // Passenger -> Policy (HAS_POLICY)
    if (entities.passengers && entities.policies) {
      entities.passengers.forEach(p => {
        entities.policies.forEach(pol => addLink(p, pol, 'HAS_POLICY'));
      });
    }

    // Airports: Route link (ROUTE)
    if (entities.airports && entities.airports.length > 1) {
      addLink(entities.airports[0], entities.airports[1], 'ROUTE');
    }

    // Origin Airport -> Waiver (HAS_WAIVER)
    if (entities.airports && entities.waivers && entities.airports.length > 0) {
      const origin = entities.airports[0];
      entities.waivers.forEach(w => addLink(origin, w, 'HAS_WAIVER'));
    }

    // Airlines operating on route (OPERATED_BY)
    if (entities.airlines && entities.airports && entities.airports.length > 1) {
      const origin = entities.airports[0];
      entities.airlines.forEach(airl => {
        addLink(airl, origin, 'DEPARTS');
      });
    }

    setNodes(extractedNodes);
    setLinks(extractedLinks);
  }, [context, dimensions.width]);

  // Run lightweight physics simulation (force-directed layout)
  useEffect(() => {
    if (nodes.length === 0) return;

    let animFrame;
    const updatePhysics = () => {
      setNodes(prevNodes => {
        const nextNodes = prevNodes.map(n => ({ ...n, vx: 0, vy: 0 }));

        // 1. Repulsion force between all nodes (prevent overlapping)
        for (let i = 0; i < nextNodes.length; i++) {
          for (let j = i + 1; j < nextNodes.length; j++) {
            const dx = nextNodes[j].x - nextNodes[i].x;
            const dy = nextNodes[j].y - nextNodes[i].y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const minDist = 80;
            
            if (dist < minDist) {
              const force = (minDist - dist) / dist * 0.15;
              nextNodes[i].vx -= dx * force;
              nextNodes[i].vy -= dy * force;
              nextNodes[j].vx += dx * force;
              nextNodes[j].vy += dy * force;
            }
          }
        }

        // 2. Attraction force along links (keep connected nodes close)
        links.forEach(link => {
          const sNode = nextNodes.find(n => n.id === link.source);
          const tNode = nextNodes.find(n => n.id === link.target);
          if (sNode && tNode) {
            const dx = tNode.x - sNode.x;
            const dy = tNode.y - sNode.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const targetDist = 100;
            const force = (dist - targetDist) / dist * 0.08;
            
            sNode.vx += dx * force;
            sNode.vy += dy * force;
            tNode.vx -= dx * force;
            tNode.vy -= dy * force;
          }
        });

        // 3. Gravity/center attraction (keep nodes from flying off-screen)
        const cx = dimensions.width / 2;
        const cy = dimensions.height / 2;
        nextNodes.forEach(n => {
          if (n.id === draggedNodeId) return; // skip for dragged node
          
          const dx = cx - n.x;
          const dy = cy - n.y;
          n.vx += dx * 0.01;
          n.vy += dy * 0.01;
          
          // Apply velocity and drag friction
          n.x += n.vx;
          n.y += n.vy;
          
          // Constrain within bounds
          const margin = 20;
          n.x = Math.max(margin, Math.min(dimensions.width - margin, n.x));
          n.y = Math.max(margin, Math.min(dimensions.height - margin, n.y));
        });

        return nextNodes;
      });

      animFrame = requestAnimationFrame(updatePhysics);
    };

    animFrame = requestAnimationFrame(updatePhysics);
    return () => cancelAnimationFrame(animFrame);
  }, [nodes.length, links, draggedNodeId, dimensions]);

  // Drag and drop event handlers
  const handleMouseDown = (e, nodeId) => {
    e.preventDefault();
    setDraggedNodeId(nodeId);
  };

  const handleMouseMove = (e) => {
    if (draggedNodeId === null || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    setNodes(prev => prev.map(n => {
      if (n.id === draggedNodeId) {
        return {
          ...n,
          x: Math.max(10, Math.min(dimensions.width - 10, mouseX)),
          y: Math.max(10, Math.min(dimensions.height - 10, mouseY)),
          vx: 0,
          vy: 0
        };
      }
      return n;
    }));
  };

  const handleMouseUp = () => {
    setDraggedNodeId(null);
  };

  // Node styling configuration
  const getNodeConfig = (type) => {
    switch (type) {
      case 'passenger':
        return { fill: 'rgba(99,102,241,0.15)', stroke: '#818cf8', icon: '👤', title: 'Passenger' };
      case 'policy':
        return { fill: 'rgba(245,158,11,0.15)', stroke: '#fbbf24', icon: '📜', title: 'Corporate Policy' };
      case 'airport':
        return { fill: 'rgba(59,130,246,0.15)', stroke: '#60a5fa', icon: '✈️', title: 'Airport Node' };
      case 'waiver':
        return { fill: 'rgba(16,185,129,0.15)', stroke: '#34d399', icon: '🎟️', title: 'Weather/Fee Waiver' };
      case 'airline':
        return { fill: 'rgba(168,85,247,0.15)', stroke: '#c084fc', icon: '🛩️', title: 'Airline Carrier' };
      default:
        return { fill: 'rgba(107,114,128,0.15)', stroke: '#9ca3af', icon: '⚙️', title: 'Node' };
    }
  };

  return (
    <div 
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      className="relative w-full h-[260px] bg-bg/50 border border-border/40 rounded-lg overflow-hidden cursor-crosshair shadow-inner"
    >
      {/* SVG Canvas */}
      <svg width={dimensions.width} height={dimensions.height} className="select-none">
        <defs>
          {/* Arrow markers for route directionality */}
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="23"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--text-tertiary)" opacity="0.6" />
          </marker>
        </defs>

        {/* Links (lines) */}
        {links.map((link, idx) => {
          const sourceNode = nodes.find(n => n.id === link.source);
          const targetNode = nodes.find(n => n.id === link.target);
          if (!sourceNode || !targetNode) return null;

          return (
            <g key={idx}>
              <line
                x1={sourceNode.x}
                y1={sourceNode.y}
                x2={targetNode.x}
                y2={targetNode.y}
                stroke="var(--text-tertiary)"
                strokeOpacity="0.4"
                strokeWidth="1.5"
                strokeDasharray={link.label === 'HAS_WAIVER' ? '4,4' : '0'}
                markerEnd="url(#arrow)"
              />
              {/* Floating Link Label */}
              <text
                x={(sourceNode.x + targetNode.x) / 2}
                y={(sourceNode.y + targetNode.y) / 2 - 4}
                textAnchor="middle"
                className="text-[8px] font-mono fill-text-tertiary select-none font-bold"
                opacity="0.8"
              >
                {link.label}
              </text>
            </g>
          );
        })}

        {/* Nodes (circles) */}
        {nodes.map(node => {
          const config = getNodeConfig(node.type);
          const isHovered = hoveredNode && hoveredNode.id === node.id;
          const isDragged = draggedNodeId === node.id;

          return (
            <g
              key={node.id}
              transform={`translate(${node.x},${node.y})`}
              onMouseEnter={() => setHoveredNode(node)}
              onMouseLeave={() => setHoveredNode(null)}
              onMouseDown={(e) => handleMouseDown(e, node.id)}
              className="cursor-pointer"
            >
              {/* Outer Glow filter on hover */}
              <circle
                r="18"
                fill={config.fill}
                stroke={config.stroke}
                strokeWidth={isHovered || isDragged ? '2.5' : '1.5'}
                className="transition-all duration-150"
                style={{
                  filter: isHovered || isDragged ? `drop-shadow(0 0 6px ${config.stroke})` : 'none'
                }}
              />
              
              {/* Node Icon */}
              <text
                textAnchor="middle"
                y="4"
                className="text-xs select-none"
              >
                {config.icon}
              </text>

              {/* Node Label underneath */}
              <text
                textAnchor="middle"
                y="28"
                className="text-[10px] font-semibold fill-text-primary select-none drop-shadow"
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Floating Node Info Tooltip */}
      {hoveredNode && (
        <div className="absolute top-2 left-2 bg-surface border border-border p-2 rounded shadow-md text-[10px] leading-relaxed max-w-[180px] pointer-events-none">
          <span className="font-bold text-accent uppercase tracking-wide block">
            {getNodeConfig(hoveredNode.type).title}
          </span>
          <span className="font-semibold text-text-primary block truncate mt-0.5">
            ID: {hoveredNode.id}
          </span>
        </div>
      )}

      {/* Empty State Instructions */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-center p-6 select-none text-[11px] text-text-secondary/70">
          🔄 Waiting for entities to construct Graph Relations...
        </div>
      )}
    </div>
  );
}
