import { useEffect, useState } from 'react'
import { Search, Shield, MapPin, Phone, Clock, ChevronRight } from 'lucide-react'
import { searchProviders, verifyInsurance } from '../services/api'

export default function Scheduling() {
  const [specialty, setSpecialty] = useState('')
  const [providers, setProviders] = useState([])
  const [searching, setSearching] = useState(false)

  const [patientId, setPatientId] = useState('')
  const [insurance, setInsurance] = useState(null)
  const [verifying, setVerifying] = useState(false)

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!specialty.trim()) return
    setSearching(true)
    try {
      const data = await searchProviders(specialty)
      setProviders(data.providers || [])
    } catch (err) {
      alert(err.message)
    }
    setSearching(false)
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    if (!patientId.trim()) return
    setVerifying(true)
    try {
      setInsurance(await verifyInsurance(patientId))
    } catch (err) {
      alert(err.message)
    }
    setVerifying(false)
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Smart Scheduling</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Provider search */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Find Providers</h2>
          <form onSubmit={handleSearch} className="flex gap-2 mb-5">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={specialty}
                onChange={(e) => setSpecialty(e.target.value)}
                placeholder="Specialty (e.g. Cardiology)"
                className="input pl-10"
              />
            </div>
            <button type="submit" disabled={searching} className="btn-primary">
              {searching ? 'Searching...' : 'Search'}
            </button>
          </form>

          {providers.length === 0 && !searching && (
            <p className="text-sm text-gray-400 text-center py-6">Search by specialty to find available providers</p>
          )}

          <div className="space-y-3">
            {providers.map((p, i) => (
              <div key={i} className="border rounded-lg p-4 hover:border-brand-200 transition-colors">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{p.name}</p>
                    <p className="text-sm text-brand-600">{p.specialty}</p>
                  </div>
                  <ChevronRight size={16} className="text-gray-300 mt-1" />
                </div>
                {p.location && (
                  <div className="flex items-center gap-1.5 mt-2 text-xs text-gray-500">
                    <MapPin size={12} /> {p.location}
                  </div>
                )}
                {p.phone && (
                  <div className="flex items-center gap-1.5 mt-1 text-xs text-gray-500">
                    <Phone size={12} /> {p.phone}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Insurance verification */}
        <div className="card">
          <h2 className="font-semibold text-gray-900 mb-4">Insurance Verification</h2>
          <form onSubmit={handleVerify} className="flex gap-2 mb-5">
            <div className="relative flex-1">
              <Shield size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="eCW Patient ID"
                className="input pl-10"
              />
            </div>
            <button type="submit" disabled={verifying} className="btn-primary">
              {verifying ? 'Verifying...' : 'Verify'}
            </button>
          </form>

          {!insurance && (
            <p className="text-sm text-gray-400 text-center py-6">Enter a patient ID to verify coverage</p>
          )}

          {insurance && (
            <div className="space-y-4">
              {insurance.coverages?.length > 0 ? (
                insurance.coverages.map((c, i) => (
                  <div key={i} className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="font-medium text-green-800">{c.payor}</p>
                    <p className="text-sm text-green-600 capitalize">{c.status}</p>
                    {c.subscriber_id && <p className="text-xs text-gray-500 mt-1">ID: {c.subscriber_id}</p>}
                    {c.period_start && (
                      <div className="flex items-center gap-1 text-xs text-gray-500 mt-1">
                        <Clock size={12} /> {c.period_start} — {c.period_end || 'ongoing'}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
                  <p className="text-sm text-yellow-700">No coverage records found</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Info banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl px-5 py-4">
        <h3 className="font-medium text-blue-800 text-sm mb-1">About Smart Scheduling</h3>
        <p className="text-sm text-blue-600 leading-relaxed">
          Provider search pulls data from your eCW FHIR endpoint.
          Actual appointment booking requires the healow Open Access API, which will be configured separately.
          Insurance verification checks active Coverage resources in eCW.
        </p>
      </div>
    </div>
  )
}
