import { useState, useEffect } from 'react'
import { Activity, DollarSign, Search, GitCompare, Settings, Key, Network, FlaskConical, Cpu, Leaf, MessageSquare, Database, Layers, Shield, Clock, Users, BarChart2 } from 'lucide-react'
import { TraceDetail } from './components/TraceDetail'
import { TraceDiff } from './components/TraceDiff'
import { Analytics } from './components/Analytics'
import { SemanticSearch } from './components/SemanticSearch'
import { ExperimentDashboard } from './components/ExperimentDashboard'
import { CostSimulator } from './components/CostSimulator'
import { Sustainability } from './components/Sustainability'
import { DependencyGraph } from './components/DependencyGraph'
import { Auth } from './components/Auth'
import { LiveFirehose } from './components/LiveFirehose'
import { PromptManager } from './components/PromptManager'
import { DatasetManager } from './components/DatasetManager'
import { SessionExplorer } from './components/SessionExplorer'
import { SLADashboard } from './components/SLADashboard'
import { HallucinationDashboard } from './components/HallucinationDashboard'
import { TeamAnnotations } from './components/TeamAnnotations'
import { ChaosEngineering } from './components/ChaosEngineering'

// --- Types ---
interface Trace {
  trace_id: string;
  agent_name: string;
  status: string;
  duration_ms: number;
  total_tokens: number;
  total_cost: number;
  started_at: string;
  error_count: number;
}

// --- Components ---
const Badge = ({ status }: { status: string }) => {
  const cn = status === 'OK' || status === 'COMPLETED' ? 'badge-ok' :
    status === 'ERROR' ? 'badge-error' : 'badge-running';
  return <span className={`badge ${cn}`}>{status}</span>
}

const formatCost = (cost: number) => {
  if (cost === 0) return '$0.00'
  if (cost < 0.0001) return `< $0.0001`
  return `$${cost.toFixed(4)}`
}

