import { useState } from 'react'
import { Download, Copy, Trash2, Edit2, Check, X } from 'lucide-react'
import { AcceptedOrder } from '../types'

interface AcceptedOrdersProps {
  orders: AcceptedOrder[]
  onOrdersChange: (orders: AcceptedOrder[]) => void
}

const algorithmNames: Record<string, string> = {
  first_fit: 'First-Fit',
  best_fit: 'Best-Fit',
  optimal: 'Optimal'
}

export default function AcceptedOrders({ orders, onOrdersChange }: AcceptedOrdersProps): JSX.Element {
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const [editingOrderId, setEditingOrderId] = useState<string | null>(null)
  const [editedName, setEditedName] = useState<string>('')

  const selectedOrder = orders.find(o => o.order_id === selectedOrderId)

  const handleExportCSV = (order: AcceptedOrder) => {
    const csv = [
      ['#', 'Satellite', 'Target', 'Start', 'End', 'Δroll (°)', 't_slew (s)', 'Slack (s)', 'Value', 'Density'].join(','),
      ...order.schedule.map((item, idx) => [
        idx + 1,
        item.satellite_id,
        item.target_id,
        item.start_time,
        item.end_time,
        item.droll_deg.toFixed(2),
        item.t_slew_s.toFixed(3),
        item.slack_s.toFixed(3),
        item.value.toFixed(2),
        item.density === 'inf' ? 'inf' : item.density.toFixed(3)
      ].join(','))
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
      created_at: new Date().toISOString()
    }
    onOrdersChange([...orders, copy])
  }

  const handleClear = (orderId: string) => {
    if (confirm('Are you sure you want to remove this order?')) {
      onOrdersChange(orders.filter(o => o.order_id !== orderId))
      if (selectedOrderId === orderId) {
        setSelectedOrderId(null)
      }
    }
  }

  const handleStartEdit = (order: AcceptedOrder) => {
    setEditingOrderId(order.order_id)
    setEditedName(order.name)
  }

  const handleSaveEdit = () => {
    if (editingOrderId && editedName.trim()) {
      onOrdersChange(orders.map(o => 
        o.order_id === editingOrderId ? { ...o, name: editedName.trim() } : o
      ))
      setEditingOrderId(null)
    }
  }

  const handleCancelEdit = () => {
    setEditingOrderId(null)
    setEditedName('')
  }

  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', { 
      month: '2-digit', 
      day: '2-digit', 
      year: 'numeric',
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    })
  }

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <h2 className="text-sm font-semibold text-white mb-1">Accepted Orders</h2>
        <p className="text-xs text-gray-400">
          Review and export accepted scheduling plans ({orders.length} total)
        </p>
      </div>

      {/* Orders List */}
      <div className="flex-1 overflow-auto">
        {orders.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center p-8">
              <div className="text-gray-500 text-5xl mb-4">📋</div>
              <h3 className="text-lg font-semibold text-gray-300 mb-2">No Orders Yet</h3>
              <p className="text-sm text-gray-400 max-w-md">
                Run algorithms in <strong>Mission Planning</strong>, then click <strong>&quot;Accept This Plan → Orders&quot;</strong> to add schedules here.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {orders.map(order => (
              <div
                key={order.order_id}
                className={`bg-gray-800 rounded-lg border transition-all cursor-pointer ${
                  selectedOrderId === order.order_id
                    ? 'border-blue-500 shadow-lg'
                    : 'border-gray-700 hover:border-gray-600'
                }`}
                onClick={() => setSelectedOrderId(order.order_id)}
              >
                {/* Order Card Header */}
                <div className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      {editingOrderId === order.order_id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editedName}
                            onChange={(e) => setEditedName(e.target.value)}
                            className="flex-1 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm"
                            autoFocus
                            onClick={(e) => e.stopPropagation()}
                          />
                          <button
                            onClick={(e) => { e.stopPropagation(); handleSaveEdit() }}
                            className="p-1 text-green-400 hover:text-green-300"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleCancelEdit() }}
                            className="p-1 text-red-400 hover:text-red-300"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2">
                          <h3 className="text-base font-semibold text-white">{order.name}</h3>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleStartEdit(order) }}
                            className="p-1 text-gray-400 hover:text-white"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <span className="px-2 py-0.5 bg-blue-900 text-blue-200 rounded text-xs font-medium">
                          {algorithmNames[order.algorithm]}
                        </span>
                        <span className="text-xs text-gray-400">{formatDateTime(order.created_at)}</span>
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleExportCSV(order) }}
                        className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
                        title="Export CSV"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDuplicate(order) }}
                        className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded"
                        title="Duplicate"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleClear(order.order_id) }}
                        className="p-2 text-red-400 hover:text-red-300 hover:bg-gray-700 rounded"
                        title="Clear"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Metrics Summary */}
                  <div className="grid grid-cols-4 gap-3 text-xs">
                    <div>
                      <div className="text-gray-400">Accepted</div>
                      <div className="text-lg font-bold text-green-400">{order.metrics.accepted}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Total Value</div>
                      <div className="text-lg font-bold text-blue-400">{order.metrics.total_value.toFixed(1)}</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Utilization</div>
                      <div className="text-lg font-bold text-blue-400">{(order.metrics.utilization * 100).toFixed(1)}%</div>
                    </div>
                    <div>
                      <div className="text-gray-400">Runtime</div>
                      <div className="text-lg font-bold text-yellow-400">{order.metrics.runtime_ms.toFixed(1)}ms</div>
                    </div>
                  </div>

                  {/* Additional Info */}
                  {order.satellites_involved && order.targets_covered && (
                    <div className="mt-3 pt-3 border-t border-gray-700 flex gap-4 text-xs">
                      <div>
                        <span className="text-gray-400">Satellites:</span>{' '}
                        <span className="text-white">{order.satellites_involved.length}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Targets:</span>{' '}
                        <span className="text-white">{order.targets_covered.length}</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Imaging Time:</span>{' '}
                        <span className="text-white">{order.metrics.imaging_time_s.toFixed(1)}s</span>
                      </div>
                      <div>
                        <span className="text-gray-400">Maneuver Time:</span>{' '}
                        <span className="text-white">{order.metrics.maneuver_time_s.toFixed(1)}s</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Panel */}
      {selectedOrder && (
        <div className="border-t border-gray-700 bg-gray-800 p-4 max-h-96 overflow-auto">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">Schedule Details</h3>
            <div className="flex gap-2">
              <button
                onClick={() => handleExportJSON(selectedOrder)}
                className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs"
              >
                Export JSON
              </button>
              <button
                onClick={() => handleExportCSV(selectedOrder)}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs"
              >
                Export CSV
              </button>
            </div>
          </div>

          {/* Detailed Metrics */}
          <div className="grid grid-cols-3 gap-4 mb-4 p-3 bg-gray-700 rounded text-xs">
            <div>
              <div className="text-gray-400">Mean Incidence</div>
              <div className="text-white font-semibold">{selectedOrder.metrics.mean_incidence_deg.toFixed(2)}°</div>
            </div>
            <div>
              <div className="text-gray-400">Rejected</div>
              <div className="text-white font-semibold">{selectedOrder.metrics.rejected}</div>
            </div>
            <div>
              <div className="text-gray-400">Order ID</div>
              <div className="text-white font-mono text-xs truncate">{selectedOrder.order_id}</div>
            </div>
          </div>

          {/* Schedule Table */}
          <div className="overflow-x-auto bg-gray-700 rounded">
            <table className="w-full text-xs">
              <thead className="border-b border-gray-600 bg-gray-750">
                <tr>
                  <th className="text-left py-2 px-2">#</th>
                  <th className="text-left py-2 px-2">Satellite</th>
                  <th className="text-left py-2 px-2">Target</th>
                  <th className="text-left py-2 px-2">Start</th>
                  <th className="text-left py-2 px-2">End</th>
                  <th className="text-right py-2 px-2">Δroll (°)</th>
                  <th className="text-right py-2 px-2">t_slew (s)</th>
                  <th className="text-right py-2 px-2">Slack (s)</th>
                  <th className="text-right py-2 px-2">Value</th>
                  <th className="text-right py-2 px-2">Density</th>
                </tr>
              </thead>
              <tbody className="text-gray-300">
                {selectedOrder.schedule.map((item, idx) => (
                  <tr key={idx} className="border-b border-gray-600 hover:bg-gray-650">
                    <td className="py-2 px-2">{idx + 1}</td>
                    <td className="py-2 px-2">{item.satellite_id}</td>
                    <td className="py-2 px-2">{item.target_id}</td>
                    <td className="py-2 px-2">{new Date(item.start_time).toLocaleString()}</td>
                    <td className="py-2 px-2">{new Date(item.end_time).toLocaleString()}</td>
                    <td className="text-right py-2 px-2">{item.droll_deg.toFixed(2)}</td>
                    <td className="text-right py-2 px-2">{item.t_slew_s.toFixed(3)}</td>
                    <td className="text-right py-2 px-2">{item.slack_s.toFixed(3)}</td>
                    <td className="text-right py-2 px-2">{item.value.toFixed(2)}</td>
                    <td className="text-right py-2 px-2">
                      {item.density === 'inf' ? '∞' : item.density.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
