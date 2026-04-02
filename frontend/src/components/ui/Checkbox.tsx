import React from 'react'
import { cn } from './utils'
import { Check } from 'lucide-react'

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string
  description?: string
  labelClassName?: string
  descriptionClassName?: string
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  (
    {
      className,
      label,
      description,
      labelClassName,
      descriptionClassName,
      id,
      disabled,
      checked,
      ...props
    },
    ref,
  ) => {
    const generatedId = React.useId()
    const checkboxId = id || generatedId

    return (
      <label
        htmlFor={checkboxId}
        className={cn(
          'flex items-start gap-2',
          disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
          className,
        )}
      >
        <span className="flex items-center h-5">
          <span className="relative flex size-4 items-center justify-center">
            <input
              ref={ref}
              type="checkbox"
              id={checkboxId}
              disabled={disabled}
              checked={checked}
              className="sr-only peer"
              {...props}
            />
            <span
              aria-hidden="true"
              className={cn(
                'size-4 border rounded transition-colors duration-200',
                'peer-focus:ring-2 peer-focus:ring-blue-500 peer-focus:ring-offset-2 peer-focus:ring-offset-gray-900',
                checked ? 'bg-blue-600 border-blue-600' : 'bg-gray-700 border-gray-600',
              )}
            >
              {checked && <Check className="absolute top-0.5 left-0.5 w-3 h-3 text-white" />}
            </span>
          </span>
        </span>
        {(label || description) && (
          <span className="min-w-0">
            {label && (
              <span className={cn('text-sm text-gray-300', labelClassName)}>
                {label}
              </span>
            )}
            {description && (
              <p className={cn('mt-0.5 text-xs text-gray-500', descriptionClassName)}>
                {description}
              </p>
            )}
          </span>
        )}
      </label>
    )
  }
)

Checkbox.displayName = 'Checkbox'
