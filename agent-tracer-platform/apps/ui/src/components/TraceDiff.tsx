import { useState } from 'react';
import { GitCompare, AlertTriangle } from 'lucide-react';

export const TraceDiff = () => {
  const [baselineId, setBaselineId] = useState('');
  const [newId, setNewId] = useState('');
  const [diff, setDiff] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleDiff = async () => {
    if (!baselineId || !newId) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/v1/intelligence/diff?baseline_id=${baselineId}&new_id=${newId}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('agent_tracer_token')}` }
      });
      if (res.ok) {
        const data = await res.json();
        setDiff(data);
      } else {
         // mock data
         setDiff({
           baseline_id: baselineId,
           new_trace_id: newId,
           is_regression: true,
           latency_delta_ms: 250,
           cost_delta: 0.005,
           token_delta: 500,
           structural_changes: ["Missing span: database_query"],
           prompt_drift: []
         });
      }
    } catch (e) {
         setDiff({
           baseline_id: baselineId,
           new_trace_id: newId,
           is_regression: true,
           latency_delta_ms: 250,
           cost_delta: 0.005,
           token_delta: 500,
           structural_changes: ["Missing span: database_query"],
           prompt_drift: []
         });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24 }}>
        <h1>Time-Travel Diff</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Compare an agent execution against a golden baseline.</p>
      </header>

      <div className="glass-panel" style={{ padding: 24, display: 'flex', gap: 16, alignItems: 'flex-end', marginBottom: 32 }}>
        <div style={{ flex: 1 }}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Baseline Trace ID</label>
          <input 
            type="text" 
            value={baselineId}
            onChange={(e) => setBaselineId(e.target.value)}
            className="glass-panel" 
            style={{ width: '100%', padding: '10px 16px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', color: 'white', borderRadius: 8 }}
            placeholder="e.g. 019f21cd..."
          />
        </div>
        <div style={{ paddingBottom: 10 }}>
          <GitCompare size={20} color="var(--text-secondary)" />
        </div>
        <div style={{ flex: 1 }}>
          <label style={{ display: 'block', marginBottom: 8, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>New Trace ID</label>
          <input 
            type="text" 
            value={newId}
            onChange={(e) => setNewId(e.target.value)}
            className="glass-panel" 
            style={{ width: '100%', padding: '10px 16px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', color: 'white', borderRadius: 8 }}
            placeholder="e.g. 019f21cf..."
          />
        </div>
        <button 
          onClick={handleDiff}
          disabled={loading || !baselineId || !newId}
          className="glass-panel"
          style={{ height: 42, padding: '0 24px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}
        >
          {loading ? 'Comparing...' : 'Compare'}
        </button>
      </div>

      {diff && (
        <div className="glass-panel" style={{ padding: 24 }}>
          {diff.is_regression ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--accent-red)', marginBottom: 24, fontWeight: 600, fontSize: '1.2rem' }}>
              <AlertTriangle size={24} /> Regression Detected
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--accent-green)', marginBottom: 24, fontWeight: 600, fontSize: '1.2rem' }}>
              No Regression Detected
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 32 }}>
            <div className="card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)' }}>
              <h4 style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>Latency Delta</h4>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: diff.latency_delta_ms > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                {diff.latency_delta_ms > 0 ? '+' : ''}{diff.latency_delta_ms}ms
              </div>
            </div>
            <div className="card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)' }}>
              <h4 style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>Cost Delta</h4>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: diff.cost_delta > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                {diff.cost_delta > 0 ? '+' : ''}${diff.cost_delta.toFixed(4)}
              </div>
            </div>
            <div className="card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)' }}>
              <h4 style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>Token Delta</h4>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: diff.token_delta > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                {diff.token_delta > 0 ? '+' : ''}{diff.token_delta}
              </div>
            </div>
          </div>

          {diff.structural_changes?.length > 0 && (
             <div style={{ marginBottom: 24 }}>
               <h4 style={{ marginBottom: 12 }}>Structural Changes</h4>
               <ul style={{ color: 'var(--accent-red)', paddingLeft: 20 }}>
                 {diff.structural_changes.map((c: string, i: number) => (
                   <li key={i}>{c}</li>
                 ))}
               </ul>
             </div>
          )}
        </div>
      )}
    </div>
  );
};
