import { useEffect, useState, useCallback } from 'react'
import {
  Package, RefreshCw, ShieldCheck, ShieldAlert, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, AlertTriangle, Send, Copy, ExternalLink,
  Inbox, Clock, RotateCcw, Activity, FileText, Truck, Store,
  PauseCircle, Play, UserCheck, ShoppingCart, Archive, CalendarClock,
  Pill, Search,
} from 'lucide-react'
import ErrorBanner from '../components/ErrorBanner'
import {
  listDMEOrders, getDMEDashboard, getDMEAutoReplaceDue,
  getDMEIncoming, getDMEAutoRefillPending, getDMEInProgress,
  getDMEAwaitingPatient, getDMEPatientConfirmed, getDMEOnHold,
  verifyDMEInsurance, approveDMEOrder, rejectDMEOrder, fulfillDMEOrder,
  updateDMECompliance, holdDMEOrder, resumeDMEOrder,
  sendDMEConfirmation, markDMEOrdered, markDMEShipped,
  updateDMEEncounter, pollPrescriptions, listPrescriptions,
} from '../services/api'

const STATUS_STYLES = {
  pending:            'bg-yellow-50 text-yellow-700 border-yellow-200',
  verifying:          'bg-blue-50 text-blue-700 border-blue-200',
  verified:           'bg-indigo-50 text-indigo-700 border-indigo-200',
  awaiting_approval:  'bg-amber-50 text-amber-700 border-amber-200',
  approved:           'bg-green-50 text-green-700 border-green-200',
  patient_contacted:  'bg-cyan-50 text-cyan-700 border-cyan-200',
  patient_confirmed:  'bg-emerald-50 text-emerald-700 border-emerald-200',
  ordering:           'bg-blue-50 text-blue-700 border-blue-200',
  shipped:            'bg-indigo-50 text-indigo-700 border-indigo-200',
  fulfilled:          'bg-gray-100 text-gray-600 border-gray-200',
  rejected:           'bg-red-50 text-red-700 border-red-200',
  on_hold:            'bg-orange-50 text-orange-700 border-orange-200',
  cancelled:          'bg-gray-100 text-gray-500 border-gray-200',
}

const STATUS_LABEL = {
  pending: 'Pending', verifying: 'Verifying', verified: 'Verified',
  awaiting_approval: 'Awaiting Approval', approved: 'Approved',
  patient_contacted: 'Awaiting Patient', patient_confirmed: 'Patient Confirmed',
  ordering: 'Ordering', shipped: 'Shipped', fulfilled: 'Fulfilled',
  rejected: 'Rejected', on_hold: 'On Hold', cancelled: 'Cancelled',
}

const COMPLIANCE_STYLES = {
  unknown:        'bg-gray-50 text-gray-500 border-gray-200',
  checking:       'bg-blue-50 text-blue-600 border-blue-200',
  compliant:      'bg-green-50 text-green-700 border-green-200',
  non_compliant:  'bg-red-50 text-red-700 border-red-200',
  not_applicable: 'bg-gray-50 text-gray-400 border-gray-200',
}

const COMPLIANCE_LABEL = {
  unknown: 'Not Checked', checking: 'Checking...', compliant: 'Compliant',
  non_compliant: 'Non-Compliant', not_applicable: 'N/A',
}

const ORIGIN_LABEL = {
  auto_refill: 'Auto-Refill', prescription: 'New Rx',
  staff_initiated: 'Staff', patient_request: 'Patient Request',
}
const ORIGIN_STYLE = {
  auto_refill: 'bg-purple-50 text-purple-600 border-purple-200',
  prescription: 'bg-teal-50 text-teal-600 border-teal-200',
  staff_initiated: 'bg-gray-50 text-gray-600 border-gray-200',
  patient_request: 'bg-amber-50 text-amber-600 border-amber-200',
}


// ── Reusable components ──────────────────────────────────────────

function StatCard({ label, value, icon: Icon, variant = 'default', active, onClick }) {
  const colors = {
    default: 'bg-white border-gray-200',
    warning: 'bg-amber-50 border-amber-200',
    success: 'bg-green-50 border-green-200',
    danger:  'bg-red-50 border-red-200',
    info:    'bg-indigo-50 border-indigo-200',
    purple:  'bg-purple-50 border-purple-200',
    cyan:    'bg-cyan-50 border-cyan-200',
    emerald: 'bg-emerald-50 border-emerald-200',
    orange:  'bg-orange-50 border-orange-200',
  }
  return (
    <div
      className={`rounded-xl border px-4 py-3 transition-all ${colors[variant]} ${
        onClick ? 'cursor-pointer hover:shadow-md' : ''
      } ${active ? 'ring-2 ring-blue-500 shadow-md' : ''}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon size={14} className="opacity-60" />}
        <p className="text-xs text-gray-500 truncate">{label}</p>
      </div>
      <p className="text-2xl font-bold">{value}</p>
    </div>
  )
}

function ComplianceBadge({ order }) {
  const status = order.compliance_status || 'unknown'
  const style = COMPLIANCE_STYLES[status] || COMPLIANCE_STYLES.unknown
  const label = COMPLIANCE_LABEL[status] || status
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${style}`}>
      {label}
      {status === 'compliant' && order.compliance_avg_hours != null && (
        <span className="ml-1">({order.compliance_avg_hours.toFixed(1)}h avg)</span>
      )}
    </span>
  )
}

