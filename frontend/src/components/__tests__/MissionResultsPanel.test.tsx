import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MissionResultsPanel from '../MissionResultsPanel'
import type { MissionData } from '../../types'
import { useSelectionStore } from '../../store/selectionStore'

const { useMissionMock } = vi.hoisted(() => ({
  useMissionMock: vi.fn(),
}))

vi.mock('../../context/MissionContext', () => ({
  useMission: useMissionMock,
}))

function buildMissionData(
  targetNames: string[],
  options?: {
    acquisitionTimeWindow?: MissionData['acquisition_time_window']
    satelliteName?: MissionData['satellite_name']
    satellites?: MissionData['satellites']
    isConstellation?: MissionData['is_constellation']
    runOrder?: MissionData['run_order']
    planningDemands?: MissionData['planning_demands']
    planningDemandSummary?: MissionData['planning_demand_summary']
  },
): MissionData {
  const start = '2026-03-08T00:00:00Z'
  const end = '2026-03-11T00:00:00Z'

  return {
    satellite_name: options?.satelliteName ?? 'ICEYE-X53',
    satellites: options?.satellites,
    is_constellation: options?.isConstellation,
    mission_type: 'imaging',
    imaging_type: 'optical',
    start_time: start,
    end_time: end,
    elevation_mask: 10,
    total_passes: targetNames.length,
    acquisition_time_window: options?.acquisitionTimeWindow,
    targets: targetNames.map((name, index) => ({
      name,
      latitude: 24 + index,
      longitude: 54 + index,
      priority: 5,
    })),
    passes: targetNames.map((name, index) => ({
      target: name,
      start_time: `2026-03-08T0${index}:00:00Z`,
      end_time: `2026-03-08T0${index}:05:00Z`,
      max_elevation_time: `2026-03-08T0${index}:02:30Z`,
      pass_type: 'descending',
      max_elevation: 55,
    })),
    run_order: options?.runOrder,
    planning_demands: options?.planningDemands,
    planning_demand_summary: options?.planningDemandSummary,
  }
}

