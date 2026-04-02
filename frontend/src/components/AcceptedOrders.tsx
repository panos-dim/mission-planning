import { useState, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Trash2, ChevronDown, ChevronRight, Camera } from 'lucide-react'
import { bulkDeleteAcquisitions, deleteOrder } from '../api/scheduleApi'
import { AcceptedOrder } from '../types'
import { formatDateTimeShort } from '../utils/date'

interface AcceptedOrdersProps {
  orders: AcceptedOrder[]
  onOrdersChange: (orders: AcceptedOrder[]) => void
}

export default function AcceptedOrders({
  orders,
  onOrdersChange,
}: AcceptedOrdersProps): JSX.Element {
  const queryClient = useQueryClient()
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)

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

  const handleClear = async (orderId: string) => {
    if (!confirm('Remove this schedule entry?')) return

    // Find the order to get its acquisition IDs for backend deletion
    const order = orders.find((o) => o.order_id === orderId)

    // Remove from local state immediately
    onOrdersChange(orders.filter((o) => o.order_id !== orderId))
    if (selectedOrderId === orderId) setSelectedOrderId(null)

    // Delete from backend DB using real acquisition IDs
    if (order) {
      try {
        // Use backend acq_* IDs if available, fall back to opportunity_ids for legacy orders
        const acqIds = order.backend_acquisition_ids?.length
          ? order.backend_acquisition_ids
          : order.schedule.map((s) => s.opportunity_id)
        if (acqIds.length > 0) {
          const res = await bulkDeleteAcquisitions({ acquisition_ids: acqIds, force: true })
          console.log('[AcceptedOrders] Backend delete:', res.message)
        }
        // Also try deleting the plan itself
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

  const formatDateTime = (isoString: string) => {
    try {
      return formatDateTimeShort(isoString)
    } catch {
      return isoString
    }
  }

  const getPlanLabel = (order: AcceptedOrder, index: number) => {
    if (orders.length === 1) return 'Active Plan'
    if (order.name?.trim() && !order.name.startsWith('Recovered')) return order.name
    return `Plan ${index + 1}`
  }

  const getPlanSummary = (order: AcceptedOrder) => {
    const satelliteCount = order.satellites_involved?.length || 0
    const targetCount = order.targets_covered?.length || 0
    return `${satelliteCount} sat${satelliteCount === 1 ? '' : 's'} • ${targetCount} target${targetCount === 1 ? '' : 's'}`
  }

  const sortedSelectedSchedule = useMemo(() => {
    if (!selectedOrder) return []
    return [...selectedOrder.schedule].sort(
      (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
    )
  }, [selectedOrder])

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-2.5">
        <h2 className="text-xs font-semibold text-gray-300 uppercase">Upcoming Plan</h2>
      </div>

      {/* Orders List — compact rows */}
      <div className="flex-1 overflow-auto">
        {orders.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center px-6 py-8">
              <Camera className="w-8 h-8 text-gray-600 mx-auto mb-3" />
              <h3 className="text-sm font-medium text-gray-400 mb-1">No scheduled acquisitions</h3>
              <p className="text-xs text-gray-500 text-pretty max-w-[240px]">
                When a planner applies a schedule, the upcoming acquisitions will appear here.
              </p>
            </div>
          </div>
        ) : (
          <div className="divide-y divide-gray-800">
            {orders.map((order, index) => {
              const isSelected = selectedOrderId === order.order_id
              const timeWindow = orderTimeWindows[order.order_id]
              const planLabel = getPlanLabel(order, index)

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
                  <div className="flex items-start gap-2 px-3 py-2.5">
                    {/* Expand indicator */}
                    <div className="w-4 flex-shrink-0 text-gray-600">
                      {isSelected ? (
                        <ChevronDown className="w-3.5 h-3.5" />
                      ) : (
                        <ChevronRight className="w-3.5 h-3.5" />
                      )}
                    </div>

                    {/* Plan summary */}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-white truncate">{planLabel}</div>
                      <div className="mt-1 text-[11px] text-gray-400 text-pretty">
                        {getPlanSummary(order)}
                      </div>
                      {timeWindow && (
                        <div className="mt-1 text-[11px] text-gray-500 tabular-nums">
                          {formatDateTime(timeWindow.start)} → {formatDateTime(timeWindow.end)}
                        </div>
                      )}
                    </div>
                  </div>

                  {isSelected && (
                    <div className="border-t border-gray-800 px-3 py-2 pl-9">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          void handleClear(order.order_id)
                        }}
                        className="inline-flex items-center gap-1 rounded border border-red-800/70 px-2 py-1 text-[11px] text-red-200 hover:bg-red-950/40"
                        aria-label={`Remove ${planLabel}`}
                      >
                        <Trash2 className="size-3.5" />
                        <span>Remove this plan</span>
                      </button>
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
            <h3 className="text-xs font-semibold text-white uppercase">Upcoming Passes</h3>
          </div>

          <div className="divide-y divide-gray-700/70">
            {sortedSelectedSchedule.map((item, idx) => {
              const pitchDeg = item.pitch_deg ?? 0

              return (
                <div key={`${item.opportunity_id}-${idx}`} className="px-3 py-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-white truncate">{item.target_id}</div>
                      <div className="mt-1 text-[11px] text-gray-400">
                        Satellite {item.satellite_id}
                      </div>
                      <div className="mt-1 text-[11px] text-gray-500 tabular-nums">
                        {formatDateTime(item.start_time)} → {formatDateTime(item.end_time)}
                      </div>
                    </div>
                    <div className="text-right text-[11px] text-gray-400 tabular-nums">
                      <div>Roll {item.droll_deg.toFixed(1)}°</div>
                      <div className="mt-1">Pitch {pitchDeg.toFixed(1)}°</div>
                      {item.t_slew_s > 0 && (
                        <div className="mt-1">Slew {item.t_slew_s.toFixed(0)}s</div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