const ENCOUNTER_TYPE_LABELS = {
  office_visit: 'Office Visit', telehealth: 'Telehealth', sleep_study: 'Sleep Study',
  cpap_titration: 'CPAP Titration', annual_wellness: 'Annual Wellness',
  initial_consultation: 'Initial Consult', urgent_visit: 'Urgent Visit',
}

function EncounterBadge({ order }) {
  if (!order.last_encounter_date) {
    return <span className="text-xs px-2 py-0.5 rounded-full border font-medium bg-red-50 border-red-200 text-red-700">No Encounter</span>
  }
  const days = order.encounter_days_ago
  const current = order.encounter_current
  if (!current) {
    return <span className="text-xs px-2 py-0.5 rounded-full border font-medium bg-red-50 border-red-200 text-red-700">Encounter Expired ({days}d ago)</span>
  }
  const expiresIn = order.encounter_expires_in_days
  if (expiresIn != null && expiresIn <= 60) {
    return <span className="text-xs px-2 py-0.5 rounded-full border font-medium bg-amber-50 border-amber-200 text-amber-700">Encounter Expires in {expiresIn}d</span>
  }
  return null // Current and not expiring soon — no badge needed
}

function EncounterModal({ order, onConfirm, onCancel }) {
  const [encDate, setEncDate] = useState(order.last_encounter_date || '')
  const [encType, setEncType] = useState(order.last_encounter_type || 'office_visit')
  const [encProvider, setEncProvider] = useState(order.last_encounter_provider || order.referring_physician || '')
  const [encNpi, setEncNpi] = useState(order.last_encounter_provider_npi || order.referring_npi || '')
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl p-5 w-full max-w-md shadow-xl space-y-3" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900 flex items-center gap-2"><CalendarClock size={16} /> Update Last Encounter</h3>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Encounter Date</label>
          <input type="date" value={encDate} onChange={e => setEncDate(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm" max={new Date().toISOString().split('T')[0]} />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Encounter Type</label>
          <select value={encType} onChange={e => setEncType(e.target.value)}
            className="w-full border rounded-lg px-3 py-2 text-sm">
            {Object.entries(ENCOUNTER_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Provider</label>
          <input value={encProvider} onChange={e => setEncProvider(e.target.value)} placeholder="Dr. Name"
            className="w-full border rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Provider NPI</label>
          <input value={encNpi} onChange={e => setEncNpi(e.target.value)} placeholder="NPI number"
            className="w-full border rounded-lg px-3 py-2 text-sm" />
        </div>
        <div className="flex gap-2 pt-2">
          <button onClick={() => onConfirm(encDate, encType, encProvider, encNpi)} disabled={!encDate}
            className="flex-1 bg-blue-600 text-white text-sm py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50">Save Encounter</button>
          <button onClick={onCancel} className="px-4 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancel</button>
        </div>
      </div>
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

function SectionHeader({ icon: Icon, title, count, color = 'text-gray-900' }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      {Icon && <Icon size={18} className={color} />}
      <h2 className={`text-lg font-semibold ${color}`}>{title}</h2>
      {count != null && (
        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-medium">{count}</span>
      )}
    </div>
  )
}

function EmptyState({ icon: Icon, message }) {
  return (
    <div className="text-center py-8 text-gray-400">
      {Icon && <Icon size={28} className="mx-auto mb-2 opacity-30" />}
      <p className="text-sm">{message}</p>
    </div>
  )
}

// ── Modals ──────────────────────────────────────────────────────

function RejectModal({ onConfirm, onCancel }) {
  const [reason, setReason] = useState('')
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900">Reject Order</h3>
        <textarea className="input resize-none w-full" rows={3} placeholder="Reason for rejection..." value={reason} onChange={e => setReason(e.target.value)} />
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
          <button onClick={() => onConfirm(reason)} className="btn-primary text-sm bg-red-600 hover:bg-red-700">Reject</button>
        </div>
      </div>
    </div>
  )
}

function HoldModal({ onConfirm, onCancel }) {
  const [reason, setReason] = useState('')
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900">Place On Hold</h3>
        <textarea className="input resize-none w-full" rows={3} placeholder="Why is this on hold? (patient unreachable, missing docs, etc.)" value={reason} onChange={e => setReason(e.target.value)} />
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
          <button onClick={() => onConfirm(reason)} className="btn-primary text-sm bg-orange-600 hover:bg-orange-700">Hold</button>
        </div>
      </div>
    </div>
  )
}

function VendorModal({ onConfirm, onCancel }) {
  const [vendor, setVendor] = useState('')
  const [orderId, setOrderId] = useState('')
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900">Order from Vendor</h3>
        <input className="input w-full" placeholder="Vendor name" value={vendor} onChange={e => setVendor(e.target.value)} />
        <input className="input w-full" placeholder="Vendor order ID (optional)" value={orderId} onChange={e => setOrderId(e.target.value)} />
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
          <button onClick={() => onConfirm(vendor, orderId)} className="btn-primary text-sm" disabled={!vendor}>Mark Ordered</button>
        </div>
      </div>
    </div>
  )
}

function ShipModal({ onConfirm, onCancel, isPickup }) {
  const [tracking, setTracking] = useState('')
  const [carrier, setCarrier] = useState('')
  const [estDate, setEstDate] = useState('')
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900">{isPickup ? 'Ready for Pickup' : 'Mark Shipped'}</h3>
        {!isPickup && (
          <>
            <input className="input w-full" placeholder="Tracking number" value={tracking} onChange={e => setTracking(e.target.value)} />
            <input className="input w-full" placeholder="Carrier (UPS, FedEx, etc.)" value={carrier} onChange={e => setCarrier(e.target.value)} />
            <input className="input w-full" type="date" value={estDate} onChange={e => setEstDate(e.target.value)} />
          </>
        )}
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
          <button onClick={() => onConfirm(tracking, carrier, estDate)} className="btn-primary text-sm">
            {isPickup ? 'Mark Ready' : 'Mark Shipped'}
          </button>
        </div>
      </div>
    </div>
  )
}

