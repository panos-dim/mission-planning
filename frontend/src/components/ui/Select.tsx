import React from 'react'
import { cn } from './utils'
import { ChevronDown } from 'lucide-react'

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string
  error?: string
  hint?: string
  size?: 'sm' | 'md' | 'lg'
  options: SelectOption[]
  placeholder?: string
}

const sizeStyles = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-3 py-2 text-sm',
  lg: 'px-4 py-3 text-base',
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      className,
      label,
      error,
      hint,
      size = 'md',
      options,
      placeholder,
      id,
      disabled,
      ...props
    },
    ref
  ) => {
    const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`

    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={selectId}
            className="block text-xs font-medium text-gray-300 mb-1.5"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            className={cn(
              // Base styles
              'w-full bg-gray-700 border rounded text-white appearance-none cursor-pointer',
              'transition-colors duration-200',
              'focus:outline-none focus:ring-1',
              // Size
              sizeStyles[size],
              'pr-10', // Space for chevron
              // States
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-600 focus:border-blue-500 focus:ring-blue-500',
              disabled && 'opacity-50 cursor-not-allowed',
              className
            )}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </option>
            ))}
          </select>
          <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-gray-400">
            <ChevronDown className="w-4 h-4" />
          </div>
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

Select.displayName = 'Select'
