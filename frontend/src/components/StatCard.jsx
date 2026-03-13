export default function StatCard({ icon: Icon, label, value, sub, color = 'brand' }) {
  const colors = {
    brand: 'bg-brand-50 text-brand-600',
    green: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    red: 'bg-red-50 text-red-600',
    sky: 'bg-sky-50 text-sky-600',
  }

  return (
    <div className="card flex items-start gap-4">
      <div className={`p-3 rounded-lg ${colors[color]}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-600">{label}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}