function ComplianceModal({ order, onConfirm, onCancel }) {
  const [avgHours, setAvgHours] = useState(order.compliance_avg_hours ?? '')
  const [daysMet, setDaysMet] = useState(order.compliance_days_met ?? '')
  const [totalDays, setTotalDays] = useState(order.compliance_total_days ?? 30)
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900 flex items-center gap-2"><Activity size={16} /> Record Compliance Data</h3>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Avg hours/night</label>
          <input type="number" step="0.1" min="0" max="24" className="input w-full" value={avgHours} onChange={e => setAvgHours(e.target.value)} placeholder="e.g. 5.2" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Days ≥4hrs</label>
            <input type="number" min="0" className="input w-full" value={daysMet} onChange={e => setDaysMet(e.target.value)} placeholder="e.g. 24" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Total days</label>
            <input type="number" min="1" className="input w-full" value={totalDays} onChange={e => setTotalDays(e.target.value)} placeholder="30" />
          </div>
        </div>
        <p className="text-xs text-gray-400">CMS standard: ≥4 hrs/night on ≥70% of nights in a 30-day period.</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
          <button
            onClick={() => {
              const h = parseFloat(avgHours)
              const d = parseInt(daysMet)
              const t = parseInt(totalDays) || 30
              const status = (h >= 4 && d / t >= 0.7) ? 'compliant' : 'non_compliant'
              onConfirm({ status, avg_hours: h || 0, days_met: d || 0, total_days: t })
            }}
            className="btn-primary text-sm"
            disabled={!avgHours && !daysMet}
          >Save</button>
        </div>
      </div>
    </div>
  )
}

function ConfirmationLinkModal({ url, onClose }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000) })
  }
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900">Confirmation Link Generated</h3>
        <p className="text-sm text-gray-600">Send this link to the patient via SMS or email. They'll confirm their address and choose pickup or shipping.</p>
        <div className="flex items-center gap-2 bg-gray-50 border rounded-lg p-3">
          <input readOnly value={url} className="flex-1 bg-transparent text-sm text-gray-700 outline-none" />
          <button onClick={copy} className="text-blue-600 hover:text-blue-800" title="Copy">
            {copied ? <CheckCircle2 size={16} /> : <Copy size={16} />}
          </button>
        </div>
        <p className="text-xs text-gray-400">Link expires in 48 hours.</p>
        <div className="flex justify-end">
          <button onClick={onClose} className="btn-primary text-sm">Done</button>
        </div>
      </div>
    </div>
  )
}


