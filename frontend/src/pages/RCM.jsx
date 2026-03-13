import { useEffect, useState } from 'react'
import { DollarSign, TrendingUp, PieChart, Users, RefreshCw } from 'lucide-react'
import StatCard from '../components/StatCard'
import { getRCMDashboard, getPatientBilling } from '../services/api'

export default function RCM() {
  const [dashboard, setDashboard] = useState(null)
  const [patientId, setPatientId] = useState('')
  const [billing, setBilling] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lookingUp, setLookingUp] = useState(false)

  useEffect(() => {
    getRCMDashboard()
      .then(setDashboard)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const handleLookup = async (e) => {
    e.preventDefault()
    if (!patientId.trim()) return
    setLookingUp(true)
    try {
      setBilling(await getPatientBilling(patientId))
    } catch (err) {
      alert(err.message)
    }
    setLookingUp(false)
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading RCM dashboard...</p>

  const d = dashboard || {}

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Revenue Cycle Management</h1>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Referrals Processed"
          value={d.referrals_processed ?? '—'}
          icon={<RefreshCw size={20} />}
        />
        <StatCard
          label="Pending Review"
          value={d.referrals_pending ?? '—'}
          icon={<Users size={20} />}
          variant="warning"
        />
        <StatCard
          label="Pushed to eCW"
          value={d.referrals_approved ?? '—'}
          icon={<TrendingUp size={20} />}
          variant="success"
        />
        <StatCard
          label="Rejected"
          value={d.referrals_rejected ?? '—'}
          icon={<DollarSign size={20} />}
          variant="danger"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Payer mix */}
        {d.payer_mix?.length > 0 && (
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <PieChart size={18} className="text-brand-500" />
              <h2 className="font-semibold text-gray-900">Payer Mix</h2>
            </div>
            <div className="space-y-3">
              {d.payer_mix.map((p, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-sm text-gray-700 w-40 truncate">{p.payer}</span>
                  <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-brand-500 rounded-full" style={{ width: `${p.percent}%` }} />
                  </div>
                  <span className="text-sm font-medium text-gray-600 w-12 text-right">{p.percent}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top diagnoses */}
        {d.top_diagnoses?.length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-gray-900 mb-4">Top Diagnosis Codes</h2>
            <div className="space-y-2">
              {d.top_diagnoses.map((dx, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div>
                    <span className="font-mono text-sm font-semibold text-brand-600">{dx.code}</span>
                    <span className="text-sm text-gray-600 ml-3">{dx.display}</span>
                  </div>
                  <span className="text-sm text-gray-500">{dx.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Patient billing lookup */}
        <div className="card lg:col-span-2">
          <h2 className="font-semibold text-gray-900 mb-4">Patient Billing Lookup</h2>
          <form onSubmit={handleLookup} className="flex gap-2 mb-5">
            <div className="relative flex-1 max-w-xs">
              <DollarSign size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="eCW Patient ID"
                className="input pl-10"
              />
            </div>
            <button type="submit" disabled={lookingUp} className="btn-primary">
              {lookingUp ? 'Loading...' : 'Look Up'}
            </button>
          </form>

          {billing && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {billing.encounters?.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Recent Encounters</h3>
                  <div className="space-y-1">
                    {billing.encounters.slice(0, 5).map((enc, i) => (
                      <div key={i} className="text-sm flex justify-between py-1 border-b">
                        <span className="text-gray-600 capitalize">{enc.type || enc.class}</span>
                        <span className="text-gray-400">{enc.date}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {billing.conditions?.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Active Conditions</h3>
                  <div className="space-y-1">
                    {billing.conditions.slice(0, 5).map((c, i) => (
                      <div key={i} className="text-sm py-1 border-b text-gray-600">{c.display || c.code}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {!billing && !lookingUp && (
            <p className="text-sm text-gray-400 text-center py-4">Enter a patient ID to view billing context</p>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-1">About RCM</h3>
        <p className="text-sm text-blue-600 leading-relaxed">
          Revenue data is aggregated from FHIR resources (Coverage, Encounter, Condition).
          Actual claim submission and ERA processing requires clearinghouse integration, which will be configured separately.
        </p>
      </div>
    </div>
  )
}
