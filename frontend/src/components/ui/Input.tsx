import React from 'react'
import { cn } from './utils'

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string
  error?: string
  hint?: string
  size?: 'sm' | 'md' | 'lg'
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
  suffix?: string
}

const sizeStyles = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-3 py-2 text-sm',
  lg: 'px-4 py-3 text-base',
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      label,
      error,
      hint,
      size = 'md',
      leftIcon,
      rightIcon,
      suffix,
      id,
      disabled,
      ...props
    },
    ref
  ) => {
    const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-medium text-gray-300 mb-1.5"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {leftIcon && (
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            className={cn(
              // Base styles
              'w-full bg-gray-700 border rounded text-white placeholder-gray-400',
              'transition-colors duration-200',
              'focus:outline-none focus:ring-1',
              // Size
              sizeStyles[size],
              // Icon padding
              leftIcon && 'pl-10',
              (rightIcon || suffix) && 'pr-10',
              // States
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-600 focus:border-blue-500 focus:ring-blue-500',
              disabled && 'opacity-50 cursor-not-allowed',
              className
            )}
            {...props}
          />
          {(rightIcon || suffix) && (
            <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-gray-400">
              {rightIcon || <span className="text-xs">{suffix}</span>}
            </div>
          )}
        </div>
        {(error || hint) && (
          <p className={cn('mt-1 text-xs', error ? 'text-red-400' : 'text-gray-400')}>
            {error || hint}
          </p>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input'
