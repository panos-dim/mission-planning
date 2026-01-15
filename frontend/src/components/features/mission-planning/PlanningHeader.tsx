import React from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { Button } from '../../ui'

interface PlanningHeaderProps {
  hasResults: boolean
  slewVisEnabled: boolean
  onToggleSlewVis: () => void
  hasOpportunities: boolean
  uniqueTargets: number
  opportunitiesCount: number
}

export const PlanningHeader: React.FC<PlanningHeaderProps> = ({
  hasResults,
  slewVisEnabled,
  onToggleSlewVis,
  hasOpportunities,
  uniqueTargets,
  opportunitiesCount
}) => {
  return (
    <div className="bg-gray-800 border-b border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-white">Mission Planning — Algorithm Suite</h2>
        {hasResults && (
          <Button
            variant={slewVisEnabled ? 'primary' : 'secondary'}
            size="sm"
            onClick={onToggleSlewVis}
            icon={slewVisEnabled ? <EyeOff size={14} /> : <Eye size={14} />}
          >
            {slewVisEnabled ? 'Hide' : 'Show'} Live Slew View
          </Button>
        )}
      </div>
      <p className="text-xs text-gray-400">
        {hasOpportunities 
          ? `Select and run scheduling algorithms: ${uniqueTargets} targets with ${opportunitiesCount} opportunities from Mission Analysis`
          : 'Run Mission Analysis first to generate opportunities'}
      </p>
    </div>
  )
}

PlanningHeader.displayName = 'PlanningHeader'
