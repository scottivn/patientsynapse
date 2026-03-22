import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, CalendarClock, DollarSign, Clock, CheckCircle2, AlertTriangle, Inbox, Package } from 'lucide-react'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import ErrorBanner from '../components/ErrorBanner'
import { listReferrals, getSystemStatus } from '../services/api'

export default function Dashboard() {
  const [referrals, setReferrals] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.allSettled([
      listReferrals(),
      getSystemStatus(),
    ]).then(([refResult, statusResult]) => {
      if (refResult.status === 'fulfilled') setReferrals(refResult.value)
      if (statusResult.status === 'fulfilled') setStatus(statusResult.value)
      if (refResult.status === 'rejected' && statusResult.status === 'rejected') {
        setError('Unable to connect to the backend. Is the server running?')
      } else if (refResult.status === 'rejected') {
        setError('Failed to load faxes.')
      }
      setLoading(false)
    })
  }, [])

  const emrName = status?.emr_provider || 'EMR'
  const pending = referrals.filter(r => r.status === 'review').length
  const completed = referrals.filter(r => r.status === 'completed').length
  const failed = referrals.filter(r => r.status === 'failed').length
  const referralOnly = referrals.filter(r => r.document_type === 'referral')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Overview of fax processing, referrals, and DME</p>
      </div>

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {/* Connection banner */}
      {status && !status.fhir_connected && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 flex items-center gap-3">
          <AlertTriangle size={18} className="text-amber-500 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">{emrName} not connected</p>
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
        <StatCard icon={Inbox} label="Total Faxes" value={referrals.length} color="brand" />
        <StatCard icon={Clock} label="Pending Review" value={pending} color="amber" />
        <StatCard icon={FileText} label="Referrals" value={referralOnly.length} color="sky" />
        <StatCard icon={CheckCircle2} label="Completed" value={completed} color="green" />
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <Link to="/faxes" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-brand-50 text-brand-600">
              <Inbox size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-brand-600 transition-colors">
              Fax Inbox
            </h3>
          </div>
          <p className="text-sm text-gray-500">Auto-pulled from {emrName}, scanned and classified by LLM</p>
        </Link>

        <Link to="/referrals" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-sky-50 text-sky-600">
              <FileText size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-sky-600 transition-colors">
              Referrals
            </h3>
          </div>
          <p className="text-sm text-gray-500">Review and approve referrals, push to {emrName}</p>
        </Link>

        <Link to="/scheduling" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-emerald-50 text-emerald-600">
              <CalendarClock size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-emerald-600 transition-colors">
              Scheduling
            </h3>
          </div>
          <p className="text-sm text-gray-500">Match providers and verify insurance</p>
        </Link>

        <Link to="/dme" className="card hover:shadow-md transition-shadow group">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 rounded-lg bg-purple-50 text-purple-600">
              <Package size={18} />
            </div>
            <h3 className="font-semibold text-gray-900 group-hover:text-purple-600 transition-colors">
              DME Portal
            </h3>
          </div>
          <p className="text-sm text-gray-500">Patient orders, insurance verification, auto-replace</p>
        </Link>
      </div>

      {/* Recent referrals */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">Recent Faxes</h2>
          <Link to="/faxes" className="text-sm text-brand-500 hover:text-brand-600">
            View all
          </Link>
        </div>
        {referrals.length === 0 ? (
          <p className="text-sm text-gray-500 py-8 text-center">
            {loading ? 'Loading...' : 'No faxes yet. Faxes are auto-pulled hourly or upload one manually.'}
          </p>
        ) : (
          <div className="divide-y divide-gray-100">
            {referrals.slice(0, 5).map((ref) => (
              <Link
                key={ref.id}
                to={`/faxes/${ref.id}`}
                className="flex items-center justify-between py-3 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors"
              >
                <div className="flex items-center gap-3">
                  <FileText size={16} className="text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{ref.filename}</p>
                    <p className="text-xs text-gray-500">
                      {ref.extracted_data?.patient_last_name
                        ? `${ref.extracted_data.patient_first_name} ${ref.extracted_data.patient_last_name}`
                        : ref.document_type || 'Processing...'}
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
