import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import MissionPlanning from '../MissionPlanning'
import { useExplorerStore } from '../../store/explorerStore'
import { usePlanningStore } from '../../store/planningStore'
import { useSelectionStore } from '../../store/selectionStore'
import { useSlewVisStore } from '../../store/slewVisStore'
import { useVisStore } from '../../store/visStore'
import type { AlgorithmResult, MissionData, PlanningResponse, ScheduledOpportunity } from '../../types'

const {
  useMissionMock,
  useOpportunitiesMock,
  useScheduleContextMock,
  getPlanningModeSelectionMock,
  createRepairPlanMock,
  planningScheduleMock,
  invalidateQueriesMock,
} = vi.hoisted(() => ({
  useMissionMock: vi.fn(),
  useOpportunitiesMock: vi.fn(),
  useScheduleContextMock: vi.fn(),
  getPlanningModeSelectionMock: vi.fn(),
  createRepairPlanMock: vi.fn(),
  planningScheduleMock: vi.fn(),
  invalidateQueriesMock: vi.fn(),
}))

vi.mock('../../context/MissionContext', () => ({
  useMission: useMissionMock,
}))

vi.mock('../../hooks/queries', () => ({
  useOpportunities: useOpportunitiesMock,
  useScheduleContext: useScheduleContextMock,
}))

vi.mock('../../api/scheduleApi', () => ({
  getPlanningModeSelection: getPlanningModeSelectionMock,
  createRepairPlan: createRepairPlanMock,
}))

vi.mock('../../api', () => ({
  planningApi: {
    schedule: planningScheduleMock,
  },
}))

vi.mock('../../lib/queryClient', () => ({
  queryClient: {
    invalidateQueries: invalidateQueriesMock,
  },
  queryKeys: {
    schedule: {
      all: ['schedule'],
    },
    planning: {
      opportunities: (workspaceId?: string) => ['planning', 'opportunities', workspaceId ?? ''],
    },
  },
}))

