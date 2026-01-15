import React from 'react'
import { cn } from './utils'

export interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info'
  size?: 'sm' | 'md'
  children: React.ReactNode
  className?: string
  icon?: React.ReactNode
}

const variantStyles = {
  default: 'bg-gray-700 text-gray-300 border-gray-600',
  success: 'bg-green-900/50 text-green-400 border-green-700/50',
  warning: 'bg-yellow-900/50 text-yellow-400 border-yellow-700/50',
  error: 'bg-red-900/50 text-red-400 border-red-700/50',
  info: 'bg-blue-900/50 text-blue-400 border-blue-700/50',
}

const sizeStyles = {
  sm: 'px-1.5 py-0.5 text-xs',
  md: 'px-2 py-1 text-xs',
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'default',
  size = 'sm',
  children,
  className,
  icon,
}) => {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 font-medium rounded border',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </span>
  )
}

Badge.displayName = 'Badge'
