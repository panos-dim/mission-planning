import type { MissionData } from '../types'

export interface MissionHorizon {
  start: string
  end: string
}

const MS_PER_DAY = 24 * 60 * 60 * 1000

export function getMissionHorizon(
  missionData?: Pick<MissionData, 'start_time' | 'end_time'> | null,
): MissionHorizon | null {
  if (!missionData?.start_time || !missionData?.end_time) {
    return null
  }

  return {
    start: missionData.start_time,
    end: missionData.end_time,
  }
}

export function getMissionHorizonDurationDays(horizon: MissionHorizon | null): number | null {
  if (!horizon) return null

  const startMs = new Date(horizon.start).getTime()
  const endMs = new Date(horizon.end).getTime()

  if (!Number.isFinite(startMs) || !Number.isFinite(endMs) || endMs <= startMs) {
    return null
  }

  return Math.max(1, Math.ceil((endMs - startMs) / MS_PER_DAY))
}
