import React from 'react'
import { cn } from './utils'

export interface ProgressBarProps {
  value: number // 0-100
  max?: number
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'success' | 'warning' | 'error'
  showLabel?: boolean
  label?: string
  animated?: boolean
  className?: string
}

const sizeStyles = {
  sm: 'h-1',
  md: 'h-2',
  lg: 'h-3',
}

const variantStyles = {
  default: 'bg-blue-500',
  success: 'bg-green-500',
  warning: 'bg-yellow-500',
  error: 'bg-red-500',
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  max = 100,
  size = 'md',
  variant = 'default',
  showLabel = false,
  label,
  animated = false,
  className,
}) => {
  const percentage = Math.min(Math.max((value / max) * 100, 0), 100)

  return (
    <div className={cn('w-full', className)}>
      {(showLabel || label) && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-400">
            {label || 'Progress'}
          </span>
          {showLabel && (
            <span className="text-xs text-gray-400">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          'w-full bg-gray-700 rounded-full overflow-hidden',
          sizeStyles[size]
        )}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
      >
        <div
          className={cn(
            'h-full rounded-full transition-all duration-300 ease-out',
            variantStyles[variant],
            animated && 'animate-pulse'
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

ProgressBar.displayName = 'ProgressBar'
