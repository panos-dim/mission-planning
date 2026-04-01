import type { DirectCommitItem } from '../api/scheduleApi'
import type { ScheduledOpportunity } from '../types'

/**
 * Normalize scheduled opportunities into the payload expected by direct-commit APIs.
 * Keeping this in one place prevents the preview and commit flows from drifting apart.
 */
export function scheduleToDirectCommitItems(
  schedule: ScheduledOpportunity[],
): DirectCommitItem[] {
  return schedule.map((item) => ({
    opportunity_id: item.opportunity_id,
    satellite_id: item.satellite_id,
    target_id: item.target_id,
    start_time: item.start_time,
    end_time: item.end_time,
    roll_angle_deg: item.roll_angle || item.delta_roll || 0,
    pitch_angle_deg: item.pitch_angle || 0,
    value: item.value,
    incidence_angle_deg: item.incidence_angle,
    sar_mode: item.sar_mode,
    look_side: item.look_side,
    pass_direction: item.pass_direction,
  }))
}
