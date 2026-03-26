import { useEffect, useState, useCallback } from 'react'
import {
  DollarSign, RefreshCw, Upload, Search, Filter, Edit3, Save, X,
  ChevronDown, ChevronUp, Trash2, Plus, AlertTriangle, Check, Package,
} from 'lucide-react'
import {
  getAllowableRates, getRatePayers, importAllowableRates,
  createAllowableRate, deleteAllowableRate, getBundlePricing,
} from '../services/api'

const HCPCS_CODES = [
  { code: 'A7030', label: 'Full face mask', category: 'mask' },
  { code: 'A7031', label: 'FFM cushion replacement', category: 'mask' },
  { code: 'A7034', label: 'Nasal mask interface', category: 'nasal' },
  { code: 'A7032', label: 'Nasal cushion replacement', category: 'nasal' },
  { code: 'A7033', label: 'Nasal pillow replacement', category: 'nasal' },
  { code: 'A7035', label: 'Headgear', category: 'accessory' },
  { code: 'A4604', label: 'Tubing with heating element', category: 'accessory' },
  { code: 'A7046', label: 'Water chamber / humidifier', category: 'accessory' },
  { code: 'A7038', label: 'Filter, disposable', category: 'filter' },
  { code: 'A7039', label: 'Filter, non-disposable', category: 'filter' },
]

const HCPCS_LABELS = Object.fromEntries(HCPCS_CODES.map(c => [c.code, c.label]))

const CATEGORY_LABELS = {
  mask: 'Full Face Mask',
  nasal: 'Nasal Mask / Pillow',
  accessory: 'Accessories',
  filter: 'Filters',
}

const KNOWN_PAYERS = [
  'BCBS', 'Aetna', 'Cigna', 'UHC', 'Medicare', 'Humana',
  'Devoted', 'WellMed', 'WellMed-UHC', 'WellMed-Humana', 'UMR', 'Web TPA',
]

const currentYear = new Date().getFullYear()

