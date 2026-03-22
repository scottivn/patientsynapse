import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  FileText, Filter, Phone, Tag, FlaskConical, ShieldCheck,
  FolderOpen, HelpCircle, RefreshCw, Inbox,
} from 'lucide-react'
import FileUpload from '../components/FileUpload'
import StatusBadge from '../components/StatusBadge'
import ErrorBanner from '../components/ErrorBanner'
import { listReferrals, uploadReferralFile, uploadReferralText, pollFaxes, getFaxStatus, getStatus } from '../services/api'

const STATUSES = ['all', 'review', 'processing', 'completed', 'failed', 'rejected']

const DOC_TYPES = [
  { value: null, label: 'All Types', icon: Tag },
  { value: 'referral', label: 'Referrals', icon: FileText },
  { value: 'lab_result', label: 'Lab Results', icon: FlaskConical },
  { value: 'insurance_auth', label: 'Insurance Auth', icon: ShieldCheck },
  { value: 'medical_records', label: 'Medical Records', icon: FolderOpen },
  { value: 'other', label: 'Other', icon: HelpCircle },
]

const DOC_TYPE_STYLES = {
  referral: { bg: 'bg-blue-100', text: 'text-blue-700', label: 'Referral' },
  lab_result: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Lab Result' },
  insurance_auth: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'Insurance Auth' },
  medical_records: { bg: 'bg-purple-100', text: 'text-purple-700', label: 'Medical Records' },
  other: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'Other' },
}

