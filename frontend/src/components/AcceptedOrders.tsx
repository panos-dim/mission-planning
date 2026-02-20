import { useState, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Download,
  Copy,
  Trash2,
  Edit2,
  Check,
  X,
  ChevronDown,
  ChevronRight,
  Satellite,
  Target,
  Camera,
} from 'lucide-react'
import { AcceptedOrder } from '../types'
import { formatDateTimeShort } from '../utils/date'

interface AcceptedOrdersProps {
  orders: AcceptedOrder[]
  onOrdersChange: (orders: AcceptedOrder[]) => void
}

const algorithmNames: Record<string, string> = {
  first_fit: 'First-Fit',
  best_fit: 'Best-Fit',
  optimal: 'Optimal',
  roll_pitch_best_fit: 'Optimized',
  roll_pitch_first_fit: 'Standard',
}

export default function AcceptedOrders({
  orders,
  onOrdersChange,
}: AcceptedOrdersProps): JSX.Element {
  const queryClient = useQueryClient()
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const [editingOrderId, setEditingOrderId] = useState<string | null>(null)
  const [editedName, setEditedName] = useState<string>('')

  const selectedOrder = orders.find((o) => o.order_id === selectedOrderId)

  // Compute time window for each order
  const orderTimeWindows = useMemo(() => {
    const windows: Record<string, { start: string; end: string }> = {}
    for (const order of orders) {
      if (order.schedule.length > 0) {
        const sorted = [...order.schedule].sort(
          (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
        )
        windows[order.order_id] = {
          start: sorted[0].start_time,
          end: sorted[sorted.length - 1].end_time,
        }
      }
    }
    return windows
  }, [orders])

  const handleExportCSV = (order: AcceptedOrder) => {
    const csv = [
      ['#', 'Satellite', 'Target', 'Start', 'End', 'Δroll (°)'].join(','),
      ...order.schedule.map((item, idx) =>
        [
          idx + 1,
          item.satellite_id,
          item.target_id,
          item.start_time,
          item.end_time,
          item.droll_deg.toFixed(2),
        ].join(','),
      ),
    ].join('\n')

    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${order.name}_schedule.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportJSON = (order: AcceptedOrder) => {
    const json = JSON.stringify(order, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${order.name}_order.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDuplicate = (order: AcceptedOrder) => {
    const copy: AcceptedOrder = {
      ...order,
      order_id: `order_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `${order.name}-copy`,
      created_at: new Date().toISOString(),
    }
    onOrdersChange([...orders, copy])
  }

  const handleClear = async (orderId: string) => {
    if (!confirm('Remove this schedule entry?')) return

    // Find the order to get its acquisition IDs for backend deletion
    const order = orders.find((o) => o.order_id === orderId)

    // Remove from local state immediately
    onOrdersChange(orders.filter((o) => o.order_id !== orderId))
    if (selectedOrderId === orderId) {
      setSelectedOrderId(null)
    }

    // Delete from backend DB using real acquisition IDs
    if (order) {
      try {
        const { bulkDeleteAcquisitions } = await import('../api/scheduleApi')
        // Use backend acq_* IDs if available, fall back to opportunity_ids for legacy orders
        const acqIds = order.backend_acquisition_ids?.length
          ? order.backend_acquisition_ids
          : order.schedule.map((s) => s.opportunity_id)
        if (acqIds.length > 0) {
          const res = await bulkDeleteAcquisitions({ acquisition_ids: acqIds, force: true })
          console.log('[AcceptedOrders] Backend delete:', res.message)
        }
        // Also try deleting the plan itself
        const { deleteOrder } = await import('../api/scheduleApi')
        await deleteOrder(orderId, true).catch(() => {
          // Plan may not exist in backend (legacy local-only orders) — ignore
        })
        // Invalidate schedule context cache so the badge refreshes
        queryClient.invalidateQueries({ queryKey: ['schedule'] })
      } catch (err) {
        console.warn('[AcceptedOrders] Backend cleanup failed:', err)
      }
    }
  }

  const handleStartEdit = (order: AcceptedOrder) => {
    setEditingOrderId(order.order_id)
    setEditedName(order.name)
  }

  const handleSaveEdit = () => {
    if (editingOrderId && editedName.trim()) {
      onOrdersChange(
        orders.map((o) => (o.order_id === editingOrderId ? { ...o, name: editedName.trim() } : o)),
      )
      setEditingOrderId(null)
    }
  }

  const handleCancelEdit = () => {
    setEditingOrderId(null)
    setEditedName('')
  }

  const formatDateTime = (isoString: string) => {
    try {
      return formatDateTimeShort(isoString)
    } catch {
      return isoString
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="flex items-center justify-between bg-gray-800 border-b border-gray-700 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">Schedule</h2>
          <span className="text-[10px] text-gray-500">{orders.length} entries</span>
        </div>
      </div>

      {/* Orders List — compact rows */}
      <div className="flex-1 overflow-auto">
        {orders.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center px-6 py-8">
              <Camera className="w-8 h-8 text-gray-600 mx-auto mb-3" />
              <h3 className="text-sm font-medium text-gray-400 mb-1">No schedules yet</h3>
              <p className="text-xs text-gray-500 max-w-[240px]">
                Run an algorithm in Mission Planning, then click Apply to add acquisitions.
              </p>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {orders.map((order) => {
              const isSelected = selectedOrderId === order.order_id
              const isEditing = editingOrderId === order.order_id
              const timeWindow = orderTimeWindows[order.order_id]

              return (
                <div
                  key={order.order_id}
                  className={`group transition-colors cursor-pointer ${
                    isSelected
                      ? 'bg-blue-950/40 border-l-2 border-blue-500'
                      : 'bg-gray-900 hover:bg-gray-800/60 border-l-2 border-transparent'
                  }`}
                  onClick={() => setSelectedOrderId(isSelected ? null : order.order_id)}
                >
                  {/* Compact row */}
                  <div className="flex items-center gap-2 px-3 py-2">
                    {/* Expand indicator */}
                    <div className="w-4 flex-shrink-0 text-gray-600">
                      {isSelected ? (
                        <ChevronDown className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5" />
                      )}
                    </div>

                    {/* Name + algorithm */}
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <div className="flex items-center gap-1.5">
                          <input
                            type="text"
                            value={editedName}
                            onChange={(e) => setEditedName(e.target.value)}
                            className="flex-1 bg-gray-700 border border-gray-600 rounded px-1.5 py-0.5 text-xs"
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveEdit()
                              if (e.key === 'Escape') handleCancelEdit()
                            }}
                          />
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleSaveEdit()
                            }}
                            className="p-0.5 text-green-400 hover:text-green-300"
                          >
                            <Check className="w-3 h-3" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleCancelEdit()
                            }}
                            className="p-0.5 text-red-400 hover:text-red-300"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-medium text-white truncate max-w-[140px]">
                            {order.name}
                          </span>
                          <span className="px-1.5 py-0 text-[9px] font-medium rounded bg-blue-900/60 text-blue-300 flex-shrink-0">
                            {algorithmNames[order.algorithm] || order.algorithm}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Inline metrics */}
                    <div className="flex items-center gap-2.5 flex-shrink-0 text-[10px]">
                      <span
                        className="flex items-center gap-0.5 text-green-400"
                        title="Acquisitions"
                      >
                        <Camera className="w-3 h-3" />
                        {order.metrics.accepted}
                      </span>
                      <span className="flex items-center gap-0.5 text-blue-400" title="Satellites">
                        <Satellite className="w-3 h-3" />
                        {order.satellites_involved?.length || 0}
                      </span>
                      <span className="flex items-center gap-0.5 text-purple-400" title="Targets">
                        <Target className="w-3 h-3" />
                        {order.targets_covered?.length || 0}
                      </span>
                    </div>

                    {/* Actions — visible on hover or selection */}
                    <div
                      className={`flex items-center gap-0.5 flex-shrink-0 transition-opacity ${
                        isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}
                    >
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleStartEdit(order)
                        }}
                        className="p-1 text-gray-500 hover:text-white rounded hover:bg-gray-700"
                        title="Rename"
                      >
                        <Edit2 className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleExportCSV(order)
                        }}
                        className="p-1 text-gray-500 hover:text-white rounded hover:bg-gray-700"
                        title="Export CSV"
                      >
                        <Download className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDuplicate(order)
                        }}
                        className="p-1 text-gray-500 hover:text-white rounded hover:bg-gray-700"
                        title="Duplicate"
                      >
                        <Copy className="w-3 h-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleClear(order.order_id)
                        }}
                        className="p-1 text-gray-500 hover:text-red-400 rounded hover:bg-red-900/20"
                        title="Remove"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  {/* Time window — shown below name, subtle */}
                  {timeWindow && (
                    <div className="flex items-center gap-1 px-3 pb-2 pl-9 text-[10px] text-gray-500">
                      <span>{formatDateTime(timeWindow.start)}</span>
                      <span>→</span>
                      <span>{formatDateTime(timeWindow.end)}</span>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Detail Panel — shown when an order is selected */}
      {selectedOrder && (
        <div className="border-t border-gray-700 bg-gray-800 max-h-[45%] overflow-auto">
          {/* Detail header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 sticky top-0 bg-gray-800 z-10">
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-semibold text-white">
                {selectedOrder.metrics.accepted} Acquisitions
              </h3>
              <span className="text-[10px] text-gray-500">
                {selectedOrder.satellites_involved?.length || 0} sats ·{' '}
                {selectedOrder.targets_covered?.length || 0} targets
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => handleExportJSON(selectedOrder)}
                className="px-2 py-0.5 bg-gray-700 hover:bg-gray-600 rounded text-[10px] text-gray-300"
              >
                JSON
              </button>
              <button
                onClick={() => handleExportCSV(selectedOrder)}
                className="px-2 py-0.5 bg-blue-600 hover:bg-blue-700 rounded text-[10px] text-white"
              >
                CSV
              </button>
            </div>
          </div>

          {/* Acquisitions table — ops-focused columns only */}
          <table className="w-full text-[11px]">
            <thead className="bg-gray-750 text-gray-400 sticky top-[33px] z-10">
              <tr>
                <th className="text-left py-1.5 px-3 font-medium">Target</th>
                <th className="text-left py-1.5 px-2 font-medium">Satellite</th>
                <th className="text-left py-1.5 px-2 font-medium">Start</th>
                <th className="text-left py-1.5 px-2 font-medium">End</th>
                <th className="text-right py-1.5 px-3 font-medium">Δroll°</th>
              </tr>
            </thead>
            <tbody className="text-gray-300">
              {(() => {
                const sorted = [...selectedOrder.schedule].sort(
                  (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
                )
                return sorted.map((item, idx) => (
                  <tr key={idx} className="border-t border-gray-700/50 hover:bg-gray-700/30">
                    <td className="py-1 px-3 text-white font-medium">{item.target_id}</td>
                    <td className="py-1 px-2">{item.satellite_id}</td>
                    <td className="py-1 px-2 text-gray-400">{formatDateTime(item.start_time)}</td>
                    <td className="py-1 px-2 text-gray-400">{formatDateTime(item.end_time)}</td>
                    <td className="py-1 px-3 text-right font-mono text-gray-400">
                      {item.droll_deg.toFixed(1)}
                    </td>
                  </tr>
                ))
              })()}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
