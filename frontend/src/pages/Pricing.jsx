import React, { useState, useEffect } from 'react';
import { Search, Info, ShieldAlert, HeartHandshake, Loader } from 'lucide-react';
import { getTariff } from '../api';

export default function Pricing() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await getTariff();
        setData(res.data.tariff || []);
      } catch (err) {
        console.error("Failed to load tariff data", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const filtered = data.filter(item => {
    const n = item?.name || '';
    const c = item?.code || '';
    const q = query || '';
    return n.toLowerCase().includes(q.toLowerCase()) || 
           c.toLowerCase().includes(q.toLowerCase());
  });

  return (
    <div className="page pb-5">
      <div className="hero bg-surface border-b border-border py-4 animate-in">
        <div className="container">
          <div className="flex gap-2 align-center mb-1">
            <HeartHandshake className="text-teal" size={18} />
            <span className="hero-eyebrow" style={{ margin: 0 }}>Patient Resources</span>
          </div>
          <h1 className="hero-title" style={{ fontSize: '2.5rem' }}>Fair Price <span>Finder</span></h1>
          <p className="text-muted" style={{ maxWidth: '600px' }}>
            Empower yourself before your hospital visit. Search across nationally recognized benchmarks (CGHS 2024) to discover the definitively fair prices for medical procedures. 
          </p>

          <div style={{ marginTop: '2rem', maxWidth: '800px', position: 'relative' }}>
            <Search style={{ position: 'absolute', top: '50%', left: '1.2rem', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} size={20} />
            <input 
              type="text" 
              className="form-input" 
              placeholder="Search for a procedure (e.g., 'MRI', 'Surgery', 'Maternity')..."
              style={{ padding: '1rem 1rem 1rem 3.2rem', fontSize: '1.1rem', borderRadius: '12px', width: '100%', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="container animate-in mt-4" style={{ animationDelay: '0.1s' }}>
        <div className="card p-0" style={{ overflow: 'hidden' }}>
          {loading ? (
            <div className="p-5 flex justify-center text-muted">
              <Loader className="spin" size={24} />
              <span className="ms-2">Loading national benchmarks...</span>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="w-100" style={{ minWidth: '800px', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-card)', borderBottom: '2px solid var(--border-color)', textAlign: 'left' }}>
                    <th className="p-3 text-muted" style={{ fontWeight: 600, fontSize: '0.85rem', minWidth: '180px' }}>PROCEDURE / CODE</th>
                    <th className="p-3 text-muted" style={{ fontWeight: 600, fontSize: '0.85rem', whiteSpace: 'nowrap' }}>GOVT & TRUST<br/>HOSPITALS</th>
                    <th className="p-3 text-muted" style={{ fontWeight: 600, fontSize: '0.85rem', whiteSpace: 'nowrap' }}>STANDARD<br/>PRIVATE CLINICS</th>
                    <th className="p-3" style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--green-400)', background: 'rgba(52, 211, 153, 0.05)', whiteSpace: 'nowrap' }}>
                      <div className="flex align-center gap-1">PREMIUM<br/>CORPORATE <Info size={14} style={{ flexShrink: 0 }} /></div>
                    </th>
                    <th className="p-3" style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--red-400)', background: 'rgba(239, 68, 68, 0.05)', whiteSpace: 'nowrap' }}>
                      <div className="flex align-center gap-1">LUXURY<br/>HIGH-END <ShieldAlert size={14} style={{ flexShrink: 0 }} /></div>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td colSpan="5" className="p-5 text-center text-muted">No procedures found matching your search.</td>
                    </tr>
                  ) : (
                    filtered.map((item, idx) => (
                      <tr key={item.code} style={{ borderBottom: '1px solid var(--border-color)', background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                        <td className="p-3">
                          <div style={{ fontWeight: 500, color: 'var(--text-main)', marginBottom: '0.2rem' }}>{item.name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-disabled)', fontFamily: 'monospace' }}>{item.code}</div>
                        </td>
                        <td className="p-3 text-muted">Rs. {item.p25.toLocaleString()}</td>
                        <td className="p-3" style={{ color: 'var(--text-secondary)' }}>Rs. {item.p50.toLocaleString()}</td>
                        <td className="p-3" style={{ background: 'rgba(52, 211, 153, 0.05)', fontWeight: 600, color: 'var(--green-400)' }}>
                          Rs. {item.p75.toLocaleString()}
                        </td>
                        <td className="p-3" style={{ background: 'rgba(239, 68, 68, 0.05)', fontWeight: 600, color: 'var(--red-400)' }}>
                          Rs. {item.p95.toLocaleString()} +
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="mt-4 flex gap-2 p-3" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          <Info size={16} className="text-teal mt-1 flex-shrink-0" />
          <p style={{ margin: 0 }}>
            <strong>How to read this:</strong> The <em>Fair Bound</em> represents the 75th percentile of CGHS rates. Any hospital charging above this line represents a significant markup. The <em>Extortion Risk</em> boundary indicates extreme outlier pricing that should aggressively be disputed. 
          </p>
        </div>
      </div>
    </div>
  );
}
