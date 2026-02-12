/**
 * Lock Mode Button — PR-UI-003
 *
 * Map overlay toggle that activates Lock Mode.
 * When active, clicking lockable map entities (SAR swath acquisitions)
 * toggles their lock state (Unlocked ↔ Hard Lock).
 */

import React, { useCallback } from 'react'
import { Lock, X } from 'lucide-react'
import { useLockModeStore } from '../../store/lockModeStore'
import { useTargetAddStore } from '../../store/targetAddStore'

export const LockModeButton: React.FC = () => {
  const isLockMode = useLockModeStore((s) => s.isLockMode)
  const toggleLockMode = useLockModeStore((s) => s.toggleLockMode)
  const isAddMode = useTargetAddStore((s) => s.isAddMode)
  const disableAddMode = useTargetAddStore((s) => s.disableAddMode)

  // Mutual exclusion: exiting add mode when entering lock mode
  const handleToggle = useCallback(() => {
    if (!isLockMode && isAddMode) {
      disableAddMode()
    }
    toggleLockMode()
  }, [isLockMode, isAddMode, disableAddMode, toggleLockMode])

  return (
    <div className="relative">
      <button
        onClick={handleToggle}
        className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-all ${
          isLockMode
            ? 'bg-red-600 text-white shadow-lg shadow-red-500/50'
            : 'bg-gray-900/80 backdrop-blur-sm text-white hover:bg-gray-800/90 border border-gray-700'
        }`}
        title={isLockMode ? 'Exit Lock Mode (Esc)' : 'Lock Mode — click map items to lock/unlock'}
        aria-label={isLockMode ? 'Exit Lock Mode' : 'Enter Lock Mode'}
      >
        {isLockMode ? (
          <>
            <X className="w-4 h-4" />
            <span className="text-sm font-medium">Exit Lock Mode</span>
          </>
        ) : (
          <>
            <Lock className="w-4 h-4" />
            <span className="text-sm font-medium">Lock Mode</span>
          </>
        )}
      </button>

      {/* Helper tooltip when in lock mode */}
      {isLockMode && (
        <div className="absolute top-full mt-2 left-0 right-0 bg-red-900/90 backdrop-blur-sm text-white text-xs px-3 py-2 rounded-lg shadow-lg whitespace-nowrap z-50">
          <div className="flex items-center space-x-2">
            <Lock className="w-3 h-3" />
            <span>Click an acquisition on the map to toggle its lock. Press Esc to exit.</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default LockModeButton
