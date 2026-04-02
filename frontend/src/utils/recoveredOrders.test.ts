import { describe, expect, it } from 'vitest'

import type { MasterScheduleItem } from '../api/scheduleApi'
import {
  buildRecoveredOrdersFromScheduleItems,
  getAcceptedOrderAcquisitionCount,
} from './recoveredOrders'

const buildScheduleItem = (
  id: string,
  targetId: string,
  startTime: string,
  planId = 'plan-1',
): MasterScheduleItem => ({
  id,
  satellite_id: 'SAT-1',
  target_id: targetId,
  start_time: startTime,
  end_time: new Date(new Date(startTime).getTime() + 5 * 60_000).toISOString(),
  mode: 'OPTICAL',
  state: 'committed',
  lock_level: 'none',
  plan_id: planId,
  opportunity_id: `${id}-opp`,
  target_lat: 29.3,
  target_lon: 47.9,
  geometry: {
    roll_deg: 2,
    pitch_deg: 0,
    incidence_deg: 15,
  },
  quality_score: 1,
  maneuver_time_s: 10,
  slack_time_s: 20,
})

describe('buildRecoveredOrdersFromScheduleItems', () => {
  it('groups acquisitions by plan id when explicit orders are unavailable', () => {
    const recovered = buildRecoveredOrdersFromScheduleItems([
      buildScheduleItem('acq-1', 'Kuwait_1', '2026-03-24T01:00:00Z', 'plan-1'),
      buildScheduleItem('acq-2', 'Kuwait_2', '2026-03-24T02:00:00Z', 'plan-1'),
      buildScheduleItem('acq-3', 'Kuwait_3', '2026-03-24T03:00:00Z', 'plan-2'),
    ])

    expect(recovered).toHaveLength(2)
    expect(recovered[0]?.backend_acquisition_ids).toEqual(['acq-1', 'acq-2'])
    expect(recovered[1]?.backend_acquisition_ids).toEqual(['acq-3'])
  })

  it('counts acquisitions across recovered orders', () => {
    const recovered = buildRecoveredOrdersFromScheduleItems([
      buildScheduleItem('acq-1', 'Kuwait_1', '2026-03-24T01:00:00Z'),
      buildScheduleItem('acq-2', 'Kuwait_2', '2026-03-24T02:00:00Z'),
    ])

    expect(getAcceptedOrderAcquisitionCount(recovered)).toBe(2)
  })

  it('preserves pitch geometry for recovered upcoming passes', () => {
    const recovered = buildRecoveredOrdersFromScheduleItems([
      {
        ...buildScheduleItem('acq-1', 'Kuwait_1', '2026-03-24T01:00:00Z'),
        geometry: {
          roll_deg: 3.2,
          pitch_deg: 11.4,
          incidence_deg: 15,
        },
      },
    ])

    expect(recovered[0]?.schedule[0]?.pitch_deg).toBe(11.4)
  })
})