// --- Main App ---
function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('agent_tracer_token'))
  const [activeTab, setActiveTab] = useState('traces')
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null)
  const [sessionFilter, setSessionFilter] = useState<string | null>(null)
  const [traces, setTraces] = useState<Trace[]>([])
  const [loading, setLoading] = useState(true)
  const [dashStats, setDashStats] = useState({ total_traces: 0, avg_latency_ms: 0, total_cost: 0 })

  useEffect(() => {
    if (token) {
      fetchTraces()
      fetchDashboard()
    }
  }, [token, sessionFilter])

  const fetchDashboard = async () => {
    try {
      const res = await fetch('/api/v1/analytics/dashboard', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setDashStats({
          total_traces: data.total_traces ?? 0,
          avg_latency_ms: data.avg_latency_ms ?? 0,
          total_cost: data.total_cost ?? 0,
        })
      }
    } catch (e) {
      console.error('Failed to fetch dashboard stats', e)
    }
  }

  const fetchTraces = async () => {
    try {
      setLoading(true);
      const url = sessionFilter ? `/api/v1/traces?limit=20&session_id=${sessionFilter}` : '/api/v1/traces?limit=20';
      const res = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setTraces(data.traces)
      } else {
        setTraces([]);
      }
    } catch (e) {
      console.error("Failed to fetch traces", e);
      setTraces([]);
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('agent_tracer_token')
    setToken(null)
  }

  if (!token) {
    return <Auth onLogin={setToken} />
  }

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">Agent Tracer +</div>
        </div>
        <nav className="sidebar-nav">
          <a className={`nav-item ${activeTab === 'traces' ? 'active' : ''}`} onClick={() => { setActiveTab('traces'); setSelectedTraceId(null); }}>
            <Activity size={20} />
            Trace Explorer
          </a>
          <a className={`nav-item ${activeTab === 'sessions' ? 'active' : ''}`} onClick={() => { setActiveTab('sessions'); setSelectedTraceId(null); }}>
            <Layers size={20} />
            Session Explorer
          </a>
          <a className={`nav-item ${activeTab === 'prompts' ? 'active' : ''}`} onClick={() => { setActiveTab('prompts'); setSelectedTraceId(null); }}>
            <MessageSquare size={20} />
            Prompt Manager
          </a>
          <a className={`nav-item ${activeTab === 'datasets' ? 'active' : ''}`} onClick={() => { setActiveTab('datasets'); setSelectedTraceId(null); }}>
            <Database size={20} />
            Datasets & Evals
          </a>
          <a className={`nav-item ${activeTab === 'analytics' ? 'active' : ''}`} onClick={() => { setActiveTab('analytics'); setSelectedTraceId(null); }}>
            <BarChart2 size={20} />
            Analytics
          </a>
          <a className={`nav-item ${activeTab === 'sla' ? 'active' : ''}`} onClick={() => { setActiveTab('sla'); setSelectedTraceId(null); }}>
            <Activity size={20} />
            SLA Dashboard
          </a>
          <a className={`nav-item ${activeTab === 'hallucination' ? 'active' : ''}`} onClick={() => { setActiveTab('hallucination'); setSelectedTraceId(null); }}>
            <Shield size={20} />
            Hallucination
          </a>
          <a className={`nav-item ${activeTab === 'annotations' ? 'active' : ''}`} onClick={() => { setActiveTab('annotations'); setSelectedTraceId(null); }}>
            <MessageSquare size={20} />
            Annotations
          </a>
          <a className={`nav-item ${activeTab === 'chaos' ? 'active' : ''}`} onClick={() => { setActiveTab('chaos'); setSelectedTraceId(null); }}>
            <Activity size={20} />
            Chaos Monkey
          </a>
          <a className={`nav-item ${activeTab === 'search' ? 'active' : ''}`} onClick={() => { setActiveTab('search'); setSelectedTraceId(null); }}>
            <Search size={20} />
            Semantic Search
          </a>
          <a className={`nav-item ${activeTab === 'firehose' ? 'active' : ''}`} onClick={() => { setActiveTab('firehose'); setSelectedTraceId(null); }}>
            <Activity size={20} color="#10b981" />
            Live Firehose
          </a>
          <a className={`nav-item ${activeTab === 'graph' ? 'active' : ''}`} onClick={() => { setActiveTab('graph'); setSelectedTraceId(null); }}>
            <Network size={20} />
            Topology Graph
          </a>
          <a className={`nav-item ${activeTab === 'experiments' ? 'active' : ''}`} onClick={() => { setActiveTab('experiments'); setSelectedTraceId(null); }}>
            <FlaskConical size={20} />
            A/B Testing
          </a>
          <a className={`nav-item ${activeTab === 'simulator' ? 'active' : ''}`} onClick={() => { setActiveTab('simulator'); setSelectedTraceId(null); }}>
            <Cpu size={20} />
            Cost Simulator
          </a>
          <a className={`nav-item ${activeTab === 'sustainability' ? 'active' : ''}`} onClick={() => { setActiveTab('sustainability'); setSelectedTraceId(null); }}>
            <Leaf size={20} />
            Sustainability
          </a>
          <a className={`nav-item ${activeTab === 'analytics' ? 'active' : ''}`} onClick={() => { setActiveTab('analytics'); setSelectedTraceId(null); }}>
            <DollarSign size={20} />
            Cost Analytics
          </a>
          <a className={`nav-item ${activeTab === 'diff' ? 'active' : ''}`} onClick={() => { setActiveTab('diff'); setSelectedTraceId(null); }}>
            <GitCompare size={20} />
            Time-Travel Diff
          </a>
          <a className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => { setActiveTab('settings'); setSelectedTraceId(null); }}>
            <Settings size={20} />
            Org Settings
          </a>
        </nav>
        <div style={{ padding: 24, borderTop: '1px solid var(--border-color)' }}>
          <button onClick={handleLogout} style={{ width: '100%', padding: '10px', background: 'transparent', border: '1px solid var(--border-color)', borderRadius: 8, color: 'var(--text-secondary)', cursor: 'pointer' }}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {selectedTraceId ? (
          <TraceDetail traceId={selectedTraceId} onBack={() => setSelectedTraceId(null)} />
        ) : (
          <>
            {activeTab === 'traces' && (
              <div className="animate-in">
                <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
                  <div>
                    <h1>Trace Explorer</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>View, debug, and diagnose all agent executions.</p>
                    {sessionFilter && (
                      <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Filtered by Session: <strong style={{ color: 'var(--accent-purple)' }}>{sessionFilter}</strong></span>
                        <button onClick={() => setSessionFilter(null)} style={{ background: 'transparent', border: '1px solid var(--border-color)', color: 'white', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>Clear Filter</button>
                      </div>
                    )}
                  </div>
                  <div className="glass-panel" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Search size={18} color="var(--text-secondary)" />
                    <input
                      type="text"
                      placeholder="Search agent name..."
                      style={{ background: 'transparent', border: 'none', color: 'white', outline: 'none' }}
                    />
                  </div>
                </header>

                {/* Quick Stats */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 32 }}>
                  <div className="card glass-panel">
                    <h3>Total Traces (24h)</h3>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-purple)' }}>{loading ? '-' : dashStats.total_traces.toLocaleString()}</div>
                  </div>
                  <div className="card glass-panel">
                    <h3>Avg Latency</h3>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-blue)' }}>{loading ? '-' : `${(dashStats.avg_latency_ms / 1000).toFixed(2)}s`}</div>
                  </div>
                  <div className="card glass-panel">
                    <h3>Total Cost (24h)</h3>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--accent-green)' }}>{loading ? '-' : `$${dashStats.total_cost.toFixed(2)}`}</div>
                  </div>
                </div>

                {/* Table */}
                <div className="table-container glass-panel">
                  <table>
                    <thead>
                      <tr>
                        <th>Trace ID</th>
                        <th>Agent</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Tokens</th>
                        <th>Cost</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {loading ? (
                        <tr><td colSpan={7} style={{ textAlign: 'center' }}>Loading...</td></tr>
                      ) : (
                        traces.map(t => (
                          <tr key={t.trace_id} onClick={() => setSelectedTraceId(t.trace_id)}>
                            <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>{t.trace_id.slice(0, 8)}</td>
                            <td style={{ fontWeight: 500 }}>{t.agent_name}</td>
                            <td><Badge status={t.status} /></td>
                            <td>{(t.duration_ms / 1000).toFixed(2)}s</td>
                            <td>{t.total_tokens.toLocaleString()}</td>
                            <td style={{ color: 'var(--accent-green)' }}>{formatCost(t.total_cost)}</td>
                            <td style={{ color: 'var(--text-secondary)' }}>{new Date(t.started_at).toLocaleTimeString()}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeTab === 'firehose' && <LiveFirehose />}
            {activeTab === 'sessions' && <SessionExplorer onViewSessionTraces={(id) => { setSessionFilter(id); setActiveTab('traces'); }} />}
            {activeTab === 'prompts' && <PromptManager />}
            {activeTab === 'datasets' && <DatasetManager />}
            {activeTab === 'analytics' && <Analytics />}
            {activeTab === 'sla' && <SLADashboard />}
            {activeTab === 'hallucination' && <HallucinationDashboard />}
            {activeTab === 'annotations' && <TeamAnnotations />}
            {activeTab === 'chaos' && <ChaosEngineering />}
            {activeTab === 'search' && <SemanticSearch />}
            {activeTab === 'graph' && <DependencyGraph />}
            {activeTab === 'experiments' && <ExperimentDashboard />}
            {activeTab === 'simulator' && <CostSimulator />}
            {activeTab === 'sustainability' && <Sustainability />}
            {activeTab === 'diff' && <TraceDiff />}
            {activeTab === 'settings' && (
              <div className="animate-in">
                <header style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h1>Organization Settings</h1>
                    <p style={{ color: 'var(--text-secondary)' }}>Manage your API keys, security, and project configuration.</p>
                  </div>
                  <div className="glass-panel" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(139, 92, 246, 0.1)', borderColor: 'var(--accent-purple)' }}>
                    <Users size={18} color="var(--accent-purple)" />
                    <span style={{ fontSize: '0.875rem', color: 'white' }}>Current Role: <strong>Admin</strong></span>
                  </div>
                </header>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
                  {/* API Keys Panel */}
                  <div className="glass-panel" style={{ padding: 24 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                      <Key size={24} color="var(--accent-purple)" />
                      <h2 style={{ margin: 0 }}>API Keys</h2>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>Use these keys to configure the `agent-tracer-plus` SDK.</p>

                    <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
                      <label style={{ display: 'block', marginBottom: 8, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Public Key (X-Public-Key)</label>
                      <div style={{ fontFamily: 'monospace', color: 'white' }}>pk_default</div>
                    </div>

                    <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 16 }}>
                      <label style={{ display: 'block', marginBottom: 8, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Secret Key (Authorization Bearer)</label>
                      <div style={{ fontFamily: 'monospace', color: 'var(--accent-green)' }}>sk_default</div>
                    </div>

                    <button className="glass-panel" style={{ marginTop: 24, padding: '10px 20px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 600 }}>
                      Generate New Key Pair
                    </button>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                    {/* Data Retention (TTL) Panel */}
                    <div className="glass-panel" style={{ padding: 24 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                        <Clock size={24} color="var(--accent-blue)" />
                        <h2 style={{ margin: 0 }}>Data Retention (TTL)</h2>
                      </div>
                      <p style={{ color: 'var(--text-secondary)', marginBottom: 24, fontSize: '0.9rem' }}>Configure how long traces are kept before being automatically deleted by the background worker.</p>
                      
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 4 }}>Default</div>
                          <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'white' }}>90 <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 400 }}>days</span></div>
                        </div>
                        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 4 }}>Errors</div>
                          <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--accent-red)' }}>365 <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 400 }}>days</span></div>
                        </div>
                        <div style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', borderRadius: 8, padding: 12, textAlign: 'center' }}>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 4 }}>Debug</div>
                          <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--accent-orange)' }}>7 <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 400 }}>days</span></div>
                        </div>
                      </div>
                    </div>

                    {/* Encryption & Security Panel */}
                    <div className="glass-panel" style={{ padding: 24 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <Shield size={24} color="var(--accent-green)" />
                          <h2 style={{ margin: 0 }}>Encryption (KMS)</h2>
                        </div>
                        <span className="badge badge-ok">Active</span>
                      </div>
                      <p style={{ color: 'var(--text-secondary)', marginBottom: 16, fontSize: '0.9rem' }}>Payloads are encrypted at rest using AES-256-GCM via the KeyManager.</p>
                      
                      <div style={{ background: 'rgba(16, 185, 129, 0.05)', border: '1px solid rgba(16, 185, 129, 0.2)', borderRadius: 8, padding: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Current Key Provider</div>
                          <div style={{ fontWeight: 600, color: 'var(--accent-green)' }}>Environment Variable (Local)</div>
                        </div>
                        <button style={{ background: 'transparent', border: '1px solid var(--accent-green)', color: 'var(--accent-green)', padding: '6px 12px', borderRadius: 4, cursor: 'pointer', fontSize: '0.85rem' }}>Rotate Key</button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
