import { useState, useEffect } from 'react';
import ReactFlow, { Background, Controls, Edge, Node, Position } from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';

interface VisualizerProps {
  traceId: string;
}

export function TraceVisualizer({ traceId }: VisualizerProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchGraph() {
      try {
        const res = await axios.get(`/api/v1/traces/${traceId}/graph`, {
          headers: { Authorization: `Bearer ${localStorage.getItem('agent_tracer_token')}` }
        });
        
        // Simple horizontal layout algorithm placeholder
        let x = 100;
        let y = 200;

        const formattedNodes = res.data.nodes.map((n: any, idx: number) => {
          const typeColors: any = { 'AGENT': '#8b5cf6', 'LLM': '#3b82f6', 'TOOL': '#f59e0b', 'CUSTOM': '#10b981' };
          const bg = typeColors[n.type] || '#121214';
          
          return {
            id: n.id,
            position: { x: x + (idx * 250), y: y + ((idx % 2 === 0) ? -50 : 50) },
            data: { label: n.label },
            sourcePosition: Position.Right,
            targetPosition: Position.Left,
            style: {
              background: bg,
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: '8px',
              padding: '10px 15px',
              boxShadow: `0 0 15px ${bg}40`,
            }
          };
        });

        const formattedEdges = res.data.edges.map((e: any) => ({
          id: `e-${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          animated: true,
          style: { stroke: '#8b5cf6', strokeWidth: 2 }
        }));

        setNodes(formattedNodes);
        setEdges(formattedEdges);
      } catch (err) {
        console.error("Failed to load trace graph", err);
      } finally {
        setLoading(false);
      }
    }
    
    if (traceId) fetchGraph();
  }, [traceId]);

  if (loading) return <div className="glass-panel" style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading Graph...</div>;

  return (
    <div className="glass-panel animate-in" style={{ height: 500, width: '100%', marginTop: '20px' }}>
      <ReactFlow nodes={nodes} edges={edges} fitView>
        <Background color="#3b82f6" gap={16} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
