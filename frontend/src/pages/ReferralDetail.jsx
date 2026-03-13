import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, XCircle, User, Stethoscope, FileText, AlertTriangle } from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import { getReferral, approveReferral, rejectReferral } from '../services/api'

export default function ReferralDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [referral, setReferral] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)

  useEffect(() => {
    getReferral(id)
      .then(setReferral)
      .catch(() => navigate('/referrals'))
      .finally(() => setLoading(false))
  }, [id])

  const handleApprove = async () => {
    setActing(true)
    try {
      const updated = await approveReferral(id)
      setReferral(updated)
    } catch (err) {
      alert(err.message)
    }
    setActing(false)
  }

  const handleReject = async () => {
    const reason = prompt('Rejection reason (optional):')
    setActing(true)
    try {
      const updated = await rejectReferral(id, reason)
      setReferral(updated)
    } catch (err) {
      alert(err.message)
    }
    setActing(false)
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading...</p>
  if (!referral) return null

  const d = referral.extracted_data || {}

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/referrals')} className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">Referral {referral.id}</h1>
            <StatusBadge status={referral.status} />
          </div>
          <p className="text-sm text-gray-500 mt-0.5">{referral.filename}</p>
        </div>
        {referral.status === 'review' && (
          <div className="flex items-center gap-2">
            <button onClick={handleApprove} disabled={acting} className="btn-success flex items-center gap-2">
              <CheckCircle2 size={16} />
              Approve & Push to eCW
            </button>
            <button onClick={handleReject} disabled={acting} className="btn-danger flex items-center gap-2">
              <XCircle size={16} />
              Reject
            </button>
          </div>
        )}
      </div>

      {referral.error && (
        <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4 flex items-center gap-3">
          <AlertTriangle size={18} className="text-red-500" />
          <p className="text-sm text-red-700">{referral.error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

        {/* Diagnosis codes */}
        {d.diagnosis_codes?.length > 0 && (
          <div className="card lg:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <FileText size={18} className="text-brand-500" />
              <h2 className="font-semibold text-gray-900">Diagnosis Codes</h2>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
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
        <div className="card lg:col-span-2">
          <h2 className="font-semibold text-gray-900 mb-3">Processing Details</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
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
                <p className="text-gray-500">eCW Patient ID</p>
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
