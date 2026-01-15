/**
 * Toolbar button to toggle Target Add Mode
 */

import React from 'react'
import { MapPin, X } from 'lucide-react'
import { useTargetAddStore } from '../../store/targetAddStore'

export const AddTargetButton: React.FC = () => {
  const { isAddMode, toggleAddMode } = useTargetAddStore()

  return (
    <div className="relative">
      <button
        onClick={toggleAddMode}
        className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${
          isAddMode
            ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/50'
            : 'bg-white/10 text-white hover:bg-white/20'
        }`}
        title={isAddMode ? 'Exit Target Add Mode (Esc)' : 'Add Target (Map)'}
      >
        {isAddMode ? (
          <>
            <X className="w-4 h-4" />
            <span className="text-sm font-medium">Exit Add Mode</span>
          </>
        ) : (
          <>
            <MapPin className="w-4 h-4" />
            <span className="text-sm font-medium">Add Target (Map)</span>
          </>
        )}
      </button>

      {/* Helper tooltip when in add mode */}
      {isAddMode && (
        <div className="absolute top-full mt-2 left-0 right-0 bg-blue-900/90 backdrop-blur-sm text-white text-xs px-3 py-2 rounded-lg shadow-lg whitespace-nowrap z-50">
          <div className="flex items-center space-x-2">
            <MapPin className="w-3 h-3" />
            <span>Click the map to place a target. Press Esc to cancel.</span>
          </div>
        </div>
      )}
    </div>
  )
}
