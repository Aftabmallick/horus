import { useState, useEffect } from 'react';
import { MessageSquare, Filter, Tag, CheckCircle, Clock } from 'lucide-react';

export const TeamAnnotations = () => {
  const [annotations, setAnnotations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // all, open, resolved
  const [tagFilter, setTagFilter] = useState('all');

  useEffect(() => {
    fetchAnnotations();
  }, []);

  const fetchAnnotations = async () => {
    try {
      // In a real implementation, this would call /api/v1/annotations
      setTimeout(() => {
        setAnnotations([
          {
            id: '1',
            trace_id: 't_abc123',
            author: 'alice@example.com',
            content: 'Agent hallucinated the API endpoint URL here.',
            status: 'open',
            tag: 'hallucination',
            timestamp: '10 mins ago',
            replies: [
              { id: '1_1', author: 'bob@example.com', content: 'Good catch. I think it is because the prompt missed context.', timestamp: '5 mins ago' }
            ]
          },
          {
            id: '2',
            trace_id: 't_def456',
            author: 'charlie@example.com',
            content: 'Cost spike observed due to recursive loop.',
            status: 'resolved',
            tag: 'cost',
            timestamp: '2 hours ago',
            replies: []
          },
          {
            id: '3',
            trace_id: 't_ghi789',
            author: 'alice@example.com',
            content: 'SLA breached. Need to optimize the SQL query in the tool.',
            status: 'open',
            tag: 'performance',
            timestamp: '1 day ago',
            replies: []
          }
        ]);
        setLoading(false);
      }, 500);
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  if (loading) return <div>Loading Annotations...</div>;

  const filteredAnnotations = annotations.filter(a => {
    if (filter !== 'all' && a.status !== filter) return false;
    if (tagFilter !== 'all' && a.tag !== tagFilter) return false;
    return true;
  });

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Team Annotations</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Collaborate on traces, flag issues, and discuss fixes.</p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(0,0,0,0.3)', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color)' }}>
            <Filter size={16} color="var(--text-secondary)" />
            <select value={filter} onChange={e => setFilter(e.target.value)} style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none' }}>
              <option value="all">All Status</option>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(0,0,0,0.3)', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color)' }}>
            <Tag size={16} color="var(--text-secondary)" />
            <select value={tagFilter} onChange={e => setTagFilter(e.target.value)} style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none' }}>
              <option value="all">All Tags</option>
              <option value="hallucination">Hallucination</option>
              <option value="cost">Cost</option>
              <option value="performance">Performance</option>
            </select>
          </div>
        </div>
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {filteredAnnotations.map(a => (
          <div key={a.id} className="card glass-panel" style={{ padding: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--accent-purple)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                  {a.author.charAt(0).toUpperCase()}
                </div>
                <div>
                  <div style={{ fontWeight: 600 }}>{a.author}</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Trace: <span style={{ fontFamily: 'monospace', color: 'var(--accent-blue)' }}>{a.trace_id}</span></div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={14} /> {a.timestamp}</span>
                <span style={{ padding: '4px 12px', borderRadius: 16, fontSize: '0.8rem', fontWeight: 600, background: a.status === 'open' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)', color: a.status === 'open' ? '#ef4444' : 'var(--accent-green)', display: 'flex', alignItems: 'center', gap: 4 }}>
                  {a.status === 'resolved' ? <CheckCircle size={14} /> : <MessageSquare size={14} />} {a.status.toUpperCase()}
                </span>
                <span style={{ padding: '4px 12px', borderRadius: 16, fontSize: '0.8rem', background: 'rgba(255,255,255,0.1)', color: 'white' }}>
                  #{a.tag}
                </span>
              </div>
            </div>
            
            <p style={{ margin: '16px 0', fontSize: '1.05rem', lineHeight: 1.5 }}>{a.content}</p>
            
            {/* Replies */}
            {a.replies.length > 0 && (
              <div style={{ marginTop: 16, paddingLeft: 16, borderLeft: '2px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {a.replies.map((reply: any) => (
                  <div key={reply.id} style={{ display: 'flex', gap: 12 }}>
                    <div style={{ width: 24, height: 24, borderRadius: '50%', background: 'rgba(255,255,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 'bold' }}>
                      {reply.author.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontSize: '0.9rem' }}><strong style={{ color: 'var(--text-secondary)' }}>{reply.author}</strong> <span style={{ fontSize: '0.8rem', color: 'rgba(255,255,255,0.3)', marginLeft: 8 }}>{reply.timestamp}</span></div>
                      <div style={{ fontSize: '0.95rem', marginTop: 4 }}>{reply.content}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            <div style={{ marginTop: 24, display: 'flex', gap: 12 }}>
              <input type="text" placeholder="Reply to this thread..." style={{ flex: 1, padding: '10px 16px', borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }} />
              <button style={{ padding: '10px 20px', background: 'white', color: 'black', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>Reply</button>
              {a.status === 'open' && (
                <button style={{ padding: '10px 20px', background: 'transparent', color: 'var(--accent-green)', border: '1px solid var(--accent-green)', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>Mark Resolved</button>
              )}
            </div>
          </div>
        ))}
        {filteredAnnotations.length === 0 && (
          <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-secondary)' }}>No annotations found matching the selected filters.</div>
        )}
      </div>
    </div>
  );
};
