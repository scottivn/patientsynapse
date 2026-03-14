import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Filter, Phone, Tag, FlaskConical, ShieldCheck, FolderOpen, HelpCircle } from 'lucide-react'
import FileUpload from '../components/FileUpload'
import StatusBadge from '../components/StatusBadge'
import { listReferrals, uploadReferralFile, uploadReferralText, pollFaxes, getFaxStatus } from '../services/api'

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

export default function Referrals() {
  const [referrals, setReferrals] = useState([])
  const [filter, setFilter] = useState('all')
  const [docTypeFilter, setDocTypeFilter] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showTextInput, setShowTextInput] = useState(false)
  const [textInput, setTextInput] = useState('')
  const [fetching, setFetching] = useState(false)
  const [faxStatus, setFaxStatus] = useState(null)

  const load = () => {
    setLoading(true)
    listReferrals(filter === 'all' ? null : filter, docTypeFilter)
      .then(setReferrals)
      .catch(() => setReferrals([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter, docTypeFilter])

  useEffect(() => {
    getFaxStatus().then(setFaxStatus).catch(() => {})
  }, [])

  const handleFetchFaxes = async () => {
    setFetching(true)
    try {
      const result = await pollFaxes()
      if (result.referrals?.length) {
        setReferrals((prev) => [...result.referrals, ...prev])
      }
      setFaxStatus(result.status)
    } catch (e) {
      console.error('Fax fetch failed:', e)
    } finally {
      setFetching(false)
    }
  }

  const handleFileUpload = async (file) => {
    const result = await uploadReferralFile(file)
    setReferrals((prev) => [result, ...prev])
  }

  const handleTextUpload = async () => {
    if (!textInput.trim()) return
    const result = await uploadReferralText(textInput, 'manual-entry.txt')
    setReferrals((prev) => [result, ...prev])
    setTextInput('')
    setShowTextInput(false)
  }

  // Count by doc type for badges
  const typeCounts = referrals.reduce((acc, r) => {
    const t = r.document_type || 'referral'
    acc[t] = (acc[t] || 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fax Inbox</h1>
          <p className="text-sm text-gray-500 mt-1">Classify, review, and process incoming faxes</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleFetchFaxes}
            disabled={fetching}
            className="btn-primary text-sm flex items-center gap-2"
          >
            <Phone size={16} />
            {fetching ? 'Fetching...' : 'Fetch Faxes'}
          </button>
          <button
            onClick={() => setShowTextInput(!showTextInput)}
            className="btn-secondary text-sm"
          >
            {showTextInput ? 'Upload File' : 'Paste Text'}
          </button>
        </div>
      </div>

      {/* Fax inbox status */}
      {faxStatus && (
        <div className="card bg-brand-50 border-brand-200 flex items-center justify-between">
          <div className="flex items-center gap-4 text-sm">
            <span className="font-medium text-brand-700">Fax Inbox</span>
            <span className="text-brand-600">{faxStatus.total_files} total files</span>
            <span className="text-brand-600">{faxStatus.pending} pending</span>
            <span className="text-brand-600">{faxStatus.processed} processed</span>
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
          const count = value ? (typeCounts[value] || 0) : referrals.length
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
          <h3 className="text-sm font-medium text-gray-700">Paste referral text</h3>
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
        ) : referrals.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="mx-auto mb-3 text-gray-300" size={40} />
            <p className="text-sm text-gray-500">No faxes found</p>
          </div>
        ) : (
          referrals.map((ref) => {
            const typeStyle = DOC_TYPE_STYLES[ref.document_type] || DOC_TYPE_STYLES.other
            return (
              <Link
                key={ref.id}
                to={`/referrals/${ref.id}`}
                className="card flex items-center justify-between hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-gray-50 rounded-lg">
                    <FileText size={20} className="text-gray-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold text-gray-800">{ref.filename}</p>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${typeStyle.bg} ${typeStyle.text}`}>
                        {typeStyle.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      {ref.document_type === 'referral' && ref.extracted_data?.patient_last_name && (
                        <span className="text-xs text-gray-600">
                          {ref.extracted_data.patient_first_name} {ref.extracted_data.patient_last_name}
                        </span>
                      )}
                      {ref.document_type === 'referral' && ref.extracted_data?.referring_provider && (
                        <span className="text-xs text-gray-400">
                          from {ref.extracted_data.referring_provider}
                        </span>
                      )}
                      {ref.document_type !== 'referral' && ref.raw_text && (
                        <span className="text-xs text-gray-400 truncate max-w-[300px]">
                          {ref.raw_text.slice(0, 80)}...
                        </span>
                      )}
                      {ref.extracted_data?.urgency && ref.extracted_data.urgency !== 'routine' && (
                        <span className="badge bg-red-100 text-red-700 uppercase text-[10px]">
                          {ref.extracted_data.urgency}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-gray-400">
                    {new Date(ref.uploaded_at).toLocaleString()}
                  </span>
                  <StatusBadge status={ref.status} />
                </div>
              </Link>
            )
          })
        )}
      </div>
    </div>
  )
}