// ── Order Row (expanded detail + actions) ────────────────────────

function OrderRow({ order, onAction }) {
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState(false)
  const [modal, setModal] = useState(null) // 'reject' | 'hold' | 'vendor' | 'ship' | 'link'
  const [confirmationUrl, setConfirmationUrl] = useState('')

  const act = async (fn) => {
    setBusy(true)
    try { await fn() } finally { setBusy(false) }
  }

  const statusStyle = STATUS_STYLES[order.status] || 'bg-gray-100 text-gray-600'
  const originLabel = ORIGIN_LABEL[order.origin] || order.origin
  const originStyle = ORIGIN_STYLE[order.origin] || 'bg-gray-50 text-gray-500 border-gray-200'

  return (
    <>
      {modal === 'reject' && (
        <RejectModal
          onConfirm={async (reason) => { setModal(null); await act(() => onAction('reject', order.id, reason)) }}
          onCancel={() => setModal(null)}
        />
      )}
      {modal === 'hold' && (
        <HoldModal
          onConfirm={async (reason) => { setModal(null); await act(() => onAction('hold', order.id, reason)) }}
          onCancel={() => setModal(null)}
        />
      )}
      {modal === 'vendor' && (
        <VendorModal
          onConfirm={async (v, oid) => { setModal(null); await act(() => onAction('mark-ordered', order.id, { vendor: v, orderId: oid })) }}
          onCancel={() => setModal(null)}
        />
      )}
      {modal === 'ship' && (
        <ShipModal
          isPickup={order.fulfillment_method === 'pickup'}
          onConfirm={async (t, c, d) => { setModal(null); await act(() => onAction('mark-shipped', order.id, { tracking: t, carrier: c, date: d })) }}
          onCancel={() => setModal(null)}
        />
      )}
      {modal === 'link' && (
        <ConfirmationLinkModal url={confirmationUrl} onClose={() => setModal(null)} />
      )}
      {modal === 'encounter' && (
        <EncounterModal
          order={order}
          onConfirm={async (date, type, provider, npi) => {
            setModal(null)
            await act(() => onAction('update-encounter', order.id, { date, type, provider, npi }))
          }}
          onCancel={() => setModal(null)}
        />
      )}
      {modal === 'compliance' && (
        <ComplianceModal
          order={order}
          onConfirm={async (data) => {
            setModal(null)
            await act(() => onAction('check-compliance', order.id, data))
          }}
          onCancel={() => setModal(null)}
        />
      )}

      <div className="border rounded-lg overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-gray-50 transition-colors" onClick={() => setExpanded(v => !v)}>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-gray-900 text-sm">{order.patient_first_name} {order.patient_last_name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusStyle}`}>{STATUS_LABEL[order.status] || order.status}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${originStyle}`}>{originLabel}</span>
              <ComplianceBadge order={order} />
              <EncounterBadge order={order} />
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              {order.equipment_category}{order.equipment_description ? ` — ${order.equipment_description}` : ''}
              {' · '}#{order.id}{' · '}{new Date(order.created_at).toLocaleDateString()}
            </p>
          </div>
          {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </div>

        {expanded && (
          <div className="border-t px-4 py-4 bg-gray-50 space-y-4">
            {/* Patient + Insurance details */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-sm">
              <DetailItem label="DOB" value={order.patient_dob || '—'} />
              <DetailItem label="Phone" value={order.patient_phone || '—'} />
              <DetailItem label="Email" value={order.patient_email || '—'} />
              <DetailItem label="Address" value={[order.patient_address, order.patient_city, order.patient_state, order.patient_zip].filter(Boolean).join(', ') || '—'} />
              <DetailItem label="Insurance" value={order.insurance_payer || '—'} />
              <DetailItem label="Member ID" value={order.insurance_member_id || '—'} />
              <DetailItem label="Diagnosis" value={order.diagnosis_code ? `${order.diagnosis_code} — ${order.diagnosis_description}` : '—'} />
              <DetailItem label="Referring Physician" value={order.referring_physician || '—'} />
              <DetailItem label="HCPCS Codes" value={order.hcpcs_codes?.join(', ') || '—'} />
              {order.expected_reimbursement != null && (
                <DetailItem label="Expected Reimbursement" value={`$${order.expected_reimbursement.toFixed(2)}`} />
              )}
              {order.fulfillment_method !== 'not_selected' && (
                <DetailItem label="Fulfillment" value={order.fulfillment_method === 'ship' ? 'Ship to patient' : 'Office pickup'} />
              )}
              {order.vendor_name && <DetailItem label="Vendor" value={`${order.vendor_name} (${order.vendor_order_id || 'no order #'})`} />}
              {order.shipping_tracking_number && <DetailItem label="Tracking" value={`${order.shipping_carrier || ''} ${order.shipping_tracking_number}`} />}
            </div>

            {/* Compliance card */}
            {order.compliance_status !== 'unknown' && order.compliance_status !== 'not_applicable' && (
              <div className={`rounded-lg px-3 py-2 text-xs border flex items-start gap-2 ${COMPLIANCE_STYLES[order.compliance_status]}`}>
                <Activity size={14} className="mt-0.5" />
                <div>
                  <span className="font-medium">{COMPLIANCE_LABEL[order.compliance_status]}</span>
                  {order.compliance_avg_hours != null && <span> — Avg {order.compliance_avg_hours.toFixed(1)} hrs/night</span>}
                  {order.compliance_days_met != null && order.compliance_total_days != null && (
                    <span> · {order.compliance_days_met}/{order.compliance_total_days} days ≥4hrs</span>
                  )}
                  {order.compliance_last_checked && (
                    <span className="text-gray-400 ml-2">(checked {new Date(order.compliance_last_checked).toLocaleDateString()})</span>
                  )}
                </div>
              </div>
            )}

            {/* Encounter card */}
            {order.last_encounter_date && (
              <div className={`rounded-lg px-3 py-2 text-xs border flex items-start gap-2 ${
                order.encounter_current ? 'bg-blue-50 border-blue-200 text-blue-700' : 'bg-red-50 border-red-200 text-red-700'
              }`}>
                <CalendarClock size={14} className="mt-0.5" />
                <div>
                  <span className="font-medium">Last Encounter: </span>
                  {ENCOUNTER_TYPE_LABELS[order.last_encounter_type] || order.last_encounter_type}
                  {' on '}{new Date(order.last_encounter_date + 'T00:00:00').toLocaleDateString()}
                  {order.last_encounter_provider && <span> with {order.last_encounter_provider}</span>}
                  {order.last_encounter_provider_npi && <span className="text-gray-400 ml-1">(NPI: {order.last_encounter_provider_npi})</span>}
                  <span className="ml-2">
                    ({order.encounter_days_ago}d ago
                    {order.encounter_current
                      ? order.encounter_expires_in_days != null && ` · expires in ${order.encounter_expires_in_days}d`
                      : ' · EXPIRED'}
                    )
                  </span>
                </div>
              </div>
            )}
            {!order.last_encounter_date && (
              <div className="rounded-lg px-3 py-2 text-xs border flex items-start gap-2 bg-red-50 border-red-200 text-red-700">
                <CalendarClock size={14} className="mt-0.5" />
                <span><span className="font-medium">No encounter on file</span> — patient needs a provider visit before DME reauthorization</span>
              </div>
            )}

            {/* Insurance notes */}
            {order.insurance_notes && (
              <div className={`rounded-lg px-3 py-2 text-xs border flex items-start gap-2 ${
                order.insurance_verified === true ? 'bg-green-50 border-green-200 text-green-700'
                : order.insurance_verified === false ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-yellow-50 border-yellow-200 text-yellow-700'
              }`}>
                {order.insurance_verified === true ? <ShieldCheck size={14} /> : <ShieldAlert size={14} />}
                <span>{order.insurance_notes}</span>
              </div>
            )}

            {/* Hold reason */}
            {order.hold_reason && (
              <div className="text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded px-3 py-2">
                <span className="font-medium">On hold: </span>{order.hold_reason}
              </div>
            )}

            {/* Patient notes (from confirmation) */}
            {order.patient_notes && (
              <div className="text-xs text-blue-700 bg-blue-50 border border-blue-200 rounded px-3 py-2">
                <span className="font-medium">Patient notes: </span>{order.patient_notes}
              </div>
            )}

            {/* Staff notes */}
            {order.staff_notes && (
              <div className="text-xs text-gray-600 bg-white border rounded px-3 py-2">
                <span className="font-medium">Staff notes: </span>{order.staff_notes}
              </div>
            )}

            {/* Rejection reason */}
            {order.rejection_reason && (
              <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
                <span className="font-medium">Rejected: </span>{order.rejection_reason}
              </div>
            )}

            {/* Actions — contextual based on status */}
            <div className="flex flex-wrap gap-2 pt-1">
              {/* Update Encounter — any active order */}
              {!['rejected', 'fulfilled', 'cancelled'].includes(order.status) && (
                <button disabled={busy} onClick={() => setModal('encounter')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-blue-300 text-blue-700 hover:bg-blue-50 flex items-center gap-1.5 disabled:opacity-50">
                  <CalendarClock size={13} /> Update Encounter
                </button>
              )}

              {/* Compliance check — any active order */}
              {!['rejected', 'fulfilled', 'cancelled'].includes(order.status) && (
                <button disabled={busy} onClick={() => setModal('compliance')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-purple-300 text-purple-700 hover:bg-purple-50 flex items-center gap-1.5 disabled:opacity-50">
                  <Activity size={13} /> Check Compliance
                </button>
              )}

              {/* Verify Insurance — pending or verified */}
              {['pending', 'verified'].includes(order.status) && (
                <button disabled={busy} onClick={() => act(() => onAction('verify', order.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 hover:bg-indigo-50 flex items-center gap-1.5 disabled:opacity-50">
                  <ShieldCheck size={13} /> Verify Insurance
                </button>
              )}

              {/* Approve — pending or verified */}
              {['pending', 'verified'].includes(order.status) && (
                <button disabled={busy} onClick={() => act(() => onAction('approve', order.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-green-300 text-green-700 hover:bg-green-50 flex items-center gap-1.5 disabled:opacity-50">
                  <CheckCircle2 size={13} /> Approve
                </button>
              )}

              {/* Send confirmation to patient — approved */}
              {order.status === 'approved' && (
                <button disabled={busy} onClick={async () => {
                  setBusy(true)
                  try {
                    const result = await sendDMEConfirmation(order.id, 'sms')
                    setConfirmationUrl(result.confirmation_url)
                    setModal('link')
                    onAction('refresh')
                  } catch (err) { onAction('error', null, err.message) } finally { setBusy(false) }
                }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-cyan-300 text-cyan-700 hover:bg-cyan-50 flex items-center gap-1.5 disabled:opacity-50">
                  <Send size={13} /> Send to Patient
                </button>
              )}

              {/* Order from vendor — patient_confirmed */}
              {order.status === 'patient_confirmed' && (
                <button disabled={busy} onClick={() => setModal('vendor')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-blue-300 text-blue-700 hover:bg-blue-50 flex items-center gap-1.5 disabled:opacity-50">
                  <ShoppingCart size={13} /> Order from Vendor
                </button>
              )}

              {/* Mark shipped — ordering */}
              {order.status === 'ordering' && (
                <button disabled={busy} onClick={() => setModal('ship')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-indigo-300 text-indigo-700 hover:bg-indigo-50 flex items-center gap-1.5 disabled:opacity-50">
                  {order.fulfillment_method === 'pickup' ? <Store size={13} /> : <Truck size={13} />}
                  {order.fulfillment_method === 'pickup' ? 'Ready for Pickup' : 'Mark Shipped'}
                </button>
              )}

              {/* Mark fulfilled — shipped */}
              {order.status === 'shipped' && (
                <button disabled={busy} onClick={() => act(() => onAction('fulfill', order.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-green-300 text-green-700 hover:bg-green-50 flex items-center gap-1.5 disabled:opacity-50">
                  <Package size={13} /> Mark Delivered
                </button>
              )}

              {/* Resume — on_hold */}
              {order.status === 'on_hold' && (
                <button disabled={busy} onClick={() => act(() => onAction('resume', order.id))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-green-300 text-green-700 hover:bg-green-50 flex items-center gap-1.5 disabled:opacity-50">
                  <Play size={13} /> Resume
                </button>
              )}

              {/* Hold — any active status */}
              {!['rejected', 'fulfilled', 'cancelled', 'on_hold'].includes(order.status) && (
                <button disabled={busy} onClick={() => setModal('hold')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-orange-300 text-orange-600 hover:bg-orange-50 flex items-center gap-1.5 disabled:opacity-50">
                  <PauseCircle size={13} /> Hold
                </button>
              )}

              {/* Reject — any active status */}
              {!['rejected', 'fulfilled', 'cancelled'].includes(order.status) && (
                <button disabled={busy} onClick={() => setModal('reject')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-red-300 text-red-600 hover:bg-red-50 flex items-center gap-1.5 disabled:opacity-50">
                  <XCircle size={13} /> Reject
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


// ── Main component ───────────────────────────────────────────────

const LANES = [
  { key: 'incoming',   label: 'New Orders',         icon: Inbox,       variant: 'warning',  color: 'text-amber-700' },
  { key: 'autoRefill', label: 'Auto-Refill Due',    icon: RotateCcw,   variant: 'purple',   color: 'text-purple-700' },
  { key: 'inProgress', label: 'In Progress',        icon: Clock,       variant: 'info',     color: 'text-indigo-700' },
  { key: 'awaiting',   label: 'Awaiting Patient',   icon: UserCheck,   variant: 'cyan',     color: 'text-cyan-700' },
  { key: 'confirmed',  label: 'Ready to Order',     icon: ShoppingCart, variant: 'emerald', color: 'text-emerald-700' },
  { key: 'onHold',     label: 'On Hold',            icon: PauseCircle, variant: 'orange',   color: 'text-orange-700' },
]

export default function DMEAdmin() {
  const [dashboard, setDashboard] = useState(null)
  const [lanes, setLanes] = useState({})
  const [allOrders, setAllOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeView, setActiveView] = useState('pipeline')
  const [allFilter, setAllFilter] = useState('all')
  const [rxScanning, setRxScanning] = useState(false)
  const [rxResults, setRxResults] = useState(null)
  const [rxHistory, setRxHistory] = useState([])
  const [error, setError] = useState(null)
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [dash, inc, refill, prog, await_, conf, hold, all] = await Promise.all([
        getDMEDashboard(),
        getDMEIncoming(),
        getDMEAutoRefillPending(),
        getDMEInProgress(),
        getDMEAwaitingPatient(),
        getDMEPatientConfirmed(),
        getDMEOnHold(),
        listDMEOrders(),
      ])
      setDashboard(dash)
      setLanes({ incoming: inc, autoRefill: refill, inProgress: prog, awaiting: await_, confirmed: conf, onHold: hold })
      setAllOrders(all)
    } catch (err) {
      console.error('DME admin load failed:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAction = async (action, orderId, extra) => {
    if (action === 'refresh') { load(); return }
    if (action === 'error') { setError(extra); return }
    try {
      if (action === 'verify')           await verifyDMEInsurance(orderId)
      if (action === 'approve')          await approveDMEOrder(orderId)
      if (action === 'reject')           await rejectDMEOrder(orderId, extra)
      if (action === 'fulfill')          await fulfillDMEOrder(orderId)
      if (action === 'hold')             await holdDMEOrder(orderId, extra)
      if (action === 'resume')           await resumeDMEOrder(orderId)
      if (action === 'mark-ordered')     await markDMEOrdered(orderId, extra.vendor, extra.orderId)
      if (action === 'mark-shipped')     await markDMEShipped(orderId, extra.tracking, extra.carrier, extra.date)
      if (action === 'update-encounter') {
        await updateDMEEncounter(orderId, {
          last_encounter_date: extra.date,
          last_encounter_type: extra.type,
          last_encounter_provider: extra.provider,
          last_encounter_provider_npi: extra.npi,
        })
      }
      if (action === 'check-compliance') {
        await updateDMECompliance(orderId, extra)
      }
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const scanForPrescriptions = async () => {
    setRxScanning(true)
    try {
      const result = await pollPrescriptions()
      setRxResults(result)
      // Refresh Rx history and DME orders (new orders may have been created)
      const [history] = await Promise.all([listPrescriptions(), load()])
      setRxHistory(history)
    } catch (err) {
      setError(`Rx scan failed: ${err.message}`)
    } finally {
      setRxScanning(false)
    }
  }

  // Load Rx history on mount
  useEffect(() => {
    listPrescriptions().then(setRxHistory).catch(() => {})
  }, [])

  const d = dashboard || {}
  const laneCount = (key) => lanes[key]?.length ?? 0

  const allFiltered = allFilter === 'all' ? allOrders : allOrders.filter(o => o.status === allFilter)
  const ALL_STATUSES = ['all', 'pending', 'verified', 'approved', 'patient_contacted', 'patient_confirmed', 'ordering', 'shipped', 'fulfilled', 'on_hold', 'rejected', 'cancelled']

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">DME Workflow</h1>
          <p className="text-xs text-gray-400">Sleep medicine supply management</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={scanForPrescriptions} disabled={rxScanning}
            className="text-sm flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50 transition-colors">
            {rxScanning ? <RefreshCw size={14} className="animate-spin" /> : <Pill size={14} />}
            {rxScanning ? 'Scanning eCW...' : 'Scan for Rx'}
          </button>
          <button onClick={() => setActiveView(activeView === 'pipeline' ? 'all_orders' : 'pipeline')}
            className="btn-secondary text-sm">
            {activeView === 'pipeline' ? 'All Orders' : 'Pipeline'}
          </button>
          <button onClick={load} disabled={loading} className="btn-secondary text-sm flex items-center gap-2">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        {LANES.map(l => (
          <StatCard key={l.key} label={l.label} value={laneCount(l.key)} icon={l.icon} variant={l.variant} />
        ))}
        <StatCard label="Fulfilled" value={d.fulfilled ?? '—'} icon={Archive} variant="default"
          onClick={() => { setActiveView('all_orders'); setAllFilter('fulfilled') }} />
      </div>

      {/* Rx scan results banner */}
      {rxResults && (
        <div className={`rounded-xl border px-4 py-3 ${
          rxResults.orders_created > 0 ? 'bg-teal-50 border-teal-200' : 'bg-gray-50 border-gray-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Pill size={16} className={rxResults.orders_created > 0 ? 'text-teal-600' : 'text-gray-400'} />
              <span className="text-sm font-medium text-gray-800">
                {rxResults.orders_created > 0
                  ? `${rxResults.orders_created} new Rx order${rxResults.orders_created > 1 ? 's' : ''} created from eCW`
                  : rxResults.detected > 0
                    ? `${rxResults.detected} prescription${rxResults.detected > 1 ? 's' : ''} found, ${rxResults.failed} failed`
                    : 'No new prescriptions found in eCW'}
              </span>
            </div>
            <button onClick={() => setRxResults(null)} className="text-xs text-gray-400 hover:text-gray-600">Dismiss</button>
          </div>
        </div>
      )}

      {/* Detected prescriptions history */}
      {rxHistory.length > 0 && (
        <div className="space-y-2">
          <SectionHeader icon={Pill} title="Recent Prescriptions" count={rxHistory.length} color="text-teal-700" />
          <div className="space-y-1">
            {rxHistory.map(rx => (
              <div key={rx.id} className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border text-sm ${
                rx.status === 'order_created' ? 'bg-teal-50 border-teal-200'
                : rx.status === 'failed' ? 'bg-red-50 border-red-200'
                : 'bg-yellow-50 border-yellow-200'
              }`}>
                <div className="flex-1 min-w-0">
                  <span className="font-medium text-gray-900">{rx.description || rx.id}</span>
                  <span className="text-xs text-gray-500 ml-2">by {rx.author || 'Unknown'}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                  rx.status === 'order_created' ? 'bg-teal-100 text-teal-700 border-teal-200'
                  : rx.status === 'failed' ? 'bg-red-100 text-red-700 border-red-200'
                  : rx.status === 'extracted' ? 'bg-blue-100 text-blue-700 border-blue-200'
                  : 'bg-yellow-100 text-yellow-700 border-yellow-200'
                }`}>
                  {rx.status === 'order_created' ? `Order ${rx.dme_order_id}` : rx.status.replace('_', ' ')}
                </span>
                {rx.error && <span className="text-xs text-red-500 truncate max-w-48" title={rx.error}>{rx.error}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <p className="text-gray-400 text-center py-12">Loading...</p>
      ) : activeView === 'pipeline' ? (
        <div className="space-y-8">
          {LANES.map(lane => {
            const orders = lanes[lane.key] || []
            return (
              <section key={lane.key}>
                <SectionHeader icon={lane.icon} title={lane.label} count={orders.length} color={lane.color} />
                {orders.length === 0 ? (
                  <EmptyState icon={lane.icon} message={`No orders in ${lane.label.toLowerCase()}`} />
                ) : (
                  <div className="space-y-2">
                    {orders.map(o => <OrderRow key={o.id} order={o} onAction={handleAction} />)}
                  </div>
                )}
              </section>
            )
          })}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex gap-1 flex-wrap">
            {ALL_STATUSES.map(f => (
              <button key={f} onClick={() => setAllFilter(f)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  allFilter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}>
                {f === 'all' ? `All (${allOrders.length})` : `${STATUS_LABEL[f] || f} (${allOrders.filter(o => o.status === f).length})`}
              </button>
            ))}
          </div>
          {allFiltered.length === 0 ? (
            <EmptyState icon={Package} message={`No ${allFilter !== 'all' ? STATUS_LABEL[allFilter]?.toLowerCase() || allFilter : ''} orders`} />
          ) : (
            <div className="space-y-2">
              {allFiltered.map(o => <OrderRow key={o.id} order={o} onAction={handleAction} />)}
            </div>
          )}
        </div>
      )}

      {/* Workflow guide */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-1">DME Supply Workflow</h3>
        <ol className="text-sm text-blue-600 leading-relaxed list-decimal list-inside space-y-1">
          <li>New orders and auto-refills appear in their respective lanes</li>
          <li>Check compliance (AirPM) and verify insurance coverage</li>
          <li><strong>Approve</strong>, then <strong>Send to Patient</strong> — generates a confirmation link</li>
          <li>Patient confirms address and chooses pickup or shipping</li>
          <li><strong>Order from Vendor</strong> when patient confirms, then track through delivery</li>
          <li>Fulfilled orders auto-schedule the next refill based on frequency</li>
        </ol>
      </div>
    </div>
  )
}
