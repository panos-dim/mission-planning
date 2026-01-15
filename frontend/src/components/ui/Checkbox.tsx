import React from 'react'
import { cn } from './utils'
import { Check } from 'lucide-react'

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  description?: string
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, description, id, disabled, checked, ...props }, ref) => {
    const checkboxId = id || `checkbox-${Math.random().toString(36).substr(2, 9)}`

    return (
      <div className={cn('flex items-start', className)}>
        <div className="flex items-center h-5">
          <div className="relative">
            <input
              ref={ref}
              type="checkbox"
              id={checkboxId}
              disabled={disabled}
              checked={checked}
              className="sr-only peer"
              {...props}
            />
            <div
              className={cn(
                'w-4 h-4 border rounded transition-colors duration-200',
                'peer-focus:ring-2 peer-focus:ring-blue-500 peer-focus:ring-offset-2 peer-focus:ring-offset-gray-900',
                checked
                  ? 'bg-blue-600 border-blue-600'
                  : 'bg-gray-700 border-gray-600',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
            >
              {checked && (
                <Check className="w-3 h-3 text-white absolute top-0.5 left-0.5" />
              )}
            </div>
          </div>
        </div>
        {(label || description) && (
          <div className="ml-2">
            {label && (
              <label
                htmlFor={checkboxId}
                className={cn(
                  'text-sm text-gray-300 cursor-pointer',
                  disabled && 'cursor-not-allowed opacity-50'
                )}
              >
                {label}
              </label>
            )}
            {description && (
              <p className="text-xs text-gray-500 mt-0.5">{description}</p>
            )}
          </div>
        )}
      </div>
    )
  }
)

Checkbox.displayName = 'Checkbox'
