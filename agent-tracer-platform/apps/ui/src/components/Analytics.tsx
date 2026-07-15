import { useState, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const Analytics = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const res = await fetch('/api/v1/analytics/dashboard', {
        headers: { Authorization: `Bearer ${localStorage.getItem('agent_tracer_token')}` }
      });
      if (res.ok) {
        const json = await res.json();
        
        // Format chart data
        const chartData = json.daily_cost.map((cost: number, index: number) => ({
          name: `Day ${index + 1}`,
          cost: cost
        }));
        
        setData({ ...json, chartData });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading Analytics...</div>;
  if (!data) return <div>Failed to load analytics.</div>;

  return (
    <div className="animate-in">
      <header style={{ marginBottom: 24 }}>
        <h1>Cost Analytics</h1>
        <p style={{ color: 'var(--text-secondary)' }}>Time-series token and cost usage.</p>
      </header>
      
      <div className="glass-panel" style={{ padding: 24, marginBottom: 24 }}>
        <h3 style={{ marginBottom: 16 }}>Daily Cost (Last 7 Days)</h3>
        <div style={{ height: 300, width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-purple)" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="var(--accent-purple)" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(v) => `$${v}`} />
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                itemStyle={{ color: 'var(--accent-purple)' }}
                formatter={(value: any) => [`$${Number(value).toFixed(4)}`, 'Cost']}
              />
              <Area type="monotone" dataKey="cost" stroke="var(--accent-purple)" fillOpacity={1} fill="url(#colorCost)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        <div className="glass-panel card">
           <h3 style={{ marginBottom: 16 }}>Top Agents by Cost</h3>
           <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, color: 'var(--text-secondary)', fontSize: '0.85rem' }}><span>Agent</span><span>Cost</span></div>
           {data.top_cost.length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No data available</div>}
           {data.top_cost.map((item: any, idx: number) => (
             <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
               <span>{item.agent}</span>
               <span style={{color: 'var(--accent-purple)'}}>${item.cost.toFixed(4)}</span>
             </div>
           ))}
        </div>
        <div className="glass-panel card">
           <h3 style={{ marginBottom: 16 }}>Top Agents by Errors</h3>
           <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, color: 'var(--text-secondary)', fontSize: '0.85rem' }}><span>Agent</span><span>Error Rate</span></div>
           {data.top_errors.length === 0 && <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No data available</div>}
           {data.top_errors.map((item: any, idx: number) => (
             <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
               <span>{item.agent}</span>
               <span style={{color: item.error_rate > 5 ? 'var(--accent-red)' : 'var(--accent-orange)'}}>{item.error_rate}%</span>
             </div>
           ))}
        </div>
      </div>
    </div>
  );
};
