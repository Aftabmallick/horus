import { useState, useEffect } from 'react';
import { Database, Plus, DatabaseZap, Download } from 'lucide-react';

interface Dataset {
  id: string;
  name: string;
  created_at: string;
}

interface DatasetItem {
  id: string;
  input: Record<string, any>;
  expected_output: Record<string, any>;
  created_at: string;
}

export function DatasetManager() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null);
  const [items, setItems] = useState<DatasetItem[]>([]);
  const [newDatasetName, setNewDatasetName] = useState('');
  
  const token = localStorage.getItem('agent_tracer_token');

  useEffect(() => {
    fetchDatasets();
  }, []);

  useEffect(() => {
    if (selectedDataset) {
      fetchItems(selectedDataset);
    }
  }, [selectedDataset]);

  const fetchDatasets = async () => {
    try {
      const res = await fetch('/api/v1/datasets', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setDatasets(data.datasets || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchItems = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/datasets/${id}/items`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const createDataset = async () => {
    if (!newDatasetName) return;
    try {
      const res = await fetch('/api/v1/datasets', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ name: newDatasetName })
      });
      if (res.ok) {
        setNewDatasetName('');
        fetchDatasets();
      }
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24 }}>
        <h1>Datasets & Evaluations</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Manage test cases to evaluate your agents against.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 24 }}>
        <div className="glass-panel" style={{ padding: 24 }}>
          <h3>Your Datasets</h3>
          
          <div style={{ display: 'flex', gap: 8, marginTop: 16, marginBottom: 24 }}>
            <input 
              type="text" 
              placeholder="New dataset name..." 
              value={newDatasetName}
              onChange={e => setNewDatasetName(e.target.value)}
              style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color)', background: 'rgba(0,0,0,0.3)', color: 'white' }}
            />
            <button 
              onClick={createDataset}
              style={{ padding: '8px 12px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer' }}
            >
              <Plus size={18} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {datasets.length === 0 && <div style={{ color: 'var(--text-secondary)' }}>No datasets found.</div>}
            {datasets.map(ds => (
              <div 
                key={ds.id} 
                onClick={() => setSelectedDataset(ds.id)}
                style={{ 
                  padding: 16, 
                  borderRadius: 8, 
                  border: '1px solid',
                  borderColor: selectedDataset === ds.id ? 'var(--accent-purple)' : 'var(--border-color)',
                  background: selectedDataset === ds.id ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12
                }}
              >
                <DatabaseZap size={18} color={selectedDataset === ds.id ? "var(--accent-purple)" : "var(--text-secondary)"} />
                <div style={{ flex: 1, fontWeight: 500 }}>{ds.name}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>Dataset Items</h3>
            {selectedDataset && (
              <div style={{ display: 'flex', gap: 8 }}>
                <select style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-color)', color: 'white', borderRadius: 8, padding: '4px 8px', fontSize: '0.85rem' }}>
                  <option value="jsonl">JSONL</option>
                  <option value="openai_finetune">OpenAI Fine-tune</option>
                  <option value="huggingface">HuggingFace</option>
                </select>
                <button style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 12px', background: 'var(--accent-purple)', color: 'white', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 }}>
                  <Download size={14} />
                  Export for RLHF
                </button>
              </div>
            )}
          </div>
          {selectedDataset ? (
            <div className="table-container" style={{ marginTop: 16 }}>
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Input</th>
                    <th>Expected Output</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length === 0 ? (
                    <tr><td colSpan={3} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>No items in this dataset.</td></tr>
                  ) : (
                    items.map(item => (
                      <tr key={item.id}>
                        <td style={{ fontFamily: 'monospace', color: 'var(--accent-blue)' }}>{item.id.slice(0,8)}</td>
                        <td style={{ color: 'var(--text-secondary)', maxWidth: 200, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {JSON.stringify(item.input)}
                        </td>
                        <td style={{ color: 'var(--text-secondary)', maxWidth: 200, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {JSON.stringify(item.expected_output)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              
              <div style={{ marginTop: 24, padding: 16, border: '1px dashed var(--border-color)', borderRadius: 8, textAlign: 'center', color: 'var(--text-secondary)' }}>
                Use the API or SDK to push items to this dataset.
                <br/>
                <code style={{ fontSize: '0.85rem', color: 'var(--accent-purple)' }}>POST /api/v1/dataset-items</code>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: 40, textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Database size={48} style={{ opacity: 0.2, marginBottom: 16 }} />
              <p>Select a dataset to view its test items.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
