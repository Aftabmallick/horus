import { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, Clock, Network, History, ToggleRight, ToggleLeft } from 'lucide-react';
import ReactFlow, { MiniMap, Controls, Background, useNodesState, useEdgesState, MarkerType } from 'reactflow';
import 'reactflow/dist/style.css';
import { TimeTravelConsole } from './TimeTravelConsole';
import { MermaidGraph } from './MermaidGraph';

interface Span {
  span_id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  status: string;
  duration_ms: number;
  input: any;
  output: any;
  error: any;
  token_usage?: { total_tokens: number; input_tokens: number; output_tokens: number };
  cost_info?: { total_cost: number };
}

interface TraceDetailProps {
  traceId: string;
  onBack: () => void;
}

const JSONViewer = ({ data, title, proMode }: { data: any, title: string, proMode: boolean }) => {
  if (!data) return null;
  let parsed = data;
  if (typeof data === 'string') {
    try { parsed = JSON.parse(data); } catch (e) { }
  }
  const display = typeof parsed === 'object' ? JSON.stringify(parsed, null, proMode ? 0 : 2) : parsed;
  return (
    <div style={{ marginTop: proMode ? 8 : 16 }}>
      <h4 style={{ color: 'var(--text-secondary)', marginBottom: proMode ? 4 : 8, fontSize: '0.85rem' }}>{title}</h4>
      <pre className="glass-panel" style={{ padding: proMode ? 8 : 16, overflowX: 'auto', fontSize: proMode ? '0.75rem' : '0.85rem', color: '#e2e8f0', background: 'rgba(0,0,0,0.3)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: proMode ? 1.2 : 1.5 }}>
        {display}
      </pre>
    </div>
  );
};

export const TraceDetail = ({ traceId, onBack }: TraceDetailProps) => {
  const [trace, setTrace] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);
  const [activeView, setActiveView] = useState<'dag' | 'timetravel' | 'mermaid'>('dag');
  const [proMode, setProMode] = useState(false); // High density toggle
  
  // React Flow State
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    fetchTrace();
  }, [traceId]);

  const fetchTrace = async () => {
    try {
      const res = await fetch(`/api/v1/traces/${traceId}`, { headers: { Authorization: `Bearer ${localStorage.getItem('agent_tracer_token')}` } });
      if (res.ok) {
        const data = await res.json();
        setTrace(data);
        if (data.spans && data.spans.length > 0) {
            buildReactFlow(data.spans);
            setSelectedSpan(data.spans[0]);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  const buildReactFlow = (spans: Span[]) => {
    const newNodes: any[] = [];
    const newEdges: any[] = [];
    
    // Very basic DAG layout logic (in production, use dagre)
    
    spans.forEach((span, index) => {
      newNodes.push({
        id: span.span_id,
        position: { x: (span.parent_span_id ? 250 : 50), y: index * 100 },
        data: { label: `${span.name} (${span.duration_ms}ms)` },
        style: {
          background: span.status === 'ERROR' ? '#fecaca' : '#fff',
          color: '#000',
          border: '1px solid #333',
          borderRadius: '8px',
          padding: '10px',
          fontSize: '12px',
          fontWeight: 'bold',
          width: 200,
        }
      });
      
      if (span.parent_span_id) {
        newEdges.push({
          id: `e-${span.parent_span_id}-${span.span_id}`,
          source: span.parent_span_id,
          target: span.span_id,
          type: 'smoothstep',
          markerEnd: { type: MarkerType.ArrowClosed, color: '#999' },
          style: { stroke: '#999', strokeWidth: 2 },
        });
      }
    });

    setNodes(newNodes as any);
    setEdges(newEdges as any);
  };

  const onNodeClick = useCallback((_event: any, node: any) => {
    if (trace && trace.spans) {
      const span = trace.spans.find((s: Span) => s.span_id === node.id);
      if (span) setSelectedSpan(span);
    }
  }, [trace]);

  if (loading) return <div>Loading trace...</div>;
  if (!trace) return <div>Trace not found.</div>;

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: proMode ? 12 : 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button className="glass-panel" onClick={onBack} style={{ padding: '8px 12px', cursor: 'pointer', background: 'transparent', color: 'white', border: '1px solid var(--border-color)', borderRadius: 8 }}>
            <ArrowLeft size={18} />
          </button>
          <div>
            <h2 style={{ margin: 0, fontSize: proMode ? '1.2rem' : '1.5rem' }}>{trace.agent_name}</h2>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>ID: {trace.trace_id}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <button 
            onClick={() => setProMode(!proMode)} 
            style={{ background: 'transparent', border: 'none', color: proMode ? 'var(--accent-green)' : 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}
          >
            {proMode ? <ToggleRight size={24} /> : <ToggleLeft size={24} />}
            Pro Mode (High Density)
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', gap: 8, marginBottom: proMode ? 8 : 16 }}>
        <button onClick={() => setActiveView('dag')} className="glass-panel" style={{ padding: proMode ? '4px 12px' : '8px 16px', background: activeView === 'dag' ? 'rgba(255,255,255,0.1)' : 'transparent', color: 'white', border: '1px solid var(--border-color)', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Network size={16} /> Interactive DAG
        </button>
        <button onClick={() => setActiveView('timetravel')} className="glass-panel" style={{ padding: proMode ? '4px 12px' : '8px 16px', background: activeView === 'timetravel' ? 'rgba(255,255,255,0.1)' : 'transparent', color: 'white', border: '1px solid var(--border-color)', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
          <History size={16} /> Time-Travel Replay
        </button>
      </div>

      <div style={{ display: 'flex', gap: proMode ? 12 : 24, flex: 1, overflow: 'hidden' }}>
        
        {/* Left Side: React Flow DAG Viewer */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'hidden' }}>
          {activeView === 'dag' && (
            <div className="glass-panel" style={{ flex: 1, height: '100%', borderRadius: 8, overflow: 'hidden' }}>
               <ReactFlow 
                 nodes={nodes} 
                 edges={edges} 
                 onNodesChange={onNodesChange} 
                 onEdgesChange={onEdgesChange} 
                 onNodeClick={onNodeClick}
                 fitView
               >
                 <Background color="#555" gap={16} />
                 <Controls />
                 <MiniMap />
               </ReactFlow>
            </div>
          )}
          {activeView === 'mermaid' && <MermaidGraph spans={trace.spans || []} />}
          {activeView === 'timetravel' && <TimeTravelConsole traceId={traceId} />}
        </div>

        {/* Right Side: High Density Panel */}
        {selectedSpan && (
          <div className="glass-panel" style={{ width: proMode ? 350 : 450, padding: proMode ? 16 : 24, overflowY: 'auto', background: 'var(--bg-secondary)', transition: 'width 0.2s' }}>
            <h3 style={{ marginBottom: proMode ? 8 : 16, fontSize: proMode ? '1.1rem' : '1.3rem' }}>{selectedSpan.name}</h3>
            
            <div style={{ display: 'flex', gap: 8, marginBottom: proMode ? 12 : 24, flexWrap: 'wrap' }}>
              <span className={`badge ${selectedSpan.status === 'OK' ? 'badge-ok' : 'badge-error'}`}>{selectedSpan.status}</span>
              <span className="badge badge-running" style={{ background: 'rgba(255,255,255,0.1)', color: '#fff' }}><Clock size={12} style={{marginRight: 4}}/> {selectedSpan.duration_ms}ms</span>
            </div>

            <JSONViewer title="Input Payload" data={selectedSpan.input} proMode={proMode} />
            <JSONViewer title="Output / Response" data={selectedSpan.output} proMode={proMode} />
          </div>
        )}
      </div>
    </div>
  );
};
