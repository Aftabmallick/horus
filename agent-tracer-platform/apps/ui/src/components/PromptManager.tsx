import { useState } from 'react';
import { Play, Variable, GitBranch, GitCommit, SplitSquareHorizontal } from 'lucide-react';

interface Prompt {
  id: string;
  name: string;
  branch: string;
  version: number;
  parent_id: string | null;
  content: Record<string, any> | string;
  created_at: string;
}

export function PromptManager() {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [newPromptName, setNewPromptName] = useState('');
  const [newPromptContent, setNewPromptContent] = useState('');
  const [branchName, setBranchName] = useState('main');
  const [maxTokens, setMaxTokens] = useState<number | ''>('');
  const [maxCost, setMaxCost] = useState<number | ''>('');

  
  // A/B Testing Playground State
  const [selectedPromptA, setSelectedPromptA] = useState<Prompt | null>(null);
  const [selectedPromptB, setSelectedPromptB] = useState<Prompt | null>(null);
  const [variables, setVariables] = useState<string>('{\n  "topic": "AI"\n}');
  const [resultA, setResultA] = useState<any>(null);
  const [resultB, setResultB] = useState<any>(null);
  const [isRunning, setIsRunning] = useState(false);

  const token = localStorage.getItem('agent_tracer_token');

  const fetchPrompt = async (name: string) => {
    try {
      // In a real app, this would fetch all branches and versions
      const res = await fetch(`/api/v1/prompts/${name}?branch=${branchName}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setPrompts([data]); // Simplified for MVP
      }
    } catch (e) {
      console.error(e);
    }
  };

  const createPrompt = async () => {
    if (!newPromptName || !newPromptContent) return;
    try {
      let contentJson = {};
      try { contentJson = JSON.parse(newPromptContent); } catch (e) { contentJson = { text: newPromptContent }; }

      const parentId = prompts.length > 0 ? prompts[0].id : null;

      const res = await fetch('/api/v1/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: newPromptName,
          branch: branchName,
          version: (prompts[0]?.version || 0) + 1,
          parent_id: parentId,
          content: contentJson,
          metadata: {
            budget: {
              max_tokens: maxTokens || null,
              max_cost: maxCost || null
            }
          }
        })
      });
      if (res.ok) {
        fetchPrompt(newPromptName);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const runPlayground = async () => {
    if (!selectedPromptA && !selectedPromptB) return;
    setIsRunning(true);
    let vars = {};
    try { vars = JSON.parse(variables); } catch (e) { console.warn("Invalid variables"); }

    const runSingle = async (prompt: Prompt | null) => {
      if (!prompt) return null;
      const promptText = typeof prompt.content === 'object' ? (prompt.content as any).text : prompt.content;
      try {
        const res = await fetch('/api/v1/prompts/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ model: 'gpt-4o-mini', prompt: promptText, variables: vars })
        });
        return await res.json();
      } catch (e) {
        return { error: String(e) };
      }
    };

    const [resA, resB] = await Promise.all([runSingle(selectedPromptA), runSingle(selectedPromptB)]);
    setResultA(resA);
    setResultB(resB);
    setIsRunning(false);
  };

  return (
    <div className="animate-in" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <header style={{ marginBottom: 24 }}>
        <h1>Advanced Prompt Lifecycle</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Branch, version, and A/B test prompts with LangFuse-grade control.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, flex: 1 }}>
        {/* Left Column: Version Control */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          
          {/* Create / Branch */}
          <div className="glass-panel" style={{ padding: 24 }}>
            <h3><GitBranch size={18} style={{ display: 'inline', marginRight: 8 }}/> Commit New Version</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
              <div style={{ display: 'flex', gap: 12 }}>
                <input type="text" placeholder="Prompt Name" value={newPromptName} onChange={e => setNewPromptName(e.target.value)} style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }} />
                <input type="text" placeholder="Branch (main)" value={branchName} onChange={e => setBranchName(e.target.value)} style={{ width: 120, padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }} />
              </div>
              <textarea placeholder="Prompt Content (use {{var}})" value={newPromptContent} onChange={e => setNewPromptContent(e.target.value)} style={{ padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white', minHeight: 120 }} />
              <div style={{ display: 'flex', gap: 12 }}>
                <input type="number" placeholder="Max Tokens" value={maxTokens} onChange={e => setMaxTokens(parseInt(e.target.value) || '')} style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }} />
                <input type="number" step="0.01" placeholder="Max Cost ($)" value={maxCost} onChange={e => setMaxCost(parseFloat(e.target.value) || '')} style={{ flex: 1, padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }} />
              </div>
              <button onClick={createPrompt} style={{ padding: '12px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                <GitCommit size={18} /> Commit to {branchName}
              </button>
            </div>
          </div>
          
          {/* Version Tree Explorer */}
          <div className="glass-panel" style={{ padding: 24, flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3>Version Tree</h3>
              <input type="text" placeholder="Search prompts..." onKeyDown={e => { if(e.key === 'Enter') fetchPrompt(e.currentTarget.value) }} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }} />
            </div>

            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Branch</th>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {prompts.length === 0 ? (
                    <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>No prompts found.</td></tr>
                  ) : (
                    prompts.map(p => (
                      <tr key={p.id}>
                        <td><span style={{ padding: '2px 8px', background: 'rgba(168, 85, 247, 0.2)', color: 'var(--accent-purple)', borderRadius: 12, fontSize: '0.8rem' }}>{p.branch}</span></td>
                        <td style={{ fontWeight: 600 }}>{p.name}</td>
                        <td>v{p.version}</td>
                        <td style={{ display: 'flex', gap: 8 }}>
                          <button onClick={() => setSelectedPromptA(p)} style={{ padding: '4px 8px', background: 'var(--accent-green)', color: 'black', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '0.8rem' }}>Set A</button>
                          <button onClick={() => setSelectedPromptB(p)} style={{ padding: '4px 8px', background: 'var(--accent-blue)', color: 'black', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '0.8rem' }}>Set B</button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Column: A/B Playground */}
        <div className="glass-panel" style={{ padding: 24, display: 'flex', flexDirection: 'column' }}>
          <h3><SplitSquareHorizontal size={18} style={{ display: 'inline', marginRight: 8 }}/> A/B Testing Playground</h3>
          
          <div style={{ marginTop: 16, marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: 'var(--text-secondary)' }}><Variable size={16} /> Variables (JSON)</label>
            <textarea value={variables} onChange={e => setVariables(e.target.value)} style={{ width: '100%', padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white', fontFamily: 'monospace', minHeight: 80 }} />
          </div>

          <button onClick={runPlayground} disabled={isRunning || (!selectedPromptA && !selectedPromptB)} style={{ padding: '12px', background: 'white', color: 'black', fontWeight: 600, border: 'none', borderRadius: 8, cursor: isRunning ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, opacity: (isRunning || (!selectedPromptA && !selectedPromptB)) ? 0.5 : 1 }}>
            <Play size={18} /> {isRunning ? 'Running Simulation...' : 'Run A/B Test'}
          </button>

          <div style={{ display: 'flex', gap: 16, marginTop: 24, flex: 1 }}>
            {/* Variant A Result */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <h4 style={{ color: 'var(--accent-green)', marginBottom: 8 }}>Variant A: {selectedPromptA?.name} (v{selectedPromptA?.version})</h4>
              <div style={{ flex: 1, background: 'rgba(0,0,0,0.4)', borderRadius: 8, padding: 16, border: '1px solid var(--border-color)', overflowY: 'auto', whiteSpace: 'pre-wrap', color: resultA?.error ? '#f87171' : 'white' }}>
                {resultA ? (resultA.error || resultA.output) : <span style={{ color: 'var(--text-secondary)', opacity: 0.5 }}>Waiting...</span>}
              </div>
              {resultA && !resultA.error && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 8 }}>
                  Latency: {resultA.latency?.toFixed(2)}s | Cost: ${resultA.cost?.toFixed(5)}
                </div>
              )}
            </div>

            {/* Variant B Result */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              <h4 style={{ color: 'var(--accent-blue)', marginBottom: 8 }}>Variant B: {selectedPromptB?.name} (v{selectedPromptB?.version})</h4>
              <div style={{ flex: 1, background: 'rgba(0,0,0,0.4)', borderRadius: 8, padding: 16, border: '1px solid var(--border-color)', overflowY: 'auto', whiteSpace: 'pre-wrap', color: resultB?.error ? '#f87171' : 'white' }}>
                {resultB ? (resultB.error || resultB.output) : <span style={{ color: 'var(--text-secondary)', opacity: 0.5 }}>Waiting...</span>}
              </div>
              {resultB && !resultB.error && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 8 }}>
                  Latency: {resultB.latency?.toFixed(2)}s | Cost: ${resultB.cost?.toFixed(5)}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
