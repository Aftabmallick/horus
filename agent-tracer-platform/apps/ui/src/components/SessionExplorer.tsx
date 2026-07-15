import { useState, useEffect } from 'react';
import { Layers, Clock } from 'lucide-react';

interface Session {
  id: string;
  created_at: string;
}

interface SessionExplorerProps {
  onViewSessionTraces: (id: string) => void;
}

export function SessionExplorer({ onViewSessionTraces }: SessionExplorerProps) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  
  const token = localStorage.getItem('agent_tracer_token');

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await fetch('/api/v1/sessions', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24 }}>
        <h1>Session Explorer</h1>
        <p style={{ color: 'var(--text-secondary)' }}>View and analyze multi-turn agent interactions.</p>
      </header>

      <div className="table-container glass-panel">
        <table>
          <thead>
            <tr>
              <th>Session ID</th>
              <th>Created At</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={3} style={{ textAlign: 'center' }}>Loading sessions...</td></tr>
            ) : sessions.length === 0 ? (
              <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>No sessions found.</td></tr>
            ) : (
              sessions.map(s => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 600, color: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Layers size={16} />
                    {s.id}
                  </td>
                  <td style={{ color: 'var(--text-secondary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Clock size={14} />
                      {new Date(s.created_at).toLocaleString()}
                    </div>
                  </td>
                  <td>
                    <button 
                      onClick={() => onViewSessionTraces(s.id)}
                      style={{ padding: '6px 12px', background: 'transparent', border: '1px solid var(--accent-purple)', color: 'var(--accent-purple)', borderRadius: 6, cursor: 'pointer', fontSize: '0.85rem' }}
                    >
                      View Traces
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
