import { useEffect, useState, useCallback } from 'react'
import {
  ClipboardCheck, RefreshCw, Plus, ShieldCheck, ShieldAlert,
  ChevronDown, ChevronUp, AlertTriangle, CalendarClock, XCircle,
  CheckCircle2, FileText, Phone, Printer,
} from 'lucide-react'
import ErrorBanner from '../components/ErrorBanner'
import {
  listReferralAuths, getReferralAuthDashboard, getExpiringReferralAuths,
  createReferralAuth, recordReferralAuthVisit, requestReferralAuthRenewal,
  getRenewalContent, cancelReferralAuth,
} from '../services/api'

const STATUS_STYLES = {
  active:          'bg-green-50 text-green-700 border-green-200',
  expiring_soon:   'bg-amber-50 text-amber-700 border-amber-200',
  expired:         'bg-red-50 text-red-700 border-red-200',
  exhausted:       'bg-red-50 text-red-700 border-red-200',
  pending_renewal: 'bg-blue-50 text-blue-700 border-blue-200',
  cancelled:       'bg-gray-100 text-gray-600 border-gray-200',
}

const STATUS_LABEL = {
  active: 'Active',
  expiring_soon: 'Expiring Soon',
  expired: 'Expired',
  exhausted: 'Exhausted',
  pending_renewal: 'Pending Renewal',
  cancelled: 'Cancelled',
}

const STATUS_FILTERS = ['all', 'active', 'expiring_soon', 'expired', 'exhausted', 'pending_renewal']

const INSURANCE_TYPES = [
  { value: 'hmo', label: 'HMO' },
  { value: 'ppo', label: 'PPO' },
  { value: 'pos', label: 'POS' },
  { value: 'epo', label: 'EPO' },
  { value: 'unknown', label: 'Unknown' },
]

