import { Lock, Unlock, Shield } from 'lucide-react'
import { useState } from 'react'
import type { LockLevel } from '../api/scheduleApi'

interface LockToggleProps {
  lockLevel: LockLevel
  onChange: (level: LockLevel) => void
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  className?: string
}

// PR-OPS-REPAIR-DEFAULT-01: Simplified lock model - only hard/none
const LOCK_CONFIG: Record<
  LockLevel,
  {
    icon: typeof Lock
    color: string
    bgColor: string
    label: string
    description: string
  }
> = {
  none: {
    icon: Unlock,
    color: 'text-gray-400',
    bgColor: 'bg-gray-700',
    label: 'Unlocked',
    description: 'Can be adjusted by repair',
  },
  hard: {
    icon: Shield,
    color: 'text-red-400',
    bgColor: 'bg-red-900/30',
    label: 'Hard Lock',
    description: 'Immutable, never touched by repair',
  },
}

const SIZES = {
  sm: { button: 'w-6 h-6', icon: 'w-3 h-3', text: 'text-xs' },
  md: { button: 'w-8 h-8', icon: 'w-4 h-4', text: 'text-sm' },
  lg: { button: 'w-10 h-10', icon: 'w-5 h-5', text: 'text-base' },
}

export default function LockToggle({
  lockLevel,
  onChange,
  disabled = false,
  size = 'md',
  showLabel = false,
  className = '',
}: LockToggleProps): JSX.Element {
  const [showTooltip, setShowTooltip] = useState(false)

  const config = LOCK_CONFIG[lockLevel]
  const sizeConfig = SIZES[size]
  const Icon = config.icon

  // PR-OPS-REPAIR-DEFAULT-01: Simplified lock toggle - only none <-> hard
  const cycleLock = () => {
    if (disabled) return
    // Toggle between none and hard (2-level lock model)
    const newLevel: LockLevel = lockLevel === 'hard' ? 'none' : 'hard'
    onChange(newLevel)
  }

  return (
    <div className={`relative inline-flex items-center gap-1 ${className}`}>
      <button
        onClick={cycleLock}
        disabled={disabled}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={`
          ${sizeConfig.button} ${config.bgColor}
          rounded-md flex items-center justify-center
          border border-gray-600 transition-all
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-500 cursor-pointer'}
        `}
        title={config.description}
      >
        <Icon className={`${sizeConfig.icon} ${config.color}`} />
      </button>

      {showLabel && (
        <span className={`${sizeConfig.text} ${config.color} font-medium`}>{config.label}</span>
      )}

      {showTooltip && !disabled && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 pointer-events-none">
          <div className="bg-gray-800 text-white text-xs rounded-md px-2 py-1 whitespace-nowrap shadow-lg border border-gray-700">
            <div className="font-medium">{config.label}</div>
            <div className="text-gray-400 text-[10px]">{config.description}</div>
            <div className="text-gray-500 text-[10px] mt-1">Click to cycle</div>
          </div>
        </div>
      )}
    </div>
  )
}

interface LockBadgeProps {
  lockLevel: LockLevel
  size?: 'sm' | 'md'
}

export function LockBadge({ lockLevel, size = 'sm' }: LockBadgeProps): JSX.Element {
  const config = LOCK_CONFIG[lockLevel]
  const Icon = config.icon
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <span
      className={`
        inline-flex items-center gap-1 px-1.5 py-0.5 rounded
        ${config.bgColor} ${config.color} ${textSize}
      `}
      title={config.description}
    >
      <Icon className={iconSize} />
      <span className="font-medium">{config.label}</span>
    </span>
  )
}

interface BulkLockActionsProps {
  selectedIds: string[]
  onBulkLock: (level: LockLevel) => void
  disabled?: boolean
}

// PR-OPS-REPAIR-DEFAULT-01: Simplified bulk lock actions - only hard/none
export function BulkLockActions({
  selectedIds,
  onBulkLock,
  disabled = false,
}: BulkLockActionsProps): JSX.Element | null {
  if (selectedIds.length === 0) return null

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 border-b border-gray-700">
      <span className="text-sm text-gray-400">{selectedIds.length} selected:</span>
      <button
        onClick={() => onBulkLock('none')}
        disabled={disabled}
        className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded disabled:opacity-50"
      >
        <Unlock className="w-3 h-3 inline mr-1" />
        Unlock
      </button>
      <button
        onClick={() => onBulkLock('hard')}
        disabled={disabled}
        className="px-2 py-1 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded disabled:opacity-50"
      >
        <Shield className="w-3 h-3 inline mr-1" />
        Hard Lock
      </button>
    </div>
  )
}
