import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Filter } from 'lucide-react'
import FileUpload from '../components/FileUpload'
import StatusBadge from '../components/StatusBadge'
import { listReferrals, uploadReferralFile, uploadReferralText } from '../services/api'

const STATUSES = ['all', 'review', 'processing', 'completed', 'failed', 'rejected']

export default function Referrals() {
  const [referrals, setReferrals] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [showTextInput, setShowTextInput] = useState(false)
  const [textInput, setTextInput] = useState('')

  const load = () => {
    setLoading(true)
    listReferrals(filter === 'all' ? null : filter)
      .then(setReferrals)
      .catch(() => setReferrals([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filter])

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Referral Inbox</h1>
          <p className="text-sm text-gray-500 mt-1">Upload, process, and review referral faxes</p>
        </div>
        <button
          onClick={() => setShowTextInput(!showTextInput)}
          className="btn-secondary text-sm"
        >
          {showTextInput ? 'Upload File' : 'Paste Text'}
        </button>
      </div>

      {/* Upload area */}
      {showTextInput ? (
        <div className="card space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Paste referral text</h3>
          <textarea
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            placeholder="Paste the referral fax text here..."
            className="input min-h-[160px] resize-y"
          />
          <button onClick={handleTextUpload} className="btn-primary text-sm">
            Process Text
          </button>
        </div>
      ) : (
        <FileUpload onUpload={handleFileUpload} />
      )}

      {/* Filter tabs */}
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
          </div>
        ) : (
          referrals.map((ref) => (
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
                  <p className="text-sm font-semibold text-gray-800">{ref.filename}</p>
                  <div className="flex items-center gap-3 mt-1">
                    {ref.extracted_data?.patient_last_name && (
                      <span className="text-xs text-gray-600">
                        {ref.extracted_data.patient_first_name} {ref.extracted_data.patient_last_name}
                      </span>
                    )}
                    {ref.extracted_data?.referring_provider && (
                      <span className="text-xs text-gray-400">
                        from {ref.extracted_data.referring_provider}
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
          ))
        )}
      </div>
    </div>
  )
}
