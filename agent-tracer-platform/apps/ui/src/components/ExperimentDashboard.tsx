import { useState, useEffect } from 'react';
import { Play, Activity } from 'lucide-react';

export const ExperimentDashboard = () => {
  const [experiments, setExperiments] = useState<any[]>([]);
  const [newExpName, setNewExpName] = useState('');
  const [promptName, setPromptName] = useState('');
  const [datasetId, setDatasetId] = useState('');
  
  const [selectedExp, setSelectedExp] = useState<string | null>(null);
  const [results, setResults] = useState<any[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const token = localStorage.getItem('agent_tracer_token');

  useEffect(() => {
    fetchExperiments();
  }, []);

  const fetchExperiments = async () => {
    try {
      const res = await fetch('/api/v1/experiments', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setExperiments(data.experiments || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const runExperiment = async () => {
    if (!newExpName || !promptName || !datasetId) return;
    setIsRunning(true);
    try {
      const res = await fetch('/api/v1/experiments/run', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: newExpName,
          dataset_id: datasetId,
          prompt_id: promptName
        })
      });
      if (res.ok) {
        fetchExperiments();
        setNewExpName('');
      }
    } catch (e) {
      console.error(e);
    }
    setIsRunning(false);
  };

  const fetchResults = async (expId: string) => {
    setSelectedExp(expId);
    try {
      const res = await fetch(`/api/v1/experiments/${expId}/results`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const aggregateResults = () => {
    if (results.length === 0) return null;
    const successes = results.filter(r => r.success).length;
    const avgLatency = results.reduce((sum, r) => sum + r.latency, 0) / results.length;
    const totalCost = results.reduce((sum, r) => sum + r.cost, 0);
    return {
      successRate: (successes / results.length) * 100,
      avgLatency,
      totalCost,
      count: results.length
    };
  };

  const stats = aggregateResults();

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 32 }}>
        <h1>Evaluation Engine</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Run batch evaluations of Prompts against Datasets.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Create Run Form */}
          <div className="glass-panel" style={{ padding: 24 }}>
            <h3>New Evaluation Run</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
              <input 
                type="text" 
                placeholder="Experiment Name (e.g. gpt-4o vs gpt-4)" 
                value={newExpName}
                onChange={e => setNewExpName(e.target.value)}
                style={{ padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }}
              />
              <input 
                type="text" 
                placeholder="Dataset ID" 
                value={datasetId}
                onChange={e => setDatasetId(e.target.value)}
                style={{ padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }}
              />
              <input 
                type="text" 
                placeholder="Prompt Name (ID)" 
                value={promptName}
                onChange={e => setPromptName(e.target.value)}
                style={{ padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }}
              />
              
              <button 
                onClick={runExperiment}
                disabled={isRunning}
                style={{ padding: '12px', background: 'var(--accent-blue)', color: 'white', border: 'none', borderRadius: 8, cursor: isRunning ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
              >
                <Play size={18} /> {isRunning ? 'Queuing Run...' : 'Start Evaluation'}
              </button>
            </div>
          </div>

          <div className="glass-panel" style={{ padding: 24 }}>
            <h3>Experiment History</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 16 }}>
              {experiments.length === 0 && <span style={{ color: 'var(--text-secondary)' }}>No runs found.</span>}
              {experiments.map(exp => (
                <div 
                  key={exp.id} 
                  onClick={() => fetchResults(exp.id)}
                  style={{ 
                    padding: 12, 
                    borderRadius: 8, 
                    border: '1px solid',
                    borderColor: selectedExp === exp.id ? 'var(--accent-blue)' : 'var(--border-color)',
                    background: selectedExp === exp.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                    cursor: 'pointer'
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{exp.name}</div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                    {new Date(exp.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Results Panel */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3>Evaluation Results</h3>
          
          {selectedExp && stats ? (
            <div style={{ marginTop: 24 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: 16, borderRadius: 8, border: '1px solid var(--border-color)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 4 }}>Success Rate</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600, color: stats.successRate >= 80 ? 'var(--accent-green)' : (stats.successRate < 50 ? '#f87171' : 'var(--accent-orange)') }}>
                    {stats.successRate.toFixed(1)}%
                  </div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: 16, borderRadius: 8, border: '1px solid var(--border-color)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 4 }}>Avg Latency</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{stats.avgLatency.toFixed(2)}s</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: 16, borderRadius: 8, border: '1px solid var(--border-color)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 4 }}>Total Cost</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>${stats.totalCost.toFixed(4)}</div>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: 16, borderRadius: 8, border: '1px solid var(--border-color)' }}>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: 4 }}>Data Points</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{stats.count}</div>
                </div>
              </div>

              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Latency</th>
                      <th>Cost</th>
                      <th>Output Preview</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map(r => (
                      <tr key={r.id}>
                        <td>
                          {r.success ? <span className="badge badge-ok">Pass</span> : <span className="badge badge-error">Fail</span>}
                        </td>
                        <td>{r.latency.toFixed(2)}s</td>
                        <td>${r.cost.toFixed(5)}</td>
                        <td style={{ color: 'var(--text-secondary)', maxWidth: 300, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {JSON.stringify(r.output)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: 60, textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Activity size={48} style={{ opacity: 0.2, marginBottom: 16 }} />
              <p>Select an experiment to view its results, or start a new run.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
