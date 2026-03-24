import type { MasterScheduleItem } from '../api/scheduleApi'
import type { AcceptedOrder, TargetData } from '../types'

export type ScheduleTargetStatus = 'upcoming' | 'past'

const updateTargetStatus = (
  targetStatus: Map<string, ScheduleTargetStatus>,
  targetId: string | undefined,
  endTime: string | undefined,
  nowTs: number,
) => {
  if (!targetId || !endTime) return

  const endTs = new Date(endTime).getTime()
  const current = targetStatus.get(targetId)

  if (endTs >= nowTs) {
    targetStatus.set(targetId, 'upcoming')
  } else if (current !== 'upcoming') {
    targetStatus.set(targetId, 'past')
  }
}

export function buildScheduleTargetStatus(
  scheduleItems: MasterScheduleItem[],
  committedOrders: AcceptedOrder[],
  nowTs = Date.now(),
): Map<string, ScheduleTargetStatus> {
  const targetStatus = new Map<string, ScheduleTargetStatus>()

  if (scheduleItems.length > 0) {
    for (const item of scheduleItems) {
      updateTargetStatus(targetStatus, item.target_id, item.end_time, nowTs)
    }
    return targetStatus
  }

  for (const order of committedOrders) {
    for (const item of order.schedule || []) {
      updateTargetStatus(targetStatus, item.target_id, item.end_time, nowTs)
    }
  }

  return targetStatus
}

export function collectScheduleTargetGeo(
  scheduleItems: MasterScheduleItem[],
  missionTargets: TargetData[],
  committedOrders: AcceptedOrder[],
): Map<string, { lat: number; lon: number }> {
  const targetGeo = new Map<string, { lat: number; lon: number }>()

  for (const item of scheduleItems) {
    if (item.target_id && item.target_lat != null && item.target_lon != null) {
      targetGeo.set(item.target_id, { lat: item.target_lat, lon: item.target_lon })
    }
  }

  for (const target of missionTargets) {
    if (
      !targetGeo.has(target.name) &&
      target.latitude != null &&
      target.longitude != null
    ) {
      targetGeo.set(target.name, { lat: target.latitude, lon: target.longitude })
    }
  }

  for (const order of committedOrders) {
    for (const targetPosition of order.target_positions || []) {
      if (
        !targetGeo.has(targetPosition.target_id) &&
        targetPosition.latitude != null &&
        targetPosition.longitude != null
      ) {
        targetGeo.set(targetPosition.target_id, {
          lat: targetPosition.latitude,
          lon: targetPosition.longitude,
        })
      }
    }
  }

  return targetGeo
}
