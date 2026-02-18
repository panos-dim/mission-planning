/**
 * TargetConfirmPanel — RightSidebar panel for confirming a map-clicked target.
 *
 * Rendered inside the RightSidebar panel system (same bg-gray-900 chrome).
 * The panel body contains the form; header/footer are handled by RightSidebar.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { Save, RotateCcw, X, Palette, AlertCircle } from 'lucide-react'
import { useTargetAddStore } from '../../store/targetAddStore'
import { usePreFeasibilityOrdersStore } from '../../store/preFeasibilityOrdersStore'
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

const DEFAULT_COLOR = '#EF4444'

const TargetConfirmPanel: React.FC = () => {
  const { pendingTarget, isAddMode, clearPendingTarget, setPendingPreview } = useTargetAddStore()
  const { activeOrderId, orders, addTarget } = usePreFeasibilityOrdersStore()

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState(DEFAULT_COLOR)
  const [priority, setPriority] = useState(5)

  // Reset form when pending target changes (new click on map)
  useEffect(() => {
    if (pendingTarget) {
      setName(pendingTarget.name || '')
      setDescription(pendingTarget.description || '')
      setColor(DEFAULT_COLOR)
      setPriority(5)
    }
  }, [pendingTarget])

  // Sync name + color to store so GlobeViewport can live-preview the marker
  const syncPreview = useCallback(
    (newName: string, newColor: string) => {
      setPendingPreview(newName, newColor)
    },
    [setPendingPreview],
  )

  // Push preview on every name or color change
  useEffect(() => {
    syncPreview(name, color)
  }, [name, color, syncPreview])

  if (!pendingTarget) {
    return (
      <div className="p-4 text-center">
        <p className="text-xs text-gray-500">Click on the map to place a target.</p>
      </div>
    )
  }

  const formatted = formatCoordinates(pendingTarget.latitude, pendingTarget.longitude)
  const isNameEmpty = !name.trim()

  // Resolve which order gets the target
  const targetOrderId = activeOrderId || (orders.length > 0 ? orders[0].id : null)
  const targetOrderName = targetOrderId
    ? orders.find((o) => o.id === targetOrderId)?.name || 'Unknown'
    : null

  const handleSave = () => {
    if (isNameEmpty || !targetOrderId) return

    const target: TargetData = {
      name: name.trim(),
      latitude: formatted.lat,
      longitude: formatted.lon,
      description: description.trim(),
      priority,
      color,
    }

    addTarget(targetOrderId, target)
    clearPendingTarget()
  }

  // Discard: reset form fields but keep the pending marker and sidebar open
  const handleDiscard = () => {
    setName('')
    setDescription('')
    setColor(DEFAULT_COLOR)
    setPriority(5)
    setPendingPreview('', DEFAULT_COLOR)
  }

  // Cancel: close everything (remove marker, close panel)
  const handleCancel = () => {
    clearPendingTarget()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !isNameEmpty) handleSave()
  }

  return (
    <div className="h-full flex flex-col">
      {/* Form content — scrollable */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Coordinate Display */}
        <div className="bg-gray-800/50 rounded-lg p-3 space-y-2">
          <h3 className="text-[10px] font-semibold text-gray-400 uppercase tracking-wide">
            Clicked Location
          </h3>
          <div className="text-sm text-white font-mono">{formatted.decimal}</div>
          <div className="text-xs text-gray-400 font-mono">{formatted.dms}</div>
          <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
            <div>
              <span className="text-gray-500">Latitude</span>
              <div className="text-white font-mono">{formatted.lat.toFixed(6)}°</div>
            </div>
            <div>
              <span className="text-gray-500">Longitude</span>
              <div className="text-white font-mono">{formatted.lon.toFixed(6)}°</div>
            </div>
          </div>
        </div>

        {/* Destination order */}
        {targetOrderName && (
          <div className="bg-blue-900/20 border border-blue-800/30 rounded-lg p-2.5 text-xs text-blue-300 flex items-center gap-2">
            <span className="text-gray-500">Adding to:</span>
            <span className="font-medium">{targetOrderName}</span>
          </div>
        )}

        {!targetOrderId && (
          <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-2.5 text-xs text-red-400 flex items-center gap-2">
            <AlertCircle className="w-3 h-3 flex-shrink-0" />
            <span>Create an order first to save targets.</span>
          </div>
        )}

        {/* Target Name */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Target Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g., Ground Station Alpha"
            className={`input-field w-full ${isNameEmpty && name !== '' ? 'border-red-500/50' : ''}`}
            autoFocus
          />
          {isNameEmpty && name !== '' && (
            <div className="flex items-center gap-1 mt-1 text-[10px] text-red-400">
              <AlertCircle className="w-3 h-3" />
              <span>Target name is required</span>
            </div>
          )}
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Description <span className="text-gray-500">(optional)</span>
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Additional notes..."
            className="input-field w-full resize-none"
            rows={2}
          />
        </div>

        {/* Color & Priority */}
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
          <div className="bg-gray-800/50 rounded-lg p-3 text-xs text-gray-400">
            After saving, click the map again to add more targets. Press{' '}
            <kbd className="px-1 py-0.5 bg-gray-700 rounded text-gray-300">Esc</kbd> to exit.
          </div>
        )}
      </div>

      {/* Footer Actions */}
      <div className="p-3 border-t border-gray-700 space-y-2">
        <button
          onClick={handleSave}
          disabled={isNameEmpty || !targetOrderId}
          className="btn-primary w-full disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Save className="w-4 h-4" />
          <span>{isNameEmpty ? 'Enter a name to save' : 'Save Target'}</span>
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button onClick={handleDiscard} className="btn-secondary text-xs">
            <RotateCcw className="w-3 h-3" />
            <span>Reset</span>
          </button>
          <button onClick={handleCancel} className="btn-secondary text-xs">
            <X className="w-3 h-3" />
            <span>Cancel</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default TargetConfirmPanel