describe('MissionResultsPanel', () => {
  let missionData: MissionData | null
  let navigateToPassWindowMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    missionData = null
    navigateToPassWindowMock = vi.fn()
    useMissionMock.mockReset()
    useSelectionStore.getState().clearSelection()
    useMissionMock.mockImplementation(() => ({
      state: { missionData },
      navigateToPassWindow: navigateToPassWindowMock,
    }))
  })

  it('clears stale target filters after a fresh feasibility result arrives', async () => {
    const user = userEvent.setup()

    missionData = buildMissionData(['Alpha', 'Bravo'])
    const { rerender } = render(<MissionResultsPanel />)

    await user.click(screen.getByRole('button', { name: /Alpha/i }))
    expect(screen.getByRole('button', { name: /Show all/i })).toBeInTheDocument()

    missionData = buildMissionData(['Charlie'])
    rerender(<MissionResultsPanel />)

    expect(screen.queryByText(/No windows for selected targets/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show all/i })).not.toBeInTheDocument()
    expect(screen.getByText('1 windows')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Charlie/i })).toBeInTheDocument()
  })

  it('shows the active acquisition time window chip in results', () => {
    missionData = buildMissionData(['Alpha'], {
      acquisitionTimeWindow: {
        enabled: true,
        start_time: '15:00',
        end_time: '17:00',
        timezone: 'UTC',
        reference: 'off_nadir_time',
      },
    })

    render(<MissionResultsPanel />)

    expect(
      screen.getByLabelText('Global acquisition filter active: 15:00-17:00'),
    ).toBeInTheDocument()
  })

  it('shows the filtered empty-state message when the time window removes every opportunity', () => {
    missionData = buildMissionData([], {
      acquisitionTimeWindow: {
        enabled: true,
        start_time: '22:00',
        end_time: '02:00',
        timezone: 'UTC',
        reference: 'off_nadir_time',
      },
    })

    render(<MissionResultsPanel />)

    expect(
      screen.getByText('No opportunities found inside the selected acquisition time window.'),
    ).toBeInTheDocument()
  })

  it('shows constellation summary without the redundant timeline heading', () => {
    missionData = buildMissionData(['Alpha'], {
      satelliteName: null,
      isConstellation: true,
      satellites: [
        { id: 'sat-1', name: 'PLEIADES NEO 3' },
        { id: 'sat-2', name: 'PLEIADES NEO 4' },
      ],
    })

    render(<MissionResultsPanel />)

    expect(screen.queryByText(/^Timeline$/)).not.toBeInTheDocument()
    expect(screen.getByText('Satellites')).toBeInTheDocument()
    expect(screen.getByText('2 selected')).toBeInTheDocument()
  })

  it('shows demand-aware counts and groups recurring demands by day', () => {
    missionData = buildMissionData(['Alpha', 'Bravo'], {
      runOrder: {
        id: 'order-1',
        name: 'Daily Port Sweep',
        order_type: 'repeats',
        target_count: 2,
        planning_demand_count: 3,
        recurrence: {
          recurrence_type: 'daily',
          interval: 1,
          days_of_week: null,
          window_start_hhmm: '09:00',
          window_end_hhmm: '11:00',
          timezone_name: 'UTC',
          effective_start_date: '2026-03-08',
          effective_end_date: '2026-03-10',
        },
      },
      planningDemands: [
        {
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
          best_pass_index: 0,
        },
        {
          run_order_id: 'order-1',
          demand_id: 'order-1::alpha::2026-03-09',
          canonical_target_id: 'Alpha',
          display_target_name: 'Alpha',
          demand_type: 'recurring_instance',
          template_id: 'tmpl-1',
          instance_key: '2026-03-09',
          requested_window_start: '2026-03-09T09:00:00Z',
          requested_window_end: '2026-03-09T11:00:00Z',
          local_date: '2026-03-09',
          priority: 1,
          feasibility_status: 'no_opportunity',
          has_feasible_pass: false,
          matching_pass_count: 0,
          matching_pass_indexes: [],
          best_pass_index: null,
        },
        {
          run_order_id: 'order-1',
          demand_id: 'order-1::bravo::2026-03-09',
          canonical_target_id: 'Bravo',
          display_target_name: 'Bravo',
          demand_type: 'recurring_instance',
          template_id: 'tmpl-2',
          instance_key: '2026-03-09',
          requested_window_start: '2026-03-09T09:00:00Z',
          requested_window_end: '2026-03-09T11:00:00Z',
          local_date: '2026-03-09',
          priority: 2,
          feasibility_status: 'feasible',
          has_feasible_pass: true,
          matching_pass_count: 1,
          matching_pass_indexes: [1],
          best_pass_index: 1,
        },
      ],
      planningDemandSummary: {
        run_order_id: 'order-1',
        total_demands: 3,
        feasible_demands: 2,
        infeasible_demands: 1,
        one_time_demands: 0,
        recurring_instance_demands: 3,
      },
    })

    render(<MissionResultsPanel />)

    expect(screen.getByText('2/3 demands')).toBeInTheDocument()
    expect(screen.getByText('2/2 targets')).toBeInTheDocument()
    expect(screen.getByText('Demand Summary')).toBeInTheDocument()
    expect(screen.getAllByText('08-03-2026').length).toBeGreaterThan(0)
    expect(screen.getAllByText('09-03-2026').length).toBeGreaterThan(0)
    expect(screen.getByText('Daily Port Sweep')).toBeInTheDocument()
    expect(screen.getAllByText('Recurring').length).toBeGreaterThan(0)
    expect(screen.getByText('Master Timeline')).toBeInTheDocument()
  })

  it('clicking a demand row navigates to the best matching pass', async () => {
    const user = userEvent.setup()

    missionData = buildMissionData(['Alpha'], {
      runOrder: {
        id: 'order-1',
        name: 'Order 1',
        order_type: 'one_time',
        target_count: 1,
        planning_demand_count: 1,
        recurrence: null,
      },
      planningDemands: [
        {
          run_order_id: 'order-1',
          demand_id: 'order-1::one_time::Alpha',
          canonical_target_id: 'Alpha',
          display_target_name: 'Alpha',
          demand_type: 'one_time',
          template_id: null,
          instance_key: null,
          requested_window_start: '2026-03-08T09:00:00Z',
          requested_window_end: '2026-03-08T11:00:00Z',
          local_date: null,
          priority: 1,
          feasibility_status: 'feasible',
          has_feasible_pass: true,
          matching_pass_count: 1,
          matching_pass_indexes: [0],
          best_pass_index: 0,
        },
      ],
      planningDemandSummary: {
        run_order_id: 'order-1',
        total_demands: 1,
        feasible_demands: 1,
        infeasible_demands: 0,
        one_time_demands: 1,
        recurring_instance_demands: 0,
      },
    })

    render(<MissionResultsPanel />)

    await user.click(screen.getByRole('button', { name: 'Demand Alpha' }))

    expect(navigateToPassWindowMock).toHaveBeenCalledWith(0)
    expect(useSelectionStore.getState().selectedTargetId).toBe('Alpha')
    expect(useSelectionStore.getState().selectedPlanningDemandId).toBe('order-1::one_time::Alpha')
  })

  it('keeps no-opportunity demands inspectable even when there is no pass to focus', async () => {
    const user = userEvent.setup()

    missionData = buildMissionData(['Alpha'], {
      runOrder: {
        id: 'order-1',
        name: 'Order 1',
        order_type: 'repeats',
        target_count: 1,
        planning_demand_count: 1,
        recurrence: {
          recurrence_type: 'daily',
          interval: 1,
          days_of_week: null,
          window_start_hhmm: '09:00',
          window_end_hhmm: '11:00',
          timezone_name: 'UTC',
          effective_start_date: '2026-03-08',
          effective_end_date: '2026-03-10',
        },
      },
      planningDemands: [
        {
          run_order_id: 'order-1',
          demand_id: 'order-1::alpha::2026-03-09',
          canonical_target_id: 'Alpha',
          display_target_name: 'Alpha',
          demand_type: 'recurring_instance',
          template_id: 'tmpl-1',
          instance_key: '2026-03-09',
          requested_window_start: '2026-03-09T09:00:00Z',
          requested_window_end: '2026-03-09T11:00:00Z',
          local_date: '2026-03-09',
          priority: 1,
          feasibility_status: 'no_opportunity',
          has_feasible_pass: false,
          matching_pass_count: 0,
          matching_pass_indexes: [],
          best_pass_index: null,
        },
      ],
      planningDemandSummary: {
        run_order_id: 'order-1',
        total_demands: 1,
        feasible_demands: 0,
        infeasible_demands: 1,
        one_time_demands: 0,
        recurring_instance_demands: 1,
      },
    })

    render(<MissionResultsPanel />)

    const demandButton = screen.getByRole('button', { name: 'Demand Alpha on 09-03-2026' })
    expect(demandButton).toBeEnabled()

    await user.click(demandButton)

    expect(navigateToPassWindowMock).not.toHaveBeenCalled()
    expect(useSelectionStore.getState().selectedTargetId).toBe('Alpha')
    expect(useSelectionStore.getState().selectedPlanningDemandId).toBe('order-1::alpha::2026-03-09')
  })
})
