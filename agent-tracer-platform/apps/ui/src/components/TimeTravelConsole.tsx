import { useState } from 'react';
import { History, GitBranch } from 'lucide-react';
import axios from 'axios';

interface ConsoleProps {
  traceId: string;
}

export function TimeTravelConsole({ traceId }: ConsoleProps) {
  const [diverging, setDiverging] = useState(false);
  const [newPrompt, setNewPrompt] = useState("");

  const handleDiverge = async () => {
    setDiverging(true);
    try {
      const res = await axios.post(`/api/v1/replay/${traceId}/diverge`, {
        span_id: "example_span",
        new_input: newPrompt
      }, {
        headers: { Authorization: `Bearer ${localStorage.getItem('agent_tracer_token')}` }
      });
      alert(`Divergence started! Job ID: ${res.data.job_id}`);
    } catch (err) {
      console.error(err);
      alert("Failed to start divergence.");
    } finally {
      setDiverging(false);
    }
  };

  return (
    <div className="glass-panel" style={{ marginTop: '24px', display: 'flex', flexDirection: 'column', height: '400px' }}>
      <div style={{ padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', gap: '12px' }}>
        <History size={20} color="#8b5cf6" />
        <h3 style={{ margin: 0, color: '#fff' }}>Time-Travel Console</h3>
      </div>
      
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Left pane: Memory State */}
        <div style={{ flex: 1, borderRight: '1px solid rgba(255,255,255,0.1)', padding: '16px', overflowY: 'auto' }}>
          <h4 style={{ color: 'var(--text-secondary)', marginBottom: '12px' }}>Memory Snapshot</h4>
          <pre style={{ 
            background: 'rgba(0,0,0,0.3)', 
            padding: '12px', 
            borderRadius: '6px', 
            fontSize: '0.85rem',
            color: '#a1a1aa',
            whiteSpace: 'pre-wrap'
          }}>
{`{
  "short_term": [
    "User asked about pricing"
  ],
  "env_vars": {
    "LLM_PROVIDER": "OpenAI"
  }
}`}
          </pre>
        </div>
        
        {/* Right pane: Divergence Controls */}
        <div style={{ flex: 1, padding: '16px', display: 'flex', flexDirection: 'column' }}>
          <h4 style={{ color: 'var(--text-secondary)', marginBottom: '12px' }}>Divergence Execution (What-If)</h4>
          <textarea 
            value={newPrompt}
            onChange={(e) => setNewPrompt(e.target.value)}
            placeholder="Enter a modified prompt to test how the agent WOULD have reacted..."
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: '6px',
              padding: '12px',
              color: '#fff',
              fontFamily: 'monospace',
              resize: 'none',
              marginBottom: '16px'
            }}
          />
          <button 
            onClick={handleDiverge}
            disabled={diverging || !newPrompt}
            style={{
              background: 'var(--accent-purple)',
              color: '#fff',
              border: 'none',
              padding: '12px',
              borderRadius: '6px',
              fontWeight: 600,
              cursor: (diverging || !newPrompt) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              opacity: (diverging || !newPrompt) ? 0.5 : 1
            }}
          >
            <GitBranch size={18} />
            {diverging ? 'Running Alternate Reality...' : 'Branch Execution'}
          </button>
        </div>
      </div>
    </div>
  );
}
