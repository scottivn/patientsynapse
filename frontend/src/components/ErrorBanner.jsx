import { AlertTriangle, X } from 'lucide-react'

export default function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-3 flex items-start gap-3">
      <AlertTriangle size={18} className="text-red-500 mt-0.5 shrink-0" />
      <p className="text-sm text-red-700 flex-1">{message}</p>
      {onDismiss && (
        <button onClick={onDismiss} className="text-red-400 hover:text-red-600">
          <X size={16} />
        </button>
      )}
    </div>
  )
}
