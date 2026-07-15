import { useEffect, useState } from 'react';
import { Activity, Server, ShieldAlert, ShieldCheck } from 'lucide-react';

export function LiveFirehose() {
  const [events, setEvents] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:3000/api/v1/stream/live');
    let buffer: any[] = [];
    let flushInterval: any;
    
    ws.onopen = () => {
      setConnected(true);
      flushInterval = setInterval(() => {
        if (buffer.length > 0) {
          setEvents(prev => [...buffer, ...prev].slice(0, 100));
          buffer = [];
        }
      }, 500); // Flush buffer every 500ms
    };
    
    ws.onclose = () => {
      setConnected(false);
      clearInterval(flushInterval);
    };
    
    ws.onmessage = (event) => {
      try {
        buffer.push(JSON.parse(event.data));
      } catch (e) {
        // Ignore parsing errors on high-throughput
      }
    };

    return () => {
      ws.close();
      clearInterval(flushInterval);
    };
  }, []);

  return (
    <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
          <Activity size={24} color="#10b981" /> Live Telemetry Firehose
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '10px', height: '10px', borderRadius: '50%',
            backgroundColor: connected ? '#10b981' : '#ef4444',
            boxShadow: connected ? '0 0 10px #10b981' : 'none'
          }} />
          <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            {connected ? 'Streaming' : 'Disconnected'}
          </span>
        </div>
      </div>
      
      {/* System Health Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <Server size={14} /> SQLite (Primary)
            </div>
            <span className="badge badge-ok" style={{ display: 'flex', alignItems: 'center', gap: 4 }}><ShieldCheck size={12} /> UP</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>Connected</div>
        </div>
        <div style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <Server size={14} /> ClickHouse
            </div>
            <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent-green)', border: '1px solid rgba(16, 185, 129, 0.2)', display: 'flex', alignItems: 'center', gap: 4 }}><ShieldCheck size={12} /> CLOSED</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>Connected</div>
        </div>
        <div style={{ background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: 8, padding: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <Server size={14} /> Redis
            </div>
            <span className="badge badge-error" style={{ display: 'flex', alignItems: 'center', gap: 4 }}><ShieldAlert size={12} /> OPEN</span>
          </div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--accent-red)' }}>Circuit Broken</div>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {events.length === 0 && (
          <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>Waiting for traces...</div>
        )}
        {events.map((e, idx) => (
          <div key={idx} className="animate-in" style={{
            padding: '12px',
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '6px',
            borderLeft: `4px solid ${e.status === 'OK' ? '#10b981' : '#ef4444'}`,
            display: 'flex',
            justifyContent: 'space-between'
          }}>
            <span style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>{e.trace_id}</span>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              {new Date(e.timestamp).toLocaleTimeString()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
