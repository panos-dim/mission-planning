/**
 * PR-UI-036 — Inline Target Editor (Right Sidebar)
 *
 * Replaces the old "Confirm Target" modal. When the user clicks the map in
 * add-mode the target is saved immediately (auto-name, default priority).
 * This panel opens automatically so the operator can refine Name and Priority
 * on the already-saved target.
 */

import React, { useState, useEffect } from 'react'
import { MapPin, Check, X } from 'lucide-react'
import { useTargetAddStore } from '../../store/targetAddStore'
import { usePreFeasibilityOrdersStore } from '../../store/preFeasibilityOrdersStore'

const TargetConfirmPanel: React.FC = () => {
  const { lastAddedTarget, clearLastAddedTarget } = useTargetAddStore()
  const order = usePreFeasibilityOrdersStore((s) => s.order)
  const updateTarget = usePreFeasibilityOrdersStore((s) => s.updateTarget)

  const [name, setName] = useState('')
  const [priority, setPriority] = useState(5)

  // Resolve the saved target from the order store
  const savedTarget = (() => {
    if (!lastAddedTarget) return null
    if (!order || order.id !== lastAddedTarget.orderId) return null
    return order.targets[lastAddedTarget.targetIndex] ?? null
  })()

  // Sync local state when lastAddedTarget changes
  useEffect(() => {
    if (savedTarget) {
      setName(savedTarget.name || '')
      setPriority(savedTarget.priority ?? 5)
    }
  }, [lastAddedTarget]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!lastAddedTarget || !savedTarget) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-gray-500">Click on the map to place a target.</p>
      </div>
    )
  }

  const handleDone = () => {
    if (!name.trim()) return
    updateTarget(lastAddedTarget.orderId, lastAddedTarget.targetIndex, {
      name: name.trim(),
      priority,
    })
    clearLastAddedTarget()
  }

  const handleCancel = () => {
    clearLastAddedTarget()
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Location display */}
        <div className="glass-panel rounded-lg p-3">
          <div className="flex items-center space-x-2 mb-2">
            <MapPin className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-medium text-gray-300">Added Location</span>
          </div>
          <div className="text-xs text-gray-400 space-y-1">
            <div>
              Lat:{' '}
              <span className="text-white tabular-nums">{savedTarget.latitude.toFixed(6)}°</span>
            </div>
            <div>
              Lon:{' '}
              <span className="text-white tabular-nums">{savedTarget.longitude.toFixed(6)}°</span>
            </div>
          </div>
        </div>

        {/* Name field */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Observation Site Alpha"
            className="input-field w-full text-sm"
            autoFocus
          />
        </div>

        {/* Priority */}
        <div>
          <label className="block text-xs font-medium text-gray-400 mb-1">
            Priority <span className="text-gray-500 text-[10px]">(1 = highest)</span>
          </label>
          <div className="grid grid-cols-5 gap-1">
            {[1, 2, 3, 4, 5].map((p) => (
              <button
                key={p}
                onClick={() => setPriority(p)}
                className={`py-1 rounded text-xs font-medium transition-colors ${
                  priority === p
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Action bar pinned to bottom */}
      <div className="border-t border-gray-700 p-3 flex items-center gap-2">
        <button
          onClick={handleDone}
          disabled={!name.trim()}
          className="flex-1 btn-primary text-xs py-2 flex items-center justify-center gap-1 disabled:opacity-50"
        >
          <Check className="w-3 h-3" />
          Done
        </button>
        <button
          onClick={handleCancel}
          className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
          title="Dismiss"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

export default TargetConfirmPanel
