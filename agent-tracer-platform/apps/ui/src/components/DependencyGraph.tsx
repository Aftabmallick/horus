
import { useState, useEffect } from 'react';

export const DependencyGraph = () => {
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [hasCycles, setHasCycles] = useState(false);
  const [bottlenecks, setBottlenecks] = useState<any[]>([]);
  const [mermaidData, setMermaidData] = useState('');

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const token = localStorage.getItem('agent_tracer_token');
        const res = await fetch('/api/v1/intelligence/graph', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setNodes(data.nodes || []);
          setEdges(data.edges || []);
          setHasCycles(data.has_cycles || false);
          setBottlenecks(data.bottlenecks || []);
          setMermaidData(data.mermaid || '');
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchGraph();
  }, []);

  const downloadMermaid = () => {
    const blob = new Blob([mermaidData], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'topology.mermaid';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-in" style={{ height: '80vh', display: 'flex', flexDirection: 'column' }}>
      <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Dependency Topology</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Auto-discovered agent interaction map.</p>
        </div>
        <button 
          onClick={downloadMermaid} 
          disabled={!mermaidData}
          style={{ padding: '8px 16px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600, opacity: mermaidData ? 1 : 0.5 }}
        >
          Export Mermaid
        </button>
      </header>

      {hasCycles && (
        <div style={{ marginBottom: 16, padding: '12px 16px', background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', borderRadius: 8, border: '1px solid #ef4444', display: 'flex', alignItems: 'center', gap: 8 }}>
          <strong>Warning:</strong> Cycle detected in agent topology! This could lead to infinite loops. (Red edges indicate cyclic paths)
        </div>
      )}

      {bottlenecks.length > 0 && (
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ color: 'var(--text-secondary)' }}>Identified Bottlenecks:</span>
          {bottlenecks.map(b => (
             <span key={b[0]} style={{ padding: '2px 8px', background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', borderRadius: 4, fontSize: '0.85rem' }}>{b[0]}</span>
          ))}
        </div>
      )}

      <div className="glass-panel" style={{ flex: 1, position: 'relative', overflow: 'hidden', borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle, rgba(139,92,246,0.05) 0%, transparent 70%)' }}>
        <svg width="100%" height="100%" viewBox="0 0 800 600" style={{ filter: 'drop-shadow(0 0 10px rgba(0,0,0,0.5))' }}>
          {/* Real nodes (for MVP we map them simply to grid, ideally we'd use a force-layout like d3) */}
          {edges.map((_, i) => (
            <path key={i} d={`M 400 150 L ${250 + (i*150)} 350`} stroke={hasCycles && i === edges.length - 1 ? "#ef4444" : "var(--border-color)"} strokeWidth="2" fill="none" />
          ))}
          
          {nodes.map((n, i) => {
            const isBottleneck = bottlenecks.some(b => b[0] === n.label);
            return (
              <g key={n.id} transform={`translate(${400 + (i*100 - (nodes.length*50))}, ${150 + (i%2)*200})`} style={{ cursor: 'pointer' }}>
                <circle r="40" fill="var(--bg-secondary)" stroke={isBottleneck ? "#f59e0b" : (n.type === 'agent' ? "var(--accent-purple)" : "var(--accent-blue)")} strokeWidth={isBottleneck ? "4" : "3"} />
                <text fill="white" textAnchor="middle" dy="5" fontSize="12" fontWeight="bold">{n.label}</text>
              </g>
            );
          })}
          
          {nodes.length === 0 && (
             <text x="400" y="300" fill="var(--text-secondary)" textAnchor="middle">No agent dependencies recorded yet.</text>
          )}
        </svg>

        <div style={{ position: 'absolute', bottom: 24, right: 24, display: 'flex', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--accent-purple)' }}></div><span style={{ fontSize: '0.85rem' }}>Orchestrator</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><div style={{ width: 12, height: 12, borderRadius: '50%', background: 'var(--accent-blue)' }}></div><span style={{ fontSize: '0.85rem' }}>Worker</span></div>
        </div>
      </div>
    </div>
  );
};
