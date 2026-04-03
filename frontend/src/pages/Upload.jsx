import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload as UploadIcon, FileJson, Zap, ArrowRight, AlertCircle, Loader } from 'lucide-react'
import { uploadBill, getSampleBill } from '../api'
import { AuthContext } from '../context/AuthContext'
import { useContext } from 'react'

const PLACEHOLDER_BILL = `{
  "patient_id": "PT-001",
  "hospital_name": "City General Hospital",
  "date_of_service": "2024-03-15",
  "line_items": [
    { "description": "MRI Brain Plain",   "unit_price": 22000, "quantity": 1 },
    { "description": "MRI Brain Plain",   "unit_price": 22000, "quantity": 1 },
    { "description": "ICU Charges",       "unit_price": 18000, "quantity": 3 },
    { "description": "Room Charge",       "unit_price": 4500,  "quantity": 3 },
    { "description": "CBC Blood Test",    "unit_price": 800,   "quantity": 1 },
    { "description": "CT Scan Abdomen",   "unit_price": 9500,  "quantity": 1 },
    { "description": "Doctor Consultation", "unit_price": 2500, "quantity": 1 }
  ]
}`

export default function Upload() {
  const navigate = useNavigate()
  const { user } = useContext(AuthContext)
  const [patientId, setPatientId]     = useState('')
  const [hospitalName, setHospital]   = useState('')
  const [billJson, setBillJson]       = useState('')
  const [fileMode, setFileMode]       = useState(false)
  const [file, setFile]               = useState(null)
  const [error, setError]             = useState('')
  const [loading, setLoading]         = useState(false)
  const [loadingDemo, setLoadingDemo] = useState(false)
  const textareaRef = useRef(null)

  const handleLoadDemo = async (scenario) => {
    setLoadingDemo(true)
    try {
      const res = await getSampleBill(scenario)
      const bill = res.data.bill
      setBillJson(JSON.stringify(bill, null, 2))
      setPatientId(bill.patient_id)
      setHospital(bill.hospital_name)
    } catch {
      setError('Could not load demo bill. Is the backend running?')
    } finally {
      setLoadingDemo(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (fileMode) {
      if (!file) { setError('Please select a bill image or PDF.'); return }
    } else {
      if (!billJson.trim()) { setError('Please paste your bill JSON or load a demo.'); return }
      try { JSON.parse(billJson) } catch { setError('Invalid JSON. Please check the bill format.'); return }
    }
    if (!patientId.trim()) { setError('Patient ID is required.'); return }

    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('patient_id', patientId)
      fd.append('hospital_name', hospitalName || 'Unknown Hospital')
      if (user) {
        fd.append('user_id', user.id)
      }
      if (fileMode) {
        fd.append('file', file)
      } else {
        fd.append('bill_json', billJson)
      }
      const res = await uploadBill(fd)
      navigate(`/dashboard/${res.data.job_id}`)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed. Ensure the backend is running on port 8000.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="container" style={{ maxWidth: 820 }}>
        <div className="hero animate-in" style={{ paddingBottom: '1.5rem' }}>
          <div className="hero-eyebrow"><UploadIcon size={13} /> Bill Upload</div>
          <h1 className="hero-title">Analyze Your <span>Hospital Bill</span></h1>
          <p>Paste your itemized bill in JSON format or load a demo scenario below.</p>
        </div>

        <div className="card animate-in">
          {/* Demo loaders */}
          <div className="flex gap-1 mb-3" style={{ flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.83rem', color: 'var(--text-muted)', alignSelf: 'center' }}>Load demo:</span>
            <button className="btn btn-ghost btn-sm" onClick={() => handleLoadDemo('moderate')} disabled={loadingDemo}>
              <Zap size={13} /> Moderate Risk Bill
            </button>
            <button className="btn btn-danger btn-sm" onClick={() => handleLoadDemo('fraud')} disabled={loadingDemo}>
              <AlertCircle size={13} /> High Fraud Bill
            </button>
            {loadingDemo && <span className="spinner" />}
          </div>

          <div className="divider" />

          <form onSubmit={handleSubmit}>
            <div className="grid-2">
              <div className="form-group">
                <label htmlFor="patient-id">Patient ID *</label>
                <input
                  id="patient-id"
                  type="text"
                  placeholder="e.g. PT-2024-001"
                  value={patientId}
                  onChange={e => setPatientId(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="hospital-name">Hospital Name</label>
                <input
                  id="hospital-name"
                  type="text"
                  placeholder="e.g. City General Hospital"
                  value={hospitalName}
                  onChange={e => setHospital(e.target.value)}
                />
              </div>
            </div>

            {/* Input Method Toggle */}
            <div className="tabs mb-2" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
              <button type="button" className={`tab-btn ${!fileMode ? 'active' : ''}`} onClick={() => {setFileMode(false); setFile(null)}}>
                <FileJson size={14} style={{ display: 'inline', marginRight: 4 }} /> Paste JSON
              </button>
              <button type="button" className={`tab-btn ${fileMode ? 'active' : ''}`} onClick={() => {setFileMode(true); setBillJson('')}}>
                <UploadIcon size={14} style={{ display: 'inline', marginRight: 4 }} /> Upload Image/PDF
              </button>
            </div>

            {/* Input Area */}
            {fileMode ? (
              <div className="form-group">
                <label>Bill Image / PDF *</label>
                <div style={{
                  border: '2px dashed var(--border)', borderRadius: 'var(--radius-md)',
                  padding: '2rem', textAlign: 'center', background: 'rgba(255,255,255,0.02)'
                }}>
                  <input
                    type="file"
                    accept="image/png, image/jpeg, application/pdf"
                    onChange={e => setFile(e.target.files[0])}
                    style={{ display: 'block', margin: '0 auto' }}
                  />
                  <small style={{ display: 'block', marginTop: '0.5rem' }}>Powered by OCR Engine</small>
                </div>
              </div>
            ) : (
              <div className="form-group">
                <label htmlFor="bill-json">Bill JSON *</label>
                <textarea
                  id="bill-json"
                  ref={textareaRef}
                  placeholder={PLACEHOLDER_BILL}
                  value={billJson}
                  onChange={e => setBillJson(e.target.value)}
                  style={{ minHeight: 180, fontFamily: 'var(--font-mono)', fontSize: '0.8rem', lineHeight: 1.6 }}
                />
              </div>
            )}

            {error && (
              <div className="alert alert-critical mb-2">
                <AlertCircle size={16} style={{ flexShrink: 0, marginTop: 2 }} />
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary btn-lg w-full" disabled={loading}>
              {loading ? (
                <><span className="spinner" /> Analyzing...</>
              ) : (
                <>Analyze Bill <ArrowRight size={18} /></>
              )}
            </button>
          </form>
        </div>

        {/* Format reference */}
        {!fileMode && (
        <div className="card mt-3" style={{ padding: '1.25rem' }}>
          <h4 className="mb-2">Expected JSON Format</h4>
          <pre style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)', overflowX: 'auto' }}>{`{
  "patient_id": "PT-001",
  "hospital_name": "Hospital Name",
  "date_of_service": "YYYY-MM-DD",
  "line_items": [
    {
      "description": "Procedure name",
      "unit_price": 5000,       ← per unit in INR
      "quantity": 1             ← optional, defaults to 1
  ]
}
`}</pre>
        </div>
        )}
      </div>
    </div>
  )
}
