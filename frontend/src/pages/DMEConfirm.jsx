import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Package, MapPin, Truck, Store, CheckCircle2, XCircle, Clock, AlertCircle, Loader2, MessageSquare } from 'lucide-react'
import { validateDMEConfirmation, submitDMEConfirmation, rejectDMEConfirmation } from '../services/api'

const STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
  'VA','WA','WV','WI','WY',
]

function StatusBadge({ status }) {
  const styles = {
    patient_contacted: 'bg-amber-100 text-amber-800',
    patient_confirmed: 'bg-green-100 text-green-800',
    ordering: 'bg-blue-100 text-blue-800',
    shipped: 'bg-indigo-100 text-indigo-800',
    fulfilled: 'bg-green-100 text-green-800',
    cancelled: 'bg-gray-100 text-gray-600',
    rejected: 'bg-red-100 text-red-800',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-600'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}

function TrackingTimeline({ order }) {
  const steps = [
    { key: 'confirmed', label: 'Confirmed', done: order.patient_confirmed_address },
    { key: 'ordering', label: 'Ordering', done: ['ordering', 'shipped', 'fulfilled'].includes(order.status) },
    { key: 'shipped', label: order.fulfillment_method === 'pickup' ? 'Ready for Pickup' : 'Shipped', done: ['shipped', 'fulfilled'].includes(order.status) },
    { key: 'delivered', label: 'Delivered', done: order.status === 'fulfilled' },
  ]

  return (
    <div className="flex items-center justify-between mt-6">
      {steps.map((step, i) => (
        <div key={step.key} className="flex items-center flex-1">
          <div className={`flex items-center justify-center w-8 h-8 rounded-full border-2 ${
            step.done ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 text-gray-400'
          }`}>
            {step.done ? <CheckCircle2 className="w-4 h-4" /> : <span className="text-xs">{i + 1}</span>}
          </div>
          <span className={`ml-2 text-xs ${step.done ? 'text-blue-700 font-medium' : 'text-gray-400'}`}>{step.label}</span>
          {i < steps.length - 1 && (
            <div className={`flex-1 h-0.5 mx-3 ${step.done ? 'bg-blue-600' : 'bg-gray-200'}`} />
          )}
        </div>
      ))}
    </div>
  )
}


export default function DMEConfirm() {
  const { token } = useParams()
  const [order, setOrder] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  // Editable fields
  const [address, setAddress] = useState('')
  const [city, setCity] = useState('')
  const [state, setState] = useState('')
  const [zip, setZip] = useState('')
  const [phone, setPhone] = useState('')
  const [fulfillment, setFulfillment] = useState('')
  const [notes, setNotes] = useState('')
  const [selectedItems, setSelectedItems] = useState([])
  const [showRejectForm, setShowRejectForm] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [wantCallback, setWantCallback] = useState(false)
  const [rejected, setRejected] = useState(false)

  useEffect(() => {
    validateDMEConfirmation(token)
      .then(data => {
        setOrder(data)
        setAddress(data.patient_address || '')
        setCity(data.patient_city || '')
        setState(data.patient_state || '')
        setZip(data.patient_zip || '')
        setPhone(data.patient_phone || '')
        setFulfillment(data.fulfillment_method !== 'not_selected' ? data.fulfillment_method : '')
        if (data.bundle_items?.length) {
          setSelectedItems(data.selected_items?.length ? data.selected_items : [...data.bundle_items])
        }
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!fulfillment) return
    setSubmitting(true)
    try {
      const result = await submitDMEConfirmation(token, {
        address, city, state, zip, phone,
        fulfillment_method: fulfillment,
        patient_notes: notes || undefined,
        selected_items: order.bundle_items?.length ? selectedItems : undefined,
      })
      setOrder(result)
      setSubmitted(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSkip = async () => {
    if (!confirm('Are you sure you want to skip this supply order? You can always call our office if you change your mind.')) return
    setSubmitting(true)
    try {
      const result = await submitDMEConfirmation(token, { skip: true })
      setOrder(result)
      setSubmitted(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    setSubmitting(true)
    try {
      await rejectDMEConfirmation(token, rejectReason, wantCallback)
      setRejected(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const toggleItem = (item) => {
    setSelectedItems(prev =>
      prev.includes(item) ? prev.filter(i => i !== item) : [...prev, item]
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-sm border p-8 max-w-md text-center">
          <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Link Expired or Invalid</h2>
          <p className="text-gray-600 text-sm">{error}</p>
          <p className="text-gray-500 text-sm mt-4">
            If you need help, please call our office at <span className="font-medium">(210) 555-0100</span>.
          </p>
        </div>
      </div>
    )
  }

  // Patient rejected — show acknowledgment
  if (rejected) {
    return (
      <div className="min-h-screen bg-gray-50 p-4">
        <div className="max-w-lg mx-auto mt-8">
          <div className="bg-white rounded-lg shadow-sm border p-6 text-center">
            <MessageSquare className="w-12 h-12 text-blue-500 mx-auto mb-3" />
            <h1 className="text-xl font-semibold text-gray-900">We've received your feedback</h1>
            <p className="text-gray-600 text-sm mt-2">
              {wantCallback
                ? "A team member will call you shortly to resolve this."
                : "Our team will review your feedback and reach out if needed."}
            </p>
            <p className="text-center text-xs text-gray-400 mt-6">
              Questions? Call <span className="font-medium">(210) 555-0100</span>
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Already confirmed — show status tracker
  if (order.patient_confirmed_address || submitted) {
    return (
      <div className="min-h-screen bg-gray-50 p-4">
        <div className="max-w-lg mx-auto mt-8">
          <div className="bg-white rounded-lg shadow-sm border p-6">
            <div className="text-center mb-6">
              <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
              <h1 className="text-xl font-semibold text-gray-900">
                {submitted && order.status === 'cancelled' ? 'Order Skipped' : "You're all set!"}
              </h1>
              <p className="text-gray-600 text-sm mt-1">
                {order.status === 'cancelled'
                  ? 'This supply cycle has been skipped. Call us if you change your mind.'
                  : order.status_label}
              </p>
            </div>

            {order.status !== 'cancelled' && (
              <>
                <TrackingTimeline order={order} />

                <div className="mt-6 space-y-3 bg-gray-50 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <Package className="w-4 h-4 text-gray-400 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{order.equipment_description}</p>
                      <p className="text-xs text-gray-500">{order.equipment_category}</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    {order.fulfillment_method === 'ship' ? (
                      <Truck className="w-4 h-4 text-gray-400 mt-0.5" />
                    ) : (
                      <Store className="w-4 h-4 text-gray-400 mt-0.5" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {order.fulfillment_method === 'ship' ? 'Shipping to:' : 'Pickup at office'}
                      </p>
                      {order.fulfillment_method === 'ship' && (
                        <p className="text-xs text-gray-500">
                          {order.patient_address}, {order.patient_city}, {order.patient_state} {order.patient_zip}
                        </p>
                      )}
                    </div>
                  </div>
                  {order.shipping_tracking_number && (
                    <div className="flex items-start gap-3">
                      <Truck className="w-4 h-4 text-blue-500 mt-0.5" />
                      <div>
                        <p className="text-sm font-medium text-gray-900">Tracking: {order.shipping_tracking_number}</p>
                        <p className="text-xs text-gray-500">{order.shipping_carrier} — Est. delivery: {order.estimated_delivery_date}</p>
                      </div>
                    </div>
                  )}
                  {order.pickup_ready_date && (
                    <div className="flex items-start gap-3">
                      <Store className="w-4 h-4 text-green-500 mt-0.5" />
                      <p className="text-sm font-medium text-gray-900">Ready for pickup since {order.pickup_ready_date}</p>
                    </div>
                  )}
                </div>
              </>
            )}

            <p className="text-center text-xs text-gray-400 mt-6">
              Questions? Call <span className="font-medium">(210) 555-0100</span>
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Confirmation form
  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-lg mx-auto mt-8">
        <div className="bg-white rounded-lg shadow-sm border p-6">
          {/* Header */}
          <div className="text-center mb-6">
            <Package className="w-10 h-10 text-blue-600 mx-auto mb-3" />
            <h1 className="text-xl font-semibold text-gray-900">
              Hi {order.patient_first_name}, your supplies are ready!
            </h1>
            <p className="text-gray-600 text-sm mt-1">
              Please confirm your details so we can get your order out to you.
            </p>
          </div>

          {/* What's being ordered */}
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 mb-6">
            <p className="text-sm font-medium text-blue-900">{order.equipment_description}</p>
            <p className="text-xs text-blue-700 mt-1">{order.equipment_category}</p>
            {order.bundle_items?.length > 0 && (
              <div className="mt-3 space-y-2">
                <p className="text-xs font-medium text-blue-800">Included supplies — uncheck any you don't need:</p>
                {order.bundle_items.map(item => (
                  <label key={item} className="flex items-center gap-2 text-sm text-blue-900 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedItems.includes(item)}
                      onChange={() => toggleItem(item)}
                      className="rounded border-blue-300 text-blue-600 focus:ring-blue-500"
                    />
                    {item}
                  </label>
                ))}
              </div>
            )}
            {order.auto_replace && (
              <p className="text-xs text-blue-600 mt-2 flex items-center gap-1">
                <Clock className="w-3 h-3" /> Auto-refill — {order.auto_replace_frequency}
              </p>
            )}
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Address */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                <MapPin className="w-4 h-4" /> Shipping Address
              </label>
              <p className="text-xs text-gray-500 mb-2">Please verify this is correct, or update it below.</p>
              <input
                type="text" value={address} onChange={e => setAddress(e.target.value)}
                placeholder="Street address"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                required
              />
              <div className="grid grid-cols-6 gap-2 mt-2">
                <input
                  type="text" value={city} onChange={e => setCity(e.target.value)}
                  placeholder="City" className="col-span-3 border border-gray-300 rounded-md px-3 py-2 text-sm" required
                />
                <select
                  value={state} onChange={e => setState(e.target.value)}
                  className="col-span-1 border border-gray-300 rounded-md px-2 py-2 text-sm" required
                >
                  <option value="">ST</option>
                  {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <input
                  type="text" value={zip} onChange={e => setZip(e.target.value)}
                  placeholder="ZIP" className="col-span-2 border border-gray-300 rounded-md px-3 py-2 text-sm" required
                  pattern="[0-9]{5}" maxLength={5}
                />
              </div>
            </div>

            {/* Phone */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">Phone Number</label>
              <input
                type="tel" value={phone} onChange={e => setPhone(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              />
            </div>

            {/* Fulfillment choice */}
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-2">How would you like to receive your supplies?</label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setFulfillment('ship')}
                  className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors ${
                    fulfillment === 'ship'
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-200 hover:border-gray-300 text-gray-600'
                  }`}
                >
                  <Truck className="w-6 h-6" />
                  <span className="text-sm font-medium">Ship to me — $15.00</span>
                  <span className="text-xs text-gray-500">Delivered to your door</span>
                </button>
                <button
                  type="button"
                  onClick={() => setFulfillment('pickup')}
                  className={`flex flex-col items-center gap-2 p-4 rounded-lg border-2 transition-colors ${
                    fulfillment === 'pickup'
                      ? 'border-blue-600 bg-blue-50 text-blue-700'
                      : 'border-gray-200 hover:border-gray-300 text-gray-600'
                  }`}
                >
                  <Store className="w-6 h-6" />
                  <span className="text-sm font-medium">Pick up</span>
                  <span className="text-xs text-gray-500">At our office</span>
                </button>
              </div>
              {!fulfillment && (
                <p className="text-xs text-amber-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" /> Please select one
                </p>
              )}
            </div>

            {/* Notes */}
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-1">
                <MessageSquare className="w-4 h-4" /> Notes <span className="text-gray-400 font-normal">(optional)</span>
              </label>
              <textarea
                value={notes} onChange={e => setNotes(e.target.value)}
                rows={2}
                placeholder="Any special instructions? (e.g., leave at front door)"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm resize-none"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={!fulfillment || submitting}
              className="w-full bg-blue-600 text-white rounded-lg py-3 text-sm font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Confirming...
                </span>
              ) : (
                'Confirm & Submit'
              )}
            </button>

            {/* Skip option */}
            <button
              type="button"
              onClick={handleSkip}
              disabled={submitting}
              className="w-full text-gray-500 text-xs hover:text-gray-700 py-2"
            >
              I don't need supplies right now — skip this cycle
            </button>
          </form>

          {/* Report issue */}
          <div className="mt-4 border-t border-gray-100 pt-4">
            <button
              onClick={() => setShowRejectForm(!showRejectForm)}
              className="text-xs text-red-500 hover:text-red-700 font-medium"
            >
              {showRejectForm ? 'Cancel' : "Something's not right?"}
            </button>
            {showRejectForm && (
              <div className="mt-3 space-y-3 bg-red-50 border border-red-100 rounded-lg p-4">
                <textarea
                  value={rejectReason}
                  onChange={e => setRejectReason(e.target.value)}
                  rows={2}
                  placeholder="Tell us what's wrong (wrong supplies, incorrect info, etc.)"
                  className="w-full border border-red-200 rounded-md px-3 py-2 text-sm resize-none focus:ring-red-500 focus:border-red-500"
                />
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={wantCallback}
                    onChange={e => setWantCallback(e.target.checked)}
                    className="rounded border-gray-300 text-red-600 focus:ring-red-500"
                  />
                  Please call me to resolve this
                </label>
                <button
                  onClick={handleReject}
                  disabled={submitting}
                  className="w-full bg-red-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-red-700 disabled:bg-gray-300 transition-colors"
                >
                  Report Issue
                </button>
              </div>
            )}
          </div>

          <p className="text-center text-xs text-gray-400 mt-6">
            Questions? Call <span className="font-medium">(210) 555-0100</span>
          </p>
        </div>
      </div>
    </div>
  )
}
