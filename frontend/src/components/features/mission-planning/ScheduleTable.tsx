import React from 'react'
import { ScheduledOpportunity } from '../../../types'

interface ScheduleTableProps {
  schedule: ScheduledOpportunity[]
  onRowClick: (startTime: string) => void
  onRowHover: (opportunityId: string | null) => void
}

export const ScheduleTable: React.FC<ScheduleTableProps> = ({
  schedule,
  onRowClick,
  onRowHover
}) => {
  return (
    <div className="overflow-x-auto bg-gray-700 rounded">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-600">
          <tr>
            <th className="text-left py-2 px-3">#</th>
            <th className="text-left py-2 px-3">Satellite</th>
            <th className="text-left py-2 px-3">Target</th>
            <th className="text-left py-2 px-3">Time</th>
            <th className="text-right py-2 px-3" title="Off-nadir angle">Off-Nadir (°)</th>
            <th className="text-right py-2 px-3" title="Delta roll">Δroll (°)</th>
            <th className="text-right py-2 px-3" title="Delta pitch">Δpitch (°)</th>
            <th className="text-right py-2 px-3" title="Roll angle">Roll (°)</th>
            <th className="text-right py-2 px-3" title="Pitch angle">Pitch (°)</th>
            <th className="text-right py-2 px-3">t_slew (s)</th>
            <th className="text-right py-2 px-3">Value</th>
          </tr>
        </thead>
        <tbody className="text-gray-300">
          {schedule.map((sched, idx) => {
            // Calculate display deltas based on previous row
            let displayDeltaRoll = sched.delta_roll
            let displayDeltaPitch = sched.delta_pitch
            
            if (idx > 0) {
              const prevSched = schedule[idx - 1]
              if (sched.roll_angle !== undefined && prevSched.roll_angle !== undefined) {
                displayDeltaRoll = Math.abs(sched.roll_angle - prevSched.roll_angle)
              }
              if (sched.pitch_angle !== undefined && prevSched.pitch_angle !== undefined) {
                displayDeltaPitch = Math.abs(sched.pitch_angle - prevSched.pitch_angle)
              }
            }
            
            // Calculate true off-nadir angle
            const roll = Math.abs(sched.roll_angle ?? 0)
            const pitch = Math.abs(sched.pitch_angle ?? 0)
            const offNadirAngle = Math.sqrt(roll * roll + pitch * pitch)
            
            return (
              <tr 
                key={idx} 
                className="border-b border-gray-600 hover:bg-gray-600 cursor-pointer"
                onClick={() => onRowClick(sched.start_time)}
                onMouseEnter={() => onRowHover(sched.opportunity_id)}
                onMouseLeave={() => onRowHover(null)}
                title="Click to navigate to this pass in timeline"
              >
                <td className="py-2 px-3">{idx + 1}</td>
                <td className="py-2 px-3">{sched.satellite_id}</td>
                <td className="py-2 px-3">{sched.target_id}</td>
                <td className="py-2 px-3">
                  {sched.start_time.substring(8, 10)}-{sched.start_time.substring(5, 7)}-{sched.start_time.substring(0, 4)} [{sched.start_time.substring(11, 19)}] UTC
                </td>
                <td className="text-right py-2 px-3">{offNadirAngle.toFixed(2)}</td>
                <td className="text-right py-2 px-3">{displayDeltaRoll?.toFixed(2) ?? 'N/A'}</td>
                <td className="text-right py-2 px-3">{displayDeltaPitch?.toFixed(2) ?? 'N/A'}</td>
                <td className="text-right py-2 px-3">
                  {sched.roll_angle !== undefined 
                    ? `${sched.roll_angle >= 0 ? '+' : ''}${sched.roll_angle.toFixed(2)}` 
                    : 'N/A'}
                </td>
                <td className="text-right py-2 px-3">
                  {sched.pitch_angle !== undefined 
                    ? `${sched.pitch_angle >= 0 ? '+' : ''}${sched.pitch_angle.toFixed(2)}` 
                    : 'N/A'}
                </td>
                <td className="text-right py-2 px-3">{sched.maneuver_time?.toFixed(3) ?? 'N/A'}</td>
                <td className="text-right py-2 px-3">{sched.value?.toFixed(2) ?? 'N/A'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

ScheduleTable.displayName = 'ScheduleTable'
