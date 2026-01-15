import React from 'react'
import { cn } from './utils'

export interface CardProps {
  title?: string
  description?: string
  children: React.ReactNode
  className?: string
  headerClassName?: string
  bodyClassName?: string
  footer?: React.ReactNode
  collapsible?: boolean
  defaultCollapsed?: boolean
  actions?: React.ReactNode
}

export const Card: React.FC<CardProps> = ({
  title,
  description,
  children,
  className,
  headerClassName,
  bodyClassName,
  footer,
  collapsible = false,
  defaultCollapsed = false,
  actions,
}) => {
  const [isCollapsed, setIsCollapsed] = React.useState(defaultCollapsed)

  return (
    <div
      className={cn(
        'bg-gray-800 rounded-lg border border-gray-700',
        className
      )}
    >
      {(title || actions) && (
        <div
          className={cn(
            'flex items-center justify-between px-4 py-3 border-b border-gray-700',
            collapsible && 'cursor-pointer hover:bg-gray-750',
            headerClassName
          )}
          onClick={collapsible ? () => setIsCollapsed(!isCollapsed) : undefined}
        >
          <div>
            {title && (
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                {collapsible && (
                  <span
                    className={cn(
                      'transition-transform duration-200',
                      isCollapsed ? '' : 'rotate-90'
                    )}
                  >
                    ▶
                  </span>
                )}
                {title}
              </h3>
            )}
            {description && (
              <p className="text-xs text-gray-400 mt-0.5">{description}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {(!collapsible || !isCollapsed) && (
        <div className={cn('p-4', bodyClassName)}>{children}</div>
      )}
      {footer && (
        <div className="px-4 py-3 border-t border-gray-700 bg-gray-850">
          {footer}
        </div>
      )}
    </div>
  )
}

Card.displayName = 'Card'
