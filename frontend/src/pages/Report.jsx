import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { FileText, Download, AlertTriangle, CheckCircle, ArrowLeft, Shield, IndianRupee } from 'lucide-react'
import { getReport } from '../api'

export default function Report() {
  const { jobId }  = useParams()
  const navigate   = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]  = useState('')

  useEffect(() => {
    getReport(jobId)
      .then(r => setReport(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Could not load report'))
      .finally(() => setLoading(false))
  }, [jobId])

  const handlePrint = () => window.print()

  if (loading) return (
    <div className="page flex-center" style={{ minHeight: '80vh' }}>
      <div className="spinner" style={{ width: 36, height: 36, borderWidth: 3 }} />
    </div>
  )

  if (error) return (
    <div className="page container" style={{ maxWidth: 680 }}>
      <div className="alert alert-critical mt-4"><AlertTriangle size={16} />{error}</div>
      <button className="btn btn-ghost mt-2" onClick={() => navigate(-1)}><ArrowLeft size={14} /> Back</button>
    </div>
  )

  const riskColor = { LOW: 'var(--green-400)', MODERATE: 'var(--amber-400)', HIGH: 'var(--risk-high)', CRITICAL: 'var(--red-400)' }[report.risk_label]
  const flaggedItems  = report.all_flagged_items || []
  const disputedItems = report.disputed_items || []
  const overcharge = flaggedItems.reduce((s, i) => {
    if (i.unit_price && i.benchmark_p75 && i.unit_price > i.benchmark_p75)
      return s + (i.unit_price - i.benchmark_p75) * (i.quantity || 1)
    return s
  }, 0)

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 860 }}>
        {/* Actions */}
        <div className="flex-between mt-3 mb-3" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/dashboard/${jobId}`)}>
            <ArrowLeft size={14} /> Back to Dashboard
          </button>
          <div className="flex gap-1">
            <button className="btn btn-primary btn-sm" onClick={handlePrint}>
              <Download size={14} /> Print / Save PDF
            </button>
          </div>
        </div>

        {/* Report card */}
        <div className="card animate-in" style={{ marginBottom: '2rem' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div>
              <div className="flex gap-1" style={{ alignItems: 'center', marginBottom: '0.5rem' }}>
                <Shield size={20} color="var(--teal-400)" />
                <span className="text-teal" style={{ fontWeight: 700, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>BillGuard AI</span>
              </div>
              <h2 className="mb-1">Billing Analysis Dispute Report</h2>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Report ID: {report.report_id} · Generated: {new Date(report.generated_at).toLocaleString('en-IN')}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '3rem', fontWeight: 800, color: riskColor, lineHeight: 1 }}>
                {report.fraud_score}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Fraud Score / 100</div>
              <span className="badge mt-1" style={{
                background: `${riskColor}1a`, color: riskColor, padding: '0.3rem 0.8rem',
                border: `1px solid ${riskColor}40`,
              }}>
                {report.risk_label} RISK
              </span>
            </div>
          </div>

          <div className="divider" />

          {/* Patient / Hospital info */}
          <div className="grid-2 mb-3">
            <div>
              <div className="stat-label mb-1">Patient ID</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.9rem' }}>{report.patient_id}</div>
            </div>
            <div>
              <div className="stat-label mb-1">Hospital</div>
              <div style={{ fontSize: '0.9rem' }}>{report.hospital_name}</div>
            </div>
          </div>

          {/* Summary */}
          <div className={`alert ${report.risk_label === 'LOW' ? 'alert-success' : report.risk_label === 'CRITICAL' ? 'alert-critical' : 'alert-warning'} mb-3`}>
            <AlertTriangle size={16} style={{ flexShrink: 0 }} />
            <span>{report.summary}</span>
          </div>

          {/* Stats row */}
          <div className="grid-4 mb-3" style={{ gap: '0.75rem' }}>
            <div className="stat-card">
              <span className="stat-label">Total Flagged</span>
              <span className="stat-value" style={{ color: 'var(--red-400)' }}>{report.total_flagged}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Disputed</span>
              <span className="stat-value" style={{ color: 'var(--amber-400)' }}>{disputedItems.length}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Est. Overcharge</span>
              <span className="stat-value" style={{ color: 'var(--red-400)', fontSize: '1.3rem' }}>
                ₹{overcharge.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Score</span>
              <span className="stat-value" style={{ color: riskColor }}>{report.fraud_score}</span>
            </div>
          </div>

          <div className="divider" />

          {/* Flagged items detail */}
          <h3 className="mb-2">Flagged Line Items</h3>
          {flaggedItems.length === 0 && (
            <div className="flex-center" style={{ padding: '2rem', color: 'var(--text-muted)' }}>
              <CheckCircle size={20} color="var(--green-400)" style={{ marginRight: 8 }} />
              No items were flagged.
            </div>
          )}
          {flaggedItems.map((item, idx) => (
            <div key={item.item_id} style={{
              borderLeft: `3px solid ${item.severity === 'HIGH' ? 'var(--red-400)' : item.severity === 'MEDIUM' ? 'var(--amber-400)' : 'var(--teal-400)'}`,
              padding: '1rem 1.25rem',
              marginBottom: '1rem',
              background: 'rgba(255,255,255,0.02)',
              borderRadius: '0 var(--radius-sm) var(--radius-sm) 0',
            }}>
              <div className="flex-between mb-1" style={{ flexWrap: 'wrap', gap: '0.5rem' }}>
                <span style={{ fontWeight: 600 }}>{idx + 1}. {item.raw_description}</span>
                <div className="flex gap-1">
                  <span className="badge badge-info" style={{ fontSize: '0.65rem' }}>{item.mapped_category}</span>
                  <span className={`badge ${item.severity === 'HIGH' ? 'badge-critical' : item.severity === 'MEDIUM' ? 'badge-moderate' : 'badge-info'}`}>
                    {item.severity}
                  </span>
                  {disputedItems.find(d => d.item_id === item.item_id) && (
                    <span className="badge badge-critical">DISPUTED</span>
                  )}
                </div>
              </div>
              <div className="grid-2 mb-1" style={{ fontSize: '0.82rem', color: 'var(--text-muted)', gap: '0.5rem' }}>
                <span>Charged: <strong style={{ color: 'var(--text-primary)' }}>₹{item.unit_price?.toLocaleString('en-IN')} × {item.quantity}</strong></span>
                <span>Benchmark median: <strong style={{ color: 'var(--text-primary)' }}>₹{item.benchmark_p50?.toLocaleString('en-IN')}</strong></span>
              </div>
              {item.explanations?.map((ex, i) => (
                <div key={i} style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '0.4rem', lineHeight: 1.6 }}>
                  • {ex}
                </div>
              ))}
            </div>
          ))}

          <div className="divider" />

          {/* Disclaimer */}
          <div style={{
            background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)', padding: '1rem',
            fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.7,
          }}>
            <strong style={{ color: 'var(--text-secondary)' }}>Disclaimer: </strong>
            {report.disclaimer}
          </div>
        </div>
      </div>
    </div>
  )
}