function StatPill({ label, value, variant = 'default' }) {
  const colors = {
    default: 'bg-gray-100 text-gray-700',
    warning: 'bg-yellow-50 text-yellow-700',
    success: 'bg-green-50 text-green-700',
    danger:  'bg-red-50 text-red-700',
    info:    'bg-indigo-50 text-indigo-700',
  }
  return (
    <div className={`rounded-xl px-4 py-3 ${colors[variant]}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs mt-0.5">{label}</p>
    </div>
  )
}

function DetailItem({ label, value }) {
  return (
    <div>
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm text-gray-700 break-words">{value ?? '—'}</p>
    </div>
  )
}

function VisitsBar({ used, allowed }) {
  if (!allowed || allowed <= 0) return <span className="text-xs text-gray-400">No visit limit</span>
  const remaining = Math.max(0, allowed - used)
  const pct = Math.round((used / allowed) * 100)
  const color = remaining < 2 ? 'bg-red-500' : pct >= 50 ? 'bg-amber-500' : 'bg-green-500'
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
        </div>
        <span className="text-xs text-gray-500 whitespace-nowrap">{used}/{allowed}</span>
      </div>
      <p className="text-xs text-gray-500">{remaining} visit{remaining !== 1 ? 's' : ''} remaining</p>
    </div>
  )
}

// ── Renewal content modal ──
function RenewalModal({ content, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg space-y-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">Renewal Fax Content</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><XCircle size={18} /></button>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <DetailItem label="To" value={content.to_name || '—'} />
          <DetailItem label="Fax" value={content.to_fax || '—'} />
          <DetailItem label="Phone" value={content.to_phone || '—'} />
          <DetailItem label="NPI" value={content.to_npi || '—'} />
        </div>
        <div className="bg-gray-50 border rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
          {content.message}
        </div>
        <p className="text-xs text-gray-400">Print this content or fax it to the PCP to request a referral renewal.</p>
        <div className="flex justify-end">
          <button onClick={onClose} className="btn-secondary text-sm">Close</button>
        </div>
      </div>
    </div>
  )
}

// ── New Auth form modal ──
function NewAuthModal({ onCreated, onCancel }) {
  const [form, setForm] = useState({
    patient_id: '', patient_first_name: '', patient_last_name: '',
    insurance_name: '', insurance_type: 'hmo',
    insurance_member_id: '', insurance_npi: '', copay: '',
    referral_number: '', referring_pcp_name: '', referring_pcp_npi: '',
    referring_pcp_phone: '', referring_pcp_fax: '',
    start_date: '', end_date: '', visits_allowed: '',
    notes: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.patient_id.trim() || !form.patient_first_name.trim() || !form.patient_last_name.trim()) {
      setError('Patient ID, first name, and last name are required.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const payload = { ...form, visits_allowed: parseInt(form.visits_allowed) || 0 }
      await createReferralAuth(payload)
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl max-h-[85vh] overflow-y-auto space-y-4">
        <h3 className="font-semibold text-gray-900 text-lg">New Referral Authorization</h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Patient */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wider text-gray-400">Patient</legend>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Patient ID *</label>
                <input className="input" value={form.patient_id} onChange={(e) => set('patient_id', e.target.value)} placeholder="EMR Patient ID" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">First Name *</label>
                <input className="input" value={form.patient_first_name} onChange={(e) => set('patient_first_name', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Last Name *</label>
                <input className="input" value={form.patient_last_name} onChange={(e) => set('patient_last_name', e.target.value)} />
              </div>
            </div>
          </fieldset>

          {/* Insurance */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wider text-gray-400">Insurance</legend>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Insurance Name</label>
                <input className="input" value={form.insurance_name} onChange={(e) => set('insurance_name', e.target.value)} placeholder="e.g. BCBS HMO" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Plan Type</label>
                <select className="input" value={form.insurance_type} onChange={(e) => set('insurance_type', e.target.value)}>
                  {INSURANCE_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Member ID</label>
                <input className="input" value={form.insurance_member_id} onChange={(e) => set('insurance_member_id', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">NPI</label>
                <input className="input" value={form.insurance_npi} onChange={(e) => set('insurance_npi', e.target.value)} placeholder="e.g. 1316010986" />
              </div>
            </div>
            <div className="w-32">
              <label className="block text-xs font-medium text-gray-600 mb-1">Co-Pay</label>
              <input className="input" value={form.copay} onChange={(e) => set('copay', e.target.value)} placeholder="$70" />
            </div>
          </fieldset>

          {/* Referral details */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wider text-gray-400">Referral Authorization</legend>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Referral Number</label>
                <input className="input font-mono" value={form.referral_number} onChange={(e) => set('referral_number', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Start Date</label>
                <input type="date" className="input" value={form.start_date} onChange={(e) => set('start_date', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">End Date</label>
                <input type="date" className="input" value={form.end_date} onChange={(e) => set('end_date', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Visits Allowed</label>
                <input type="number" min="0" className="input" value={form.visits_allowed} onChange={(e) => set('visits_allowed', e.target.value)} />
              </div>
            </div>
          </fieldset>

          {/* Referring PCP */}
          <fieldset className="space-y-3">
            <legend className="text-xs font-semibold uppercase tracking-wider text-gray-400">Referring PCP</legend>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">PCP Name</label>
                <input className="input" value={form.referring_pcp_name} onChange={(e) => set('referring_pcp_name', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">PCP NPI</label>
                <input className="input" value={form.referring_pcp_npi} onChange={(e) => set('referring_pcp_npi', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">PCP Phone</label>
                <input className="input" value={form.referring_pcp_phone} onChange={(e) => set('referring_pcp_phone', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">PCP Fax</label>
                <input className="input" value={form.referring_pcp_fax} onChange={(e) => set('referring_pcp_fax', e.target.value)} />
              </div>
            </div>
          </fieldset>

          {/* Notes */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Notes</label>
            <textarea className="input resize-none w-full" rows={2} value={form.notes} onChange={(e) => set('notes', e.target.value)} />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg px-3 py-2 text-sm text-red-700">{error}</div>
          )}

          <div className="flex gap-2 justify-end">
            <button type="button" onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
            <button type="submit" disabled={saving} className="btn-primary text-sm flex items-center gap-2">
              {saving && <RefreshCw size={14} className="animate-spin" />}
              {saving ? 'Saving...' : 'Create Authorization'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Auth row ──
function AuthRow({ auth, onAction }) {
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [renewalContent, setRenewalContent] = useState(null)

  const act = async (fn) => {
    setBusy(true)
    try { await fn() } finally { setBusy(false) }
  }

  const statusStyle = STATUS_STYLES[auth.status] || 'bg-gray-100 text-gray-600'

  return (
    <>
      {renewalContent && <RenewalModal content={renewalContent} onClose={() => setRenewalContent(null)} />}

      <div className="border rounded-lg overflow-hidden">
        {/* Header */}
        <div
          className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors"
          onClick={() => setExpanded((v) => !v)}
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-gray-900 text-sm">
                {auth.patient_first_name} {auth.patient_last_name}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusStyle}`}>
                {STATUS_LABEL[auth.status] || auth.status}
              </span>
              {auth.insurance_type && auth.insurance_type !== 'unknown' && (
                <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 border border-purple-200 font-medium uppercase">
                  {auth.insurance_type}
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              {auth.insurance_name || 'No insurance'}{auth.referral_number ? ` · Ref #${auth.referral_number}` : ''}
              {auth.end_date ? ` · Expires ${auth.end_date}` : ''}
              {auth.visits_allowed > 0 ? ` · ${auth.visits_remaining} visit${auth.visits_remaining !== 1 ? 's' : ''} left` : ''}
            </p>
          </div>

          {/* Mini visits bar */}
          {auth.visits_allowed > 0 && (
            <div className="w-20 hidden sm:block">
              <VisitsBar used={auth.visits_used} allowed={auth.visits_allowed} />
            </div>
          )}

          {expanded ? <ChevronUp size={16} className="text-gray-400 flex-shrink-0" /> : <ChevronDown size={16} className="text-gray-400 flex-shrink-0" />}
        </div>

        {/* Expanded */}
        {expanded && (
          <div className="border-t px-4 py-4 bg-gray-50 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
              <DetailItem label="Patient ID" value={auth.patient_id} />
              <DetailItem label="Insurance" value={auth.insurance_name || '—'} />
              <DetailItem label="Plan Type" value={(auth.insurance_type || '').toUpperCase()} />
              <DetailItem label="Member ID" value={auth.insurance_member_id || '—'} />
              <DetailItem label="NPI" value={auth.insurance_npi || '—'} />
              <DetailItem label="Co-Pay" value={auth.copay || '—'} />
              <DetailItem label="Referral #" value={auth.referral_number || '—'} />
              <DetailItem label="Start Date" value={auth.start_date || '—'} />
              <DetailItem label="End Date" value={auth.end_date || '—'} />
              <DetailItem label="Days Until Expiry" value={auth.days_until_expiry != null ? `${auth.days_until_expiry} day(s)` : '—'} />
              <DetailItem label="Referring PCP" value={auth.referring_pcp_name || '—'} />
              <DetailItem label="PCP NPI" value={auth.referring_pcp_npi || '—'} />
              <DetailItem label="PCP Phone" value={auth.referring_pcp_phone || '—'} />
              <DetailItem label="PCP Fax" value={auth.referring_pcp_fax || '—'} />
              <DetailItem label="Created" value={auth.created_at} />
              {auth.renewal_requested_at && (
                <DetailItem label="Renewal Requested" value={auth.renewal_requested_at} />
              )}
            </div>

            {/* Visits */}
            {auth.visits_allowed > 0 && (
              <div className="max-w-xs">
                <p className="text-xs text-gray-400 mb-1">Visit Usage</p>
                <VisitsBar used={auth.visits_used} allowed={auth.visits_allowed} />
              </div>
            )}

            {auth.notes && (
              <div className="text-xs text-gray-600 bg-white border rounded px-3 py-2">
                <span className="font-medium">Notes: </span>{auth.notes}
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-1">
              {['active', 'expiring_soon'].includes(auth.status) && (
                <button
                  disabled={busy}
                  onClick={() => act(() => onAction('record-visit', auth.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-green-300 text-green-700 hover:bg-green-50 flex items-center gap-1.5 disabled:opacity-50"
                >
                  <CheckCircle2 size={13} />
                  Record Visit
                </button>
              )}
              {['active', 'expiring_soon', 'expired', 'exhausted'].includes(auth.status) && (
                <button
                  disabled={busy}
                  onClick={() => act(() => onAction('request-renewal', auth.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 hover:bg-indigo-50 flex items-center gap-1.5 disabled:opacity-50"
                >
                  <RefreshCw size={13} />
                  Request Renewal
                </button>
              )}
              {auth.status === 'pending_renewal' && (
                <button
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    try {
                      const content = await getRenewalContent(auth.id)
                      setRenewalContent(content)
                    } catch (err) {
                      onAction('error', null, err.message)
                    } finally {
                      setBusy(false)
                    }
                  }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-blue-300 text-blue-700 hover:bg-blue-50 flex items-center gap-1.5 disabled:opacity-50"
                >
                  <Printer size={13} />
                  View Renewal Fax
                </button>
              )}
              {auth.status !== 'cancelled' && (
                <button
                  disabled={busy}
                  onClick={() => act(() => onAction('cancel', auth.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-red-300 text-red-600 hover:bg-red-50 flex items-center gap-1.5 disabled:opacity-50"
                >
                  <XCircle size={13} />
                  Cancel
                </button>
              )}
              {busy && <RefreshCw size={14} className="animate-spin text-gray-400 self-center" />}
            </div>
          </div>
        )}
      </div>
    </>
  )
}

// ── Main page ──
export default function ReferralAuths() {
  const [auths, setAuths] = useState([])
  const [dashboard, setDashboard] = useState(null)
  const [expiringSoon, setExpiringSoon] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeFilter, setActiveFilter] = useState('all')
  const [showNewForm, setShowNewForm] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [dash, all, expiring] = await Promise.all([
        getReferralAuthDashboard(),
        listReferralAuths(),
        getExpiringReferralAuths(),
      ])
      setDashboard(dash)
      setAuths(all)
      setExpiringSoon(expiring)
    } catch (err) {
      console.error('Referral auth load failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAction = async (action, authId, extra) => {
    if (action === 'error') { setError(extra); return }
    try {
      let updated
      if (action === 'record-visit') updated = await recordReferralAuthVisit(authId)
      if (action === 'request-renewal') updated = await requestReferralAuthRenewal(authId)
      if (action === 'cancel') updated = await cancelReferralAuth(authId)
      if (updated) {
        setAuths((prev) => prev.map((a) => a.id === authId ? updated : a))
        getReferralAuthDashboard().then(setDashboard).catch(() => {})
        getExpiringReferralAuths().then(setExpiringSoon).catch(() => {})
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const filtered = activeFilter === 'all'
    ? auths
    : auths.filter((a) => a.status === activeFilter)

  const d = dashboard || {}

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      {showNewForm && (
        <NewAuthModal
          onCreated={() => { setShowNewForm(false); load() }}
          onCancel={() => setShowNewForm(false)}
        />
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Referral Authorizations</h1>
          <p className="text-sm text-gray-500 mt-0.5">Track HMO/POS/EPO referral authorizations from PCPs</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="btn-secondary text-sm flex items-center gap-2"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            onClick={() => setShowNewForm(true)}
            className="btn-primary text-sm flex items-center gap-2"
          >
            <Plus size={14} />
            New Auth
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatPill label="Total" value={d.total ?? '—'} />
        <StatPill label="Active" value={d.active ?? '—'} variant="success" />
        <StatPill label="Expiring Soon" value={d.expiring_soon ?? '—'} variant="warning" />
        <StatPill label="Expired" value={d.expired ?? '—'} variant="danger" />
        <StatPill label="Exhausted" value={d.exhausted ?? '—'} variant="danger" />
        <StatPill label="Pending Renewal" value={d.pending_renewal ?? '—'} variant="info" />
      </div>

      {/* Expiring soon alerts */}
      {expiringSoon.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 space-y-3">
          <div className="flex items-center gap-2 text-amber-800 font-medium text-sm">
            <AlertTriangle size={16} />
            {expiringSoon.length} referral auth{expiringSoon.length > 1 ? 's' : ''} expiring soon or low on visits
          </div>
          <div className="space-y-2">
            {expiringSoon.map((a) => (
              <div key={a.id} className="flex items-center gap-3 text-sm text-amber-700">
                <ShieldAlert size={14} />
                <span className="font-medium">{a.patient_first_name} {a.patient_last_name}</span>
                <span>·</span>
                <span>{a.insurance_name || 'Unknown'}</span>
                <span>·</span>
                <span>
                  {a.days_until_expiry != null && a.days_until_expiry <= 14 && `expires in ${a.days_until_expiry}d`}
                  {a.days_until_expiry != null && a.days_until_expiry <= 14 && a.visits_remaining < 2 && ' · '}
                  {a.visits_allowed > 0 && a.visits_remaining < 2 && `${a.visits_remaining} visit${a.visits_remaining !== 1 ? 's' : ''} left`}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 flex-wrap">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setActiveFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeFilter === f
                ? 'bg-brand-500 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {f === 'all'
              ? `All (${auths.length})`
              : `${STATUS_LABEL[f] || f} (${auths.filter((a) => a.status === f).length})`}
          </button>
        ))}
      </div>

      {/* Auth list */}
      {loading ? (
        <p className="text-gray-400 text-center py-12">Loading referral authorizations...</p>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <ClipboardCheck size={36} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">No referral authorizations {activeFilter !== 'all' ? `with status "${STATUS_LABEL[activeFilter] || activeFilter}"` : 'yet'}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((a) => (
            <AuthRow key={a.id} auth={a} onAction={handleAction} />
          ))}
        </div>
      )}

      {/* Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-1">About Referral Authorizations</h3>
        <p className="text-sm text-blue-600 leading-relaxed">
          HMO, POS, and EPO plans require an active referral authorization from the patient's PCP before
          being seen. Track referral numbers, expiration dates, and visit counts here. When a referral is
          expiring or running low on visits, use <em>Request Renewal</em> to generate fax content for
          the PCP. The Scheduling page will warn if an HMO patient is missing a valid referral.
        </p>
      </div>
    </div>
  )
}
