import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Plus, RefreshCw } from 'lucide-react'
import StatusBadge from '../components/StatusBadge'
import ErrorBanner from '../components/ErrorBanner'
import { listReferrals, uploadReferralText, getStatus } from '../services/api'

const STATUSES = ['all', 'review', 'processing', 'completed', 'failed', 'rejected']

export default function Referrals() {
  const [referrals, setReferrals] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [emrName, setEmrName] = useState('EMR')
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    // Only show referral-type documents
    listReferrals(filter === 'all' ? null : filter, 'referral')
      .then(setReferrals)
      .catch((e) => { setReferrals([]); setError(`Failed to load referrals: ${e.message}`) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter])

  useEffect(() => {
    getStatus()
      .then((s) => setEmrName(s?.emr_provider || 'EMR'))
      .catch(() => {})
  }, [])

  const pending = referrals.filter(r => r.status === 'review').length
  const completed = referrals.filter(r => r.status === 'completed').length
  const failed = referrals.filter(r => r.status === 'failed').length

  const handleCreated = (result) => {
    setReferrals((prev) => [result, ...prev])
    setShowCreate(false)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Referrals</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage patient referrals — created from faxes or entered manually
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="btn-secondary text-sm flex items-center gap-2">
            <RefreshCw size={14} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="btn-primary text-sm flex items-center gap-2"
          >
            <Plus size={14} />
            {showCreate ? 'Cancel' : 'New Referral'}
          </button>
        </div>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-brand-50 rounded-xl px-4 py-3">
          <p className="text-xl font-bold text-brand-700">{referrals.length}</p>
          <p className="text-xs text-brand-600">Total</p>
        </div>
        <div className="bg-amber-50 rounded-xl px-4 py-3">
          <p className="text-xl font-bold text-amber-700">{pending}</p>
          <p className="text-xs text-amber-600">Pending Review</p>
        </div>
        <div className="bg-green-50 rounded-xl px-4 py-3">
          <p className="text-xl font-bold text-green-700">{completed}</p>
          <p className="text-xs text-green-600">Completed</p>
        </div>
        <div className="bg-red-50 rounded-xl px-4 py-3">
          <p className="text-xl font-bold text-red-700">{failed}</p>
          <p className="text-xs text-red-600">Failed</p>
        </div>
      </div>

      {/* Manual create form */}
      {showCreate && (
        <ManualReferralForm onCreated={handleCreated} emrName={emrName} />
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

      {/* Referral list */}
      <div className="space-y-2">
        {loading ? (
          <p className="text-sm text-gray-500 text-center py-12">Loading...</p>
        ) : referrals.length === 0 ? (
          <div className="text-center py-12">
            <FileText className="mx-auto mb-3 text-gray-300" size={40} />
            <p className="text-sm text-gray-500">No referrals found</p>
            <p className="text-xs text-gray-400 mt-1">
              Referrals are created from the Fax Inbox or entered manually above
            </p>
          </div>
        ) : (
          referrals.map((ref) => (
            <Link
              key={ref.id}
              to={`/referrals/${ref.id}`}
              className="card flex items-center justify-between hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-4">
                <div className="p-2 bg-blue-50 rounded-lg">
                  <FileText size={20} className="text-blue-500" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    {ref.extracted_data?.patient_last_name ? (
                      <p className="text-sm font-semibold text-gray-800">
                        {ref.extracted_data.patient_first_name} {ref.extracted_data.patient_last_name}
                      </p>
                    ) : (
                      <p className="text-sm font-semibold text-gray-800">{ref.filename}</p>
                    )}
                    {ref.extracted_data?.urgency && ref.extracted_data.urgency !== 'routine' && (
                      <span className="badge bg-red-100 text-red-700 uppercase text-[10px]">
                        {ref.extracted_data.urgency}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    {ref.extracted_data?.referring_provider && (
                      <span className="text-xs text-gray-500">
                        from {ref.extracted_data.referring_provider}
                      </span>
                    )}
                    {ref.extracted_data?.reason && (
                      <span className="text-xs text-gray-400 truncate max-w-[250px]">
                        {ref.extracted_data.reason}
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
          ))
        )}
      </div>

      {/* Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-1">About Referrals</h3>
        <p className="text-sm text-blue-600 leading-relaxed">
          Referrals are created automatically when faxes are classified as referrals in the Fax
          Inbox. You can also create referrals manually. Approved referrals are pushed to {emrName}
          as FHIR ServiceRequest resources.
        </p>
      </div>
    </div>
  )
}

function ManualReferralForm({ onCreated }) {
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!text.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const result = await uploadReferralText(text, 'manual-referral.txt')
      onCreated(result)
      setText('')
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card space-y-3 border-brand-200">
      <div className="flex items-center gap-2">
        <Plus size={16} className="text-brand-500" />
        <h3 className="font-semibold text-gray-900 text-sm">Create Referral Manually</h3>
      </div>
      <p className="text-xs text-gray-500">
        Paste referral text below. The LLM will extract patient info, referring provider,
        diagnosis codes, and urgency automatically.
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste referral content here (fax text, notes, etc.)..."
          className="input min-h-[140px] resize-y"
        />
        {error && (
          <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
        )}
        <button type="submit" disabled={submitting} className="btn-primary text-sm flex items-center gap-2">
          {submitting && <RefreshCw size={14} className="animate-spin" />}
          {submitting ? 'Processing...' : 'Create Referral'}
        </button>
      </form>
    </div>
  )
}
