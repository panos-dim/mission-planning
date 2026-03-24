import { describe, expect, it } from 'vitest'

import type { MasterScheduleItem } from '../api/scheduleApi'
import type { AcceptedOrder, TargetData } from '../types'
import { buildScheduleTargetStatus, collectScheduleTargetGeo } from './scheduleTargets'

const buildScheduleItem = (targetId: string, endTime: string): MasterScheduleItem => ({
  id: `${targetId}-acq`,
  satellite_id: 'SAT-1',
  target_id: targetId,
  start_time: '2026-03-24T01:00:00Z',
  end_time: endTime,
  mode: 'OPTICAL',
  state: 'committed',
  lock_level: 'none',
  target_lat: 29.3759,
  target_lon: 47.9774,
})

const buildOrder = (targetId: string): AcceptedOrder => ({
  order_id: `${targetId}-order`,
  name: targetId,
  created_at: '2026-03-24T00:00:00Z',
  algorithm: 'roll_pitch_best_fit',
  metrics: {
    accepted: 1,
    rejected: 0,
    total_value: 1,
    mean_incidence_deg: 10,
    imaging_time_s: 60,
    maneuver_time_s: 0,
    utilization: 1,
    runtime_ms: 1,
  },
  schedule: [
    {
      opportunity_id: `${targetId}-opp`,
      satellite_id: 'SAT-1',
      target_id: targetId,
      start_time: '2026-03-24T01:00:00Z',
      end_time: '2026-03-24T01:05:00Z',
      droll_deg: 0,
      t_slew_s: 0,
      slack_s: 0,
      value: 1,
      density: 1,
    },
  ],
  target_positions: [
    {
      target_id: targetId,
      latitude: 24.7136,
      longitude: 46.6753,
    },
  ],
})

describe('buildScheduleTargetStatus', () => {
  it('prefers master schedule items over persisted orders', () => {
    const status = buildScheduleTargetStatus(
      [buildScheduleItem('Kuwait_1', '2026-03-24T03:05:00Z')],
      [buildOrder('Target 1')],
      new Date('2026-03-24T02:00:00Z').getTime(),
    )

    expect([...status.keys()]).toEqual(['Kuwait_1'])
    expect(status.get('Kuwait_1')).toBe('upcoming')
  })

  it('falls back to persisted orders when the master schedule is empty', () => {
    const status = buildScheduleTargetStatus(
      [],
      [buildOrder('Target 1')],
      new Date('2026-03-24T10:00:00Z').getTime(),
    )

    expect(status.get('Target 1')).toBe('past')
  })
})

describe('collectScheduleTargetGeo', () => {
  it('keeps master schedule coordinates authoritative for matching target ids', () => {
    const missionTargets: TargetData[] = [
      { name: 'Kuwait_1', latitude: 1, longitude: 2, priority: 1 },
    ]

    const geo = collectScheduleTargetGeo(
      [buildScheduleItem('Kuwait_1', '2026-03-24T03:05:00Z')],
      missionTargets,
      [buildOrder('Kuwait_1')],
    )

    expect(geo.get('Kuwait_1')).toEqual({ lat: 29.3759, lon: 47.9774 })
  })
})
