/**
 * SatelliteColorLegend — Minimal legend overlay for the Cesium viewer.
 *
 * Shows a small collapsible panel listing each satellite currently in
 * the scene together with its assigned color swatch.
 *
 * PR-UI-026: Satellite Color Registry & Groundtrack Object Parity
 */

import React, { useState, useMemo } from 'react'
import { ChevronDown, ChevronRight, Satellite } from 'lucide-react'
import { useMission } from '../../context/MissionContext'
import {
  getRegisteredSatelliteColors,
  satIdToDisplayName,
} from '../../utils/satelliteColors'

const SatelliteColorLegend: React.FC = () => {
  const { state } = useMission()
  const [isOpen, setIsOpen] = useState(true)

  // Re-derive entries whenever CZML data changes (triggers re-render)
  const entries = useMemo(() => {
    // Access state.czmlData to set up the dependency — the registry is populated
    // when CZML loads in GlobeViewport, so this memo recomputes after that.
    if (!state.czmlData || state.czmlData.length === 0) return []
    return getRegisteredSatelliteColors()
  }, [state.czmlData])

  // Don't render if no satellites are registered
  if (entries.length === 0) return null

  return (
    <div className="absolute bottom-24 right-3 z-40 select-none">
      <div className="bg-gray-900/90 backdrop-blur-sm border border-gray-700/60 rounded-lg shadow-xl overflow-hidden min-w-[140px]">
        {/* Header */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="w-full flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800/60 transition-colors"
        >
          <Satellite className="w-3.5 h-3.5 text-gray-400" />
          <span className="flex-1 text-left">Satellites</span>
          {isOpen ? (
            <ChevronDown className="w-3 h-3 text-gray-500" />
          ) : (
            <ChevronRight className="w-3 h-3 text-gray-500" />
          )}
        </button>

        {/* Entries */}
        {isOpen && (
          <div className="px-2.5 pb-2 space-y-1">
            {entries.map(({ satId, cssColor }) => (
              <div key={satId} className="flex items-center gap-2 text-xs text-gray-300">
                <span
                  className="w-3 h-3 rounded-sm flex-shrink-0 border border-white/10"
                  style={{ backgroundColor: cssColor }}
                />
                <span className="truncate">{satIdToDisplayName(satId)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default SatelliteColorLegend
