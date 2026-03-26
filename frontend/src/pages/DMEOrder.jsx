import { Package, Phone, MessageSquare, Clock } from 'lucide-react'

/**
 * Public DME landing page.
 *
 * Patients don't submit DME orders — orders originate internally
 * (auto-refill schedule, new Rx, staff-initiated). When supplies
 * are ready, patients receive a confirmation link via SMS/email
 * to verify their address and choose pickup or shipping.
 *
 * This page explains that process for patients who navigate to /dme directly.
 */
export default function DMEOrder() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-lg shadow-sm border p-8 text-center">
          <Package className="w-12 h-12 text-blue-600 mx-auto mb-4" />
          <h1 className="text-xl font-semibold text-gray-900 mb-2">
            CPAP & Sleep Supply Orders
          </h1>
          <p className="text-gray-600 text-sm leading-relaxed mb-6">
            When your supplies are due for replacement, we'll send you a text message
            or email with a link to confirm your details and choose how you'd like to
            receive your order.
          </p>

          <div className="space-y-4 text-left mb-6">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Clock className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">We track your schedule</p>
                <p className="text-xs text-gray-500">Based on your insurance and equipment, we know when you're eligible for new supplies.</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <MessageSquare className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">You'll get a link</p>
                <p className="text-xs text-gray-500">When it's time, we'll text or email you a link to confirm your address and choose pickup or delivery.</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Package className="w-4 h-4 text-blue-600" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">We handle the rest</p>
                <p className="text-xs text-gray-500">We verify your insurance, order from our supplier, and get your supplies to you.</p>
              </div>
            </div>
          </div>

          <div className="border-t pt-4">
            <p className="text-sm text-gray-600 mb-1">Need supplies sooner? Have questions?</p>
            <a href="tel:2105550100" className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-800 font-medium text-sm">
              <Phone className="w-4 h-4" /> (210) 555-0100
            </a>
          </div>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          If you received a confirmation link, please use that link directly.
        </p>
      </div>
    </div>
  )
}
