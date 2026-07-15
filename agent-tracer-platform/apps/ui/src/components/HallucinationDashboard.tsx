import { useState, useEffect } from 'react';
import { ShieldAlert, TrendingUp, Cpu } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const HallucinationDashboard = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHallucinations();
  }, []);

  const fetchHallucinations = async () => {
    try {
      // In a real implementation, this would call /api/v1/analytics/hallucinations
      setTimeout(() => {
        setData({
          average_score: 0.12,
          critical_flags: 14,
          histogram: [
            { range: '0.0-0.2', count: 1240 },
            { range: '0.2-0.4', count: 320 },
            { range: '0.4-0.6', count: 85 },
            { range: '0.6-0.8', count: 24 },
            { range: '0.8-1.0', count: 14 } // High probability of hallucination
          ],
          top_agents: [
            { agent: 'ResearchAgent', avg_score: 0.45, max_score: 0.92, traces_flagged: 8 },
            { agent: 'WriterAgent', avg_score: 0.22, max_score: 0.65, traces_flagged: 4 },
            { agent: 'SummaryAgent', avg_score: 0.15, max_score: 0.81, traces_flagged: 2 }
          ]
        });
        setLoading(false);
      }, 500);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  if (loading) return <div>Loading Hallucination Data...</div>;
  if (!data) return <div>Failed to load hallucination data.</div>;

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24 }}>
        <h1>Hallucination Dashboard</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Cross-encoder scoring and confidence intervals for agent outputs.</p>
      </header>
      
      {/* Top Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 24, marginBottom: 24 }}>
        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><TrendingUp size={18} /> Global Average Score</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: data.average_score > 0.5 ? '#ef4444' : 'var(--accent-green)' }}>
            {data.average_score.toFixed(2)}
          </div>
          <div style={{ fontSize: '0.875rem', marginTop: 8, color: 'var(--text-secondary)' }}>Scale: 0.0 (Factual) to 1.0 (Hallucinated)</div>
        </div>

        <div className="card glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><ShieldAlert size={18} color="#ef4444" /> Critical Flags (&gt;0.8)</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: '#ef4444' }}>{data.critical_flags}</div>
          <div style={{ fontSize: '0.875rem', marginTop: 8, color: 'var(--text-secondary)' }}>Traces requiring manual review</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Histogram */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16 }}>Score Distribution</h3>
          <div style={{ height: 250, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.histogram} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                <XAxis dataKey="range" stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: '#1e1e1e', borderColor: 'var(--border-color)', borderRadius: '8px' }} />
                <Bar dataKey="count" fill="var(--accent-purple)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Hallucinating Agents */}
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Cpu size={18} /> Top Hallucinating Agents
          </h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Agent Name</th>
                  <th>Avg Score</th>
                  <th>Max Score</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {data.top_agents.map((a: any) => (
                  <tr key={a.agent}>
                    <td style={{ fontWeight: 600 }}>{a.agent}</td>
                    <td style={{ color: a.avg_score > 0.4 ? '#ef4444' : 'white' }}>{a.avg_score.toFixed(2)}</td>
                    <td style={{ color: a.max_score > 0.8 ? '#ef4444' : 'var(--accent-blue)' }}>{a.max_score.toFixed(2)}</td>
                    <td><span style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', padding: '2px 8px', borderRadius: 12, fontSize: '0.8rem' }}>{a.traces_flagged}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
