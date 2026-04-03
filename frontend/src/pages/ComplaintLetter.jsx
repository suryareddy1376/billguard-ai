import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Download, FileText, Phone, ExternalLink,
  Scale, Shield, AlertTriangle, Globe, Copy, Check,
} from 'lucide-react'
import { getComplaintLetter } from '../api'
import { Document, Packer, Paragraph, TextRun } from 'docx'
import { saveAs } from 'file-saver'

export default function ComplaintLetter() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lang, setLang] = useState('en')
  const [copied, setCopied] = useState(false)

  const getLetterText = (language, dataObj) => {
    if (!dataObj) return ''
    switch(language) {
      case 'hi': return dataObj.letter_body_hindi || ''
      case 'mr': return dataObj.letter_body_marathi || ''
      case 'ta': return dataObj.letter_body_tamil || ''
      case 'te': return dataObj.letter_body_telugu || ''
      case 'bn': return dataObj.letter_body_bengali || ''
      case 'kn': return dataObj.letter_body_kannada || ''
      default: return dataObj.letter_body || ''
    }
  }

  useEffect(() => {
    getComplaintLetter(jobId)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Could not generate complaint letter'))
      .finally(() => setLoading(false))
  }, [jobId])

  const handleExportDocx = async () => {
    const text = getLetterText(lang, data)
    const doc = new Document({
      sections: [{
        properties: {},
        children: text.split('\n').map(line => new Paragraph({
          children: [new TextRun({ text: line, size: 24 })], // 24 half-points = 12pt
          spacing: { after: 120 }
        }))
      }]
    })
    const blob = await Packer.toBlob(doc)
    saveAs(blob, `Complaint_Letter_${data.report_id}.docx`)
  }

  const handleCopy = async () => {
    const text = getLetterText(lang, data)
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

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

  const letterText = getLetterText(lang, data)

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 900 }}>
        {/* Actions bar */}
        <div className="flex-between mt-3 mb-3 no-print" style={{ flexWrap: 'wrap', gap: '1rem' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/dashboard/${jobId}`)}>
            <ArrowLeft size={14} /> Back to Dashboard
          </button>
          <div className="flex gap-1">
            <button className="btn btn-ghost btn-sm" onClick={handleCopy}>
              {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy Letter</>}
            </button>
            <button className="btn btn-primary btn-sm" onClick={handleExportDocx}>
              <Download size={14} /> Export .docx
            </button>
          </div>
        </div>

        {/* Header card */}
        <div className="card animate-in mb-3 no-print">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
            <div>
              <div className="flex gap-1" style={{ alignItems: 'center', marginBottom: '0.5rem' }}>
                <Scale size={20} color="var(--teal-400)" />
                <span className="text-teal" style={{ fontWeight: 700, fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  Legal Complaint Generator
                </span>
              </div>
              <h2 className="mb-1">Formal Dispute Letter</h2>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Report: {data.report_id} · Hospital: {data.hospital_name}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: data.total_overcharge_estimate > 0 ? 'var(--red-400)' : 'var(--green-400)', lineHeight: 1 }}>
                ₹{data.total_overcharge_estimate?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>estimated overcharge</div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid-4 mb-3" style={{ gap: '0.75rem' }}>
            <div className="stat-card">
              <span className="stat-label">Overcharged Items</span>
              <span className="stat-value text-red">{data.total_overcharged_items}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Total Flagged</span>
              <span className="stat-value text-amber">{data.total_flagged}</span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Fraud Score</span>
              <span className="stat-value" style={{ color: data.fraud_score >= 61 ? 'var(--red-400)' : data.fraud_score >= 31 ? 'var(--amber-400)' : 'var(--green-400)' }}>
                {data.fraud_score}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-label">Risk Level</span>
              <span className={`badge ${data.risk_label === 'CRITICAL' ? 'badge-critical' : data.risk_label === 'HIGH' ? 'badge-critical' : data.risk_label === 'MODERATE' ? 'badge-moderate' : 'badge-low'}`}>
                {data.risk_label}
              </span>
            </div>
          </div>

          {/* Overcharged items table */}
          {data.items.length > 0 && (
            <>
              <h4 className="mb-2">Overcharged Line Items</h4>
              <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Procedure</th>
                      <th>Your Price</th>
                      <th>CGHS Rate</th>
                      <th>Excess</th>
                      <th>% Above</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((item, i) => (
                      <tr key={i}>
                        <td style={{ maxWidth: 200 }} className="truncate">{item.description}</td>
                        <td style={{ color: 'var(--red-400)', fontWeight: 600 }}>₹{item.charged?.toLocaleString('en-IN')}</td>
                        <td style={{ color: 'var(--green-400)' }}>₹{item.benchmark?.toLocaleString('en-IN')}</td>
                        <td style={{ fontWeight: 600 }}>₹{item.difference?.toLocaleString('en-IN')}</td>
                        <td>
                          <span className="badge badge-critical" style={{ fontSize: '0.7rem' }}>
                            +{item.deviation_pct}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {data.items.length === 0 && (
            <div className="alert alert-success mb-3">
              <Shield size={16} />
              No items exceeded CGHS benchmark rates. Your bill appears fairly priced — a complaint letter may not be necessary.
            </div>
          )}
        </div>

        {/* Language toggle + Letter */}
        <div className="card animate-in mb-3">
          <div className="flex-between mb-2 no-print">
            <h3 className="flex gap-1" style={{ alignItems: 'center' }}>
              <FileText size={18} /> Generated Complaint Letter
            </h3>
            <div className="tabs" style={{ borderBottom: 'none', paddingBottom: 0, gap: '0.2rem', overflowX: 'auto', display: 'flex' }}>
              <button className={`tab-btn ${lang === 'en' ? 'active' : ''}`} onClick={() => setLang('en')}>English</button>
              <button className={`tab-btn ${lang === 'hi' ? 'active' : ''}`} onClick={() => setLang('hi')}>हिन्दी</button>
              <button className={`tab-btn ${lang === 'mr' ? 'active' : ''}`} onClick={() => setLang('mr')}>मराठी</button>
              <button className={`tab-btn ${lang === 'te' ? 'active' : ''}`} onClick={() => setLang('te')}>తెలుగు</button>
              <button className={`tab-btn ${lang === 'ta' ? 'active' : ''}`} onClick={() => setLang('ta')}>தமிழ்</button>
              <button className={`tab-btn ${lang === 'bn' ? 'active' : ''}`} onClick={() => setLang('bn')}>বাংলা</button>
              <button className={`tab-btn ${lang === 'kn' ? 'active' : ''}`} onClick={() => setLang('kn')}>ಕನ್ನಡ</button>
            </div>
          </div>

          <div className="letter-content" style={{
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            padding: '2rem',
            fontFamily: lang === 'en' ? 'var(--font-body)' : 'inherit',
            fontSize: '0.88rem',
            lineHeight: 1.8,
            whiteSpace: 'pre-wrap',
            color: 'var(--text-secondary)',
          }}>
            {letterText}
          </div>

          <div className="flex gap-1 mt-2 no-print" style={{ flexWrap: 'wrap' }}>
            <button className="btn btn-primary btn-sm" onClick={handleExportDocx}>
              <Download size={14} /> Export as .docx
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleCopy}>
              {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy to Clipboard</>}
            </button>
          </div>
        </div>

        {/* Helplines & Legal Resources */}
        <div className="grid-2 mb-3 no-print" style={{ gap: '1.5rem' }}>
          {/* Helplines */}
          <div className="card animate-in">
            <h3 className="flex gap-1 mb-2" style={{ alignItems: 'center' }}>
              <Phone size={18} color="var(--teal-400)" /> Consumer Helplines
            </h3>
            <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Contact these authorities to escalate your complaint:
            </p>
            {data.helplines.map((h, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.75rem', borderRadius: 'var(--radius-sm)',
                background: 'rgba(255,255,255,0.02)', marginBottom: '0.5rem',
                border: '1px solid var(--border)',
              }}>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{h.name}</div>
                  {h.number && <div style={{ fontSize: '0.8rem', color: 'var(--teal-400)', fontFamily: 'var(--font-mono)' }}>{h.number}</div>}
                </div>
                {h.url && (
                  <a href={h.url} target="_blank" rel="noopener noreferrer" className="btn btn-ghost btn-sm" style={{ textDecoration: 'none' }}>
                    <ExternalLink size={13} /> Visit
                  </a>
                )}
              </div>
            ))}
          </div>

          {/* Legal refs */}
          <div className="card animate-in">
            <h3 className="flex gap-1 mb-2" style={{ alignItems: 'center' }}>
              <Scale size={18} color="var(--amber-400)" /> Legal References
            </h3>
            <p style={{ fontSize: '0.83rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Your rights under Indian law:
            </p>
            {data.legal_references.map((ref, i) => (
              <div key={i} style={{
                padding: '0.75rem', borderRadius: 'var(--radius-sm)',
                background: 'rgba(255,255,255,0.02)', marginBottom: '0.5rem',
                fontSize: '0.83rem', lineHeight: 1.6,
                borderLeft: '3px solid var(--amber-400)',
                color: 'var(--text-secondary)',
              }}>
                {ref}
              </div>
            ))}
          </div>
        </div>

        {/* Disclaimer */}
        <div className="card mb-3 no-print" style={{ padding: '1rem', fontSize: '0.78rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
          <strong style={{ color: 'var(--text-secondary)' }}>Disclaimer: </strong>
          This complaint letter is auto-generated by BillGuard AI for reference purposes only.
          It should be reviewed and customized before submission. Consult a legal professional for
          specific advice. BillGuard AI is not a legal service provider.
        </div>

        <div style={{ height: '3rem' }} />
      </div>
    </div>
  )
}
