import React from 'react'
import { cn } from './utils'
import { Spinner } from './Spinner'
import { Check, AlertCircle } from 'lucide-react'

export interface AnalysisStep {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'error'
  detail?: string
}

export interface AnalysisProgressProps {
  steps: AnalysisStep[]
  title?: string
  className?: string
}

export const AnalysisProgress: React.FC<AnalysisProgressProps> = ({
  steps,
  title = 'Analysis Progress',
  className
}) => {
  const completedCount = steps.filter(s => s.status === 'completed').length
  const hasError = steps.some(s => s.status === 'error')
  const isComplete = completedCount === steps.length && !hasError

  return (
    <div className={cn('bg-gray-800 rounded-lg p-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <span className="text-xs text-gray-400">
          {completedCount}/{steps.length} steps
        </span>
      </div>

      {/* Progress Bar */}
      <div className="h-2 bg-gray-700 rounded-full mb-4 overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500',
            hasError ? 'bg-red-500' : isComplete ? 'bg-green-500' : 'bg-blue-500'
          )}
          style={{ width: `${(completedCount / steps.length) * 100}%` }}
        />
      </div>

      {/* Steps List */}
      <div className="space-y-2">
        {steps.map((step) => (
          <div
            key={step.id}
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded',
              step.status === 'running' && 'bg-blue-900/30',
              step.status === 'error' && 'bg-red-900/30'
            )}
          >
            {/* Status Icon */}
            <div className="flex-shrink-0">
              {step.status === 'pending' && (
                <div className="w-4 h-4 rounded-full border-2 border-gray-600" />
              )}
              {step.status === 'running' && (
                <Spinner size="sm" className="text-blue-400" />
              )}
              {step.status === 'completed' && (
                <Check className="w-4 h-4 text-green-400" />
              )}
              {step.status === 'error' && (
                <AlertCircle className="w-4 h-4 text-red-400" />
              )}
            </div>

            {/* Label and Detail */}
            <div className="flex-1 min-w-0">
              <div
                className={cn(
                  'text-sm',
                  step.status === 'pending' && 'text-gray-500',
                  step.status === 'running' && 'text-blue-300',
                  step.status === 'completed' && 'text-gray-300',
                  step.status === 'error' && 'text-red-300'
                )}
              >
                {step.label}
              </div>
              {step.detail && (
                <div className="text-xs text-gray-500 truncate">
                  {step.detail}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

AnalysisProgress.displayName = 'AnalysisProgress'
