import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
} from 'recharts'
import {
  AlertTriangle, CheckCircle, ChevronDown, ChevronUp, FileText,
  RefreshCw, Flag, MessageSquare, Eye, TrendingUp, IndianRupee, Scale,
} from 'lucide-react'
import { getStatus, getAnalysis, getItems, submitAction } from '../api'

// ── Helpers ────────────────────────────────────────────────────────────────
const riskColor = (label) => ({
  LOW: 'var(--green-400)', MODERATE: 'var(--amber-400)',
  HIGH: 'var(--risk-high)', CRITICAL: 'var(--red-400)',
})[label] || 'var(--text-muted)'

const badgeClass = (label) => ({
  LOW: 'badge-low', MODERATE: 'badge-moderate', HIGH: 'badge-high', CRITICAL: 'badge-critical',
})[label] || 'badge-info'

const severityClass = (s) => ({
  HIGH: 'severity-high', MEDIUM: 'severity-medium', LOW: 'severity-low',
})[s] || 'severity-ok'

// ── Score Gauge ────────────────────────────────────────────────────────────
function ScoreGauge({ score, riskLabel }) {
  const color = riskColor(riskLabel)
  const data = [{ name: 'score', value: score }]
  return (
    <div className="gauge-wrap">
      <div className="gauge-arc" style={{ width: 220, height: 130 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%" cy="100%" innerRadius="75%" outerRadius="100%"
            startAngle={180} endAngle={0} data={data}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar dataKey="value" cornerRadius={8} fill={color} background={{ fill: 'rgba(255,255,255,0.04)' }} />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="gauge-score-text">
          <div className="gauge-score-number" style={{ color }}>{score}</div>
          <div className="gauge-score-label">/ 100</div>
        </div>
      </div>
      <span className={`badge ${badgeClass(riskLabel)}`} style={{ fontSize: '0.85rem', padding: '0.4rem 1rem' }}>
        {riskLabel} RISK
      </span>
    </div>
  )
}

// ── Status Poller ──────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const cls = `status-pill status-${(status || '').toLowerCase()}`
  return (
    <span className={cls}>
      <span className="dot" />
      {status}
    </span>
  )
}

// ── Line Item Card ─────────────────────────────────────────────────────────
function LineItemCard({ item, onAction, actionState }) {
  const [open, setOpen] = useState(false)
  const hasFlag = item.severity && item.severity !== 'ok'
  const devPct = item.price_deviation_percentage

  return (
    <div className={`item-card ${severityClass(item.severity)}`}>
      <div className="item-card-header" onClick={() => setOpen(o => !o)}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="flex gap-1" style={{ alignItems: 'center', flexWrap: 'wrap', marginBottom: '0.3rem' }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem' }} className="truncate">{item.raw_description}</span>
            {item.severity === 'HIGH'   && <span className="badge badge-critical">HIGH</span>}
            {item.severity === 'MEDIUM' && <span className="badge badge-moderate">MEDIUM</span>}
            {item.severity === 'LOW'    && <span className="badge badge-info">LOW</span>}
            {(item.rule_violations?.length > 0) && <span className="badge badge-critical" style={{ fontSize: '0.65rem' }}>RULE VIOLATION</span>}
          </div>
          <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
            <span className="text-muted" style={{ fontSize: '0.78rem' }}>{item.mapped_category}</span>
            {item.unit_price != null && (
              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                ₹{item.unit_price?.toLocaleString('en-IN')}
                {item.quantity > 1 && ` × ${item.quantity}`}
              </span>
            )}
            {devPct != null && Math.abs(devPct) > 5 && (
              <span style={{ fontSize: '0.78rem', color: devPct > 0 ? 'var(--red-400)' : 'var(--green-400)', fontWeight: 600 }}>
                {devPct > 0 ? '+' : ''}{devPct.toFixed(0)}% vs median
              </span>
            )}
          </div>
        </div>
        <div style={{ flexShrink: 0, color: 'var(--text-muted)' }}>
          {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {open && (
        <div className="item-card-body">
          {/* Benchmark bar */}
          {item.benchmark_p50 != null && item.unit_price != null && (
            <div style={{ marginBottom: '0.25rem' }}>
              <div className="flex-between mb-1" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>Price vs. Benchmark (CGHS {item.benchmark_source})</span>
                <span>Median: ₹{item.benchmark_p50?.toLocaleString('en-IN')}</span>
              </div>
              <BenchmarkBar
                charged={item.unit_price}
                p25={item.benchmark_p25}
                p50={item.benchmark_p50}
                p75={item.benchmark_p75}
              />
              <div className="flex-between mt-1" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                <span>₹{item.benchmark_p25?.toLocaleString('en-IN')} (p25)</span>
                <span>₹{item.benchmark_p75?.toLocaleString('en-IN')} (p75)</span>
              </div>
              
              <div style={{ marginTop: '1.25rem', marginBottom: '0.5rem' }}>
                <h4 style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Multi-Hospital Price Comparison</h4>
                <table style={{ width: '100%', fontSize: '0.8rem', borderCollapse: 'collapse', textAlign: 'left', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', overflow: 'hidden' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.05)', borderBottom: '1px solid var(--border)' }}>
                      <th style={{ padding: '0.5rem' }}>Hospital Type</th>
                      <th style={{ padding: '0.5rem' }}>Price</th>
                      <th style={{ padding: '0.5rem' }}>Potential Savings</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '0.5rem' }}>CGHS Panel (Govt)</td>
                      <td style={{ padding: '0.5rem' }}>₹{item.benchmark_p25?.toLocaleString('en-IN')}</td>
                      <td style={{ padding: '0.5rem', color: 'var(--green-400)', fontWeight: 500 }}>
                         ₹{Math.max(0, item.unit_price - item.benchmark_p25).toLocaleString('en-IN')}
                      </td>
                    </tr>
                    <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td style={{ padding: '0.5rem' }}>Private Average</td>
                      <td style={{ padding: '0.5rem' }}>₹{item.benchmark_p50?.toLocaleString('en-IN')}</td>
                      <td style={{ padding: '0.5rem', color: 'var(--green-400)', fontWeight: 500 }}>
                         ₹{Math.max(0, item.unit_price - item.benchmark_p50).toLocaleString('en-IN')}
                      </td>
                    </tr>
                    <tr style={{ background: 'rgba(239, 68, 68, 0.08)' }}>
                      <td style={{ padding: '0.5rem', fontWeight: 600 }}>Your Hospital</td>
                      <td style={{ padding: '0.5rem', color: 'var(--red-400)', fontWeight: 600 }}>₹{item.unit_price?.toLocaleString('en-IN')}</td>
                      <td style={{ padding: '0.5rem', color: 'var(--text-disabled)' }}>—</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Explanations */}
          {item.explanations?.map((ex, i) => (
            <div key={i} className={`explanation-callout ${item.severity === 'HIGH' ? 'danger' : item.severity === 'MEDIUM' ? 'warning' : ''}`}>
              {ex}
            </div>
          ))}

          {/* Action buttons */}
          <div className="flex gap-1 mt-1" style={{ flexWrap: 'wrap' }}>
            <button
              className="btn btn-danger btn-sm"
              disabled={!!actionState[item.item_id]}
              onClick={() => onAction(item.item_id, 'DISPUTE')}
            >
              <Flag size={13} /> {actionState[item.item_id] === 'DISPUTE' ? 'Disputed ✓' : 'Dispute'}
            </button>
            <button
              className="btn btn-ghost btn-sm"
              disabled={!!actionState[item.item_id]}
              onClick={() => onAction(item.item_id, 'REQUEST_CLARIFICATION')}
            >
              <MessageSquare size={13} /> Request Clarification
            </button>
            <button
              className="btn btn-ghost btn-sm"
              disabled={!!actionState[item.item_id]}
              onClick={() => onAction(item.item_id, 'MARK_REVIEWED')}
            >
              <Eye size={13} /> Mark Reviewed
            </button>
          </div>
          {actionState[item.item_id] && (
            <div className="alert alert-success" style={{ padding: '0.5rem 0.75rem', marginTop: '0.5rem' }}>
              <CheckCircle size={14} />
              Action recorded: {actionState[item.item_id].replace(/_/g, ' ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Benchmark visual bar ───────────────────────────────────────────────────
function BenchmarkBar({ charged, p25, p50, p75 }) {
  const max = Math.max(charged, p75) * 1.25
  const toPercent = (v) => Math.min((v / max) * 100, 100)

  return (
    <div style={{ position: 'relative', height: 28, background: 'rgba(255,255,255,0.04)', borderRadius: 6, overflow: 'hidden' }}>
      {/* Fair range p25–p75 */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0,
        left: `${toPercent(p25)}%`,
        width: `${toPercent(p75) - toPercent(p25)}%`,
        background: 'rgba(74,222,128,0.15)',
        borderLeft: '1px solid rgba(74,222,128,0.3)',
        borderRight: '1px solid rgba(74,222,128,0.3)',
      }} />
      {/* Median line */}
      <div style={{
        position: 'absolute', top: 0, bottom: 0, width: 2,
        left: `${toPercent(p50)}%`,
        background: 'rgba(74,222,128,0.6)',
      }} />
      {/* Charged price marker */}
      <div style={{
        position: 'absolute', top: '15%', bottom: '15%', width: 4,
        left: `calc(${toPercent(charged)}% - 2px)`,
        background: charged > p75 ? 'var(--red-400)' : 'var(--teal-400)',
        borderRadius: 2,
        boxShadow: charged > p75 ? '0 0 8px rgba(248,113,113,0.6)' : '0 0 8px rgba(46,196,182,0.5)',
      }} />
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────────────────
export default function Dashboard() {
  const { jobId } = useParams()
  const navigate  = useNavigate()

  const [status,   setStatus]   = useState('QUEUED')
  const [analysis, setAnalysis] = useState(null)
  const [allItems, setAllItems] = useState([])
  const [tab,      setTab]      = useState('flagged')
  const [actions,  setActions]  = useState({}) // item_id → action_type
  const [error,    setError]    = useState('')
  const [polling,  setPolling]  = useState(true)

  // Poll job status until COMPLETE or FAILED
  const poll = useCallback(async () => {
    try {
      const res = await getStatus(jobId)
      const s   = res.data.status
      setStatus(s)
      if (s === 'COMPLETE') {
        setPolling(false)
        const [aRes, iRes] = await Promise.all([getAnalysis(jobId), getItems(jobId)])
        setAnalysis(aRes.data)
        setAllItems(iRes.data.items)
      } else if (s === 'FAILED') {
        setPolling(false)
        setError('Processing failed. Please check your bill format and try again.')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to reach backend.')
      setPolling(false)
    }
  }, [jobId])

  useEffect(() => {
    poll()
    let interval
    if (polling) { interval = setInterval(poll, 2000) }
    return () => clearInterval(interval)
  }, [poll, polling])

  const handleAction = async (itemId, actionType) => {
    try {
      await submitAction(jobId, { item_id: itemId, action_type: actionType })
      setActions(prev => ({ ...prev, [itemId]: actionType }))
    } catch { /* silent */ }
  }

  // ── Loading state ──────────────────────────────────────────────────────
  if (polling || !analysis) {
    return (
      <div className="page">
        <div className="container" style={{ maxWidth: 680 }}>
          <div className="card mt-4 text-center animate-in" style={{ padding: '3rem 2rem' }}>
            <RefreshCw size={40} color="var(--teal-400)" style={{ margin: '0 auto 1.5rem', animation: 'spin 1.2s linear infinite' }} />
            <h2 className="mb-1">Analyzing Your Bill</h2>
            <p className="mb-3">Running all 6 detection layers asynchronously...</p>
            <StatusBadge status={status} />
            <div className="text-muted mt-2" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
              job_id: {jobId}
            </div>
            {error && <div className="alert alert-critical mt-3"><AlertTriangle size={16} />{error}</div>}
            {/* Progress steps */}
            <div style={{ marginTop: '2rem', textAlign: 'left' }}>
              {['Ingestion & Validation', 'Normalization & Mapping', 'Feature Extraction', 'Rules Engine', 'Statistical Detection', 'Score & Explanations'].map((step, i) => (
                <div key={step} className="flex gap-1 mb-1" style={{ alignItems: 'center', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  <div className="spinner" style={{ width: 12, height: 12, borderWidth: 1.5 }} />
                  Layer {i + 1}: {step}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  const flaggedItems = analysis.flagged_items || []
  const okItems = allItems.filter(i => !flaggedItems.find(f => f.item_id === i.item_id))
  const disputedCount = Object.values(actions).filter(a => a === 'DISPUTE').length
  const overcharge = flaggedItems.reduce((sum, i) => {
    if (i.unit_price && i.benchmark_p75 && i.unit_price > i.benchmark_p75) {
      return sum + (i.unit_price - i.benchmark_p75) * (i.quantity || 1)
    }
    return sum
  }, 0)

  return (
    <div className="page">
      <div className="container">
        {/* Header */}
        <div className="flex-between mt-3 mb-3" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="hero-eyebrow" style={{ marginBottom: '0.5rem' }}><TrendingUp size={13} /> Analysis Complete</div>
            <h1 style={{ fontSize: '1.75rem' }}>Bill Analysis Report</h1>
            <div className="text-muted mt-1" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
              job_id: {jobId}
            </div>
          </div>
          <div className="flex gap-1">
            <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/report/${jobId}`)}>
              <FileText size={14} /> Export Report
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => navigate(`/complaint/${jobId}`)}>
              <Scale size={14} /> Generate Complaint Letter
            </button>
          </div>
        </div>

        {/* Summary alert */}
        <div className={`alert ${
          analysis.risk_label === 'CRITICAL' ? 'alert-critical' :
          analysis.risk_label === 'HIGH' ? 'alert-warning' :
          analysis.risk_label === 'MODERATE' ? 'alert-warning' : 'alert-success'
        } mb-3`}>
          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
          <span>{analysis.summary_explanation}</span>
        </div>

        <div className="grid-2 mb-3">
          {/* Score Gauge card */}
          <div className="card">
            <h3 className="mb-2">Fraud Risk Score</h3>
            <ScoreGauge score={analysis.fraud_score} riskLabel={analysis.risk_label} />
            <div className="divider" />
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <div className="stat-card">
                <span className="stat-label">Flagged Items</span>
                <span className="stat-value text-red">{flaggedItems.length}</span>
                <span className="stat-sub">of {allItems.length} total</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Rule Violations</span>
                <span className="stat-value text-amber">{analysis.rule_violations_count}</span>
                <span className="stat-sub">deterministic checks</span>
              </div>
            </div>
          </div>

          {/* Overcharge estimate card */}
          <div className="card">
            <h3 className="mb-2">Financial Impact</h3>
            <div style={{ marginBottom: '1.5rem' }}>
              <div className="stat-label mb-1">Estimated Potential Overcharge</div>
              <div style={{ fontSize: '2.5rem', fontWeight: 800, color: overcharge > 0 ? 'var(--red-400)' : 'var(--green-400)', lineHeight: 1 }}>
                <IndianRupee size={24} style={{ display: 'inline', verticalAlign: 'middle' }} />
                {overcharge.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <small>Based on p75 benchmark upper bound per procedure</small>
            </div>
            <div className="divider" />
            <div className="grid-2" style={{ gap: '0.75rem' }}>
              <div className="stat-card">
                <span className="stat-label">Anomaly Signals</span>
                <span className="stat-value text-amber">{analysis.anomaly_signals_count}</span>
                <span className="stat-sub">statistical flags</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Disputed</span>
                <span className="stat-value text-teal">{disputedCount}</span>
                <span className="stat-sub">items marked</span>
              </div>
            </div>
          </div>
        </div>

        {/* Category chart */}
        {flaggedItems.length > 0 && <DeviationChart items={flaggedItems} />}

        {/* Line items tabs */}
        <div className="card mt-3">
          <div className="tabs">
            <button className={`tab-btn ${tab === 'flagged' ? 'active' : ''}`} onClick={() => setTab('flagged')}>
              Flagged Items ({flaggedItems.length})
            </button>
            <button className={`tab-btn ${tab === 'all' ? 'active' : ''}`} onClick={() => setTab('all')}>
              All Items ({allItems.length})
            </button>
          </div>

          {tab === 'flagged' && (
            <div className="flex-col gap-2">
              {flaggedItems.length === 0 && (
                <div className="text-center" style={{ padding: '2rem', color: 'var(--text-muted)' }}>
                  <CheckCircle size={32} color="var(--green-400)" style={{ margin: '0 auto 0.75rem' }} />
                  No flagged items. Your bill looks clean!
                </div>
              )}
              {flaggedItems
                .sort((a, b) => ({ HIGH: 3, MEDIUM: 2, LOW: 1 }[b.severity] - { HIGH: 3, MEDIUM: 2, LOW: 1 }[a.severity]))
                .map(item => (
                  <LineItemCard key={item.item_id} item={item} onAction={handleAction} actionState={actions} />
                ))}
            </div>
          )}

          {tab === 'all' && (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Category</th>
                    <th>Qty</th>
                    <th>Unit Price</th>
                    <th>Total</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {allItems.map(item => {
                    const flagged = flaggedItems.find(f => f.item_id === item.item_id)
                    return (
                      <tr key={item.id}>
                        <td style={{ maxWidth: 240 }} className="truncate">{item.raw_description}</td>
                        <td><span className="badge badge-info" style={{ fontSize: '0.65rem' }}>{item.mapped_category}</span></td>
                        <td>{item.quantity}</td>
                        <td>₹{item.unit_price?.toLocaleString('en-IN') ?? '—'}</td>
                        <td>₹{item.total_price?.toLocaleString('en-IN') ?? '—'}</td>
                        <td>
                          {flagged
                            ? <span className={`badge ${badgeClass(flagged.severity)}`}>{flagged.severity}</span>
                            : <span className="badge badge-low">OK</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div style={{ height: '4rem' }} />
      </div>
    </div>
  )
}

// ── Deviation bar chart ────────────────────────────────────────────────────
function DeviationChart({ items }) {
  const data = items
    .filter(i => i.price_deviation_percentage != null)
    .slice(0, 8)
    .map(i => ({
      name: i.raw_description.substring(0, 18) + (i.raw_description.length > 18 ? '…' : ''),
      deviation: Math.round(i.price_deviation_percentage),
    }))
    .sort((a, b) => b.deviation - a.deviation)

  if (!data.length) return null

  return (
    <div className="card mt-2" style={{ padding: '1.5rem' }}>
      <h3 className="mb-1">Price Deviation vs. Regional Median (%)</h3>
      <p style={{ fontSize: '0.83rem', marginBottom: '1rem' }}>
        Green = below median, Red = above median. Bars show % difference from CGHS benchmark.
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 0, right: 30 }}>
          <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickFormatter={v => `${v}%`} />
          <YAxis type="category" dataKey="name" width={140} tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
          <Tooltip
            formatter={(v) => [`${v}%`, 'Deviation']}
            contentStyle={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: 'var(--text-primary)' }}
          />
          <Bar dataKey="deviation" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.deviation > 75 ? 'var(--red-400)' : d.deviation > 30 ? 'var(--amber-400)' : 'var(--teal-400)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
