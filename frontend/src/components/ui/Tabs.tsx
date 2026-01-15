import React, { createContext, useContext, useState } from 'react'
import { cn } from './utils'

interface TabsContextType {
  activeTab: string
  setActiveTab: (value: string) => void
}

const TabsContext = createContext<TabsContextType | null>(null)

function useTabsContext() {
  const context = useContext(TabsContext)
  if (!context) {
    throw new Error('Tabs components must be used within a Tabs provider')
  }
  return context
}

export interface TabsProps {
  defaultValue: string
  value?: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
  className?: string
}

export const Tabs: React.FC<TabsProps> = ({
  defaultValue,
  value,
  onValueChange,
  children,
  className,
}) => {
  const [internalValue, setInternalValue] = useState(defaultValue)
  const activeTab = value ?? internalValue

  const setActiveTab = (newValue: string) => {
    if (!value) {
      setInternalValue(newValue)
    }
    onValueChange?.(newValue)
  }

  return (
    <TabsContext.Provider value={{ activeTab, setActiveTab }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  )
}

interface TabsListProps {
  children: React.ReactNode
  className?: string
}

export const TabsList: React.FC<TabsListProps> = ({ children, className }) => {
  return (
    <div
      className={cn(
        'flex items-center gap-1 p-1 bg-gray-800 rounded-lg',
        className
      )}
      role="tablist"
    >
      {children}
    </div>
  )
}

interface TabsTriggerProps {
  value: string
  children: React.ReactNode
  disabled?: boolean
  className?: string
}

export const TabsTrigger: React.FC<TabsTriggerProps> = ({
  value,
  children,
  disabled = false,
  className,
}) => {
  const { activeTab, setActiveTab } = useTabsContext()
  const isActive = activeTab === value

  return (
    <button
      role="tab"
      aria-selected={isActive}
      aria-controls={`tabpanel-${value}`}
      disabled={disabled}
      onClick={() => setActiveTab(value)}
      className={cn(
        'px-3 py-1.5 text-sm font-medium rounded-md transition-colors duration-200',
        'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-gray-800',
        isActive
          ? 'bg-gray-700 text-white'
          : 'text-gray-400 hover:text-white hover:bg-gray-750',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
    >
      {children}
    </button>
  )
}

interface TabsContentProps {
  value: string
  children: React.ReactNode
  className?: string
}

export const TabsContent: React.FC<TabsContentProps> = ({
  value,
  children,
  className,
}) => {
  const { activeTab } = useTabsContext()

  if (activeTab !== value) return null

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${value}`}
      aria-labelledby={`tab-${value}`}
      className={cn('mt-4', className)}
    >
      {children}
    </div>
  )
}

Tabs.displayName = 'Tabs'
TabsList.displayName = 'TabsList'
TabsTrigger.displayName = 'TabsTrigger'
TabsContent.displayName = 'TabsContent'
