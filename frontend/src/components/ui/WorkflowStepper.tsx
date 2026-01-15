import React from 'react'
import { cn } from './utils'
import { Check, Circle, Loader2 } from 'lucide-react'

export interface WorkflowStep {
  id: string
  label: string
  description?: string
  icon?: React.ReactNode
}

export interface WorkflowStepperProps {
  steps: WorkflowStep[]
  currentStep: string
  completedSteps: string[]
  onStepClick?: (stepId: string) => void
  orientation?: 'horizontal' | 'vertical'
  className?: string
}

export const WorkflowStepper: React.FC<WorkflowStepperProps> = ({
  steps,
  currentStep,
  completedSteps,
  onStepClick,
  orientation = 'horizontal',
  className
}) => {
  const getStepStatus = (stepId: string): 'completed' | 'current' | 'pending' => {
    if (completedSteps.includes(stepId)) return 'completed'
    if (stepId === currentStep) return 'current'
    return 'pending'
  }

  const isHorizontal = orientation === 'horizontal'

  return (
    <div
      className={cn(
        'flex',
        isHorizontal ? 'flex-row items-center' : 'flex-col',
        className
      )}
    >
      {steps.map((step, index) => {
        const status = getStepStatus(step.id)
        const isLast = index === steps.length - 1
        const isClickable = onStepClick && (status === 'completed' || status === 'current')

        return (
          <React.Fragment key={step.id}>
            {/* Step */}
            <div
              className={cn(
                'flex items-center gap-3',
                isHorizontal ? 'flex-col' : 'flex-row',
                isClickable && 'cursor-pointer',
                status === 'pending' && 'opacity-50'
              )}
              onClick={() => isClickable && onStepClick?.(step.id)}
            >
              {/* Step Indicator */}
              <div
                className={cn(
                  'flex items-center justify-center w-8 h-8 rounded-full border-2 transition-colors',
                  status === 'completed' && 'bg-green-600 border-green-600 text-white',
                  status === 'current' && 'bg-blue-600 border-blue-600 text-white',
                  status === 'pending' && 'bg-gray-800 border-gray-600 text-gray-400'
                )}
              >
                {status === 'completed' ? (
                  <Check className="w-4 h-4" />
                ) : status === 'current' ? (
                  step.icon || <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  step.icon || <Circle className="w-4 h-4" />
                )}
              </div>

              {/* Step Label */}
              <div className={cn('text-center', !isHorizontal && 'text-left')}>
                <div
                  className={cn(
                    'text-xs font-medium',
                    status === 'completed' && 'text-green-400',
                    status === 'current' && 'text-blue-400',
                    status === 'pending' && 'text-gray-500'
                  )}
                >
                  {step.label}
                </div>
                {step.description && (
                  <div className="text-[10px] text-gray-500 mt-0.5">
                    {step.description}
                  </div>
                )}
              </div>
            </div>

            {/* Connector Line */}
            {!isLast && (
              <div
                className={cn(
                  'transition-colors',
                  isHorizontal
                    ? 'flex-1 h-0.5 mx-2 min-w-[20px]'
                    : 'w-0.5 h-6 ml-4 my-1',
                  completedSteps.includes(step.id) ? 'bg-green-600' : 'bg-gray-700'
                )}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

WorkflowStepper.displayName = 'WorkflowStepper'
