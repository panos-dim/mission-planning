/**
 * Side sheet for editing target details after map click
 */

import React, { useState, useEffect } from 'react'
import { X, MapPin, Save, Trash2, Palette } from 'lucide-react'
import { useTargetAddStore } from '../../store/targetAddStore'
import { TargetData } from '../../types'
import { formatCoordinates } from '../../utils/coordinateUtils'

// Color presets for target markers
const TARGET_COLORS = [
  { value: '#EF4444', label: 'Red' },
  { value: '#F97316', label: 'Orange' },
  { value: '#EAB308', label: 'Yellow' },
  { value: '#84CC16', label: 'Lime' },
  { value: '#22C55E', label: 'Green' },
  { value: '#06B6D4', label: 'Cyan' },
  { value: '#3B82F6', label: 'Blue' },
  { value: '#8B5CF6', label: 'Purple' },
]

interface TargetDetailsSheetProps {
  onSave: (target: TargetData) => void
  onCancel?: () => void
}

export const TargetDetailsSheet: React.FC<TargetDetailsSheetProps> = ({ onSave, onCancel }) => {
  const { isDetailsSheetOpen, pendingTarget, closeDetailsSheet, clearPendingTarget, isAddMode } =
    useTargetAddStore()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState('#EF4444')
  const [priority, setPriority] = useState(5)

  // Update local state when pending target changes
  useEffect(() => {
    if (pendingTarget) {
      setName(pendingTarget.name || '')
      setDescription(pendingTarget.description || '')
      setColor('#EF4444') // Default red for new targets
      setPriority(5)
    }
  }, [pendingTarget])

  if (!isDetailsSheetOpen || !pendingTarget) {
    return null
  }

  const formatted = formatCoordinates(pendingTarget.latitude, pendingTarget.longitude)

  const handleSave = () => {
    const target: TargetData = {
      name: name.trim() || `Target ${Date.now()}`,
      latitude: formatted.lat,
      longitude: formatted.lon,
      description: description.trim(),
      priority,
      color,
    }

    onSave(target)

    // Clear pending target and close sheet
    clearPendingTarget()

    // Stay in add mode if enabled for multi-add
    if (!isAddMode) {
      closeDetailsSheet()
    }
  }

  const handleCancel = () => {
    clearPendingTarget()
    closeDetailsSheet()
    onCancel?.()
  }

  const handleRemovePin = () => {
    clearPendingTarget()
    closeDetailsSheet()
  }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={handleCancel} />

      {/* Side sheet */}
      <div className="fixed right-0 top-0 h-full w-96 bg-slate-900 shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center space-x-2">
            <MapPin className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-semibold text-white">Target Details</h2>
          </div>
          <button
            onClick={handleCancel}
            className="p-1 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Coordinate Display */}
          <div className="glass-panel rounded-lg p-3 space-y-2">
            <h3 className="text-xs font-medium text-gray-400 uppercase">Coordinates</h3>

            <div className="space-y-1">
              <div className="text-sm text-white font-mono">{formatted.decimal}</div>
              <div className="text-xs text-gray-400 font-mono">{formatted.dms}</div>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
              <div>
                <span className="text-gray-500">Latitude:</span>
                <div className="text-white font-mono">{formatted.lat.toFixed(6)}°</div>
              </div>
              <div>
                <span className="text-gray-500">Longitude:</span>
                <div className="text-white font-mono">{formatted.lon.toFixed(6)}°</div>
              </div>
            </div>
          </div>

          {/* Target Name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Target Name <span className="text-gray-500">(optional)</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Ground Station Alpha"
              className="input-field w-full"
              autoFocus
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Description <span className="text-gray-500">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Additional notes or details..."
              className="input-field w-full resize-none"
              rows={3}
            />
          </div>

          {/* Color & Priority Row */}
          <div className="grid grid-cols-2 gap-4">
            {/* Color Picker */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                <Palette className="w-3 h-3 inline mr-1" />
                Marker Color
              </label>
              <div className="flex flex-wrap gap-2">
                {TARGET_COLORS.map((c) => (
                  <button
                    key={c.value}
                    onClick={() => setColor(c.value)}
                    className={`w-7 h-7 rounded-full border-2 transition-all ${
                      color === c.value
                        ? 'border-white scale-110'
                        : 'border-transparent hover:border-gray-500'
                    }`}
                    style={{ backgroundColor: c.value }}
                    title={c.label}
                  />
                ))}
              </div>
            </div>

            {/* Priority */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Priority
                <span className="text-[10px] text-gray-500 ml-1">1 best → 5 lowest</span>
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(parseInt(e.target.value))}
                className="input-field w-full"
              >
                <option value="1">1 (Best)</option>
                <option value="2">2</option>
                <option value="3">3 (Medium)</option>
                <option value="4">4</option>
                <option value="5">5 (Lowest)</option>
              </select>
            </div>
          </div>

          {/* Help Text */}
          {isAddMode && (
            <div className="glass-panel rounded-lg p-3 text-xs text-gray-400">
              <p>
                💡 After saving, you can add more targets by clicking on the map again. Press{' '}
                <kbd className="px-1 py-0.5 bg-white/10 rounded">Esc</kbd> to exit Add Mode.
              </p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-white/10 space-y-2">
          <button onClick={handleSave} className="btn-primary w-full">
            <Save className="w-4 h-4" />
            <span>Save Target</span>
          </button>

          <div className="grid grid-cols-2 gap-2">
            <button onClick={handleRemovePin} className="btn-secondary text-xs">
              <Trash2 className="w-3 h-3" />
              <span>Clear Pin</span>
            </button>
            <button onClick={handleCancel} className="btn-secondary text-xs">
              <X className="w-3 h-3" />
              <span>Cancel</span>
            </button>
          </div>
        </div>
      </div>
    </>
  )
}
