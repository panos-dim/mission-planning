import { describe, expect, it } from 'vitest'

import type { PlanningDemandSummary } from '../types'
import {
  findPlanningDemandForAcquisition,
  getPlanningDemandMatchingAcquisitions,
  getPlanningDemandStatusDisplay,
} from './planningDemand'

function buildDemand(
  overrides: Partial<PlanningDemandSummary>,
): PlanningDemandSummary {
  return {
    run_order_id: 'order-1',
    demand_id: 'order-1::alpha::2026-03-08',
    canonical_target_id: 'Alpha',
    display_target_name: 'Alpha',
    demand_type: 'recurring_instance',
    template_id: 'tmpl-1',
    instance_key: '2026-03-08',
    requested_window_start: '2026-03-08T09:00:00Z',
    requested_window_end: '2026-03-08T11:00:00Z',
    local_date: '2026-03-08',
    priority: 1,
    feasibility_status: 'feasible',
    has_feasible_pass: true,
    matching_pass_count: 1,
    matching_pass_indexes: [0],
    first_pass_start: '2026-03-08T09:30:00Z',
    last_pass_end: '2026-03-08T10:00:00Z',
    best_pass_index: 0,
    best_pass_start: '2026-03-08T09:30:00Z',
    best_pass_end: '2026-03-08T09:35:00Z',
    best_max_elevation: 60,
    ...overrides,
  }
}

describe('planningDemand utilities', () => {
  it('surfaces limited status when a demand has matches but no feasible pass', () => {
    const demand = buildDemand({
      feasibility_status: 'no_opportunity',
      has_feasible_pass: false,
      matching_pass_count: 2,
      matching_pass_indexes: [0, 1],
      best_pass_index: null,
    })

    expect(getPlanningDemandStatusDisplay(demand)).toEqual({
      label: 'Limited',
      tone: 'amber',
    })
  })

  it('matches acquisitions to the correct recurring instance by requested window', () => {
    const march8 = buildDemand({})
    const march9 = buildDemand({
      demand_id: 'order-1::alpha::2026-03-09',
      instance_key: '2026-03-09',
      local_date: '2026-03-09',
      requested_window_start: '2026-03-09T09:00:00Z',
      requested_window_end: '2026-03-09T11:00:00Z',
      first_pass_start: '2026-03-09T09:15:00Z',
      last_pass_end: '2026-03-09T09:45:00Z',
      best_pass_start: '2026-03-09T09:15:00Z',
      best_pass_end: '2026-03-09T09:20:00Z',
    })

    const matched = findPlanningDemandForAcquisition({
      planningDemands: [march8, march9],
      acquisition: {
        id: 'acq-9',
        target_id: 'Alpha',
        start_time: '2026-03-09T09:18:00Z',
      },
    })

    expect(matched?.demand_id).toBe('order-1::alpha::2026-03-09')
  })

  it('filters demand acquisitions down to the selected recurring instance', () => {
    const march8 = buildDemand({})
    const acquisitions = [
      {
        id: 'acq-8',
        target_id: 'Alpha',
        start_time: '2026-03-08T09:20:00Z',
      },
      {
        id: 'acq-9',
        target_id: 'Alpha',
        start_time: '2026-03-09T09:20:00Z',
      },
    ]

    expect(getPlanningDemandMatchingAcquisitions(march8, acquisitions)).toEqual([acquisitions[0]])
  })
})
