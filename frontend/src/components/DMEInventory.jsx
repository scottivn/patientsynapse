import { useEffect, useState, useCallback, useMemo } from 'react'
import { Package, AlertTriangle, RefreshCw, Plus, Search, ChevronDown } from 'lucide-react'
import { getDMEInventory, updateDMEInventory, restockDMEInventory } from '../services/api'
import ErrorBanner from './ErrorBanner'

const CATEGORY_COLORS = {
  Equipment: 'bg-blue-100 text-blue-700',
  Masks: 'bg-purple-100 text-purple-700',
  'Replacement Parts': 'bg-amber-100 text-amber-700',
  Accessories: 'bg-gray-100 text-gray-700',
}

/** Group flat inventory rows into one entry per product with size variants. */
function groupByProduct(items) {
  const map = new Map()
  for (const item of items) {
    if (!map.has(item.product_id)) {
      map.set(item.product_id, {
        product_id: item.product_id,
        product_name: item.product_name,
        hcpcs_code: item.hcpcs_code,
        category: item.category,
        sizes: [],
      })
    }
    map.get(item.product_id).sizes.push(item)
  }
  // Compute aggregates
  for (const group of map.values()) {
    const hasSizes = group.sizes.length > 1 || group.sizes[0]?.size !== ''
    group.has_sizes = hasSizes
    group.total_qty = group.sizes.reduce((sum, s) => sum + s.quantity, 0)
    group.any_out = group.sizes.some(s => s.quantity === 0)
    group.any_low = group.sizes.some(s => s.quantity > 0 && s.quantity <= s.reorder_point)
    group.all_in_stock = !group.any_out && !group.any_low
    group.sizes_out = group.sizes.filter(s => s.quantity === 0).length
    group.sizes_low = group.sizes.filter(s => s.quantity > 0 && s.quantity <= s.reorder_point).length
  }
  return [...map.values()]
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
  const [selectedSizes, setSelectedSizes] = useState({}) // { product_id: size_index }

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

  // Group items by product and apply filters
  const { groups, categories } = useMemo(() => {
    if (!data) return { groups: [], categories: [] }
    const { items } = data
    const cats = [...new Set(items.map(i => i.category))]

    let filteredItems = items
    if (categoryFilter !== 'all') filteredItems = filteredItems.filter(i => i.category === categoryFilter)
    if (searchTerm) {
      const term = searchTerm.toLowerCase()
      filteredItems = filteredItems.filter(i =>
        i.product_name.toLowerCase().includes(term) ||
        i.hcpcs_code.toLowerCase().includes(term) ||
        i.size.toLowerCase().includes(term)
      )
    }

    let grouped = groupByProduct(filteredItems)

    // Filter groups by stock status
    if (filter === 'low') grouped = grouped.filter(g => g.any_low)
    if (filter === 'out') grouped = grouped.filter(g => g.any_out)

    return { groups: grouped, categories: cats }
  }, [data, filter, categoryFilter, searchTerm])

  if (loading) return <p className="text-gray-400 text-center py-12">Loading inventory...</p>
  if (!data) return null

  const { summary } = data

  const getSelectedSize = (group) => {
    const idx = selectedSizes[group.product_id] || 0
    return group.sizes[idx] || group.sizes[0]
  }

  const setSelectedSizeIdx = (productId, idx) => {
    setSelectedSizes(prev => ({ ...prev, [productId]: idx }))
    // Clear edit/restock state when switching sizes
    setEditing(null)
    setRestocking(null)
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

      {/* Inventory table — consolidated by product */}
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
            {groups.map(group => {
              const current = getSelectedSize(group)
              const isEditing = editing?.id === current.id
              const isRestocking = restocking?.id === current.id
              const outOfStock = current.quantity === 0
              const lowStock = current.quantity > 0 && current.quantity <= current.reorder_point

              return (
                <tr key={group.product_id} className={`${
                  outOfStock ? 'bg-red-50/50' : lowStock ? 'bg-amber-50/50' : 'hover:bg-gray-50'
                }`}>
                  {/* Product name + category badge + total stock */}
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${CATEGORY_COLORS[group.category] || 'bg-gray-100 text-gray-600'}`}>
                        {group.category}
                      </span>
                      <span className="font-medium text-gray-900">{group.product_name}</span>
                      {group.has_sizes && (
                        <span className="text-xs text-gray-400 shrink-0" title="Total across all sizes">
                          ({group.total_qty} total)
                        </span>
                      )}
                    </div>
                  </td>

                  {/* HCPCS */}
                  <td className="px-3 py-2.5 text-gray-500 font-mono text-xs">{group.hcpcs_code}</td>

                  {/* Size dropdown or dash */}
                  <td className="px-3 py-2.5">
                    {group.has_sizes ? (
                      <div className="relative inline-block">
                        <select
                          value={selectedSizes[group.product_id] || 0}
                          onChange={e => setSelectedSizeIdx(group.product_id, parseInt(e.target.value))}
                          className="appearance-none pl-2 pr-6 py-0.5 rounded border border-gray-200 bg-white text-xs font-medium text-gray-700 cursor-pointer focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          {group.sizes.map((s, i) => {
                            const sOut = s.quantity === 0
                            const sLow = s.quantity > 0 && s.quantity <= s.reorder_point
                            const indicator = sOut ? ' (OUT)' : sLow ? ' (LOW)' : ''
                            return (
                              <option key={s.id} value={i}>
                                {s.size}{indicator}
                              </option>
                            )
                          })}
                        </select>
                        <ChevronDown size={12} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      </div>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>

                  {/* Quantity for selected size */}
                  <td className="px-3 py-2.5 text-center">
                    {isEditing ? (
                      <input type="number" min="0" value={editing.quantity}
                        onChange={e => setEditing({ ...editing, quantity: e.target.value })}
                        className="w-16 text-center border rounded px-1 py-0.5 text-sm" autoFocus />
                    ) : (
                      <span className={`font-bold ${outOfStock ? 'text-red-600' : lowStock ? 'text-amber-600' : 'text-gray-900'}`}>
                        {current.quantity}
                      </span>
                    )}
                  </td>

                  {/* Reorder point for selected size */}
                  <td className="px-3 py-2.5 text-center">
                    {isEditing ? (
                      <input type="number" min="0" value={editing.reorder_point}
                        onChange={e => setEditing({ ...editing, reorder_point: e.target.value })}
                        className="w-16 text-center border rounded px-1 py-0.5 text-sm" />
                    ) : (
                      <span className="text-gray-500">{current.reorder_point}</span>
                    )}
                  </td>

                  {/* Status — selected size + aggregate indicator */}
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col gap-0.5">
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
                      {group.has_sizes && (group.sizes_out > 0 || group.sizes_low > 0) && (
                        <span className="text-[10px] text-gray-400">
                          {group.sizes_out > 0 && `${group.sizes_out} size${group.sizes_out > 1 ? 's' : ''} out`}
                          {group.sizes_out > 0 && group.sizes_low > 0 && ', '}
                          {group.sizes_low > 0 && `${group.sizes_low} low`}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Actions for selected size */}
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
                          <button onClick={() => setRestocking({ id: current.id, quantity: 1 })}
                            className="px-2 py-1 text-xs bg-emerald-50 text-emerald-700 rounded hover:bg-emerald-100 flex items-center gap-1">
                            <Plus size={12} /> Restock
                          </button>
                          <button onClick={() => setEditing({ id: current.id, quantity: current.quantity, reorder_point: current.reorder_point })}
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
        {groups.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <Package size={24} className="mx-auto mb-2 opacity-50" />
            <p>No items match your filters</p>
          </div>
        )}
      </div>
    </div>
  )
}
