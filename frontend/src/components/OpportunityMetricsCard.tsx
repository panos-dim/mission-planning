import { ScheduledOpportunity } from '../types'

interface OpportunityMetricsCardProps {
  opportunity: ScheduledOpportunity | null
}

export default function OpportunityMetricsCard({
  opportunity,
}: OpportunityMetricsCardProps): JSX.Element | null {
  if (!opportunity) return null

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr)
    return date.toISOString().substring(11, 19) + ' UTC'
  }

  const formatDensity = (density: number | 'inf') => {
    if (density === 'inf') return '∞'
    return density.toFixed(3)
  }

  return (
    <div className="absolute bottom-4 left-4 bg-gray-900/95 border border-gray-700 rounded-lg p-3 shadow-lg backdrop-blur-sm max-w-sm">
      <div className="text-xs space-y-1.5">
        <div className="flex items-center gap-2 border-b border-gray-700 pb-1.5 mb-1.5">
          <span className="font-semibold text-blue-400">{opportunity.satellite_id}</span>
          <span className="text-gray-500">→</span>
          <span className="font-semibold text-blue-400">{opportunity.target_id}</span>
        </div>

        <div className="grid grid-cols-2 gap-x-3 gap-y-1">
          <div>
            <span className="text-gray-400">Start:</span>
            <span className="ml-1 text-white">{formatTime(opportunity.start_time)}</span>
          </div>
          <div>
            <span className="text-gray-400">End:</span>
            <span className="ml-1 text-white">{formatTime(opportunity.end_time)}</span>
          </div>

          <div>
            <span className="text-gray-400">Δroll:</span>
            <span className="ml-1 text-white">{opportunity.delta_roll.toFixed(2)}°</span>
          </div>
          <div>
            <span className="text-gray-400">t_slew:</span>
            <span className="ml-1 text-white">{opportunity.maneuver_time.toFixed(2)}s</span>
          </div>

          {opportunity.incidence_angle !== undefined && (
            <div>
              <span className="text-gray-400">Off-Nadir:</span>
              <span className="ml-1 text-white">{opportunity.incidence_angle.toFixed(1)}°</span>
            </div>
          )}

          <div>
            <span className="text-gray-400">Value:</span>
            <span className="ml-1 text-white">{opportunity.value.toFixed(2)}</span>
          </div>

          <div>
            <span className="text-gray-400">Density:</span>
            <span className="ml-1 text-white">{formatDensity(opportunity.density)}</span>
          </div>

          <div>
            <span className="text-gray-400">Slack:</span>
            <span className="ml-1 text-white">{opportunity.slack_time.toFixed(2)}s</span>
          </div>
        </div>
      </div>
    </div>
  )
}
