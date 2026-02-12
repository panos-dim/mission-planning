import React from 'react'
import { AlertTriangle } from 'lucide-react'

interface NoOpportunitiesWarningProps {
  loading: boolean
}

export const NoOpportunitiesWarning: React.FC<NoOpportunitiesWarningProps> = ({ loading }) => {
  if (loading) return null

  return (
    <div className="bg-yellow-900/30 border border-yellow-700/50 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-6 h-6 text-yellow-500 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-yellow-200 mb-1">No Opportunities Available</h3>
          <p className="text-xs text-yellow-300/80 mb-3">
            Mission Planning requires opportunities from Feasibility Analysis. Please complete these
            steps:
          </p>
          <ol className="text-xs text-yellow-300/80 space-y-1 list-decimal list-inside">
            <li>
              Go to <strong>Feasibility Analysis</strong> panel (left sidebar)
            </li>
            <li>Configure targets and mission parameters</li>
            <li>
              Click <strong>Analyze Mission</strong> to generate opportunities
            </li>
            <li>Return here to schedule opportunities with algorithms</li>
          </ol>
        </div>
      </div>
    </div>
  )
}

NoOpportunitiesWarning.displayName = 'NoOpportunitiesWarning'
