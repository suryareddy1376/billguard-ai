import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, Legend,
} from 'recharts'
import {
  History as HistoryIcon, TrendingUp, IndianRupee, Shield, AlertTriangle,
  FileText, ArrowRight, RefreshCw, ChevronRight,
} from 'lucide-react'
import { getHistory } from '../api'

const riskColor = (label) => ({
  LOW: 'var(--green-400)', MODERATE: 'var(--amber-400)',
  HIGH: 'var(--risk-high)', CRITICAL: 'var(--red-400)',
})[label] || 'var(--text-muted)'

const riskColorHex = (label) => ({
  LOW: '#4ade80', MODERATE: '#fbbf24', HIGH: '#f87171', CRITICAL: '#ef4444',
})[label] || '#888'

const badgeClass = (label) => ({
  LOW: 'badge-low', MODERATE: 'badge-moderate', HIGH: 'badge-high', CRITICAL: 'badge-critical',
})[label] || 'badge-info'

export default function HistoryPage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadData = () => {
    setLoading(true)
    getHistory()
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Could not load history'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [])

  if (loading) return (
    <div className="page flex-center" style={{ minHeight: '80vh' }}>
      <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
    </div>
  )

  if (error) return (
    <div className="page container" style={{ maxWidth: 680 }}>
      <div className="alert alert-critical mt-4"><AlertTriangle size={16} />{error}</div>
    </div>
  )

  const bills = data?.bills || []
  const pieData = Object.entries(data?.risk_distribution || {})
    .filter(([_, v]) => v > 0)
    .map(([k, v]) => ({ name: k, value: v, fill: riskColorHex(k) }))

  // Score distribution for bar chart
  const scoreData = bills.map((b, i) => ({
    name: b.hospital_name?.substring(0, 15) || `Bill ${i + 1}`,
    score: b.fraud_score,
    risk: b.risk_label,
  })).reverse().slice(-10)

  return (
    <div className="page">
      <div className="container">
        {/* Header */}
        <div className="flex-between mt-3 mb-3" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="hero-eyebrow" style={{ marginBottom: '0.5rem' }}>
              <HistoryIcon size={13} /> Bill History
            </div>
            <h1 style={{ fontSize: '1.75rem' }}>Analytics Dashboard</h1>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
              Track all your past bill analyses and cumulative savings.
            </p>
          </div>
          <div className="flex gap-1">
            <button className="btn btn-ghost btn-sm" onClick={loadData}>
              <RefreshCw size={14} /> Refresh
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/upload')}>
              <FileText size={14} /> Analyze New Bill
            </button>
          </div>
        </div>

        {/* Aggregate stats */}
        <div className="grid-4 mb-3" style={{ gap: '1rem' }}>
          <div className="card" style={{ textAlign: 'center', padding: '1.5rem' }}>
            <div style={{ color: 'var(--teal-400)', marginBottom: '0.5rem' }}>
              <FileText size={28} style={{ margin: '0 auto' }} />
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--teal-400)', lineHeight: 1 }}>
              {data?.total_bills || 0}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>Bills Analyzed</div>
          </div>

          <div className="card" style={{ textAlign: 'center', padding: '1.5rem' }}>
            <div style={{ color: 'var(--red-400)', marginBottom: '0.5rem' }}>
              <IndianRupee size={28} style={{ margin: '0 auto' }} />
            </div>
            <div style={{ fontSize: '2.2rem', fontWeight: 800, color: data?.total_overcharge_detected > 0 ? 'var(--red-400)' : 'var(--green-400)', lineHeight: 1 }}>
              ₹{(data?.total_overcharge_detected || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>Total Overcharges Detected</div>
          </div>

          <div className="card" style={{ textAlign: 'center', padding: '1.5rem' }}>
            <div style={{ color: 'var(--amber-400)', marginBottom: '0.5rem' }}>
              <TrendingUp size={28} style={{ margin: '0 auto' }} />
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: (data?.average_fraud_score || 0) >= 61 ? 'var(--red-400)' : (data?.average_fraud_score || 0) >= 31 ? 'var(--amber-400)' : 'var(--green-400)', lineHeight: 1 }}>
              {data?.average_fraud_score || 0}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>Average Fraud Score</div>
          </div>

          <div className="card" style={{ textAlign: 'center', padding: '1.5rem' }}>
            <div style={{ color: 'var(--green-400)', marginBottom: '0.5rem' }}>
              <Shield size={28} style={{ margin: '0 auto' }} />
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: 'var(--green-400)', lineHeight: 1 }}>
              {data?.risk_distribution?.LOW || 0}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>Clean Bills</div>
          </div>
        </div>

        {/* Charts row */}
        {bills.length > 0 && (
          <div className="grid-2 mb-3" style={{ gap: '1.5rem' }}>
            {/* Score chart */}
            <div className="card" style={{ padding: '1.5rem' }}>
              <h3 className="mb-2">Fraud Score by Bill</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={scoreData}>
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} angle={-20} textAnchor="end" height={60} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                  <Tooltip
                    formatter={(v) => [`${v}/100`, 'Fraud Score']}
                    contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                    {scoreData.map((d, i) => (
                      <Cell key={i} fill={riskColorHex(d.risk)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Risk distribution pie */}
            <div className="card" style={{ padding: '1.5rem' }}>
              <h3 className="mb-2">Risk Distribution</h3>
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%" cy="50%"
                      innerRadius={55} outerRadius={85}
                      paddingAngle={5}
                      dataKey="value"
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {pieData.map((d, i) => (
                        <Cell key={i} fill={d.fill} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    />
                    <Legend
                      wrapperStyle={{ fontSize: 12, color: 'var(--text-muted)' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex-center" style={{ height: 250, color: 'var(--text-muted)' }}>
                  No data yet
                </div>
              )}
            </div>
          </div>
        )}

        {/* Bills table */}
        <div className="card mb-3">
          <div className="flex-between mb-2">
            <h3>All Bill Analyses</h3>
            <span style={{ fontSize: '0.83rem', color: 'var(--text-muted)' }}>{bills.length} total</span>
          </div>

          {bills.length === 0 ? (
            <div className="text-center" style={{ padding: '3rem', color: 'var(--text-muted)' }}>
              <FileText size={40} style={{ margin: '0 auto 1rem', opacity: 0.3 }} />
              <p>No bills analyzed yet. Upload your first bill to get started!</p>
              <button className="btn btn-primary mt-2" onClick={() => navigate('/upload')}>
                Analyze Your First Bill <ArrowRight size={16} />
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {bills.map((bill) => (
                <div
                  key={bill.job_id}
                  onClick={() => navigate(`/dashboard/${bill.job_id}`)}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '1rem 1.25rem', borderRadius: 'var(--radius-sm)',
                    background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
                    cursor: 'pointer', transition: 'all 0.2s',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
                    e.currentTarget.style.borderColor = 'var(--teal-400)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.02)'
                    e.currentTarget.style.borderColor = 'var(--border)'
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="flex gap-1 mb-1" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.92rem' }}>
                        {bill.hospital_name || 'Unknown Hospital'}
                      </span>
                      <span className={`badge ${badgeClass(bill.risk_label)}`} style={{ fontSize: '0.65rem' }}>
                        {bill.risk_label}
                      </span>
                    </div>
                    <div className="flex gap-2" style={{ fontSize: '0.78rem', color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                      <span>ID: {bill.patient_id}</span>
                      <span>•</span>
                      <span>{bill.total_items} items</span>
                      <span>•</span>
                      <span>{bill.flagged_count} flagged</span>
                      <span>•</span>
                      <span>{bill.created_at ? new Date(bill.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'}</span>
                    </div>
                  </div>

                  <div className="flex gap-2" style={{ alignItems: 'center' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{
                        fontSize: '1.5rem', fontWeight: 800, lineHeight: 1,
                        color: riskColor(bill.risk_label),
                      }}>
                        {bill.fraud_score}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>/100</div>
                    </div>
                    {bill.overcharge_estimate > 0 && (
                      <div style={{ textAlign: 'right', paddingLeft: '0.75rem', borderLeft: '1px solid var(--border)' }}>
                        <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--red-400)', lineHeight: 1 }}>
                          ₹{bill.overcharge_estimate.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </div>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>overcharge</div>
                      </div>
                    )}
                    <ChevronRight size={18} color="var(--text-muted)" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ height: '3rem' }} />
      </div>
    </div>
  )
}
