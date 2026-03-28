import { useEffect, useState, useCallback } from 'react'
import { Package, AlertTriangle, RefreshCw, Plus, Minus, Search } from 'lucide-react'
import { getDMEInventory, updateDMEInventory, restockDMEInventory } from '../services/api'
import ErrorBanner from './ErrorBanner'

const CATEGORY_COLORS = {
  Equipment: 'bg-blue-100 text-blue-700',
  Masks: 'bg-purple-100 text-purple-700',
  'Replacement Parts': 'bg-amber-100 text-amber-700',
  Accessories: 'bg-gray-100 text-gray-700',
}

export default function DMEInventory() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('all') // all | low | out
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')
  const [editing, setEditing] = useState(null) // { id, quantity, reorder_point }
  const [restocking, setRestocking] = useState(null) // { id, quantity }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getDMEInventory()
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleSave = async () => {
    if (!editing) return
    try {
      await updateDMEInventory(editing.id, {
        quantity: parseInt(editing.quantity),
        reorder_point: parseInt(editing.reorder_point),
      })
      setEditing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleRestock = async () => {
    if (!restocking || restocking.quantity <= 0) return
    try {
      await restockDMEInventory(restocking.id, parseInt(restocking.quantity))
      setRestocking(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (loading) return <p className="text-gray-400 text-center py-12">Loading inventory...</p>
  if (!data) return null

  const { items, summary } = data
  const categories = [...new Set(items.map(i => i.category))]

  let filtered = items
  if (filter === 'low') filtered = filtered.filter(i => i.quantity > 0 && i.quantity <= i.reorder_point)
  if (filter === 'out') filtered = filtered.filter(i => i.quantity === 0)
  if (categoryFilter !== 'all') filtered = filtered.filter(i => i.category === categoryFilter)
  if (searchTerm) {
    const term = searchTerm.toLowerCase()
    filtered = filtered.filter(i =>
      i.product_name.toLowerCase().includes(term) ||
      i.hcpcs_code.toLowerCase().includes(term) ||
      i.size.toLowerCase().includes(term)
    )
  }

  return (
    <div className="space-y-4">
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-center">
          <p className="text-2xl font-bold text-gray-900">{summary.total_skus}</p>
          <p className="text-xs text-gray-500">Total SKUs</p>
        </div>
        <div className={`rounded-xl border px-4 py-3 text-center cursor-pointer transition-colors ${
          filter === 'low' ? 'bg-amber-100 border-amber-300' : 'bg-amber-50 border-amber-200 hover:bg-amber-100'
        }`} onClick={() => setFilter(filter === 'low' ? 'all' : 'low')}>
          <p className="text-2xl font-bold text-amber-700">{summary.low_stock}</p>
          <p className="text-xs text-amber-600">Low Stock</p>
        </div>
        <div className={`rounded-xl border px-4 py-3 text-center cursor-pointer transition-colors ${
          filter === 'out' ? 'bg-red-100 border-red-300' : 'bg-red-50 border-red-200 hover:bg-red-100'
        }`} onClick={() => setFilter(filter === 'out' ? 'all' : 'out')}>
          <p className="text-2xl font-bold text-red-700">{summary.out_of_stock}</p>
          <p className="text-xs text-red-600">Out of Stock</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 items-center flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, HCPCS, or size..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
          <option value="all">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button onClick={load} disabled={loading} className="btn-secondary text-sm flex items-center gap-1">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Inventory table */}
      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Product</th>
              <th className="text-left px-3 py-2.5 text-gray-600 font-medium">HCPCS</th>
              <th className="text-left px-3 py-2.5 text-gray-600 font-medium">Size</th>
              <th className="text-center px-3 py-2.5 text-gray-600 font-medium">Qty</th>
              <th className="text-center px-3 py-2.5 text-gray-600 font-medium">Reorder At</th>
              <th className="text-left px-3 py-2.5 text-gray-600 font-medium">Status</th>
              <th className="text-right px-4 py-2.5 text-gray-600 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map(item => {
              const isEditing = editing?.id === item.id
              const isRestocking = restocking?.id === item.id
              const outOfStock = item.quantity === 0
              const lowStock = item.quantity > 0 && item.quantity <= item.reorder_point

              return (
                <tr key={item.id} className={`${
                  outOfStock ? 'bg-red-50/50' : lowStock ? 'bg-amber-50/50' : 'hover:bg-gray-50'
                }`}>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${CATEGORY_COLORS[item.category] || 'bg-gray-100 text-gray-600'}`}>
                        {item.category}
                      </span>
                      <span className="font-medium text-gray-900">{item.product_name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-gray-500 font-mono text-xs">{item.hcpcs_code}</td>
                  <td className="px-3 py-2.5">
                    {item.size ? (
                      <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-medium">{item.size}</span>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {isEditing ? (
                      <input type="number" min="0" value={editing.quantity}
                        onChange={e => setEditing({ ...editing, quantity: e.target.value })}
                        className="w-16 text-center border rounded px-1 py-0.5 text-sm" autoFocus />
                    ) : (
                      <span className={`font-bold ${outOfStock ? 'text-red-600' : lowStock ? 'text-amber-600' : 'text-gray-900'}`}>
                        {item.quantity}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {isEditing ? (
                      <input type="number" min="0" value={editing.reorder_point}
                        onChange={e => setEditing({ ...editing, reorder_point: e.target.value })}
                        className="w-16 text-center border rounded px-1 py-0.5 text-sm" />
                    ) : (
                      <span className="text-gray-500">{item.reorder_point}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    {outOfStock ? (
                      <span className="flex items-center gap-1 text-red-600 text-xs font-medium">
                        <AlertTriangle size={12} /> Out of Stock
                      </span>
                    ) : lowStock ? (
                      <span className="flex items-center gap-1 text-amber-600 text-xs font-medium">
                        <AlertTriangle size={12} /> Low Stock
                      </span>
                    ) : (
                      <span className="text-green-600 text-xs font-medium">In Stock</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      {isEditing ? (
                        <>
                          <button onClick={handleSave}
                            className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>
                          <button onClick={() => setEditing(null)}
                            className="px-2 py-1 text-xs bg-gray-200 text-gray-600 rounded hover:bg-gray-300">Cancel</button>
                        </>
                      ) : isRestocking ? (
                        <>
                          <input type="number" min="1" value={restocking.quantity}
                            onChange={e => setRestocking({ ...restocking, quantity: e.target.value })}
                            className="w-16 text-center border rounded px-1 py-0.5 text-sm" autoFocus />
                          <button onClick={handleRestock}
                            className="px-2 py-1 text-xs bg-emerald-600 text-white rounded hover:bg-emerald-700">Add</button>
                          <button onClick={() => setRestocking(null)}
                            className="px-2 py-1 text-xs bg-gray-200 text-gray-600 rounded hover:bg-gray-300">Cancel</button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => setRestocking({ id: item.id, quantity: 1 })}
                            className="px-2 py-1 text-xs bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 flex items-center gap-1">
                            <Plus size={12} /> Restock
                          </button>
                          <button onClick={() => setEditing({ id: item.id, quantity: item.quantity, reorder_point: item.reorder_point })}
                            className="px-2 py-1 text-xs bg-gray-50 text-gray-600 rounded hover:bg-gray-100">
                            Edit
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <Package size={24} className="mx-auto mb-2 opacity-50" />
            <p>No items match your filters</p>
          </div>
        )}
      </div>
    </div>
  )
}
