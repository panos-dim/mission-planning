import React from 'react'
import { cn } from './utils'
import { Spinner } from './Spinner'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
  iconPosition?: 'left' | 'right'
}

const variantStyles = {
  primary: 'bg-blue-600 hover:bg-blue-700 text-white border-transparent focus:ring-blue-500',
  secondary: 'bg-gray-700 hover:bg-gray-600 text-gray-200 border-gray-600 focus:ring-gray-500',
  ghost: 'bg-transparent hover:bg-gray-800 text-gray-300 border-transparent focus:ring-gray-500',
  danger: 'bg-red-600 hover:bg-red-700 text-white border-transparent focus:ring-red-500',
  success: 'bg-green-600 hover:bg-green-700 text-white border-transparent focus:ring-green-500',
}

const sizeStyles = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      loading = false,
      disabled,
      icon,
      iconPosition = 'left',
      children,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          // Base styles
          'inline-flex items-center justify-center gap-2 font-medium rounded-lg border',
          'transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900',
          // Variant
          variantStyles[variant],
          // Size
          sizeStyles[size],
          // Disabled state
          isDisabled && 'opacity-50 cursor-not-allowed',
          className
        )}
        {...props}
      >
        {loading ? (
          <>
            <Spinner size="sm" />
            <span>{children}</span>
          </>
        ) : (
          <>
            {icon && iconPosition === 'left' && <span className="flex-shrink-0">{icon}</span>}
            {children && <span>{children}</span>}
            {icon && iconPosition === 'right' && <span className="flex-shrink-0">{icon}</span>}
          </>
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'
