import { useState, useEffect } from 'react';
import { Activity, AlertTriangle, Clock } from 'lucide-react';

export const SLADashboard = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSLA();
  }, []);

  const fetchSLA = async () => {
    try {
      // Stubbing the API call since the backend route might not exist yet
      // In a real implementation, this would call /api/v1/analytics/sla
      setTimeout(() => {
        setData({
          compliance_rate: 98.5,
          p95_latency: 1.2,
          p99_latency: 2.8,
          breaches: [
            { id: 't_101', agent: 'ResearchAgent', latency: 4.5, limit: 3.0, time: '10 mins ago' },
            { id: 't_205', agent: 'WriterAgent', latency: 3.2, limit: 2.5, time: '1 hr ago' },
            { id: 't_344', agent: 'SupervisorAgent', latency: 5.1, limit: 4.0, time: '2 hrs ago' }
          ]
        });
        setLoading(false);
      }, 500);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  if (loading) return <div>Loading SLA Data...</div>;
  if (!data) return <div>Failed to load SLA data.</div>;

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24 }}>
        <h1>SLA Compliance Dashboard</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Monitor Service Level Agreements, P95/P99 latencies, and breaches.</p>
      </header>
      
      {/* Top Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 24 }}>
        <div className="card glass-panel" style={{ padding: 24, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <h3 style={{ marginBottom: 16, color: 'var(--text-secondary)' }}>Compliance Rate</h3>
          <div style={{ fontSize: '3rem', fontWeight: 800, color: data.compliance_rate >= 99 ? 'var(--accent-green)' : (data.compliance_rate >= 95 ? 'var(--accent-blue)' : '#ef4444') }}>
            {data.compliance_rate.toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.875rem', marginTop: 8, color: 'var(--text-secondary)' }}>Target: 99.0%</div>
        </div>

        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><Activity size={18} /> P95 Latency</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'white' }}>{data.p95_latency.toFixed(2)}s</div>
        </div>

        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><Clock size={18} /> P99 Latency</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'white' }}>{data.p99_latency.toFixed(2)}s</div>
        </div>
      </div>

      {/* Breach Table */}
      <div className="glass-panel" style={{ padding: 24 }}>
        <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={18} color="#ef4444" /> Recent SLA Breaches
        </h3>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Trace ID</th>
                <th>Agent</th>
                <th>Actual Latency</th>
                <th>SLA Limit</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {data.breaches.map((b: any) => (
                <tr key={b.id}>
                  <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>{b.id}</td>
                  <td>{b.agent}</td>
                  <td style={{ color: '#ef4444', fontWeight: 600 }}>{b.latency.toFixed(2)}s</td>
                  <td>{b.limit.toFixed(2)}s</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{b.time}</td>
                </tr>
              ))}
              {data.breaches.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>No recent breaches. System is healthy!</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
