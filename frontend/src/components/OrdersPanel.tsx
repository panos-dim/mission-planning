/**
 * OrdersPanel Component
 *
 * Pre-feasibility orders section. Allows operator to create named orders,
 * add/remove targets per order, and validates before feasibility run.
 * Supports: manual entry, file upload, sample targets, and map-click addition.
 */

import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  Package,
  Target,
  MapPin,
  AlertCircle,
  CheckCircle,
  Pencil,
  Check,
  X,
  Upload,
  FileText,
  Map,
} from 'lucide-react'
import type { TargetData } from '../types'
import {
  usePreFeasibilityOrdersStore,
  type PreFeasibilityOrder,
} from '../store/preFeasibilityOrdersStore'
import { usePreviewTargetsStore } from '../store/previewTargetsStore'
import { useTargetAddStore } from '../store/targetAddStore'

// =============================================================================
// Gulf Area Sample Targets — debugging / demo scenario
// =============================================================================

const GULF_SAMPLE_TARGETS: TargetData[] = [
  {
    name: 'Dubai',
    latitude: 25.2048,
    longitude: 55.2708,
    description: 'UAE - Major City',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Abu Dhabi',
    latitude: 24.4539,
    longitude: 54.3773,
    description: 'UAE - Capital (~130km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Doha',
    latitude: 25.2854,
    longitude: 51.531,
    description: 'Qatar - Capital (~380km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Manama',
    latitude: 26.2285,
    longitude: 50.586,
    description: 'Bahrain - Capital (~470km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Kuwait City',
    latitude: 29.3759,
    longitude: 47.9774,
    description: 'Kuwait - Capital (~870km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Muscat',
    latitude: 23.588,
    longitude: 58.3829,
    description: 'Oman - Capital (~350km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Riyadh',
    latitude: 24.7136,
    longitude: 46.6753,
    description: 'Saudi Arabia - Capital (~870km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Jeddah',
    latitude: 21.4858,
    longitude: 39.1925,
    description: 'Saudi Arabia - Red Sea (~1800km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Bandar Abbas',
    latitude: 27.1865,
    longitude: 56.2808,
    description: 'Iran - Strait of Hormuz (~220km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
  {
    name: 'Salalah',
    latitude: 17.0151,
    longitude: 54.0924,
    description: 'Oman - Southern coast (~1000km from Dubai)',
    priority: 5,
    color: '#3B82F6',
  },
]

// =============================================================================
// OrderTargetRow — compact target display within an order
// =============================================================================

interface OrderTargetRowProps {
  target: TargetData
  onRemove: () => void
  onUpdate: (updates: Partial<TargetData>) => void
  disabled?: boolean
}

const OrderTargetRow: React.FC<OrderTargetRowProps> = ({
  target,
  onRemove,
  onUpdate,
  disabled,
}) => {
  return (
    <div className="flex items-center gap-2 py-1.5 px-2 bg-gray-800/50 rounded text-xs group">
      <Target className="w-3 h-3 flex-shrink-0 text-blue-500" />
      <span className="font-medium text-white truncate flex-1 min-w-0">{target.name}</span>
      <span className="text-gray-500 flex-shrink-0">
        {target.latitude.toFixed(2)}°, {target.longitude.toFixed(2)}°
      </span>
      <select
        value={target.priority || 5}
        onChange={(e) => onUpdate({ priority: parseInt(e.target.value) })}
        disabled={disabled}
        className="w-10 px-0.5 py-0 bg-gray-700 border border-gray-600 rounded text-[10px] text-white focus:border-blue-500 focus:outline-none"
        title="Priority (1 best → 5 lowest)"
      >
        <option value="1">1</option>
        <option value="2">2</option>
        <option value="3">3</option>
        <option value="4">4</option>
        <option value="5">5</option>
      </select>
      {!disabled && (
        <button
          onClick={onRemove}
          className="p-0.5 text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded transition-colors opacity-0 group-hover:opacity-100"
          title="Remove target"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      )}
    </div>
  )
}

// =============================================================================
// InlineTargetAdd — compact target creation inside an order
// =============================================================================

interface InlineTargetAddProps {
  onAdd: (target: TargetData) => void
}

const InlineTargetAdd: React.FC<InlineTargetAddProps> = ({ onAdd }) => {
  const [name, setName] = useState('')
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [error, setError] = useState('')

  const handleAdd = () => {
    setError('')
    if (!name.trim()) {
      setError('Target name is required')
      return
    }
    const latNum = parseFloat(lat)
    const lonNum = parseFloat(lon)
    if (isNaN(latNum) || latNum < -90 || latNum > 90) {
      setError('Latitude must be -90 to 90')
      return
    }
    if (isNaN(lonNum) || lonNum < -180 || lonNum > 180) {
      setError('Longitude must be -180 to 180')
      return
    }

    onAdd({
      name: name.trim(),
      latitude: latNum,
      longitude: lonNum,
      priority: 5,
      color: '#3B82F6',
    })
    setName('')
    setLat('')
    setLon('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleAdd()
  }

  const isNameEmpty = !name.trim()

  return (
    <div className="space-y-1.5 pt-2 border-t border-gray-700/50">
      {error && (
        <div className="flex items-center gap-1 text-[10px] text-red-400">
          <AlertCircle className="w-3 h-3" />
          <span>{error}</span>
        </div>
      )}
      <div className="flex gap-1.5">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Target name *"
          className={`input-field flex-1 text-xs py-1 ${isNameEmpty && name !== '' ? 'border-red-500/50' : ''}`}
        />
        <input
          type="number"
          value={lat}
          onChange={(e) => setLat(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Lat"
          step="0.01"
          className="input-field w-16 text-xs py-1"
        />
        <input
          type="number"
          value={lon}
          onChange={(e) => setLon(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Lon"
          step="0.01"
          className="input-field w-16 text-xs py-1"
        />
        <button
          onClick={handleAdd}
          disabled={isNameEmpty}
          className="px-2 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-xs text-white flex-shrink-0"
          title={isNameEmpty ? 'Target name is required' : 'Add target'}
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}

// =============================================================================
// OrderCard — single order with its targets
// =============================================================================

interface OrderCardProps {
  order: PreFeasibilityOrder
  isMapActive: boolean
  onToggleMap: () => void
  disabled?: boolean
}

const OrderCard: React.FC<OrderCardProps> = ({ order, isMapActive, onToggleMap, disabled }) => {
  const [expanded, setExpanded] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(order.name)
  const [uploadStatus, setUploadStatus] = useState<{
    type: 'success' | 'error' | null
    message: string
  }>({ type: null, message: '' })
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { renameOrder, removeOrder, addTarget, addTargets, removeTarget, updateTarget } =
    usePreFeasibilityOrdersStore()

  const handleSaveName = () => {
    if (editName.trim()) {
      renameOrder(order.id, editName.trim())
    } else {
      setEditName(order.name)
    }
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setEditName(order.name)
    setIsEditing(false)
  }

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSaveName()
    if (e.key === 'Escape') handleCancelEdit()
  }

  // File upload handler
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    setUploadStatus({ type: null, message: '' })

    const formData = new FormData()
    formData.append('file', file)

    try {
      const response = await fetch('/api/v1/targets/upload', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()
      if (response.ok && data.targets) {
        const newTargets: TargetData[] = data.targets.map((t: Record<string, unknown>) => ({
          name: t.name as string,
          latitude: t.latitude as number,
          longitude: t.longitude as number,
          description: (t.description as string) || '',
          priority: (t.priority as number) || 5,
          color: '#3B82F6',
        }))
        addTargets(order.id, newTargets)
        setUploadStatus({
          type: 'success',
          message: `Added ${newTargets.length} target(s) from ${file.name}`,
        })
      } else {
        setUploadStatus({
          type: 'error',
          message: data.error || 'Failed to upload file',
        })
      }
    } catch {
      setUploadStatus({ type: 'error', message: 'Error uploading file' })
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  // Load Gulf sample targets
  const handleLoadSamples = () => {
    addTargets(order.id, GULF_SAMPLE_TARGETS)
    setUploadStatus({
      type: 'success',
      message: `Added ${GULF_SAMPLE_TARGETS.length} Gulf area targets`,
    })
  }

  const nameIsEmpty = !order.name.trim()

  return (
    <div
      className={`glass-panel rounded-lg overflow-hidden ${nameIsEmpty ? 'ring-1 ring-red-500/50' : ''} ${isMapActive ? 'ring-1 ring-green-500/50' : ''}`}
    >
      {/* Order Header */}
      <div className="flex items-center gap-2 p-2.5 bg-gray-800/30">
        <button
          onClick={() => setExpanded(!expanded)}
          className="p-0.5 text-gray-400 hover:text-white transition-colors"
        >
          {expanded ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </button>

        <Package className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />

        {isEditing && !disabled ? (
          <div className="flex items-center gap-1 flex-1 min-w-0">
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={handleNameKeyDown}
              autoFocus
              className="input-field text-xs py-0.5 flex-1 min-w-0"
            />
            <button onClick={handleSaveName} className="p-0.5 text-green-400 hover:text-green-300">
              <Check className="w-3 h-3" />
            </button>
            <button onClick={handleCancelEdit} className="p-0.5 text-gray-400 hover:text-white">
              <X className="w-3 h-3" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <span
              className={`text-xs font-semibold truncate ${nameIsEmpty ? 'text-red-400 italic' : 'text-white'}`}
            >
              {nameIsEmpty ? 'Unnamed order' : order.name}
            </span>
            {!disabled && (
              <button
                onClick={() => {
                  setEditName(order.name)
                  setIsEditing(true)
                }}
                className="p-0.5 text-gray-500 hover:text-gray-300 transition-colors"
                title="Rename order"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
          </div>
        )}

        <span className="text-[10px] text-gray-500 flex-shrink-0">
          {order.targets.length} target{order.targets.length !== 1 ? 's' : ''}
        </span>

        {!disabled && (
          <button
            onClick={() => removeOrder(order.id)}
            className="p-0.5 text-red-400 hover:text-red-300 hover:bg-red-900/30 rounded transition-colors"
            title="Remove order"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Order Body */}
      {expanded && (
        <div className="px-2.5 pb-2.5 space-y-1">
          {nameIsEmpty && (
            <div className="flex items-center gap-1 text-[10px] text-red-400 py-1">
              <AlertCircle className="w-3 h-3" />
              <span>Order name is required to run feasibility</span>
            </div>
          )}

          {/* Quick actions toolbar: samples, file upload, map-click */}
          {!disabled && (
            <div className="flex items-center gap-1.5 py-1.5">
              <button
                onClick={handleLoadSamples}
                className="px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded text-[10px] font-medium transition-colors flex items-center gap-1 border border-gray-700"
                title="Load Gulf area sample targets for debugging"
              >
                <FileText className="w-3 h-3" />
                <span>Gulf Samples</span>
              </button>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-2 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded text-[10px] font-medium transition-colors flex items-center gap-1 border border-gray-700"
                title="Upload targets from CSV, KML, or JSON file"
              >
                <Upload className="w-3 h-3" />
                <span>Upload File</span>
              </button>
              <button
                onClick={onToggleMap}
                className={`px-2 py-1 rounded text-[10px] font-medium transition-colors flex items-center gap-1 border ${
                  isMapActive
                    ? 'bg-green-600 hover:bg-green-700 text-white border-green-500'
                    : 'bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border-gray-700'
                }`}
                title={
                  isMapActive ? 'Exit map-click mode' : 'Click map to add targets to this order'
                }
              >
                <Map className="w-3 h-3" />
                <span>{isMapActive ? 'Exit Map' : 'Add via Map'}</span>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".kml,.kmz,.json,.csv,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
            </div>
          )}

          {/* Map-click active indicator */}
          {isMapActive && (
            <div className="glass-panel rounded p-1.5 text-[10px] text-green-300 flex items-center gap-1.5">
              <MapPin className="w-3 h-3 flex-shrink-0" />
              <span>
                Click on the map to add targets. Press{' '}
                <kbd className="px-1 py-0.5 bg-white/10 rounded">Esc</kbd> to exit.
              </span>
            </div>
          )}

          {/* Upload status feedback */}
          {uploadStatus.type && (
            <div
              className={`flex items-center gap-1 p-1.5 rounded text-[10px] ${
                uploadStatus.type === 'success'
                  ? 'bg-green-900/30 text-green-400'
                  : 'bg-red-900/30 text-red-400'
              }`}
            >
              {uploadStatus.type === 'success' ? (
                <CheckCircle className="w-3 h-3 flex-shrink-0" />
              ) : (
                <AlertCircle className="w-3 h-3 flex-shrink-0" />
              )}
              <span>{uploadStatus.message}</span>
            </div>
          )}

          {order.targets.length === 0 ? (
            <div className="text-center py-3 text-gray-500">
              <MapPin className="w-5 h-5 mx-auto mb-1 opacity-30" />
              <p className="text-[10px]">No targets yet</p>
            </div>
          ) : (
            <div className="space-y-1">
              {order.targets.map((target, idx) => (
                <OrderTargetRow
                  key={`${order.id}-${idx}`}
                  target={target}
                  onRemove={() => removeTarget(order.id, idx)}
                  onUpdate={(updates) => updateTarget(order.id, idx, updates)}
                  disabled={disabled}
                />
              ))}
            </div>
          )}

          {!disabled && <InlineTargetAdd onAdd={(target) => addTarget(order.id, target)} />}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// OrdersPanel — top-level pre-feasibility orders section
// =============================================================================

interface OrdersPanelProps {
  disabled?: boolean
}

const OrdersPanel: React.FC<OrdersPanelProps> = ({ disabled = false }) => {
  const { orders, createOrder, activeOrderId, setActiveOrder } = usePreFeasibilityOrdersStore()
  const { setTargets: setPreviewTargets } = usePreviewTargetsStore()
  const { isAddMode, toggleAddMode, disableAddMode } = useTargetAddStore()

  // Sync all order targets to preview store for map display
  const allTargets = useMemo(() => orders.flatMap((o) => o.targets), [orders])
  useEffect(() => {
    setPreviewTargets(allTargets)
  }, [allTargets, setPreviewTargets])

  // Toggle map mode for a specific order
  const handleToggleMapForOrder = (orderId: string) => {
    if (activeOrderId === orderId && isAddMode) {
      // Turn off map mode for this order
      disableAddMode()
      setActiveOrder(null)
    } else {
      // Activate map mode for this order
      setActiveOrder(orderId)
      if (!isAddMode) {
        toggleAddMode()
      }
    }
  }

  // Clean up: if active order is removed, disable map mode
  useEffect(() => {
    if (activeOrderId && !orders.find((o) => o.id === activeOrderId)) {
      disableAddMode()
      setActiveOrder(null)
    }
  }, [orders, activeOrderId, disableAddMode, setActiveOrder])

  return (
    <div className={`space-y-3 ${disabled ? 'opacity-60 pointer-events-none' : ''}`}>
      {/* Orders List */}
      {orders.length === 0 ? (
        <div className="text-center py-6 glass-panel rounded-lg">
          <Package className="w-8 h-8 mx-auto mb-2 text-gray-500 opacity-30" />
          <p className="text-xs font-medium text-gray-400">No orders created yet</p>
          <p className="text-[10px] text-gray-500 mt-1">
            Create an order and add targets to run feasibility
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {orders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              isMapActive={isAddMode && activeOrderId === order.id}
              onToggleMap={() => handleToggleMapForOrder(order.id)}
              disabled={disabled}
            />
          ))}
        </div>
      )}

      {/* Create Order Button */}
      {!disabled && (
        <button
          onClick={createOrder}
          className="w-full px-3 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 hover:text-blue-200 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 border border-blue-600/30 hover:border-blue-500/50"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Create Order</span>
        </button>
      )}
    </div>
  )
}

export default OrdersPanel
