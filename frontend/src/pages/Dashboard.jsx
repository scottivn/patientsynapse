import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, CalendarClock, DollarSign, Clock, CheckCircle2, AlertTriangle } from 'lucide-react'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import { listReferrals, getSystemStatus } from '../services/api'

export default function Dashboard() {
  const [referrals, setReferrals] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      listReferrals(),
      getSystemStatus(),
    ]).then(([refResult, statusResult]) => {
      if (refResult.status === 'fulfilled') setReferrals(refResult.value)
      if (statusResult.status === 'fulfilled') setStatus(statusResult.value)
      setLoading(false)
    })
  }, [])

  const pending = referrals.filter(r => r.status === 'review').length
  const completed = referrals.filter(r => r.status === 'completed').length
  const failed = referrals.filter(r => r.status === 'failed').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Referral processing overview</p>
      </div>

      {/* Connection banner */}
      {status && !status.fhir_connected && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 flex items-center gap-3">
          <AlertTriangle size={18} className="text-amber-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">eCW not connected</p>
            <p className="text-xs text-amber-600">
              Complete the SMART on FHIR OAuth flow in{' '}
              <Link to="/settings" className="underline">Settings</Link> to enable live data.
              LLM provider: <span className="font-medium">{status.llm_provider}</span>
            </p>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={FileText} label="Total Referrals" value={referrals.length} color="brand" />
        <StatCard icon={Clock} label="Pending Review" value={pending} color="amber" />
        <StatCard icon={CheckCircle2} label="Completed" value={completed} color="green" />
        <StatCard icon={AlertTriangle} label="Failed" value={failed} color="red" />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Link to="/referrals" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-brand-50 text-brand-600">
              <FileText size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-brand-600 transition-colors">
              Referral Inbox
            </h3>
          </div>
          <p className="text-sm text-gray-500">Upload and process referral faxes with AI extraction</p>
        </Link>

        <Link to="/scheduling" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-sky-50 text-sky-600">
              <CalendarClock size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-sky-600 transition-colors">
              Scheduling
            </h3>
          </div>
          <p className="text-sm text-gray-500">Match referrals to providers and verify insurance</p>
        </Link>

        <Link to="/rcm" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <DollarSign size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-emerald-600 transition-colors">
              RCM Analytics
            </h3>
          </div>
          <p className="text-sm text-gray-500">Revenue cycle metrics, payer mix, and diagnosis trends</p>
        </Link>
      </div>

      {/* Recent referrals */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Recent Referrals</h2>
          <Link to="/referrals" className="text-sm text-brand-500 hover:text-brand-600">
            View all →
          </Link>
        </div>
        {referrals.length === 0 ? (
          <p className="text-sm text-gray-500 py-8 text-center">
            {loading ? 'Loading...' : 'No referrals yet. Upload a fax to get started.'}
          </p>
        ) : (
          <div className="divide-y divide-gray-100">
            {referrals.slice(0, 5).map((ref) => (
              <Link
                key={ref.id}
                to={`/referrals/${ref.id}`}
                className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{ref.filename}</p>
                    <p className="text-xs text-gray-500">
                      {ref.extracted_data?.patient_last_name
                        ? `${ref.extracted_data.patient_first_name} ${ref.extracted_data.patient_last_name}`
                        : 'Processing...'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">
                    {new Date(ref.uploaded_at).toLocaleDateString()}
                  </span>
                  <StatusBadge status={ref.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
