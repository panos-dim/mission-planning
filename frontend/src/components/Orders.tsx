import { useState } from 'react'
import { Order, ScheduledOpportunity } from '../types'

interface OrdersProps {
  initialOrders?: Order[]
}

export default function Orders({ initialOrders = [] }: OrdersProps): JSX.Element {
  const [orders, setOrders] = useState<Order[]>(initialOrders)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'start_time' | 'priority' | 'created_at'>('start_time')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  
  // Filter and sort orders
  const filteredOrders = orders
    .filter((order) => {
      if (filterStatus !== 'all' && order.status !== filterStatus) return false
      if (filterType !== 'all' && order.order_type !== filterType) return false
      return true
    })
    .sort((a, b) => {
      let comparison = 0
      
      if (sortBy === 'start_time') {
        comparison = new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
      } else if (sortBy === 'priority') {
        comparison = a.priority - b.priority
      } else if (sortBy === 'created_at') {
        comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      }
      
      return sortDirection === 'asc' ? comparison : -comparison
    })
  
  const statusCounts = {
    all: orders.length,
    pending: orders.filter((o) => o.status === 'pending').length,
    scheduled: orders.filter((o) => o.status === 'scheduled').length,
    executing: orders.filter((o) => o.status === 'executing').length,
    completed: orders.filter((o) => o.status === 'completed').length,
    failed: orders.filter((o) => o.status === 'failed').length
  }
  
  const updateOrderStatus = (orderId: string, newStatus: Order['status']) => {
    setOrders((prev) =>
      prev.map((order) =>
        order.id === orderId
          ? { ...order, status: newStatus, updated_at: new Date().toISOString() }
          : order
      )
    )
  }
  
  const deleteOrder = (orderId: string) => {
    setOrders((prev) => prev.filter((order) => order.id !== orderId))
    if (selectedOrder?.id === orderId) {
      setSelectedOrder(null)
    }
  }
  
  const exportOrdersToCsv = () => {
    const csv = [
      ['ID', 'Opportunity ID', 'Satellite', 'Target', 'Type', 'Start Time', 'End Time', 'Priority', 'Status', 'Created At'].join(','),
      ...filteredOrders.map((order) => [
        order.id,
        order.opportunity_id,
        order.satellite_id,
        order.target_id,
        order.order_type,
        order.start_time,
        order.end_time,
        order.priority,
        order.status,
        order.created_at
      ].join(','))
    ].join('\n')
    
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `orders_${new Date().toISOString()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }
  
  const getStatusColor = (status: Order['status']) => {
    switch (status) {
      case 'pending': return 'text-yellow-400'
      case 'scheduled': return 'text-blue-400'
      case 'executing': return 'text-green-400'
      case 'completed': return 'text-gray-400'
      case 'failed': return 'text-red-400'
      default: return 'text-gray-400'
    }
  }
  
  const getStatusBadge = (status: Order['status']) => {
    const colors = {
      pending: 'bg-yellow-900 text-yellow-200',
      scheduled: 'bg-blue-900 text-blue-200',
      executing: 'bg-green-900 text-green-200',
      completed: 'bg-gray-700 text-gray-300',
      failed: 'bg-red-900 text-red-200'
    }
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status]}`}>
        {status.toUpperCase()}
      </span>
    )
  }

  return (
    <div className="h-full flex flex-col bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-white mb-1">Orders</h2>
            <p className="text-xs text-gray-400">
              Manage scheduled mission execution orders ({orders.length} total)
            </p>
          </div>
          <button
            onClick={exportOrdersToCsv}
            disabled={filteredOrders.length === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded font-medium"
          >
            Export CSV
          </button>
        </div>
      </div>
      
      {/* Filters and Status Summary */}
      <div className="bg-gray-800 border-b border-gray-700 p-4 space-y-4">
        {/* Status Summary */}
        <div className="flex gap-2 flex-wrap">
          {Object.entries(statusCounts).map(([status, count]) => (
            <button
              key={status}
              onClick={() => setFilterStatus(status)}
              className={`px-3 py-2 rounded text-sm font-medium transition-colors ${
                filterStatus === status
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {status === 'all' ? 'All' : status.charAt(0).toUpperCase() + status.slice(1)} ({count})
            </button>
          ))}
        </div>
        
        {/* Filters */}
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-400 mb-2">Filter by Type</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            >
              <option value="all">All Types</option>
              <option value="imaging">Imaging</option>
              <option value="communication">Communication</option>
              <option value="tracking">Tracking</option>
            </select>
          </div>
          
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-400 mb-2">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            >
              <option value="start_time">Start Time</option>
              <option value="priority">Priority</option>
              <option value="created_at">Created At</option>
            </select>
          </div>
          
          <div className="flex-1">
            <label className="block text-xs font-medium text-gray-400 mb-2">Direction</label>
            <select
              value={sortDirection}
              onChange={(e) => setSortDirection(e.target.value as any)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
        </div>
      </div>
      
      {/* Orders List */}
      <div className="flex-1 overflow-auto p-4">
        {filteredOrders.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg mb-2">No orders found</p>
            <p className="text-sm">
              {orders.length === 0
                ? 'Create orders from Mission Planning schedules'
                : 'Try adjusting your filters'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredOrders.map((order) => (
              <div
                key={order.id}
                className={`bg-gray-800 rounded-lg p-4 cursor-pointer transition-colors hover:bg-gray-750 ${
                  selectedOrder?.id === order.id ? 'ring-2 ring-blue-500' : ''
                }`}
                onClick={() => setSelectedOrder(order)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <span className="text-sm font-semibold text-white">{order.satellite_id}</span>
                      <span className="text-sm text-gray-400">→</span>
                      <span className="text-sm font-semibold text-white">{order.target_id}</span>
                      {getStatusBadge(order.status)}
                    </div>
                    <div className="text-xs text-gray-400">
                      Order ID: {order.id} • Opportunity: {order.opportunity_id}
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    {order.status === 'pending' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          updateOrderStatus(order.id, 'scheduled')
                        }}
                        className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm"
                      >
                        Schedule
                      </button>
                    )}
                    {order.status === 'scheduled' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          updateOrderStatus(order.id, 'executing')
                        }}
                        className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm"
                      >
                        Execute
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (confirm('Delete this order?')) {
                          deleteOrder(order.id)
                        }
                      }}
                      className="px-3 py-1 bg-red-600 hover:bg-red-700 rounded text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-gray-400">Type</div>
                    <div className="capitalize">{order.order_type}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Priority</div>
                    <div>{order.priority}</div>
                  </div>
                  <div>
                    <div className="text-gray-400">Start Time</div>
                    <div>{new Date(order.start_time).toLocaleString()}</div>
                  </div>
                </div>
                
                {order.metadata && Object.keys(order.metadata).length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-700">
                    <div className="text-xs text-gray-400">Metadata:</div>
                    <pre className="text-xs text-gray-300 mt-1">
                      {JSON.stringify(order.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      
      {/* Order Details Panel */}
      {selectedOrder && (
        <div className="bg-gray-800 border-t border-gray-700 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-white">Order Details</h3>
            <button
              onClick={() => setSelectedOrder(null)}
              className="text-gray-400 hover:text-white"
            >
              ✕ Close
            </button>
          </div>
          
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-gray-400">Order ID</div>
              <div className="font-mono">{selectedOrder.id}</div>
            </div>
            <div>
              <div className="text-gray-400">Opportunity ID</div>
              <div className="font-mono">{selectedOrder.opportunity_id}</div>
            </div>
            <div>
              <div className="text-gray-400">Satellite</div>
              <div>{selectedOrder.satellite_id}</div>
            </div>
            <div>
              <div className="text-gray-400">Target</div>
              <div>{selectedOrder.target_id}</div>
            </div>
            <div>
              <div className="text-gray-400">Type</div>
              <div className="capitalize">{selectedOrder.order_type}</div>
            </div>
            <div>
              <div className="text-gray-400">Status</div>
              <div className={getStatusColor(selectedOrder.status)}>
                {selectedOrder.status.toUpperCase()}
              </div>
            </div>
            <div>
              <div className="text-gray-400">Priority</div>
              <div>{selectedOrder.priority}</div>
            </div>
            <div>
              <div className="text-gray-400">Created At</div>
              <div>{new Date(selectedOrder.created_at).toLocaleString()}</div>
            </div>
            <div>
              <div className="text-gray-400">Start Time</div>
              <div>{new Date(selectedOrder.start_time).toLocaleString()}</div>
            </div>
            <div>
              <div className="text-gray-400">End Time</div>
              <div>{new Date(selectedOrder.end_time).toLocaleString()}</div>
            </div>
          </div>
          
          <div className="mt-4 flex gap-2">
            <select
              value={selectedOrder.status}
              onChange={(e) => updateOrderStatus(selectedOrder.id, e.target.value as Order['status'])}
              className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2"
            >
              <option value="pending">Pending</option>
              <option value="scheduled">Scheduled</option>
              <option value="executing">Executing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
            <button
              onClick={() => {
                if (confirm('Delete this order?')) {
                  deleteOrder(selectedOrder.id)
                }
              }}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded"
            >
              Delete Order
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// Helper function to create orders from scheduled opportunities (used by MissionPlanning component)
export function createOrdersFromSchedule(
  algorithmName: string,
  scheduledOpportunities: ScheduledOpportunity[],
  missionType: 'imaging' | 'communication' | 'tracking' = 'imaging'
): Order[] {
  return scheduledOpportunities.map((sched, idx) => ({
    id: `order_${Date.now()}_${idx}`,
    opportunity_id: sched.opportunity_id,
    satellite_id: sched.satellite_id,
    target_id: sched.target_id,
    start_time: sched.start_time,
    end_time: sched.end_time,
    order_type: missionType,
    priority: Math.round(sched.value),
    status: 'pending' as const,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    metadata: {
      algorithm: algorithmName,
      delta_roll: sched.delta_roll,
      maneuver_time: sched.maneuver_time,
      slack_time: sched.slack_time,
      density: sched.density
    }
  }))
}
