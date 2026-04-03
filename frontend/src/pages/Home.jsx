import { useNavigate } from 'react-router-dom'
import { Shield, Zap, Eye, FileText, ArrowRight, CheckCircle } from 'lucide-react'

const features = [
  { icon: <Zap size={22} />, title: 'Instant Analysis', desc: 'Upload your bill and get a full fraud score in under 60 seconds. No waiting, no manual review.' },
  { icon: <Eye size={22} />, title: 'Full Transparency', desc: 'Every flagged item comes with a plain-language explanation referencing real benchmark price data.' },
  { icon: <Shield size={22} />, title: 'Rules + Statistics', desc: 'Hybrid engine: rule-based duplicate detection combined with z-score statistical anomaly detection.' },
  { icon: <FileText size={22} />, title: 'Dispute Reports', desc: 'Generate a formatted dispute report you can submit to your insurer or hospital billing department.' },
]

const how = [
  { step: '01', title: 'Upload Your Bill', desc: 'Paste JSON or upload your itemized hospital bill' },
  { step: '02', title: 'AI Analysis', desc: 'Our engine checks prices, detects duplicates, flags anomalies' },
  { step: '03', title: 'Review Results', desc: 'See your fraud score and each flagged item explained' },
  { step: '04', title: 'Take Action', desc: 'Mark items for dispute and export your evidence report' },
]

export default function Home() {
  const navigate = useNavigate()
  return (
    <div className="page">
      <div className="container">
        {/* Hero */}
        <div className="hero animate-in">
          <div className="hero-eyebrow">
            <Shield size={13} /> AI-Powered Protection
          </div>
          <h1 className="hero-title">
            Don't Overpay for<br /><span>Hospital Bills</span>
          </h1>
          <p className="hero-desc">
            BillGuard AI analyzes your itemized hospital billing statement using benchmark
            price data and statistical anomaly detection — surfacing overcharges and duplicate
            entries in plain language, so you know exactly what to dispute.
          </p>
          <div className="flex gap-1" style={{ flexWrap: 'wrap' }}>
            <button className="btn btn-primary btn-lg" onClick={() => navigate('/upload')}>
              Analyze My Bill <ArrowRight size={18} />
            </button>
            <button className="btn btn-ghost btn-lg" onClick={() => navigate('/upload')}>
              Try Demo Bill
            </button>
          </div>

          {/* Trust indicators */}
          <div className="flex gap-2 mt-4" style={{ flexWrap: 'wrap' }}>
            {['No data sold', 'Audit-logged', 'Based on CGHS rates', 'No auto-escalation'].map(t => (
              <div key={t} className="flex gap-1" style={{ alignItems: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <CheckCircle size={13} color="var(--green-400)" /> {t}
              </div>
            ))}
          </div>
        </div>

        <div className="divider" />

        {/* How it works */}
        <div className="mt-4 mb-3">
          <h2 className="mb-1">How It Works</h2>
          <p className="mb-3">Four steps from upload to dispute report.</p>
          <div className="grid-4">
            {how.map((h) => (
              <div key={h.step} className="card card-sm" style={{ position: 'relative', overflow: 'hidden' }}>
                <div style={{
                  fontSize: '3rem', fontWeight: 800, color: 'rgba(46,196,182,0.08)',
                  position: 'absolute', top: '0.5rem', right: '0.75rem', lineHeight: 1,
                  fontFamily: 'var(--font-mono)',
                }}>{h.step}</div>
                <div style={{ color: 'var(--teal-400)', marginBottom: '0.5rem', fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Step {h.step}</div>
                <h4 className="mb-1">{h.title}</h4>
                <p style={{ fontSize: '0.83rem' }}>{h.desc}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="divider" />

        {/* Features */}
        <div className="mt-4 mb-3" style={{ paddingBottom: '4rem' }}>
          <h2 className="mb-1">Built for Real Bills</h2>
          <p className="mb-3">No machine learning dependency. No black-box scores. Every signal is explainable.</p>
          <div className="grid-2">
            {features.map((f) => (
              <div key={f.title} className="card" style={{ display: 'flex', gap: '1rem' }}>
                <div style={{
                  width: 44, height: 44, borderRadius: 'var(--radius-sm)',
                  background: 'rgba(46,196,182,0.1)', border: '1px solid rgba(46,196,182,0.2)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'var(--teal-400)', flexShrink: 0,
                }}>{f.icon}</div>
                <div>
                  <h4 className="mb-1">{f.title}</h4>
                  <p style={{ fontSize: '0.875rem' }}>{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
