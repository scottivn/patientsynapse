import { useEffect, useState } from 'react'
import {
  DollarSign, TrendingUp, PieChart, Users, RefreshCw, AlertTriangle,
  Clock, FileText, XCircle, CheckCircle, BarChart3, Search,
} from 'lucide-react'
import StatCard from '../components/StatCard'
import ErrorBanner from '../components/ErrorBanner'
import { getRCMDashboard, getPatientBilling, getStatus } from '../services/api'

const fmt = (n) => typeof n === 'number' ? n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 0 }) : '—'

export default function RCM() {
  const [dashboard, setDashboard] = useState(null)
  const [patientId, setPatientId] = useState('')
  const [billing, setBilling] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lookingUp, setLookingUp] = useState(false)
  const [emrName, setEmrName] = useState('EMR')
  const [error, setError] = useState(null)

  useEffect(() => {
    getStatus()
      .then((s) => setEmrName(s?.emr_provider || 'EMR'))
      .catch(() => {})
    getRCMDashboard()
      .then(setDashboard)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleLookup = async () => {
    if (!patientId.trim() || lookingUp) return
    setLookingUp(true)
    setError(null)
    try {
      setBilling(await getPatientBilling(patientId.trim()))
    } catch (err) {
      setError(err.message)
    } finally {
      setLookingUp(false)
    }
  }

  if (loading) return <p className="text-gray-500 text-center py-12">Loading RCM dashboard...</p>

  const d = dashboard || {}
  const rev = d.revenue || {}
  const claims = d.claims || {}

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Revenue Cycle Management</h1>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Revenue KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Collected (MTD)"
          value={fmt(rev.collected_mtd)}
          icon={DollarSign}
          color="green"
        />
        <StatCard
          label="Collected (YTD)"
          value={fmt(rev.collected_ytd)}
          icon={TrendingUp}
          color="brand"
        />
        <StatCard
          label="Outstanding A/R"
          value={fmt(rev.outstanding)}
          icon={Clock}
          color="amber"
        />
        <StatCard
          label="Avg Reimbursement"
          value={fmt(rev.avg_reimbursement)}
          icon={BarChart3}
        />
      </div>

      {/* Claims pipeline */}
      {claims.submitted > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileText size={16} className="text-brand-500" />
            Claims Pipeline
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
            <div className="text-center py-3 bg-blue-50 rounded-lg">
              <p className="text-2xl font-bold text-blue-700">{claims.submitted}</p>
              <p className="text-xs text-blue-600 font-medium mt-1">Submitted</p>
            </div>
            <div className="text-center py-3 bg-green-50 rounded-lg">
              <p className="text-2xl font-bold text-green-700">{claims.paid}</p>
              <p className="text-xs text-green-600 font-medium mt-1">Paid</p>
            </div>
            <div className="text-center py-3 bg-red-50 rounded-lg">
              <p className="text-2xl font-bold text-red-700">{claims.denied}</p>
              <p className="text-xs text-red-600 font-medium mt-1">Denied</p>
            </div>
            <div className="text-center py-3 bg-amber-50 rounded-lg">
              <p className="text-2xl font-bold text-amber-700">{claims.pending}</p>
              <p className="text-xs text-amber-600 font-medium mt-1">Pending</p>
            </div>
          </div>
          {/* Clean rate bar */}
          <div className="flex h-3 rounded-full overflow-hidden bg-gray-100">
            <div className="bg-green-500 transition-all" style={{ width: `${(claims.paid / claims.submitted) * 100}%` }} title={`Paid: ${claims.paid}`} />
            <div className="bg-red-400 transition-all" style={{ width: `${(claims.denied / claims.submitted) * 100}%` }} title={`Denied: ${claims.denied}`} />
            <div className="bg-amber-400 transition-all" style={{ width: `${(claims.pending / claims.submitted) * 100}%` }} title={`Pending: ${claims.pending}`} />
          </div>
          <p className="text-xs text-gray-400 mt-2 text-right">
            Denial rate: <span className={`font-semibold ${claims.denial_rate > 10 ? 'text-red-500' : 'text-green-600'}`}>{claims.denial_rate}%</span>
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* A/R Aging */}
        {d.ar_aging?.length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Clock size={16} className="text-amber-500" />
              A/R Aging
            </h2>
            <div className="space-y-3">
              {d.ar_aging.map((bucket, i) => {
                const maxAmount = Math.max(...d.ar_aging.map(b => b.amount))
                const colors = ['bg-green-500', 'bg-amber-400', 'bg-orange-500', 'bg-red-500']
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-700 font-medium">{bucket.bucket}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-gray-400 text-xs">{bucket.count} claims</span>
                        <span className="font-semibold text-gray-900">{fmt(bucket.amount)}</span>
                      </div>
                    </div>
                    <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${colors[i] || 'bg-gray-400'}`} style={{ width: `${(bucket.amount / maxAmount) * 100}%` }} />
                    </div>
                  </div>
                )
              })}
              <div className="pt-2 border-t flex justify-between text-sm">
                <span className="font-medium text-gray-700">Total Outstanding</span>
                <span className="font-bold text-gray-900">{fmt(d.ar_aging.reduce((s, b) => s + b.amount, 0))}</span>
              </div>
            </div>
          </div>
        )}

        {/* Denial Reasons */}
        {d.denial_reasons?.length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <XCircle size={16} className="text-red-500" />
              Top Denial Reasons
            </h2>
            <div className="space-y-2">
              {d.denial_reasons.map((dr, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-sm text-gray-700 truncate">{dr.reason}</span>
                  </div>
                  <div className="flex items-center gap-3 flex-shrink-0 ml-3">
                    <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full font-medium">{dr.count}</span>
                    <span className="text-xs text-gray-400 w-10 text-right">{dr.percent}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Revenue by Payer */}
        {d.revenue_by_payer?.length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <DollarSign size={16} className="text-green-500" />
              Revenue by Payer (YTD)
            </h2>
            <div className="space-y-2">
              {d.revenue_by_payer.map((rp, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                  <span className="text-sm text-gray-700">{rp.payer}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{rp.claims} claims</span>
                    <span className="text-sm font-semibold text-gray-900 w-20 text-right">{fmt(rp.amount)}</span>
                  </div>
                </div>
              ))}
              <div className="pt-2 border-t flex justify-between text-sm">
                <span className="font-medium text-gray-700">Total</span>
                <span className="font-bold text-gray-900">{fmt(d.revenue_by_payer.reduce((s, r) => s + r.amount, 0))}</span>
              </div>
            </div>
          </div>
        )}

        {/* Monthly Trend */}
        {d.monthly_trend?.length > 0 && (
          <div className="card">
            <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp size={16} className="text-brand-500" />
              Monthly Revenue Trend
            </h2>
            <div className="space-y-2">
              {d.monthly_trend.map((m, i) => {
                const maxRev = Math.max(...d.monthly_trend.map(t => t.revenue))
                return (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-xs text-gray-500 w-20 flex-shrink-0">{m.month}</span>
                    <div className="flex-1 h-5 bg-gray-50 rounded overflow-hidden relative">
                      <div
                        className="h-full bg-brand-400 rounded transition-all"
                        style={{ width: `${(m.revenue / maxRev) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-gray-700 w-16 text-right">{fmt(m.revenue)}</span>
                    <span className="text-xs text-gray-400 w-8 text-right">{m.claims}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Payer mix */}
        {d.payer_mix?.length > 0 && (
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <PieChart size={16} className="text-brand-500" />
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
      </div>

      {/* Referral pipeline stats */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <RefreshCw size={16} className="text-brand-500" />
          Referral Pipeline
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="text-center py-3">
            <p className="text-xl font-bold text-gray-900">{d.referrals_processed ?? '—'}</p>
            <p className="text-xs text-gray-500 mt-1">Processed</p>
          </div>
          <div className="text-center py-3">
            <p className="text-xl font-bold text-amber-600">{d.referrals_pending ?? '—'}</p>
            <p className="text-xs text-gray-500 mt-1">Pending</p>
          </div>
          <div className="text-center py-3">
            <p className="text-xl font-bold text-green-600">{d.referrals_approved ?? '—'}</p>
            <p className="text-xs text-gray-500 mt-1">Pushed to {emrName}</p>
          </div>
          <div className="text-center py-3">
            <p className="text-xl font-bold text-red-600">{d.referrals_rejected ?? '—'}</p>
            <p className="text-xs text-gray-500 mt-1">Rejected</p>
          </div>
        </div>
      </div>

      {/* Patient billing lookup */}
      <div className="card">
        <h2 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Search size={16} className="text-gray-400" />
          Patient Billing Lookup
        </h2>
        <div className="flex gap-2 mb-5">
          <div className="relative flex-1 max-w-xs">
            <DollarSign size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
              placeholder={`${emrName} Patient ID (e.g. pat-001)`}
              className="input pl-10"
            />
          </div>
          <button type="button" onClick={handleLookup} disabled={lookingUp || !patientId.trim()} className="btn-primary">
            {lookingUp ? 'Loading...' : 'Look Up'}
          </button>
        </div>

        {billing && !billing.status && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
            {billing.procedures?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Procedures</h3>
                <div className="space-y-1">
                  {billing.procedures.slice(0, 5).map((p, i) => (
                    <div key={i} className="text-sm py-1 border-b text-gray-600">
                      <span className="font-mono text-xs text-gray-500">{p.code}</span> {p.display}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {billing.insurance && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-2">Insurance</h3>
                <div className="text-sm space-y-1">
                  <p className="text-gray-700 font-medium">{billing.insurance.payor}</p>
                  <p className="text-gray-500">Status: <span className={`font-medium ${billing.insurance.status === 'active' ? 'text-green-600' : 'text-red-600'}`}>{billing.insurance.status}</span></p>
                  <p className="text-gray-400 text-xs">ID: {billing.insurance.id}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {billing?.status === 'not_connected' && (
          <div className="px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
            {billing.message}
          </div>
        )}

        {!billing && !lookingUp && (
          <p className="text-sm text-gray-400 text-center py-4">Enter a patient ID to view billing context</p>
        )}
      </div>
    </div>
  )
}
