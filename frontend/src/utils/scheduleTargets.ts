import type { MasterScheduleItem } from '../api/scheduleApi'
import type { AcceptedOrder, TargetData } from '../types'

export type ScheduleTargetStatus = 'upcoming' | 'past'
type ScheduleTargetCandidate = {
  acquisitionId: string
  targetId: string
  startTime: string
  endTime: string
}

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

function pickPreferredTargetCandidate(
  candidates: ScheduleTargetCandidate[],
  nowTs: number,
): ScheduleTargetCandidate | null {
  if (candidates.length === 0) return null

  const activeCandidate = candidates
    .filter((candidate) => {
      const startTs = new Date(candidate.startTime).getTime()
      const endTs = new Date(candidate.endTime).getTime()
      return startTs <= nowTs && endTs >= nowTs
    })
    .sort((a, b) => new Date(a.endTime).getTime() - new Date(b.endTime).getTime())[0]

  if (activeCandidate) return activeCandidate

  const nextUpcomingCandidate = candidates
    .filter((candidate) => new Date(candidate.startTime).getTime() >= nowTs)
    .sort((a, b) => new Date(a.startTime).getTime() - new Date(b.startTime).getTime())[0]

  if (nextUpcomingCandidate) return nextUpcomingCandidate

  return (
    candidates.sort((a, b) => new Date(b.endTime).getTime() - new Date(a.endTime).getTime())[0] ??
    null
  )
}

export function buildScheduleTargetAcquisitionMap(
  scheduleItems: MasterScheduleItem[],
  committedOrders: AcceptedOrder[],
  nowTs = Date.now(),
): Map<string, string> {
  const candidatesByTarget = new Map<string, ScheduleTargetCandidate[]>()

  const addCandidate = (candidate: ScheduleTargetCandidate) => {
    const existing = candidatesByTarget.get(candidate.targetId) ?? []
    existing.push(candidate)
    candidatesByTarget.set(candidate.targetId, existing)
  }

  if (scheduleItems.length > 0) {
    for (const item of scheduleItems) {
      addCandidate({
        acquisitionId: item.id,
        targetId: item.target_id,
        startTime: item.start_time,
        endTime: item.end_time,
      })
    }
  } else {
    for (const order of committedOrders) {
      for (const [index, item] of (order.schedule || []).entries()) {
        const acquisitionId = order.backend_acquisition_ids?.[index] || item.opportunity_id
        if (!acquisitionId) continue
        addCandidate({
          acquisitionId,
          targetId: item.target_id,
          startTime: item.start_time,
          endTime: item.end_time,
        })
      }
    }
  }

  const targetAcquisitionMap = new Map<string, string>()
  for (const [targetId, candidates] of candidatesByTarget.entries()) {
    const preferredCandidate = pickPreferredTargetCandidate(candidates, nowTs)
    if (preferredCandidate) {
      targetAcquisitionMap.set(targetId, preferredCandidate.acquisitionId)
    }
  }

  return targetAcquisitionMap
}
