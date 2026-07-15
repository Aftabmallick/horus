import { useState, FormEvent } from 'react';
import { Search, Zap, Layers, AlertCircle, Bot } from 'lucide-react';

export const SemanticSearch = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [clusters, setClusters] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [clustering, setClustering] = useState(false);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query) return;
    setSearching(true);
    
    try {
      const token = localStorage.getItem('agent_tracer_token');
      const res = await fetch(`/api/v1/search/semantic?query=${encodeURIComponent(query)}&limit=10`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const handleCluster = async () => {
    if (!query) return;
    setClustering(true);
    setClusters([]);
    try {
      const token = localStorage.getItem('agent_tracer_token');
      // POST to the new cluster endpoint with our query
      const res = await fetch(`/api/v1/search/cluster`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query, n_clusters: 3 })
      });
      if (res.ok) {
        const data = await res.json();
        setClusters(data.clusters || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setClustering(false);
    }
  };

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 40, textAlign: 'center' }}>
        <h1 style={{ fontSize: '3rem', background: 'linear-gradient(135deg, #fff, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Semantic Search</h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.2rem' }}>Use natural language to find specific trace patterns or failures.</p>
      </header>

      <form onSubmit={handleSearch} style={{ maxWidth: 600, margin: '0 auto', position: 'relative' }}>
        <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', padding: '16px 24px', borderRadius: 32, gap: 16 }}>
          <Search size={24} color="var(--accent-purple)" />
          <input 
            autoFocus
            type="text" 
            placeholder="e.g. 'Show me traces where the agent hallucinated a price'" 
            value={query}
            onChange={e => setQuery(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 'none', color: 'white', outline: 'none', fontSize: '1.1rem' }}
          />
          <button type="submit" disabled={searching} style={{ background: 'var(--accent-purple)', border: 'none', borderRadius: 20, padding: '8px 16px', color: 'white', fontWeight: 600, cursor: 'pointer' }}>
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 16 }}>
          <button 
            type="button"
            onClick={handleCluster}
            disabled={clustering || !query}
            className="glass-panel" 
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer', borderRadius: 20 }}
          >
            <Layers size={16} />
            {clustering ? 'Running K-Means...' : 'Run Cluster Analysis'}
          </button>
        </div>
      </form>

      {clusters.length > 0 && (
        <div style={{ maxWidth: 800, margin: '40px auto 0 auto' }}>
          <h3 style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}><Layers size={20} color="var(--accent-purple)" /> Semantic Clusters</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            {clusters.map(c => (
              <div key={c.cluster_id} className="glass-panel" style={{ padding: 16, borderTop: '2px solid var(--accent-purple)' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 8 }}>Cluster {c.cluster_id} <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 400 }}>({c.size} traces)</span></div>
                
                {c.common_agent && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                    <Bot size={14} color="var(--accent-blue)" /> {c.common_agent}
                  </div>
                )}
                {c.error_count > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', color: 'var(--accent-red)', marginBottom: 8 }}>
                    <AlertCircle size={14} /> {c.error_count} Errors ({(c.error_rate * 100).toFixed(1)}%)
                  </div>
                )}
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-color)' }}>
                  <strong>Representative:</strong> <span style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>{c.representative_trace_id?.slice(0,8)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div style={{ maxWidth: 800, margin: '40px auto' }}>
          <h3 style={{ marginBottom: 16 }}>Results ({results.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {results.map((r, i) => (
              <div key={i} className="card glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>{r.id}</span>
                    <span className="badge badge-ok">{r.agent}</span>
                  </div>
                  <p style={{ color: 'var(--text-secondary)' }}>"{r.excerpt}"</p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--accent-green)' }}>
                    <Zap size={16} />
                    <span style={{ fontWeight: 600 }}>{(r.match * 100).toFixed(0)}% Match</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