vi.mock('../../utils/debug', () => ({
  default: {
    section: vi.fn(),
    apiRequest: vi.fn(),
    apiResponse: vi.fn(),
    schedule: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('../ContextFilterBar', () => ({
  default: () => <div data-testid="context-filter-bar-stub" />,
}))

vi.mock('../ApplyConfirmationPanel', () => ({
  default: () => <div data-testid="apply-confirmation-panel-stub" />,
}))

vi.mock('../RepairDiffPanel', () => ({
  RepairDiffPanel: () => <div data-testid="repair-diff-panel-stub" />,
}))

vi.mock('cesium', () => ({
  JulianDate: {
    fromIso8601: vi.fn((value: string) => value),
  },
}))

function buildMissionData(): MissionData {
  return {
    satellite_name: 'ICEYE-X53',
    mission_type: 'imaging',
    imaging_type: 'optical',
    start_time: '2026-03-23T00:00:00Z',
    end_time: '2026-03-30T00:00:00Z',
    elevation_mask: 10,
    total_passes: 3,
    targets: [
      { name: 'Alpha', latitude: 25.2, longitude: 55.3, priority: 1 },
      { name: 'Bravo', latitude: 24.4, longitude: 54.7, priority: 3 },
      { name: 'Charlie', latitude: 26.1, longitude: 50.5, priority: 5 },
    ],
    passes: [
      {
        target: 'Alpha',
        start_time: '2026-03-23T01:00:00Z',
        end_time: '2026-03-23T01:05:00Z',
        max_elevation_time: '2026-03-23T01:02:30Z',
        pass_type: 'ascending',
        max_elevation: 58,
      },
    ],
  }
}

function buildScheduledOpportunity(targetId: string, opportunityId: string): ScheduledOpportunity {
  return {
    opportunity_id: opportunityId,
    satellite_id: 'SAT-1',
    target_id: targetId,
    start_time: '2026-03-23T02:00:00Z',
    end_time: '2026-03-23T02:05:00Z',
    delta_roll: 0,
    delta_pitch: 0,
    roll_angle: 2.5,
    pitch_angle: 0.5,
    maneuver_time: 12,
    slack_time: 34,
    value: 98,
    density: 1.2,
    incidence_angle: 17,
  }
}

function buildAlgorithmResult(targetId: string, opportunityId: string): AlgorithmResult {
  return {
    schedule: [buildScheduledOpportunity(targetId, opportunityId)],
    metrics: {
      algorithm: 'roll_pitch_best_fit',
      runtime_ms: 18,
      opportunities_evaluated: 5,
      opportunities_accepted: 1,
      opportunities_rejected: 4,
      total_value: 98,
      mean_value: 98,
      total_imaging_time_s: 1,
      total_maneuver_time_s: 12,
      schedule_span_s: 300,
      utilization: 0.1,
      mean_density: 1.2,
      median_density: 1.2,
      mean_incidence_deg: 17,
    },
    target_statistics: {
      total_targets: 3,
      targets_acquired: 1,
      targets_missing: 2,
      coverage_percentage: 33.3,
      acquired_target_ids: [targetId],
      missing_target_ids: ['Bravo', 'Charlie'].filter((name) => name !== targetId),
    },
    planner_summary: {
      target_acquisitions: [
        {
          target_id: targetId,
          satellite_id: 'SAT-1',
          start_time: '2026-03-23T02:00:00Z',
          end_time: '2026-03-23T02:05:00Z',
          action: 'added',
        },
      ],
      targets_not_scheduled: ['Alpha', 'Bravo', 'Charlie']
        .filter((name) => name !== targetId)
        .map((name) => ({
          target_id: name,
          reason: 'No feasible opportunity in current horizon',
        })),
      horizon: {
        start: '2026-03-23T00:00:00Z',
        end: '2026-03-30T00:00:00Z',
      },
      satellites_used: ['SAT-1'],
      total_targets_with_opportunities: 3,
      total_targets_covered: 1,
    },
  }
}

function buildPlanningResponse(targetId: string, opportunityId: string): PlanningResponse {
  return {
    success: true,
    message: 'Planning complete',
    results: {
      roll_pitch_best_fit: buildAlgorithmResult(targetId, opportunityId),
    },
  }
}

function buildRepairResponse() {
  return {
    success: true,
    message: 'Repair complete',
    planning_mode: 'repair' as const,
    existing_acquisitions: {
      count: 2,
      by_state: { committed: 2 },
      by_satellite: { 'SAT-1': 2 },
      acquisition_ids: ['acq-1', 'acq-2'],
      horizon_start: '2026-03-23T00:00:00Z',
      horizon_end: '2026-03-30T00:00:00Z',
    },
    fixed_count: 1,
    flex_count: 1,
    new_plan_items: [
      {
        opportunity_id: 'opp-repair-1',
        satellite_id: 'SAT-1',
        target_id: 'Alpha',
        start_time: '2026-03-23T03:00:00Z',
        end_time: '2026-03-23T03:05:00Z',
        roll_angle_deg: 1.2,
        pitch_angle_deg: 0.4,
        value: 99,
        quality_score: 0.94,
      },
    ],
    repair_diff: {
      kept: ['acq-1'],
      dropped: ['acq-2'],
      added: ['opp-repair-1'],
      moved: [],
      reason_summary: {},
      change_score: {
        num_changes: 2,
        percent_changed: 50,
      },
      change_log: {
        dropped: [],
        added: [],
        moved: [],
        kept_count: 1,
      },
    },
    metrics_before: {},
    metrics_after: {},
    metrics_comparison: {
      score_before: 48,
      score_after: 99,
      score_delta: 51,
      conflicts_before: 0,
      conflicts_after: 0,
      acquisition_count_before: 2,
      acquisition_count_after: 1,
    },
    conflicts_if_committed: [],
    commit_preview: {
      will_create: 1,
      will_conflict_with: 0,
      conflict_details: [],
      warnings: [],
    },
    algorithm_metrics: {},
    plan_id: 'repair-plan-1',
    schedule_context: {},
    planner_summary: {
      target_acquisitions: [
        {
          target_id: 'Alpha',
          satellite_id: 'SAT-1',
          start_time: '2026-03-23T03:00:00Z',
          end_time: '2026-03-23T03:05:00Z',
          action: 'added' as const,
        },
      ],
      targets_not_scheduled: [
        {
          target_id: 'Bravo',
          reason: 'Preserved locked acquisition blocks timing window',
        },
      ],
      horizon: {
        start: '2026-03-23T00:00:00Z',
        end: '2026-03-30T00:00:00Z',
      },
      satellites_used: ['SAT-1'],
      total_targets_with_opportunities: 3,
      total_targets_covered: 1,
    },
  }
}

describe('MissionPlanning', () => {
  beforeEach(() => {
    localStorage.clear()

    useMissionMock.mockReset()
    useOpportunitiesMock.mockReset()
    useScheduleContextMock.mockReset()
    getPlanningModeSelectionMock.mockReset()
    createRepairPlanMock.mockReset()
    planningScheduleMock.mockReset()
    invalidateQueriesMock.mockReset()

    invalidateQueriesMock.mockResolvedValue(undefined)

    useMissionMock.mockReturnValue({
      state: {
        missionData: buildMissionData(),
        activeWorkspace: 'ws-proof',
      },
    })

    useOpportunitiesMock.mockReturnValue({
      data: {
        opportunities: [
          {
            id: 'opp-available-1',
            satellite_id: 'SAT-1',
            target_id: 'Alpha',
            start_time: '2026-03-23T02:00:00Z',
            end_time: '2026-03-23T02:05:00Z',
            duration_seconds: 300,
          },
        ],
      },
    })

    useScheduleContextMock.mockReturnValue({
      data: {
        success: true,
        count: 2,
        by_state: { committed: 2 },
        by_satellite: { 'SAT-1': 2 },
        target_ids: ['Legacy-1', 'Legacy-2'],
        horizon: {
          start: '2026-03-23T00:00:00Z',
          end: '2026-03-30T00:00:00Z',
        },
      },
      isLoading: false,
      error: null,
    })

    usePlanningStore.getState().clearResults()
    useSlewVisStore.getState().reset()
    useSelectionStore.getState().clearSelection()
    useSelectionStore.getState().clearAllContextFilters()
    useExplorerStore.getState().clearRunHistory()
    useVisStore.setState({
      uiMode: 'developer',
      clockTime: null,
      requestedRightPanel: null,
    })
  })

  it('sends priority-first weights and from_scratch mode through the planner API', async () => {
    const user = userEvent.setup()

    getPlanningModeSelectionMock.mockResolvedValue({
      success: true,
      planning_mode: 'from_scratch',
      reason: 'No committed schedule exists, so a fresh baseline is required.',
      workspace_id: 'ws-proof',
      existing_acquisition_count: 0,
      new_target_count: 3,
      conflict_count: 0,
      current_target_ids: ['Alpha', 'Bravo', 'Charlie'],
      existing_target_ids: [],
      request_payload_hash: 'hash-from-scratch',
    })
    planningScheduleMock.mockResolvedValue(buildPlanningResponse('Alpha', 'opp-fs-1'))

    render(<MissionPlanning />)

    await user.click(screen.getByRole('button', { name: /^Priority$/i }))
    await user.click(screen.getByRole('button', { name: /generate mission plan/i }))

    await waitFor(() => {
      expect(getPlanningModeSelectionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          workspace_id: 'ws-proof',
          weight_priority: 100,
          weight_geometry: 0,
          weight_timing: 0,
          horizon_from: expect.any(String),
          horizon_to: expect.any(String),
        }),
      )
    })

    await waitFor(() => {
      expect(planningScheduleMock).toHaveBeenCalledWith(
        expect.objectContaining({
          algorithms: ['roll_pitch_best_fit'],
          mode: 'from_scratch',
          workspace_id: 'ws-proof',
          weight_priority: 100,
          weight_geometry: 0,
          weight_timing: 0,
          weight_preset: 'priority_first',
        }),
      )
    })

    expect(createRepairPlanMock).not.toHaveBeenCalled()
    expect(await screen.findByText(/New Schedule/i)).toBeInTheDocument()
    expect(screen.getByText(/fresh baseline is required/i)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /^Next$/i })).toBeInTheDocument()
  })

  it('sends quality-first weights and incremental mode through the planner API', async () => {
    const user = userEvent.setup()

    getPlanningModeSelectionMock.mockResolvedValue({
      success: true,
      planning_mode: 'incremental',
      reason: 'Current scoring weights favor additive scheduling without disturbing the baseline.',
      workspace_id: 'ws-proof',
      existing_acquisition_count: 2,
      new_target_count: 1,
      conflict_count: 0,
      current_target_ids: ['Alpha', 'Bravo', 'Charlie'],
      existing_target_ids: ['Legacy-1'],
      request_payload_hash: 'hash-incremental',
    })
    planningScheduleMock.mockResolvedValue(buildPlanningResponse('Bravo', 'opp-inc-1'))

    render(<MissionPlanning />)

    await user.click(screen.getByRole('button', { name: /^Quality$/i }))
    await user.click(screen.getByRole('button', { name: /generate mission plan/i }))

    await waitFor(() => {
      expect(getPlanningModeSelectionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          workspace_id: 'ws-proof',
          weight_priority: 0,
          weight_geometry: 100,
          weight_timing: 0,
          horizon_from: expect.any(String),
          horizon_to: expect.any(String),
        }),
      )
    })

    await waitFor(() => {
      expect(planningScheduleMock).toHaveBeenCalledWith(
        expect.objectContaining({
          algorithms: ['roll_pitch_best_fit'],
          mode: 'incremental',
          workspace_id: 'ws-proof',
          weight_priority: 0,
          weight_geometry: 100,
          weight_timing: 0,
          weight_preset: 'quality_first',
        }),
      )
    })

    expect(createRepairPlanMock).not.toHaveBeenCalled()
    expect(await screen.findByText(/Incremental Mode/i)).toBeInTheDocument()
    expect(
      screen.getByText(/favor additive scheduling without disturbing the baseline/i),
    ).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /^Next$/i })).toBeInTheDocument()
  })

  it('sends urgent weights and repair mode through the repair API with per-target priorities', async () => {
    const user = userEvent.setup()

    getPlanningModeSelectionMock.mockResolvedValue({
      success: true,
      planning_mode: 'repair',
      reason: 'Urgent timing weight and existing locked work require schedule repair.',
      workspace_id: 'ws-proof',
      existing_acquisition_count: 2,
      new_target_count: 1,
      conflict_count: 1,
      current_target_ids: ['Alpha', 'Bravo', 'Charlie'],
      existing_target_ids: ['Legacy-1'],
      request_payload_hash: 'hash-repair',
    })
    createRepairPlanMock.mockResolvedValue(buildRepairResponse())

    render(<MissionPlanning />)

    await user.click(screen.getByRole('button', { name: /^Urgent$/i }))
    await user.click(screen.getByRole('button', { name: /generate mission plan/i }))

    await waitFor(() => {
      expect(getPlanningModeSelectionMock).toHaveBeenCalledWith(
        expect.objectContaining({
          workspace_id: 'ws-proof',
          weight_priority: 0,
          weight_geometry: 0,
          weight_timing: 100,
          horizon_from: expect.any(String),
          horizon_to: expect.any(String),
        }),
      )
    })

    await waitFor(() => {
      expect(createRepairPlanMock).toHaveBeenCalledWith(
        expect.objectContaining({
          planning_mode: 'repair',
          workspace_id: 'ws-proof',
          include_tentative: false,
          target_priorities: {
            Alpha: 1,
            Bravo: 3,
            Charlie: 5,
          },
          weight_priority: 0,
          weight_geometry: 0,
          weight_timing: 100,
          weight_preset: 'urgent',
        }),
      )
    })

    expect(planningScheduleMock).not.toHaveBeenCalled()
    expect(await screen.findByText(/Repair Mode/i)).toBeInTheDocument()
    expect(screen.getByText(/require schedule repair/i)).toBeInTheDocument()
    expect(screen.getByTestId('repair-diff-panel-stub')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /^Next$/i })).toBeInTheDocument()
  })
})
