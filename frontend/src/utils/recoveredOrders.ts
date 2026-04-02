import type { MasterScheduleItem } from '../api/scheduleApi'
import type { AcceptedOrder } from '../types'

const DEFAULT_RECOVERED_ALGORITHM: AcceptedOrder['algorithm'] = 'roll_pitch_best_fit'

const sortByStartTime = (a: { start_time: string }, b: { start_time: string }) =>
  new Date(a.start_time).getTime() - new Date(b.start_time).getTime()

export function buildRecoveredOrdersFromScheduleItems(
  scheduleItems: MasterScheduleItem[],
): AcceptedOrder[] {
  if (scheduleItems.length === 0) return []

  const grouped = new Map<
    string,
    {
      groupKey: string
      items: MasterScheduleItem[]
      labelHint: string | null
    }
  >()

  for (const item of [...scheduleItems].sort(sortByStartTime)) {
    const groupKey = item.order_id || item.plan_id || 'recovered-workspace-schedule'
    const labelHint = item.order_id || item.plan_id || null
    const group = grouped.get(groupKey)
    if (group) {
      group.items.push(item)
    } else {
      grouped.set(groupKey, {
        groupKey,
        items: [item],
        labelHint,
      })
    }
  }

  return Array.from(grouped.values())
    .sort((a, b) => sortByStartTime(a.items[0], b.items[0]))
    .map((group, index) => {
      const items = [...group.items].sort(sortByStartTime)
      const satellites = [...new Set(items.map((item) => item.satellite_id))]
      const targets = [...new Set(items.map((item) => item.target_id))]
      const totalDurationSeconds = items.reduce((total, item) => {
        return total + Math.max(0, new Date(item.end_time).getTime() - new Date(item.start_time).getTime())
      }, 0) / 1000

      const incidenceSamples = items
        .map((item) => item.geometry?.incidence_deg)
        .filter((value): value is number => value != null)
      const meanIncidenceDeg =
        incidenceSamples.length > 0
          ? incidenceSamples.reduce((sum, value) => sum + value, 0) / incidenceSamples.length
          : 0

      return {
        order_id: group.groupKey,
        name: group.labelHint
          ? `Recovered ${index + 1}`
          : items.length === scheduleItems.length
            ? 'Recovered Schedule'
            : `Recovered Schedule ${index + 1}`,
        created_at: items[0].start_time,
        algorithm: DEFAULT_RECOVERED_ALGORITHM,
        metrics: {
          accepted: items.length,
          rejected: 0,
          total_value: 0,
          mean_incidence_deg: meanIncidenceDeg,
          imaging_time_s: totalDurationSeconds,
          maneuver_time_s: 0,
          utilization: 0,
          runtime_ms: 0,
        },
        schedule: items.map((item) => ({
          opportunity_id: item.opportunity_id || item.id,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start_time: item.start_time,
          end_time: item.end_time,
          droll_deg: item.geometry?.roll_deg ?? 0,
          pitch_deg: item.geometry?.pitch_deg ?? 0,
          t_slew_s: item.maneuver_time_s ?? 0,
          slack_s: item.slack_time_s ?? 0,
          value: item.quality_score ?? 0,
          density: 1,
        })),
        satellites_involved: satellites,
        targets_covered: targets,
        backend_acquisition_ids: items.map((item) => item.id),
        target_positions: items
          .filter((item) => item.target_lat != null && item.target_lon != null)
          .map((item) => ({
            target_id: item.target_id,
            latitude: item.target_lat!,
            longitude: item.target_lon!,
          })),
      }
    })
}

export function getAcceptedOrderAcquisitionCount(orders: AcceptedOrder[]): number {
  return orders.reduce((sum, order) => sum + (order.schedule?.length || 0), 0)
}
