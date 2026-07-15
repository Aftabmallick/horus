import { useState, useEffect } from 'react';
import { AlertOctagon, Settings, Power, Zap, Activity } from 'lucide-react';

export const ChaosEngineering = () => {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      // In a real implementation, this calls /api/v1/chaos/status
      setTimeout(() => {
        setConfig({
          enabled: false,
          faults: [
            { id: '1', type: 'latency', target: '*', probability: 0.1, delay_ms: 2000 },
            { id: '2', type: 'error', target: 'HTTP', probability: 0.05, exception_type: 'TimeoutError', message: 'Simulated timeout' },
            { id: '3', type: 'token_exhaustion', target: 'LLM', probability: 0.02 }
          ],
          metrics: {
            faults_injected_24h: 42,
            agent_crashes_24h: 3,
            recovery_rate: 92.8
          }
        });
        setLoading(false);
      }, 500);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  const toggleStatus = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
      // In a real app, this calls /api/v1/chaos/enable or disable
      setTimeout(() => {
        setConfig({ ...config, enabled: !config.enabled });
        setIsSaving(false);
      }, 300);
    } catch (e) {
      console.error(e);
      setIsSaving(false);
    }
  };

  if (loading) return <div>Loading Chaos Configuration...</div>;

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Chaos Engineering</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Inject faults safely to test your agents' resilience and recovery.</p>
        </div>
        <button
          onClick={toggleStatus}
          disabled={isSaving}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 24px',
            borderRadius: 8,
            border: 'none',
            fontWeight: 600,
            cursor: 'pointer',
            background: config.enabled ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)',
            color: config.enabled ? '#ef4444' : 'var(--accent-green)',
            transition: 'all 0.2s'
          }}
        >
          <Power size={18} /> {config.enabled ? 'DISABLE CHAOS MONKEY' : 'ENABLE CHAOS MONKEY'}
        </button>
      </header>

      {/* Live Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 24 }}>
        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><Zap size={18} color="var(--accent-purple)" /> Faults Injected (24h)</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'white' }}>{config.metrics.faults_injected_24h}</div>
        </div>

        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><AlertOctagon size={18} color="#ef4444" /> Agent Crashes (24h)</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: '#ef4444' }}>{config.metrics.agent_crashes_24h}</div>
          <div style={{ fontSize: '0.875rem', marginTop: 8, color: 'var(--text-secondary)' }}>Failed to recover</div>
        </div>

        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><Activity size={18} color="var(--accent-green)" /> Recovery Rate</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'var(--accent-green)' }}>{config.metrics.recovery_rate.toFixed(1)}%</div>
          <div style={{ fontSize: '0.875rem', marginTop: 8, color: 'var(--text-secondary)' }}>Successfully handled faults</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 24 }}>
        {/* Fault Configuration */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Settings size={18} /> Active Fault Scenarios</h3>
            <button style={{ padding: '8px 16px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>+ Add Fault</button>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Target</th>
                  <th>Type</th>
                  <th>Probability</th>
                  <th>Configuration</th>
                </tr>
              </thead>
              <tbody>
                {config.faults.map((f: any) => (
                  <tr key={f.id}>
                    <td><span style={{ padding: '2px 8px', background: 'rgba(255,255,255,0.1)', borderRadius: 4, fontFamily: 'monospace' }}>{f.target}</span></td>
                    <td style={{ fontWeight: 600 }}>{f.type.replace('_', ' ').toUpperCase()}</td>
                    <td>{(f.probability * 100).toFixed(1)}%</td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                      {f.type === 'latency' && `Delay: ${f.delay_ms}ms`}
                      {f.type === 'error' && `Throws: ${f.exception_type} ("${f.message}")`}
                      {f.type === 'token_exhaustion' && `Returns max_tokens instantly`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Warning Panel */}
        <div className="glass-panel" style={{ padding: 24, border: '1px solid rgba(239, 68, 68, 0.3)', background: 'linear-gradient(180deg, rgba(239, 68, 68, 0.05) 0%, rgba(0,0,0,0) 100%)' }}>
          <h3 style={{ color: '#ef4444', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><AlertOctagon size={18} /> Production Warning</h3>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 16 }}>
            Enabling the Chaos Monkey in production environments can cause real user requests to fail.
            Ensure your application has appropriate retries, circuit breakers, and fallback logic implemented before enabling.
          </p>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Faults are applied dynamically to any traced execution path matching the target glob patterns.
          </p>
        </div>
      </div>
    </div>
  );
};
