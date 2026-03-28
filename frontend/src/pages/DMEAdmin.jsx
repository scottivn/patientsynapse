import { useEffect, useState, useCallback } from 'react'
import {
  Package, RefreshCw, ShieldCheck, ShieldAlert, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, AlertTriangle, Send, Copy, ExternalLink,
  Inbox, Clock, Activity, FileText, Truck, Store,
  PauseCircle, Play, UserCheck, ShoppingCart, Archive, CalendarClock,
  Pill, Search, Plus, X, Cpu, User, Warehouse,
} from 'lucide-react'
import ErrorBanner from '../components/ErrorBanner'
import DMEInventory from '../components/DMEInventory'
import {
  listDMEOrders, getDMEDashboard,
  getDMEIncoming, getDMEInProgress,
  getDMEAwaitingPatient, getDMEPatientConfirmed, getDMEOnHold,
  verifyDMEInsurance, approveDMEOrder, rejectDMEOrder, fulfillDMEOrder,
  updateDMECompliance, holdDMEOrder, resumeDMEOrder,
  sendDMEConfirmation, markDMEOrdered, markDMEShipped,
  pollPrescriptions, listPrescriptions,
  getDMEExpiringEncounters, processDMEAutoDeliveries,
  getDMEReceipt, getDMEDeliveryTicket,
  searchDMEPatients, createAdminDMEOrder,
  getDMEProducts, getDMEProductCategories, getDMEVendors,
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

const VENDOR_OPTIONS = ['In-House', 'PPM', 'VGM', 'Other']

function VendorModal({ onConfirm, onCancel }) {
  const [vendor, setVendor] = useState('')
  const [customVendor, setCustomVendor] = useState('')
  const [orderId, setOrderId] = useState('')
  const effectiveVendor = vendor === 'Other' ? `Other: ${customVendor}` : vendor
  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm space-y-4" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold text-gray-900">Order from Vendor</h3>
        <select className="input w-full" value={vendor} onChange={e => setVendor(e.target.value)}>
          <option value="">Select vendor...</option>
          {VENDOR_OPTIONS.map(v => <option key={v} value={v}>{v}</option>)}
        </select>
        {vendor === 'Other' && (
          <input className="input w-full" placeholder="Vendor name" value={customVendor} onChange={e => setCustomVendor(e.target.value)} />
        )}
        <input className="input w-full" placeholder="Vendor order ID (optional)" value={orderId} onChange={e => setOrderId(e.target.value)} />
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-secondary text-sm">Cancel</button>
          <button onClick={() => onConfirm(effectiveVendor, orderId)} className="btn-primary text-sm" disabled={!vendor || (vendor === 'Other' && !customVendor)}>Mark Ordered</button>
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

            {/* Patient-reported issue */}
            {order.patient_rejected && (
              <div className="text-xs text-orange-700 bg-orange-50 border border-orange-200 rounded px-3 py-2">
                <span className="font-medium">Patient flagged issue: </span>{order.patient_rejection_reason || 'No details provided'}
                {order.patient_callback_requested && (
                  <span className="ml-2 inline-flex items-center gap-1 text-orange-800 font-medium">
                    — Callback requested
                  </span>
                )}
              </div>
            )}

            {/* Actions — contextual based on status */}
            <div className="flex flex-wrap gap-2 pt-1">
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

              {/* View patient link — patient_contacted (token already generated) */}
              {order.status === 'patient_contacted' && order.confirmation_token && (
                <button onClick={() => {
                  setConfirmationUrl(`${window.location.origin}/dme/confirm/${order.confirmation_token}`)
                  setModal('link')
                }}
                  className="text-xs px-3 py-1.5 rounded-lg border border-cyan-300 text-cyan-700 hover:bg-cyan-50 flex items-center gap-1.5">
                  <ExternalLink size={13} /> Patient Link
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
                <>
                  <button disabled={busy} onClick={() => act(() => onAction('fulfill', order.id))}
                    className="text-xs px-3 py-1.5 rounded-lg border border-green-300 text-green-700 hover:bg-green-50 flex items-center gap-1.5 disabled:opacity-50">
                    <Package size={13} /> Mark Delivered
                  </button>
                  {order.auto_deliver_after && (
                    <span className="text-[10px] text-gray-400 flex items-center gap-1">
                      <Clock size={10} /> Auto-delivers {new Date(order.auto_deliver_after).toLocaleDateString()}
                    </span>
                  )}
                </>
              )}

              {/* Print receipt — fulfilled orders */}
              {order.status === 'fulfilled' && (
                <button disabled={busy} onClick={() => window.open(`/api/dme/orders/${order.id}/receipt`, '_blank')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 flex items-center gap-1.5 disabled:opacity-50">
                  <FileText size={13} /> Print Receipt
                </button>
              )}

              {/* Print delivery ticket — shipped or fulfilled */}
              {['shipped', 'fulfilled'].includes(order.status) && (
                <button disabled={busy} onClick={() => window.open(`/api/dme/orders/${order.id}/delivery-ticket`, '_blank')}
                  className="text-xs px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 flex items-center gap-1.5 disabled:opacity-50">
                  <Truck size={13} /> Delivery Ticket
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


// ── Equipment constants ──────────────────────────────────────────

const REFILL_FREQUENCIES = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly (90 days)' },
  { value: 'biannual', label: 'Every 6 months' },
  { value: 'annual', label: 'Annual' },
]

const VENDOR_PORTALS = {
  PPM: 'https://dev.ppmfulfillment.com/Login.aspx',
  VGM: 'https://www.vgm.com/login/?returnURL=%2fportal%2f',
}


// ── Product Selection (shared between patient and newPatient steps) ──

function ProductSelector({ form, setForm, products, categories }) {
  const selectedProduct = products.find(p => p.id === form.product_id)
  const categoryProducts = form.equipment_category
    ? products.filter(p => p.category === form.equipment_category)
    : []

  return (
    <div className="space-y-3">
      <div>
        <label className="text-xs font-medium text-gray-600">Category</label>
        <select value={form.equipment_category} onChange={e => setForm(f => ({
          ...f, equipment_category: e.target.value, product_id: '', size: '', equipment_description: '',
        }))} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm bg-white">
          <option value="">Select category...</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      {form.equipment_category && (
        <div>
          <label className="text-xs font-medium text-gray-600">Product</label>
          <select value={form.product_id || ''} onChange={e => {
            const prod = products.find(p => p.id === e.target.value)
            setForm(f => ({
              ...f,
              product_id: e.target.value,
              equipment_description: prod ? `${prod.name} (${prod.hcpcs_code})` : '',
              size: '',
            }))
          }} className="w-full mt-1 px-3 py-2 border rounded-lg text-sm bg-white">
            <option value="">Select product...</option>
            {categoryProducts.map(p => (
              <option key={p.id} value={p.id}>{p.name} — {p.hcpcs_code}</option>
            ))}
          </select>
        </div>
      )}

      {selectedProduct?.has_sizes && selectedProduct.available_sizes?.length > 0 && (
        <div>
          <label className="text-xs font-medium text-gray-600">Size</label>
          <select value={form.size || ''} onChange={e => setForm(f => ({ ...f, size: e.target.value }))}
            className="w-full mt-1 px-3 py-2 border rounded-lg text-sm bg-white">
            <option value="">Select size...</option>
            {selectedProduct.available_sizes.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      )}

      {selectedProduct && (
        <div className="text-xs bg-gray-50 border rounded-lg p-2.5 space-y-1">
          <p className="text-gray-500">{selectedProduct.description}</p>
          <p className="text-gray-400">
            HCPCS: <span className="font-mono">{selectedProduct.hcpcs_code}</span>
            {selectedProduct.resupply_months && <> · Resupply: every {selectedProduct.resupply_months} mo</>}
          </p>
          {selectedProduct.vendors?.length > 0 && (
            <div className="flex items-center gap-2 pt-1">
              <span className="text-gray-400">Order via:</span>
              {selectedProduct.vendors.map(v => VENDOR_PORTALS[v] ? (
                <a key={v} href={VENDOR_PORTALS[v]} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 font-medium">
                  {v} <ExternalLink size={10} />
                </a>
              ) : (
                <span key={v} className="text-gray-600 font-medium">{v}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}


// ── New Order Slide-Over Panel ──────────────────────────────────

function NewOrderPanel({ open, onClose, onCreated }) {
  const [step, setStep] = useState('search') // search | patient | form | newPatient
  const [searchMode, setSearchMode] = useState('name') // name | mrn
  const [searchFields, setSearchFields] = useState({ family: '', given: '', dob: '', mrn: '' })
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState(null)
  const [selectedPatient, setSelectedPatient] = useState(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [form, setForm] = useState({
    equipment_category: '', equipment_description: '', product_id: '', size: '', quantity: 1,
    diagnosis_code: '', diagnosis_description: '', referring_physician: '', referring_npi: '',
    clinical_notes: '', auto_replace: false, auto_replace_frequency: 'quarterly',
  })

  // Load product catalog when panel opens
  useEffect(() => {
    if (open && products.length === 0) {
      Promise.all([getDMEProducts(), getDMEProductCategories()])
        .then(([prods, cats]) => { setProducts(prods); setCategories(cats) })
        .catch(() => {})
    }
  }, [open, products.length])
  // New patient fields (when creating from scratch)
  const [newPatient, setNewPatient] = useState({
    first_name: '', last_name: '', dob: '', phone: '', email: '',
    address: '', city: '', state: '', zip: '',
    insurance_payer: '', insurance_member_id: '', insurance_group: '',
  })

  const resetPanel = () => {
    setStep('search')
    setResults(null)
    setSelectedPatient(null)
    setError(null)
    setSearchFields({ family: '', given: '', dob: '', mrn: '' })
    setForm({ equipment_category: '', equipment_description: '', product_id: '', size: '', quantity: 1,
      diagnosis_code: '', diagnosis_description: '', referring_physician: '', referring_npi: '',
      clinical_notes: '', auto_replace: false, auto_replace_frequency: 'quarterly' })
    setNewPatient({ first_name: '', last_name: '', dob: '', phone: '', email: '',
      address: '', city: '', state: '', zip: '',
      insurance_payer: '', insurance_member_id: '', insurance_group: '' })
  }

  const handleSearch = async () => {
    setSearching(true)
    setError(null)
    try {
      const params = searchMode === 'mrn'
        ? { mrn: searchFields.mrn }
        : { family: searchFields.family, given: searchFields.given, dob: searchFields.dob }
      const data = await searchDMEPatients(params)
      setResults(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSearching(false)
    }
  }

  const handleSelectPatient = (patient) => {
    setSelectedPatient(patient)
    setStep('patient')
  }

  const handleSubmit = async () => {
    setCreating(true)
    setError(null)
    try {
      const orderData = step === 'newPatient' ? {
        patient_first_name: newPatient.first_name,
        patient_last_name: newPatient.last_name,
        patient_dob: newPatient.dob,
        patient_phone: newPatient.phone,
        patient_email: newPatient.email,
        patient_address: newPatient.address,
        patient_city: newPatient.city,
        patient_state: newPatient.state,
        patient_zip: newPatient.zip,
        insurance_payer: newPatient.insurance_payer,
        insurance_member_id: newPatient.insurance_member_id,
        insurance_group: newPatient.insurance_group,
        ...form,
        origin: 'staff_initiated',
      } : {
        patient_first_name: selectedPatient.first_name,
        patient_last_name: selectedPatient.last_name,
        patient_dob: selectedPatient.dob,
        patient_phone: selectedPatient.phone,
        patient_email: selectedPatient.email || '',
        patient_address: selectedPatient.address,
        patient_city: selectedPatient.city,
        patient_state: selectedPatient.state,
        patient_zip: selectedPatient.zip,
        patient_id: selectedPatient.patient_id,
        insurance_payer: selectedPatient.insurance?.payer || '',
        insurance_member_id: selectedPatient.insurance?.member_id || '',
        insurance_group: selectedPatient.insurance?.group || '',
        ...form,
        origin: 'staff_initiated',
      }
      await createAdminDMEOrder(orderData)
      resetPanel()
      onClose()
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  if (!open) return null

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/30 z-40" onClick={() => { resetPanel(); onClose() }} />

      {/* Panel */}
      <div className="fixed right-0 top-0 h-full w-full max-w-lg bg-white shadow-2xl z-50 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b bg-gray-50">
          <h2 className="text-lg font-bold text-gray-900">New DME Order</h2>
          <button onClick={() => { resetPanel(); onClose() }} className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>

        {error && <div className="px-5 pt-3"><ErrorBanner message={error} onDismiss={() => setError(null)} /></div>}

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">

          {/* Step 1: Patient Search */}
          {step === 'search' && (
            <div className="space-y-4">
              <div className="flex gap-2 mb-2">
                <button onClick={() => setSearchMode('name')}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium ${searchMode === 'name' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
                  Name + DOB
                </button>
                <button onClick={() => setSearchMode('mrn')}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium ${searchMode === 'mrn' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>
                  MRN
                </button>
              </div>

              {searchMode === 'name' ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600">Last Name</label>
                    <input value={searchFields.family} onChange={e => setSearchFields(f => ({ ...f, family: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Garcia" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">First Name</label>
                    <input value={searchFields.given} onChange={e => setSearchFields(f => ({ ...f, given: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Maria" />
                  </div>
                  <div className="col-span-2">
                    <label className="text-xs font-medium text-gray-600">Date of Birth</label>
                    <input type="date" value={searchFields.dob} onChange={e => setSearchFields(f => ({ ...f, dob: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-xs font-medium text-gray-600">MRN / Patient ID</label>
                  <input value={searchFields.mrn} onChange={e => setSearchFields(f => ({ ...f, mrn: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="PT001" />
                </div>
              )}

              <button onClick={handleSearch} disabled={searching || (searchMode === 'name' && !searchFields.family && !searchFields.given)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {searching ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
                {searching ? 'Searching EMR...' : 'Search Patients'}
              </button>

              {/* Results */}
              {results && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 font-medium">{results.length} patient{results.length !== 1 ? 's' : ''} found</p>
                  {results.length === 0 && (
                    <div className="text-center py-6 space-y-2">
                      <p className="text-sm text-gray-500">No patients found in EMR</p>
                      <button onClick={() => setStep('newPatient')} className="text-sm text-blue-600 hover:text-blue-700 font-medium">
                        + Create New Patient
                      </button>
                    </div>
                  )}
                  {results.map((p, i) => (
                    <div key={i} onClick={() => handleSelectPatient(p)}
                      className="border rounded-lg p-3 cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-sm text-gray-900">{p.first_name} {p.last_name}</span>
                          <span className="text-xs text-gray-400 ml-2">DOB: {p.dob}</span>
                        </div>
                        <span className="text-xs text-gray-400">ID: {p.patient_id}</span>
                      </div>
                      {p.insurance?.payer && (
                        <p className="text-xs text-gray-500 mt-1">Insurance: {p.insurance.payer}</p>
                      )}
                      {p.devices?.length > 0 && (
                        <p className="text-xs text-purple-600 mt-1">
                          <Cpu size={10} className="inline mr-1" />
                          {p.devices.map(d => `${d.manufacturer} ${d.model}`).join(', ')}
                        </p>
                      )}
                    </div>
                  ))}
                  {results.length > 0 && (
                    <button onClick={() => setStep('newPatient')} className="text-xs text-blue-600 hover:text-blue-700 font-medium mt-2">
                      Patient not listed? Create New Patient
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 2: Patient Selected — show details + create order */}
          {step === 'patient' && selectedPatient && (
            <div className="space-y-4">
              <button onClick={() => setStep('search')} className="text-xs text-blue-600 hover:text-blue-700">← Back to search</button>

              {/* Patient card */}
              <div className="border rounded-lg p-4 bg-gray-50">
                <div className="flex items-center gap-2 mb-2">
                  <User size={16} className="text-gray-500" />
                  <span className="font-semibold text-gray-900">{selectedPatient.first_name} {selectedPatient.last_name}</span>
                  <span className="text-xs text-gray-400">#{selectedPatient.patient_id}</span>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
                  <span>DOB: {selectedPatient.dob}</span>
                  <span>Phone: {selectedPatient.phone || '—'}</span>
                  <span className="col-span-2">Address: {[selectedPatient.address, selectedPatient.city, selectedPatient.state, selectedPatient.zip].filter(Boolean).join(', ') || '—'}</span>
                </div>
                {selectedPatient.insurance?.payer && (
                  <div className="mt-2 text-xs">
                    <span className="font-medium text-gray-700">Insurance: </span>
                    <span className="text-gray-600">{selectedPatient.insurance.payer}</span>
                    {selectedPatient.insurance.member_id && <span className="text-gray-400 ml-2">ID: {selectedPatient.insurance.member_id}</span>}
                  </div>
                )}
              </div>

              {/* Devices */}
              {selectedPatient.devices?.length > 0 && (
                <div className="border rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-gray-700 mb-2 flex items-center gap-1"><Cpu size={12} /> Current Equipment</h4>
                  <div className="space-y-1.5">
                    {selectedPatient.devices.map((d, i) => (
                      <div key={i} className="text-xs text-gray-600 flex items-start gap-2">
                        <span className="text-purple-500">•</span>
                        <div>
                          <span className="font-medium">{d.type}</span>
                          {d.manufacturer && <span className="text-gray-400"> — {d.manufacturer} {d.model}</span>}
                          {d.notes && <p className="text-gray-400 mt-0.5">{d.notes}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent orders */}
              {selectedPatient.recent_orders?.length > 0 && (
                <div className="border rounded-lg p-3">
                  <h4 className="text-xs font-semibold text-gray-700 mb-2">Recent DME Orders</h4>
                  <div className="space-y-1">
                    {selectedPatient.recent_orders.slice(0, 5).map(o => (
                      <div key={o.id} className="flex items-center justify-between text-xs">
                        <span className="text-gray-600">#{o.id} — {o.equipment_description || o.equipment_category}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          o.status === 'fulfilled' ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
                        }`}>{o.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Order form */}
              <div className="border-t pt-4 space-y-3">
                <h4 className="text-sm font-semibold text-gray-900">Create Order</h4>

                <ProductSelector form={form} setForm={setForm} products={products} categories={categories} />

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600">Diagnosis Code</label>
                    <input value={form.diagnosis_code} onChange={e => setForm(f => ({ ...f, diagnosis_code: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="G47.33" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">Diagnosis</label>
                    <input value={form.diagnosis_description} onChange={e => setForm(f => ({ ...f, diagnosis_description: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Obstructive Sleep Apnea" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600">Referring Physician</label>
                    <input value={form.referring_physician} onChange={e => setForm(f => ({ ...f, referring_physician: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Dr. Reyes" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">NPI</label>
                    <input value={form.referring_npi} onChange={e => setForm(f => ({ ...f, referring_npi: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="1234567890" />
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-600">Notes</label>
                  <textarea value={form.clinical_notes} onChange={e => setForm(f => ({ ...f, clinical_notes: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" rows={2} placeholder="e.g., patient requested different mask size" />
                </div>

                {/* Auto-refill toggle */}
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={form.auto_replace}
                      onChange={e => setForm(f => ({ ...f, auto_replace: e.target.checked }))}
                      className="rounded border-purple-300 text-purple-600 focus:ring-purple-500" />
                    <span className="text-sm font-medium text-purple-800">Auto-Refill</span>
                  </label>
                  {form.auto_replace && (
                    <select value={form.auto_replace_frequency}
                      onChange={e => setForm(f => ({ ...f, auto_replace_frequency: e.target.value }))}
                      className="w-full px-3 py-1.5 border border-purple-200 rounded-lg text-sm bg-white">
                      {REFILL_FREQUENCIES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                    </select>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* New patient form (no EMR match) */}
          {step === 'newPatient' && (
            <div className="space-y-4">
              <button onClick={() => setStep('search')} className="text-xs text-blue-600 hover:text-blue-700">← Back to search</button>

              <h4 className="text-sm font-semibold text-gray-900">New Patient</h4>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">First Name *</label>
                  <input value={newPatient.first_name} onChange={e => setNewPatient(p => ({ ...p, first_name: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Last Name *</label>
                  <input value={newPatient.last_name} onChange={e => setNewPatient(p => ({ ...p, last_name: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Date of Birth</label>
                  <input type="date" value={newPatient.dob} onChange={e => setNewPatient(p => ({ ...p, dob: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Phone</label>
                  <input value={newPatient.phone} onChange={e => setNewPatient(p => ({ ...p, phone: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="(210) 555-0100" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs font-medium text-gray-600">Email</label>
                  <input type="email" value={newPatient.email} onChange={e => setNewPatient(p => ({ ...p, email: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">Address</label>
                  <input value={newPatient.address} onChange={e => setNewPatient(p => ({ ...p, address: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="text-xs font-medium text-gray-600">City</label>
                    <input value={newPatient.city} onChange={e => setNewPatient(p => ({ ...p, city: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">State</label>
                    <input value={newPatient.state} onChange={e => setNewPatient(p => ({ ...p, state: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" maxLength={2} placeholder="TX" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-gray-600">ZIP</label>
                    <input value={newPatient.zip} onChange={e => setNewPatient(p => ({ ...p, zip: e.target.value }))}
                      className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" maxLength={10} />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-600">Insurance</label>
                  <input value={newPatient.insurance_payer} onChange={e => setNewPatient(p => ({ ...p, insurance_payer: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" placeholder="Aetna" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Member ID</label>
                  <input value={newPatient.insurance_member_id} onChange={e => setNewPatient(p => ({ ...p, insurance_member_id: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Group</label>
                  <input value={newPatient.insurance_group} onChange={e => setNewPatient(p => ({ ...p, insurance_group: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 border rounded-lg text-sm" />
                </div>
              </div>

              {/* Same order form as the patient step */}
              <div className="border-t pt-4 space-y-3">
                <h4 className="text-sm font-semibold text-gray-900">Order Details</h4>
                <ProductSelector form={form} setForm={setForm} products={products} categories={categories} />
                <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" checked={form.auto_replace}
                      onChange={e => setForm(f => ({ ...f, auto_replace: e.target.checked }))}
                      className="rounded border-purple-300 text-purple-600 focus:ring-purple-500" />
                    <span className="text-sm font-medium text-purple-800">Auto-Refill</span>
                  </label>
                  {form.auto_replace && (
                    <select value={form.auto_replace_frequency}
                      onChange={e => setForm(f => ({ ...f, auto_replace_frequency: e.target.value }))}
                      className="w-full px-3 py-1.5 border border-purple-200 rounded-lg text-sm bg-white">
                      {REFILL_FREQUENCIES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                    </select>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer — Create button */}
        {(step === 'patient' || step === 'newPatient') && (
          <div className="border-t px-5 py-4 bg-gray-50">
            <button onClick={handleSubmit} disabled={creating || (!form.equipment_category && !form.equipment_description) ||
              (step === 'newPatient' && (!newPatient.first_name || !newPatient.last_name))}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50 transition-colors">
              {creating ? <RefreshCw size={14} className="animate-spin" /> : <Plus size={14} />}
              {creating ? 'Creating Order...' : 'Create Order'}
            </button>
          </div>
        )}
      </div>
    </>
  )
}


// ── Main component ───────────────────────────────────────────────

const LANES = [
  { key: 'incoming',   label: 'New Orders',         icon: Inbox,       variant: 'warning',  color: 'text-amber-700' },
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
  const [expiringEncounters, setExpiringEncounters] = useState([])
  const [newOrderOpen, setNewOrderOpen] = useState(false)
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [dash, inc, prog, await_, conf, hold, all] = await Promise.all([
        getDMEDashboard(),
        getDMEIncoming(),
        getDMEInProgress(),
        getDMEAwaitingPatient(),
        getDMEPatientConfirmed(),
        getDMEOnHold(),
        listDMEOrders(),
      ])
      setDashboard(dash)
      setLanes({ incoming: inc, inProgress: prog, awaiting: await_, confirmed: conf, onHold: hold })
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

  // Load Rx history, expiring encounters, and process auto-deliveries on mount
  useEffect(() => {
    listPrescriptions().then(setRxHistory).catch(() => {})
    getDMEExpiringEncounters().then(setExpiringEncounters).catch(() => {})
    processDMEAutoDeliveries().catch(() => {})
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
          <button onClick={() => setNewOrderOpen(true)}
            className="text-sm flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors">
            <Plus size={14} /> New Order
          </button>
          <button onClick={scanForPrescriptions} disabled={rxScanning}
            className="text-sm flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50 transition-colors">
            {rxScanning ? <RefreshCw size={14} className="animate-spin" /> : <Pill size={14} />}
            {rxScanning ? 'Scanning eCW...' : 'Scan for Rx'}
          </button>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            {[
              { key: 'pipeline', label: 'Pipeline' },
              { key: 'all_orders', label: 'All Orders' },
              { key: 'inventory', label: 'Inventory', icon: Warehouse },
            ].map(v => (
              <button key={v.key} onClick={() => setActiveView(v.key)}
                className={`px-3 py-1.5 font-medium flex items-center gap-1.5 transition-colors ${
                  activeView === v.key ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
                }`}>
                {v.icon && <v.icon size={13} />}
                {v.label}
              </button>
            ))}
          </div>
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

      {/* Expiring encounters alert */}
      {expiringEncounters.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl px-5 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CalendarClock size={18} className="text-amber-600" />
            <div>
              <p className="text-sm font-medium text-amber-800">
                {expiringEncounters.length} order{expiringEncounters.length > 1 ? 's' : ''} with encounters expiring within 14 days
              </p>
              <p className="text-xs text-amber-600 mt-0.5">Schedule follow-up appointments to avoid payer rejection</p>
            </div>
          </div>
          <div className="flex gap-1 flex-wrap max-w-sm">
            {expiringEncounters.slice(0, 5).map(o => (
              <span key={o.id} className="text-[10px] bg-amber-100 text-amber-800 px-2 py-0.5 rounded font-medium">
                {o.patient_first_name} {o.patient_last_name} — {o.encounter_expires_in_days}d left
              </span>
            ))}
            {expiringEncounters.length > 5 && (
              <span className="text-[10px] text-amber-600">+{expiringEncounters.length - 5} more</span>
            )}
          </div>
        </div>
      )}

      {activeView === 'inventory' ? (
        <DMEInventory />
      ) : loading ? (
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
          <li>New orders appear in the <strong>New Orders</strong> lane</li>
          <li>Check compliance (AirPM) and verify insurance coverage</li>
          <li><strong>Approve</strong>, then <strong>Send to Patient</strong> — generates a confirmation link</li>
          <li>Patient confirms address and chooses pickup or shipping</li>
          <li><strong>Order from Vendor</strong> when patient confirms, then track through delivery</li>
          <li>Auto-refills are sent to patients automatically when due — look for the <span className="text-purple-600 font-medium">Auto Refill</span> badge in Awaiting Patient</li>
        </ol>
      </div>

      {/* New Order slide-over panel */}
      <NewOrderPanel open={newOrderOpen} onClose={() => setNewOrderOpen(false)} onCreated={load} />
    </div>
  )
}
