import { ScheduledOpportunity } from '../types'

interface OpportunityMetricsCardProps {
  opportunity: ScheduledOpportunity | null
}

export default function OpportunityMetricsCard({
  opportunity,
}: OpportunityMetricsCardProps): JSX.Element | null {
  if (!opportunity) return null

  // PR-UI-024/028: Off-nadir angle only (1dp) — sqrt(roll² + pitch²)
  const roll = Math.abs(opportunity.roll_angle ?? 0)
  const pitch = Math.abs(opportunity.pitch_angle ?? 0)
  const offNadir = Math.sqrt(roll * roll + pitch * pitch)

  return (
    <div className="absolute bottom-4 left-4 bg-gray-900/95 border border-gray-700 rounded-lg p-3 shadow-lg backdrop-blur-sm max-w-sm">
      <div className="text-xs space-y-1.5">
        <div className="flex items-center gap-2 border-b border-gray-700 pb-1.5 mb-1.5">
          <span className="font-semibold text-blue-400">{opportunity.satellite_id}</span>
          <span className="text-gray-500">→</span>
          <span className="font-semibold text-blue-400">{opportunity.target_id}</span>
        </div>

        <div>
          <span className="text-gray-400">Off-nadir angle:</span>
          <span className="ml-1 text-white font-semibold">{offNadir.toFixed(1)}°</span>
        </div>
      </div>
    </div>
  )
}
