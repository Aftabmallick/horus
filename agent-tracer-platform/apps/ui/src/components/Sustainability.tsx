import { useState, useEffect } from 'react';
import { Leaf, Wind, BatteryCharging, Globe2, Activity } from 'lucide-react';

export const Sustainability = () => {
  const [data, setData] = useState({ total_co2_kg: 0, total_energy_kwh: 0, equivalent: 'Loading...' });

  useEffect(() => {
    const fetchReport = async () => {
      try {
        const token = localStorage.getItem('agent_tracer_token');
        const res = await fetch('/api/v1/sustainability/report', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchReport();
  }, []);
  return (
    <div className="animate-in">
      <header style={{ marginBottom: 32, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Sustainability Report</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Track your AI infrastructure's carbon footprint.</p>
        </div>
        <div className="glass-panel" style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(16, 185, 129, 0.1)', borderColor: 'var(--accent-green)' }}>
          <Activity size={18} color="var(--accent-green)" />
          <span style={{ fontSize: '0.875rem', color: 'white' }}>Data Source: <strong>Static Regional Tables</strong></span>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 24, marginBottom: 32 }}>
        <div className="card glass-panel" style={{ textAlign: 'center' }}>
          <Leaf size={32} color="var(--accent-green)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ color: 'var(--text-secondary)' }}>Total CO2 Emitted</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'white' }}>{data.total_co2_kg.toFixed(2)} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>kg</span></div>
        </div>
        
        <div className="card glass-panel" style={{ textAlign: 'center' }}>
          <BatteryCharging size={32} color="var(--accent-blue)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ color: 'var(--text-secondary)' }}>Energy Consumed</h3>
          <div style={{ fontSize: '2.5rem', fontWeight: 700, color: 'white' }}>{data.total_energy_kwh.toFixed(2)} <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>kWh</span></div>
        </div>

        <div className="card glass-panel" style={{ textAlign: 'center', background: 'rgba(16, 185, 129, 0.05)' }}>
          <Wind size={32} color="var(--accent-green)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ color: 'var(--text-secondary)' }}>Equivalent To</h3>
          <div style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--accent-green)', marginTop: 16 }}>{data.equivalent}</div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 8 }}>in an average gasoline vehicle</p>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: 24, marginTop: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <Globe2 size={24} color="var(--accent-purple)" />
          <h2 style={{ margin: 0 }}>Lowest Carbon Cloud Regions</h2>
        </div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>Route your AI workloads to these regions to minimize your carbon footprint. Values represent grid intensity (gCO2eq/kWh).</p>
        
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Region Code</th>
                <th>Cloud Provider</th>
                <th>Location</th>
                <th>Grid Intensity</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>europe-west6</td>
                <td>Google Cloud</td>
                <td>Zurich, Switzerland</td>
                <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>12 gCO2/kWh</td>
              </tr>
              <tr>
                <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>eu-north-1</td>
                <td>AWS</td>
                <td>Stockholm, Sweden</td>
                <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>14 gCO2/kWh</td>
              </tr>
              <tr>
                <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>norwayeast</td>
                <td>Azure</td>
                <td>Oslo, Norway</td>
                <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>16 gCO2/kWh</td>
              </tr>
              <tr>
                <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>europe-west1</td>
                <td>Google Cloud</td>
                <td>St. Ghislain, Belgium</td>
                <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>25 gCO2/kWh</td>
              </tr>
              <tr>
                <td style={{ fontFamily: 'monospace', color: 'var(--accent-purple)' }}>ca-central-1</td>
                <td>AWS</td>
                <td>Montreal, Canada</td>
                <td style={{ color: 'var(--accent-green)', fontWeight: 600 }}>30 gCO2/kWh</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
