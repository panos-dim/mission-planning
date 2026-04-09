import { describe, expect, it } from 'vitest'

import { MissionAnalyzeResponseSchema } from '../schemas'

describe('MissionAnalyzeResponseSchema', () => {
  it('preserves planning demand contract fields on feasibility responses', () => {
    const parsed = MissionAnalyzeResponseSchema.parse({
      success: true,
      data: {
        mission_data: {
          satellite_name: 'ICEYE-X53',
          mission_type: 'imaging',
          imaging_type: 'optical',
          start_time: '2026-04-02T00:00:00Z',
          end_time: '2026-04-03T00:00:00Z',
          elevation_mask: 10,
          total_passes: 1,
          targets: [
            {
              name: 'Alpha',
              latitude: 24.5,
              longitude: 54.3,
              priority: 1,
            },
          ],
          passes: [
            {
              target: 'Alpha',
              start_time: '2026-04-02T09:00:00Z',
              end_time: '2026-04-02T09:05:00Z',
              max_elevation_time: '2026-04-02T09:02:30Z',
              pass_type: 'ascending',
              max_elevation: 56,
            },
          ],
          run_order: {
            id: 'order-1',
            name: 'Order 1',
            order_type: 'one_time',
            target_count: 1,
            planning_demand_count: 1,
            recurrence: null,
          },
          planning_demands: [
            {
              run_order_id: 'order-1',
              demand_id: 'order-1::one_time::Alpha',
              canonical_target_id: 'Alpha',
              display_target_name: 'Alpha',
              demand_type: 'one_time',
              template_id: null,
              instance_key: null,
              requested_window_start: '2026-04-02T00:00:00Z',
              requested_window_end: '2026-04-03T00:00:00Z',
              local_date: null,
              priority: 1,
              feasibility_status: 'feasible',
              has_feasible_pass: true,
              matching_pass_count: 1,
              matching_pass_indexes: [0],
              first_pass_start: '2026-04-02T09:00:00Z',
              last_pass_end: '2026-04-02T09:05:00Z',
              best_pass_index: 0,
              best_pass_start: '2026-04-02T09:00:00Z',
              best_pass_end: '2026-04-02T09:05:00Z',
              best_max_elevation: 56,
            },
          ],
          planning_demand_summary: {
            run_order_id: 'order-1',
            total_demands: 1,
            feasible_demands: 1,
            infeasible_demands: 0,
            one_time_demands: 1,
            recurring_instance_demands: 0,
          },
        },
        czml_data: [],
      },
    })

    expect(parsed.data?.mission_data.run_order?.planning_demand_count).toBe(1)
    expect(parsed.data?.mission_data.planning_demands?.[0]?.demand_type).toBe('one_time')
    expect(parsed.data?.mission_data.planning_demand_summary?.feasible_demands).toBe(1)
  })
})