export default function FaxInbox() {
  const [faxes, setFaxes] = useState([])
  const [filter, setFilter] = useState('all')
  const [docTypeFilter, setDocTypeFilter] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showTextInput, setShowTextInput] = useState(false)
  const [textInput, setTextInput] = useState('')
  const [fetching, setFetching] = useState(false)
  const [faxStatus, setFaxStatus] = useState(null)
  const [emrName, setEmrName] = useState('EMR')
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    listReferrals(filter === 'all' ? null : filter, docTypeFilter)
      .then(setFaxes)
      .catch((e) => { setFaxes([]); setError(`Failed to load faxes: ${e.message}`) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter, docTypeFilter])

  useEffect(() => {
    getFaxStatus().then(setFaxStatus).catch(() => {})
    getStatus()
      .then((s) => setEmrName(s?.emr_provider || 'EMR'))
      .catch(() => {})
  }, [])

  const handleFetchFaxes = async () => {
    setFetching(true)
    setError(null)
    try {
      const result = await pollFaxes()
      if (result.referrals?.length) {
        setFaxes((prev) => [...result.referrals, ...prev])
      }
      setFaxStatus(result.status)
    } catch (e) {
      setError(`Fax fetch failed: ${e.message}`)
    } finally {
      setFetching(false)
    }
  }

  const handleFileUpload = async (file) => {
    setError(null)
    try {
      const result = await uploadReferralFile(file)
      setFaxes((prev) => [result, ...prev])
    } catch (e) {
      setError(`File upload failed: ${e.message}`)
    }
  }

  const handleTextUpload = async () => {
    if (!textInput.trim()) return
    setError(null)
    try {
      const result = await uploadReferralText(textInput, 'manual-entry.txt')
      setFaxes((prev) => [result, ...prev])
      setTextInput('')
      setShowTextInput(false)
    } catch (e) {
      setError(`Text upload failed: ${e.message}`)
    }
  }

  const typeCounts = faxes.reduce((acc, r) => {
    const t = r.document_type || 'other'
    acc[t] = (acc[t] || 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fax Inbox</h1>
          <p className="text-sm text-gray-500 mt-1">
            Incoming faxes auto-pulled from {emrName}, scanned and organized by LLM
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleFetchFaxes}
            disabled={fetching}
            className="btn-primary text-sm flex items-center gap-2"
          >
            {fetching ? <RefreshCw size={14} className="animate-spin" /> : <Phone size={16} />}
            {fetching ? 'Fetching...' : 'Pull Now'}
          </button>
          <button
            onClick={() => setShowTextInput(!showTextInput)}
            className="btn-secondary text-sm"
          >
            {showTextInput ? 'Upload File' : 'Paste Text'}
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Fax inbox status */}
      {faxStatus && (
        <div className="card bg-brand-50 border-brand-200 flex items-center justify-between">
          <div className="flex items-center gap-4 text-sm">
            <span className="font-medium text-brand-700">Fax Inbox</span>
            <span className="text-brand-600">{faxStatus.total_files} total files</span>
            <span className="text-brand-600">{faxStatus.pending} pending</span>
            <span className="text-brand-600">{faxStatus.processed} processed</span>
            {faxStatus.polling_active && (
              <span className="flex items-center gap-1.5 text-green-600">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                Auto-pulling hourly
              </span>
            )}
          </div>
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
            faxStatus.inbox_exists ? 'text-green-600' : 'text-red-600'
          }`}>
            <span className={`w-2 h-2 rounded-full ${
              faxStatus.inbox_exists ? 'bg-green-500' : 'bg-red-500'
            }`} />
            {faxStatus.inbox_exists ? 'Connected' : 'Inbox not found'}
          </span>
        </div>
      )}

      {/* Document type filter pills */}
      <div className="flex items-center gap-2 flex-wrap">
        {DOC_TYPES.map(({ value, label, icon: Icon }) => {
          const active = docTypeFilter === value
          const count = value ? (typeCounts[value] || 0) : faxes.length
          return (
            <button
              key={label}
              onClick={() => setDocTypeFilter(value)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                active
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <Icon size={13} />
              {label}
              {count > 0 && (
                <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] ${
                  active ? 'bg-white/20 text-white' : 'bg-gray-200 text-gray-500'
                }`}>
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Upload area */}
      {showTextInput ? (
        <div className="card space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Paste fax text</h3>
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Paste the fax text here..."
            className="input min-h-[160px] resize-y"
          />
          <button onClick={handleTextUpload} className="btn-primary text-sm">
            Process Text
          </button>
        </div>
      ) : (
        <FileUpload onUpload={handleFileUpload} />
      )}

      {/* Status filter tabs */}
      <div className="flex items-center gap-1 border-b border-gray-200">
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize ${
              filter === s
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Fax list */}
      <div className="space-y-2">
        {loading ? (
          <p className="text-sm text-gray-500 text-center py-12">Loading...</p>
        ) : faxes.length === 0 ? (
          <div className="text-center py-12">
            <Inbox className="mx-auto mb-3 text-gray-300" size={40} />
            <p className="text-sm text-gray-500">No faxes found</p>
            <p className="text-xs text-gray-400 mt-1">Faxes are auto-pulled from {emrName} every hour</p>
          </div>
        ) : (
          faxes.map((fax) => {
            const typeStyle = DOC_TYPE_STYLES[fax.document_type] || DOC_TYPE_STYLES.other
            const isReferral = fax.document_type === 'referral'
            return (
              <Link
                key={fax.id}
                to={`/faxes/${fax.id}`}
                className="card flex items-center justify-between hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-gray-50 rounded-lg">
                    <FileText size={20} className="text-gray-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-800">{fax.filename}</p>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${typeStyle.bg} ${typeStyle.text}`}>
                        {typeStyle.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      {isReferral && fax.extracted_data?.patient_last_name && (
                        <span className="text-xs text-gray-600">
                          {fax.extracted_data.patient_first_name} {fax.extracted_data.patient_last_name}
                        </span>
                      )}
                      {isReferral && fax.extracted_data?.referring_provider && (
                        <span className="text-xs text-gray-400">
                          from {fax.extracted_data.referring_provider}
                        </span>
                      )}
                      {!isReferral && fax.raw_text && (
                        <span className="text-xs text-gray-400 truncate max-w-[300px]">
                          {fax.raw_text.slice(0, 80)}...
                        </span>
                      )}
                      {fax.extracted_data?.urgency && fax.extracted_data.urgency !== 'routine' && (
                        <span className="badge bg-red-100 text-red-700 uppercase text-[10px]">
                          {fax.extracted_data.urgency}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-gray-400">
                    {new Date(fax.uploaded_at).toLocaleString()}
                  </span>
                  <StatusBadge status={fax.status} />
                </div>
              </Link>
            )
          })
        )}
      </div>

      {/* Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-1">How Fax Ingestion Works</h3>
        <p className="text-sm text-blue-600 leading-relaxed">
          Faxes are automatically pulled from {emrName} every hour, scanned via OCR, and
          classified by the LLM into categories (Referral, Lab Result, Insurance Auth, Medical
          Records, Other). Documents classified as referrals can be promoted to the Referrals
          section for full processing. Use "Pull Now" to fetch immediately.
        </p>
      </div>
    </div>
  )
}
