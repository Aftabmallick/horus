import { useState } from 'react';
import { Cpu } from 'lucide-react';

export const CostSimulator = () => {
  const [model, setModel] = useState('gpt-4o-mini');
  const [volume, setVolume] = useState(100000);

  const costs: Record<string, number> = {
    'gpt-4o': 0.015,
    'gpt-4o-mini': 0.0005,
    'claude-3-5-sonnet': 0.003,
    'claude-3-haiku': 0.00025,
  };

  const currentCost = 0.015 * volume; // Assuming current is gpt-4o
  const simulatedCost = costs[model] * volume;
  const savings = currentCost - simulatedCost;

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 32 }}>
        <h1>Cost Simulator</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Model swap simulation and token budget planning.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div className="card glass-panel">
          <h2 style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8 }}><Cpu size={20} /> Configuration</h2>
          
          <div style={{ marginBottom: 24 }}>
            <label style={{ display: 'block', marginBottom: 8, color: 'var(--text-secondary)' }}>Target Model</label>
            <select 
              value={model} 
              onChange={e => setModel(e.target.value)}
              style={{ width: '100%', padding: 12, borderRadius: 8, background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', color: 'white' }}
            >
              <option value="gpt-4o">GPT-4o (Current Baseline)</option>
              <option value="gpt-4o-mini">GPT-4o Mini</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
              <option value="claude-3-haiku">Claude 3 Haiku</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 8, color: 'var(--text-secondary)' }}>Monthly Trace Volume: {volume.toLocaleString()}</label>
            <input 
              type="range" 
              min="10000" 
              max="1000000" 
              step="10000" 
              value={volume} 
              onChange={e => setVolume(parseInt(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        </div>

        <div className="card glass-panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}>
          <h3 style={{ color: 'var(--text-secondary)', marginBottom: 8 }}>Projected Monthly Savings</h3>
          <div style={{ fontSize: '3.5rem', fontWeight: 700, color: savings >= 0 ? 'var(--accent-green)' : 'var(--accent-red)', marginBottom: 16 }}>
            {savings >= 0 ? '+' : '-'}${Math.abs(savings).toLocaleString()}
          </div>
          <p style={{ color: 'var(--text-secondary)' }}>
            Switching from <strong>GPT-4o</strong> to <strong>{model}</strong> will {savings >= 0 ? 'save' : 'cost'} you an estimated ${Math.abs(savings).toLocaleString()} per month.
          </p>
        </div>
      </div>
    </div>
  );
};
