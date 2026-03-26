import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, XCircle, User, Stethoscope, FileText, AlertTriangle, Tag } from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import ErrorBanner from '../components/ErrorBanner'
import FaxDocumentViewer from '../components/FaxDocumentViewer'
import { getReferral, approveReferral, rejectReferral } from '../services/api'

const DOC_TYPE_STYLES = {
  referral: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Referral' },
  labs_imaging: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Labs & Imaging' },
  insurance_auth: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Insurance Auth' },
  medication_prior_auth: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Med Prior Auth' },
  dme: { bg: 'bg-teal-100', text: 'text-teal-700', label: 'DME' },
  sleep_study_results: { bg: 'bg-indigo-100', text: 'text-indigo-700', label: 'Sleep Study' },
  medical_records: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Medical Records' },
  other: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Other' },
}

const VIEWABLE_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'tif']

export default function ReferralDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [referral, setReferral] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState(null)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [docCollapsed, setDocCollapsed] = useState(false)

  useEffect(() => {
    getReferral(id)
      .then(setReferral)
      .catch((e) => setError(`Failed to load referral: ${e.message}`))
      .finally(() => setLoading(false))
  }, [id])

  const handleApprove = async () => {
    setActing(true)
    try {
      const updated = await approveReferral(id)
      setReferral(updated)
    } catch (err) {
      setError(`Approve failed: ${err.message}`)
    }
    setActing(false)
  }

  const handleReject = async () => {
    setActing(true)
    setShowRejectModal(false)
    try {
      const updated = await rejectReferral(id, rejectReason)
      setReferral(updated)
      setRejectReason('')
    } catch (err) {
      setError(`Reject failed: ${err.message}`)
    }
    setActing(false)
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading...</p>
  if (!referral && error) return (
    <div className="space-y-4 py-12">
      <ErrorBanner message={error} onDismiss={() => navigate(-1)} />
    </div>
  )
  if (!referral) return null

  const d = referral.extracted_data || {}
  const docType = referral.document_type || 'referral'
  const typeStyle = DOC_TYPE_STYLES[docType] || DOC_TYPE_STYLES.other
  const isReferral = docType === 'referral'

  const fileExt = referral.filename?.split('.').pop()?.toLowerCase() || ''
  const canViewDoc = VIEWABLE_EXTENSIONS.includes(fileExt)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{isReferral ? 'Referral' : 'Document'} {referral.id}</h1>
            <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${typeStyle.bg} ${typeStyle.text}`}>
              {typeStyle.label}
            </span>
            <StatusBadge status={referral.status} />
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{referral.filename}</p>
        </div>
        {referral.status === 'review' && isReferral && (
          <div className="flex items-center gap-2">
            <button onClick={handleApprove} disabled={acting} className="btn-success flex items-center gap-2">
              <CheckCircle2 size={16} />
              Approve & Push to EMR
            </button>
            <button onClick={() => setShowRejectModal(true)} disabled={acting} className="btn-danger flex items-center gap-2">
              <XCircle size={16} />
              Reject
            </button>
          </div>
        )}
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {referral.error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 flex items-center gap-3">
          <AlertTriangle size={18} className="text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-700">Processing Error</p>
            <p className="text-sm text-red-600">{referral.error}</p>
          </div>
        </div>
      )}

      {/* Side-by-side: Document viewer + Extracted data */}
      <div className={`grid gap-6 ${canViewDoc && !docCollapsed ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1'}`}>
        {/* Left: Original document viewer */}
        {canViewDoc && (
          <div className={`${docCollapsed ? '' : 'xl:sticky xl:top-4 xl:self-start'}`}>
            <div className={`card p-0 overflow-hidden ${docCollapsed ? '' : 'min-h-[400px]'}`}>
              <FaxDocumentViewer
                filename={referral.filename}
                collapsed={docCollapsed}
                onToggle={() => setDocCollapsed(!docCollapsed)}
              />
            </div>
          </div>
        )}

        {/* Right: Extracted data panels */}
        <div className="space-y-6">
          {/* Referral-specific panels */}
          {isReferral && (
            <>
              {/* Patient info */}
              <div className="card">
                <div className="flex items-center gap-2 mb-4">
                  <User size={18} className="text-brand-500" />
                  <h2 className="font-semibold text-gray-900">Patient Information</h2>
                </div>
                <div className="space-y-3">
                  <Field label="Name" value={`${d.patient_first_name || ''} ${d.patient_last_name || ''}`} />
                  <Field label="Date of Birth" value={d.patient_dob} />
                  <Field label="Gender" value={d.patient_gender} />
                  <Field label="Phone" value={d.patient_phone} />
                  <Field label="Address" value={
                    [d.patient_address_line, d.patient_address_city, d.patient_address_state, d.patient_address_zip]
                      .filter(Boolean).join(', ')
                  } />
                  <Field label="Insurance" value={d.insurance_name} />
                  <Field label="Insurance ID" value={d.insurance_id} />
                </div>
              </div>

              {/* Referral info */}
              <div className="card">
                <div className="flex items-center gap-2 mb-4">
                  <Stethoscope size={18} className="text-brand-500" />
                  <h2 className="font-semibold text-gray-900">Referral Details</h2>
                </div>
                <div className="space-y-3">
                  <Field label="Referring Provider" value={d.referring_provider} />
                  <Field label="Practice" value={d.referring_practice} />
                  <Field label="Phone" value={d.referring_phone} />
                  <Field label="Fax" value={d.referring_fax} />
                  <Field label="Reason" value={d.reason} />
                  <Field label="Urgency" value={d.urgency} highlight={d.urgency !== 'routine'} />
                  <Field label="Notes" value={d.notes} />
                </div>
              </div>
            </>
          )}

          {/* Non-referral: show raw OCR text */}
          {!isReferral && referral.raw_text && (
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <FileText size={18} className="text-brand-500" />
                <h2 className="font-semibold text-gray-900">Document Content (OCR)</h2>
              </div>
              <pre className="text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 rounded-lg p-4 max-h-96 overflow-y-auto font-mono leading-relaxed">
                {referral.raw_text}
              </pre>
            </div>
          )}

          {/* Diagnosis codes */}
          {d.diagnosis_codes?.length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <FileText size={18} className="text-brand-500" />
                <h2 className="font-semibold text-gray-900">Diagnosis Codes</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {d.diagnosis_codes.map((dx, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg px-4 py-3">
                    <p className="text-sm font-mono font-semibold text-brand-600">{dx.code}</p>
                    <p className="text-sm text-gray-600">{dx.display}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Meta */}
          <div className="card">
            <h2 className="font-semibold text-gray-900 mb-3">Processing Details</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Uploaded</p>
                <p className="font-medium">{new Date(referral.uploaded_at).toLocaleString()}</p>
              </div>
              {referral.completed_at && (
                <div>
                  <p className="text-gray-500">Completed</p>
                  <p className="font-medium">{new Date(referral.completed_at).toLocaleString()}</p>
                </div>
              )}
              {referral.patient_id && (
                <div>
                  <p className="text-gray-500">EMR Patient ID</p>
                  <p className="font-medium font-mono">{referral.patient_id}</p>
                </div>
              )}
              {referral.service_request_id && (
                <div>
                  <p className="text-gray-500">Service Request ID</p>
                  <p className="font-medium font-mono">{referral.service_request_id}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setShowRejectModal(false)}>
          <div className="bg-white rounded-xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 mb-3">Reject Referral</h3>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Rejection reason (optional)"
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent mb-4"
              autoFocus
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowRejectModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleReject} className="btn-danger">Reject</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, value, highlight = false }) {
  return (
    <div className="flex items-start">
      <span className="text-xs text-gray-500 w-28 flex-shrink-0 pt-0.5">{label}</span>
      <span className={`text-sm ${highlight ? 'font-semibold text-red-600' : 'text-gray-800'}`}>
        {value || <span className="text-gray-300">—</span>}
      </span>
    </div>
  )
}