export default function AllowableRates() {
  const [rates, setRates] = useState([])
  const [payers, setPayers] = useState([])
  const [loading, setLoading] = useState(true)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState(null)
  const [importResult, setImportResult] = useState(null)

  // View mode
  const [view, setView] = useState('cards') // 'cards' | 'editor'
  const [editorPayer, setEditorPayer] = useState('')
  const [editorPlan, setEditorPlan] = useState('')
  const [editorYear, setEditorYear] = useState(currentYear)

  // Filters for card view
  const [filterPayer, setFilterPayer] = useState('')
  const [filterYear, setFilterYear] = useState(currentYear)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ratesData, payersData] = await Promise.all([
        getAllowableRates(filterPayer || undefined, undefined, filterYear || undefined),
        getRatePayers(filterYear || undefined),
      ])
      setRates(ratesData.rates || [])
      setPayers(payersData || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [filterPayer, filterYear])

  useEffect(() => { load() }, [load])

  const handleImport = async () => {
    setImporting(true)
    setImportResult(null)
    setError(null)
    try {
      const result = await importAllowableRates(filterYear || currentYear)
      setImportResult(result)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setImporting(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteAllowableRate(id)
      setRates(prev => prev.filter(r => r.id !== id))
    } catch (e) {
      setError(e.message)
    }
  }

  const openEditor = (payer = '', plan = '') => {
    setEditorPayer(payer)
    setEditorPlan(plan)
    setView('editor')
  }

  // Group rates by payer for card view
  const grouped = {}
  for (const rate of rates) {
    const key = rate.payer + (rate.payer_plan ? ` (${rate.payer_plan})` : '')
    if (!grouped[key]) grouped[key] = { payer: rate.payer, plan: rate.payer_plan, rates: [] }
    grouped[key].rates.push(rate)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Allowable Rates</h1>
          <p className="text-sm text-gray-500">
            Insurance reimbursement rates by payer and HCPCS code
            {rates.length > 0 && <span className="ml-1">({rates.length} rates loaded)</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {view === 'cards' ? (
            <>
              <button onClick={() => openEditor()} className="btn-primary text-sm flex items-center gap-1.5">
                <Edit3 size={14} /> Edit Payer Rates
              </button>
              <button
                onClick={handleImport}
                disabled={importing}
                className="btn-secondary text-sm flex items-center gap-1.5"
              >
                {importing ? <RefreshCw size={14} className="animate-spin" /> : <Upload size={14} />}
                {importing ? 'Importing...' : 'Import Excel'}
              </button>
            </>
          ) : (
            <button onClick={() => { setView('cards'); load() }} className="btn-secondary text-sm flex items-center gap-1.5">
              <X size={14} /> Back to Overview
            </button>
          )}
        </div>
      </div>

      {/* Import result banner */}
      {importResult && (
        <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 text-sm">
          <p className="font-medium text-green-800">
            Import complete: {importResult.rates_parsed} rates from {importResult.payers?.length} payers
          </p>
          {importResult.warnings?.length > 0 && (
            <details className="mt-2">
              <summary className="text-yellow-700 cursor-pointer flex items-center gap-1">
                <AlertTriangle size={12} /> {importResult.warnings.length} warnings (some sections couldn't be parsed)
              </summary>
              <ul className="mt-1 text-xs text-yellow-600 space-y-0.5 ml-4">
                {importResult.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700 flex items-center justify-between">
          {error}
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-4">&times;</button>
        </div>
      )}

      {/* Bundle Pricing Calculator */}
      <BundleCalculator payers={payers} />

      {view === 'editor' ? (
        <RateCardEditor
          initialPayer={editorPayer}
          initialPlan={editorPlan}
          year={editorYear}
          existingRates={rates}
          payers={payers}
          onYearChange={setEditorYear}
          onError={setError}
          onSaved={load}
        />
      ) : (
        <>
          {/* Filters */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 text-sm text-gray-500">
              <Filter size={14} />
            </div>
            <select value={filterPayer} onChange={(e) => setFilterPayer(e.target.value)} className="input text-sm w-44">
              <option value="">All Payers</option>
              {payers.map(p => (
                <option key={p.payer + p.payer_plan} value={p.payer}>
                  {p.payer}{p.payer_plan ? ` (${p.payer_plan})` : ''} ({p.rate_count})
                </option>
              ))}
            </select>
            <input
              type="number"
              value={filterYear}
              onChange={(e) => setFilterYear(e.target.value ? parseInt(e.target.value) : '')}
              className="input text-sm w-24"
              placeholder="Year"
            />
          </div>

          {/* Rates cards */}
          {loading ? (
            <div className="text-center py-12 text-gray-400">
              <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
              <p className="text-sm">Loading rates...</p>
            </div>
          ) : rates.length === 0 ? (
            <div className="text-center py-16 text-gray-400">
              <DollarSign size={32} className="mx-auto mb-3 opacity-30" />
              <p className="text-sm font-medium">No rates loaded</p>
              <p className="text-xs mt-1 mb-4">Import from an existing spreadsheet or add rates manually</p>
              <div className="flex justify-center gap-3">
                <button onClick={() => openEditor()} className="btn-primary text-sm flex items-center gap-1.5">
                  <Edit3 size={14} /> Add Payer Rates
                </button>
                <button onClick={handleImport} disabled={importing} className="btn-secondary text-sm flex items-center gap-1.5">
                  <Upload size={14} /> Import Excel
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([payerKey, data]) => (
                <PayerSection
                  key={payerKey}
                  payerKey={payerKey}
                  rates={data.rates}
                  onDelete={handleDelete}
                  onEdit={() => openEditor(data.payer, data.plan)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}


// ── Bundle Pricing Calculator ────────────────────────────────────

function BundleCalculator({ payers }) {
  const [open, setOpen] = useState(false)
  const [payer, setPayer] = useState('')
  const [supplyMonths, setSupplyMonths] = useState(6)
  const [selectedCodes, setSelectedCodes] = useState([])
  const [result, setResult] = useState(null)
  const [calculating, setCalculating] = useState(false)
  const [calcError, setCalcError] = useState(null)

  const toggleCode = (code) => {
    setSelectedCodes(prev =>
      prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
    )
    setResult(null)
  }

  const selectPreset = (preset) => {
    setSelectedCodes(preset)
    setResult(null)
  }

  const calculate = async () => {
    if (!payer || selectedCodes.length === 0) return
    setCalculating(true)
    setCalcError(null)
    try {
      setResult(await getBundlePricing(payer, selectedCodes, supplyMonths))
    } catch (e) {
      setCalcError(e.message)
    } finally {
      setCalculating(false)
    }
  }

  const PRESETS = [
    { label: 'New CPAP Setup', codes: ['E0601', 'A7030', 'A7035', 'A4604', 'A7046', 'A7038', 'A7039'] },
    { label: 'New BiPAP Setup', codes: ['E0470', 'A7030', 'A7035', 'A4604', 'A7046', 'A7038', 'A7039'] },
    { label: 'Quarterly Resupply (Full Face)', codes: ['A7031', 'A7038', 'A7039'] },
    { label: 'Quarterly Resupply (Nasal)', codes: ['A7032', 'A7038', 'A7039'] },
    { label: 'Biannual Resupply', codes: ['A7030', 'A7035', 'A4604', 'A7046', 'A7038', 'A7039'] },
  ]

  const payerNames = [...new Set(payers.map(p => p.payer))].sort()

  return (
    <div className="card">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full"
      >
        <div className="flex items-center gap-2">
          <Package size={16} className="text-indigo-500" />
          <h2 className="text-sm font-semibold text-gray-900">Bundle Pricing Calculator</h2>
          <span className="text-xs text-gray-400">Calculate total reimbursement for multi-item orders</span>
        </div>
        {open ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
      </button>

      {open && (
        <div className="mt-4 space-y-4">
          {/* Payer + supply period */}
          <div className="flex items-end gap-3 flex-wrap">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Payer</label>
              <select
                value={payer}
                onChange={(e) => { setPayer(e.target.value); setResult(null) }}
                className="input text-sm w-48"
              >
                <option value="">— Select payer —</option>
                {payerNames.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Supply Period</label>
              <select
                value={supplyMonths}
                onChange={(e) => { setSupplyMonths(parseInt(e.target.value)); setResult(null) }}
                className="input text-sm w-32"
              >
                <option value={3}>3 months</option>
                <option value={6}>6 months</option>
              </select>
            </div>
          </div>

          {/* Quick presets */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Quick Presets</label>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map(p => (
                <button
                  key={p.label}
                  onClick={() => selectPreset(p.codes)}
                  className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                    JSON.stringify(selectedCodes.sort()) === JSON.stringify([...p.codes].sort())
                      ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
                      : 'border-gray-200 text-gray-600 hover:border-indigo-200 hover:text-indigo-600'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* HCPCS code checkboxes grouped by category */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">Select Items</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-0.5">
              {Object.entries(CATEGORY_LABELS).map(([cat, label]) => (
                <div key={cat}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mt-2 mb-1">{label}</p>
                  {HCPCS_CODES.filter(h => h.category === cat).map(h => (
                    <label key={h.code} className="flex items-center gap-2 py-0.5 text-sm cursor-pointer hover:bg-gray-50 rounded px-1 -mx-1">
                      <input
                        type="checkbox"
                        checked={selectedCodes.includes(h.code)}
                        onChange={() => toggleCode(h.code)}
                        className="rounded border-gray-300 text-indigo-500 focus:ring-indigo-400"
                      />
                      <span className="font-mono text-xs text-gray-500 w-14">{h.code}</span>
                      <span className="text-gray-700">{h.label}</span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* Calculate button */}
          <div className="flex items-center gap-3">
            <button
              onClick={calculate}
              disabled={calculating || !payer || selectedCodes.length === 0}
              className="btn-primary text-sm flex items-center gap-1.5"
            >
              {calculating ? <RefreshCw size={14} className="animate-spin" /> : <DollarSign size={14} />}
              {calculating ? 'Calculating...' : `Calculate ${selectedCodes.length} item${selectedCodes.length !== 1 ? 's' : ''}`}
            </button>
            {selectedCodes.length > 0 && (
              <button onClick={() => { setSelectedCodes([]); setResult(null) }} className="text-xs text-gray-400 hover:text-gray-600">
                Clear selection
              </button>
            )}
          </div>

          {calcError && (
            <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{calcError}</div>
          )}

          {/* Results */}
          {result && (
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-gray-50 px-4 py-2.5 flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-900">
                  {result.payer} — {result.supply_months}-month supply
                </span>
                {!result.complete && (
                  <span className="text-xs bg-yellow-50 text-yellow-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                    <AlertTriangle size={10} /> Some rates missing
                  </span>
                )}
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400 uppercase tracking-wider border-b">
                    <th className="px-4 py-2 font-medium">HCPCS</th>
                    <th className="px-4 py-2 font-medium">Description</th>
                    <th className="px-4 py-2 font-medium text-right">Allowed</th>
                  </tr>
                </thead>
                <tbody>
                  {result.items?.map((item, i) => (
                    <tr key={i} className={`border-b border-gray-50 ${!item.found ? 'opacity-50' : ''}`}>
                      <td className="px-4 py-2 font-mono text-xs font-medium text-gray-600">{item.hcpcs_code}</td>
                      <td className="px-4 py-2 text-gray-700">
                        {item.description || HCPCS_LABELS[item.hcpcs_code] || '—'}
                        {!item.found && <span className="text-xs text-yellow-600 ml-2">(no rate found)</span>}
                      </td>
                      <td className="px-4 py-2 text-right font-mono font-medium text-gray-900">
                        {item.found ? `$${item.allowed_amount.toFixed(2)}` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="bg-indigo-50">
                    <td colSpan={2} className="px-4 py-2.5 font-semibold text-indigo-900">Total Allowed Amount</td>
                    <td className="px-4 py-2.5 text-right font-mono font-bold text-lg text-indigo-700">
                      ${result.total?.toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}


// ── Payer Rate Card Editor ──────────────────────────────────────

function RateCardEditor({ initialPayer, initialPlan, year, existingRates, payers, onYearChange, onError, onSaved }) {
  const [payer, setPayer] = useState(initialPayer)
  const [payerPlan, setPayerPlan] = useState(initialPlan)
  const [customPayer, setCustomPayer] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Build initial values from existing rates for this payer
  const buildInitialValues = useCallback(() => {
    const vals = {}
    for (const hcpcs of HCPCS_CODES) {
      vals[hcpcs.code] = { '3': '', '6': '' }
    }
    const activePayer = payer || customPayer
    if (activePayer) {
      for (const rate of existingRates) {
        if (rate.payer === activePayer && rate.effective_year === year) {
          if (vals[rate.hcpcs_code]) {
            vals[rate.hcpcs_code][String(rate.supply_months <= 3 ? 3 : 6)] = rate.allowed_amount.toFixed(2)
          }
        }
      }
    }
    return vals
  }, [payer, customPayer, existingRates, year])

  const [values, setValues] = useState(buildInitialValues)

  // Rebuild values when payer changes
  useEffect(() => {
    setValues(buildInitialValues())
    setSaved(false)
  }, [buildInitialValues])

  const activePayer = payer || customPayer

  const updateValue = (code, months, val) => {
    setValues(prev => ({
      ...prev,
      [code]: { ...prev[code], [months]: val },
    }))
    setSaved(false)
  }

  const handleSave = async () => {
    if (!activePayer) {
      onError('Select or enter a payer name')
      return
    }
    setSaving(true)
    try {
      const promises = []
      for (const hcpcs of HCPCS_CODES) {
        for (const months of ['3', '6']) {
          const val = values[hcpcs.code]?.[months]
          if (val && parseFloat(val) > 0) {
            promises.push(createAllowableRate({
              payer: activePayer,
              payer_plan: payerPlan,
              hcpcs_code: hcpcs.code,
              description: hcpcs.label,
              supply_months: parseInt(months),
              allowed_amount: parseFloat(val),
              effective_year: year,
            }))
          }
        }
      }
      await Promise.all(promises)
      setSaved(true)
      onSaved()
    } catch (e) {
      onError(e.message)
    } finally {
      setSaving(false)
    }
  }

  // Compute totals
  const total3 = HCPCS_CODES.reduce((s, h) => s + (parseFloat(values[h.code]?.['3']) || 0), 0)
  const total6 = HCPCS_CODES.reduce((s, h) => s + (parseFloat(values[h.code]?.['6']) || 0), 0)

  // Existing payer names for quick select
  const existingPayerNames = [...new Set(payers.map(p => p.payer))].sort()

  // Group HCPCS by category
  const categories = {}
  for (const h of HCPCS_CODES) {
    if (!categories[h.category]) categories[h.category] = []
    categories[h.category].push(h)
  }

  return (
    <div className="space-y-4">
      {/* Payer selector */}
      <div className="card space-y-4">
        <h3 className="text-sm font-semibold text-gray-700">Payer Rate Card</h3>
        <div className="flex items-end gap-3 flex-wrap">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Select Payer</label>
            <select
              value={payer}
              onChange={(e) => { setPayer(e.target.value); setCustomPayer('') }}
              className="input text-sm w-48"
            >
              <option value="">— Choose payer —</option>
              <optgroup label="Existing">
                {existingPayerNames.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </optgroup>
              <optgroup label="All Known">
                {KNOWN_PAYERS.filter(p => !existingPayerNames.includes(p)).map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </optgroup>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Or enter new</label>
            <input
              className="input text-sm w-40"
              placeholder="New payer name"
              value={customPayer}
              onChange={(e) => { setCustomPayer(e.target.value); setPayer('') }}
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Plan type</label>
            <select value={payerPlan} onChange={(e) => setPayerPlan(e.target.value)} className="input text-sm w-44">
              <option value="">Standard / Commercial</option>
              <option value="commercial">Commercial</option>
              <option value="medicare_advantage">Medicare Advantage</option>
              <option value="medicaid">Medicaid</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Year</label>
            <input
              type="number"
              className="input text-sm w-20"
              value={year}
              onChange={(e) => onYearChange(parseInt(e.target.value) || currentYear)}
            />
          </div>
        </div>
      </div>

      {/* Rate grid */}
      {activePayer ? (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-900">
              {activePayer}{payerPlan ? ` — ${payerPlan}` : ''} — {year} Rates
            </h3>
            <div className="flex items-center gap-3 text-xs">
              {total6 > 0 && (
                <span className="bg-blue-50 text-blue-600 px-2 py-1 rounded-full font-medium">
                  6mo total: ${total6.toFixed(2)}
                </span>
              )}
              {total3 > 0 && (
                <span className="bg-purple-50 text-purple-600 px-2 py-1 rounded-full font-medium">
                  3mo total: ${total3.toFixed(2)}
                </span>
              )}
            </div>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 uppercase tracking-wider border-b border-gray-200">
                <th className="pb-2.5 font-medium w-24">HCPCS</th>
                <th className="pb-2.5 font-medium">Description</th>
                <th className="pb-2.5 font-medium text-center w-32">6-Month ($)</th>
                <th className="pb-2.5 font-medium text-center w-32">3-Month ($)</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(categories).map(([cat, codes]) => (
                <CategoryGroup
                  key={cat}
                  category={cat}
                  codes={codes}
                  values={values}
                  onChange={updateValue}
                />
              ))}
            </tbody>
          </table>

          {/* Save button */}
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs text-gray-400">
              Enter dollar amounts for each supply item. Leave blank to skip.
            </p>
            <button
              onClick={handleSave}
              disabled={saving || !activePayer}
              className={`text-sm flex items-center gap-1.5 px-4 py-2 rounded-lg font-medium transition-colors ${
                saved
                  ? 'bg-green-50 text-green-600 border border-green-200'
                  : 'bg-indigo-500 hover:bg-indigo-600 text-white'
              } disabled:opacity-50`}
            >
              {saving ? <RefreshCw size={14} className="animate-spin" /> : saved ? <Check size={14} /> : <Save size={14} />}
              {saving ? 'Saving...' : saved ? 'Saved' : 'Save All Rates'}
            </button>
          </div>
        </div>
      ) : (
        <div className="text-center py-12 text-gray-400 card">
          <Edit3 size={24} className="mx-auto mb-2 opacity-30" />
          <p className="text-sm">Select a payer above to edit their rate card</p>
        </div>
      )}
    </div>
  )
}


function CategoryGroup({ category, codes, values, onChange }) {
  return (
    <>
      <tr>
        <td colSpan={4} className="pt-3 pb-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
            {CATEGORY_LABELS[category] || category}
          </span>
        </td>
      </tr>
      {codes.map(h => (
        <tr key={h.code} className="border-b border-gray-50 hover:bg-gray-50/50">
          <td className="py-1.5 font-mono text-xs font-medium text-gray-600">{h.code}</td>
          <td className="py-1.5 text-gray-700">{h.label}</td>
          <td className="py-1.5 px-2">
            <input
              type="number"
              step="0.01"
              min="0"
              className="w-full text-right text-sm font-mono px-2 py-1.5 rounded-md border border-gray-200 focus:border-blue-400 focus:ring-1 focus:ring-blue-100 outline-none bg-blue-50/30"
              placeholder="—"
              value={values[h.code]?.['6'] || ''}
              onChange={(e) => onChange(h.code, '6', e.target.value)}
            />
          </td>
          <td className="py-1.5 px-2">
            <input
              type="number"
              step="0.01"
              min="0"
              className="w-full text-right text-sm font-mono px-2 py-1.5 rounded-md border border-gray-200 focus:border-purple-400 focus:ring-1 focus:ring-purple-100 outline-none bg-purple-50/30"
              placeholder="—"
              value={values[h.code]?.['3'] || ''}
              onChange={(e) => onChange(h.code, '3', e.target.value)}
            />
          </td>
        </tr>
      ))}
    </>
  )
}


// ── Payer summary card (read-only view) ─────────────────────────

function PayerSection({ payerKey, rates, onDelete, onEdit }) {
  const [expanded, setExpanded] = useState(false)

  const bySupply = { 3: [], 6: [] }
  for (const r of rates) {
    const key = r.supply_months <= 3 ? 3 : 6
    bySupply[key].push(r)
  }
  const total6 = bySupply[6].reduce((s, r) => s + r.allowed_amount, 0)
  const total3 = bySupply[3].reduce((s, r) => s + r.allowed_amount, 0)

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-3 flex-1 py-1"
        >
          <h3 className="text-sm font-semibold text-gray-900">{payerKey}</h3>
          <span className="text-xs text-gray-400">{rates.length} rates</span>
          {total6 > 0 && (
            <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
              6mo: ${total6.toFixed(2)}
            </span>
          )}
          {total3 > 0 && (
            <span className="text-xs bg-purple-50 text-purple-600 px-2 py-0.5 rounded-full">
              3mo: ${total3.toFixed(2)}
            </span>
          )}
          {expanded ? <ChevronUp size={14} className="text-gray-300" /> : <ChevronDown size={14} className="text-gray-300" />}
        </button>
        <button onClick={onEdit} className="text-xs text-indigo-500 hover:text-indigo-700 flex items-center gap-1 ml-3">
          <Edit3 size={12} /> Edit
        </button>
      </div>

      {expanded && (
        <table className="w-full mt-3 text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 uppercase tracking-wider border-b border-gray-100">
              <th className="pb-2 font-medium">HCPCS</th>
              <th className="pb-2 font-medium">Description</th>
              <th className="pb-2 font-medium">Supply</th>
              <th className="pb-2 font-medium text-right">Allowed</th>
              <th className="pb-2 w-8"></th>
            </tr>
          </thead>
          <tbody>
            {rates
              .sort((a, b) => a.hcpcs_code.localeCompare(b.hcpcs_code) || a.supply_months - b.supply_months)
              .map(rate => (
                <tr key={rate.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                  <td className="py-2 font-mono text-xs font-medium text-gray-700">{rate.hcpcs_code}</td>
                  <td className="py-2 text-gray-600">{rate.description || HCPCS_LABELS[rate.hcpcs_code] || '—'}</td>
                  <td className="py-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      rate.supply_months <= 3 ? 'bg-purple-50 text-purple-600' : 'bg-blue-50 text-blue-600'
                    }`}>
                      {rate.supply_months}mo
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono font-medium text-gray-900">
                    ${rate.allowed_amount.toFixed(2)}
                  </td>
                  <td className="py-2 text-right">
                    <button onClick={() => onDelete(rate.id)} className="text-gray-300 hover:text-red-500 transition-colors" title="Delete">
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
