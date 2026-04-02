import { writeFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const demoSlowMs = Number(process.env.PW_DEMO_SLOW_MS ?? '0')

type SimTarget = {
  id: string
  name: string
  latitude: number
  longitude: number
  priority: number
  score: number
}

type SimAcquisition = {
  id: string
  target_id: string
  satellite_id: string
  start_time: string
  end_time: string
  state: 'committed'
  lock_level: 'none'
}

type ComputedPlan = {
  mode: 'from_scratch' | 'incremental' | 'repair'
  desiredSize: number
  beforeCount: number
  afterCount: number
  kept: SimAcquisition[]
  added: SimAcquisition[]
  dropped: SimAcquisition[]
  moved: Array<{
    id: string
    target_id: string
    satellite_id: string
    from_start: string
    from_end: string
    to_start: string
    to_end: string
  }>
}

type IterationSummary = {
  iteration: number
  added_targets_in_request: number
  current_target_count: number
  mode: ComputedPlan['mode']
  desired_size: number
  before_count: number
  after_count: number
  kept: number
  added: number
  dropped: number
  moved: number
}

type SimulationState = {
  iteration: number
  currentTargets: SimTarget[]
  nextTargetIndex: number
  addedSinceLastPlan: number
  committed: SimAcquisition[]
  pendingPlan: ComputedPlan | null
  history: IterationSummary[]
}

const workspaceId = 'ws-weekly-ops'
const workspaceName = 'Weekly Operations Simulation'
const additionPattern = [3, 1, 4, 2, 5, 1, 3, 2, 4, 1, 5, 2]
const checkpointIterations = new Set([0, 4, 8, 12])

const workspaceSummary = {
  id: workspaceId,
  name: workspaceName,
  created_at: '2026-03-24T00:00:00Z',
  updated_at: '2026-03-24T00:00:00Z',
  mission_mode: 'planner',
  time_window_start: '2026-03-24T00:00:00Z',
  time_window_end: '2026-03-31T00:00:00Z',
  satellites_count: 1,
  targets_count: 50,
  last_run_status: 'ready',
  schema_version: '1.0',
  app_version: 'test',
}

test.use({
  launchOptions: {
    slowMo: demoSlowMs > 0 ? demoSlowMs : 0,
  },
})

if (demoSlowMs > 0) {
  test.setTimeout(300_000)
}

const managedSatellitesResponse = {
  success: true,
  satellites: [
    {
      id: 'SAT-1',
      name: 'ICEYE-X53',
      line1: '1 00005U 58002B   24084.25000000  .00000023  00000-0  28098-4 0  9991',
      line2: '2 00005  34.2500  48.1200 1843000 331.7600  19.3200 10.82419157413667',
      imaging_type: 'optical',
      sensor_fov_half_angle_deg: 15,
      satellite_agility: 1.5,
      description: 'Weekly simulation managed satellite',
      active: true,
      created_at: '2026-03-24T00:00:00Z',
      tle_updated_at: '2026-03-24T00:00:00Z',
      capabilities: ['optical'],
    },
  ],
  count: 1,
}

function generateTarget(index: number): SimTarget {
  const priority = [3, 4, 2, 5, 1][index % 5]
  const lateArrivalBonus = index >= 50 ? (index % 3 === 0 ? 55 : index % 2 === 0 ? 22 : -8) : 0
  return {
    id: `T${String(index + 1).padStart(2, '0')}`,
    name: `AOI-${String(index + 1).padStart(2, '0')}`,
    latitude: 18 + ((index * 3.4) % 24),
    longitude: 32 + ((index * 6.1) % 34),
    priority,
    score: 220 - priority * 24 - index * 1.8 + lateArrivalBonus,
  }
}

function generateTargetPool(count: number): SimTarget[] {
  return Array.from({ length: count }, (_, index) => generateTarget(index))
}

function desiredSizeForIteration(iteration: number): number {
  return Math.min(18 + iteration, 29)
}

function buildTimeForSlot(slotIndex: number): { start: string; end: string } {
  const start = new Date(Date.UTC(2026, 2, 24, 1, 0, 0))
  start.setUTCMinutes(start.getUTCMinutes() + slotIndex * 210)
  const end = new Date(start)
  end.setUTCMinutes(end.getUTCMinutes() + 5)
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  }
}

function buildAcquisitionForTarget(target: SimTarget, slotIndex: number): SimAcquisition {
  const { start, end } = buildTimeForSlot(slotIndex)
  return {
    id: `acq-${target.id.toLowerCase()}`,
    target_id: target.name,
    satellite_id: 'SAT-1',
    start_time: start,
    end_time: end,
    state: 'committed',
    lock_level: 'none',
  }
}

function buildWorkspaceData(targets: SimTarget[]) {
  return {
    ...workspaceSummary,
    targets_count: targets.length,
    scenario_config: {
      satellites: [
        {
          id: 'SAT-1',
          name: 'ICEYE-X53',
          color: '#3B82F6',
          tle: {
            line1: '1 00005U 58002B   24084.25000000  .00000023  00000-0  28098-4 0  9991',
            line2: '2 00005  34.2500  48.1200 1843000 331.7600  19.3200 10.82419157413667',
          },
        },
      ],
      targets: targets.map((target) => ({
        name: target.name,
        latitude: target.latitude,
        longitude: target.longitude,
        priority: target.priority,
        color: '#3B82F6',
      })),
      constraints: {
        elevation_mask_deg: 45,
        max_spacecraft_roll_deg: 45,
      },
    },
    analysis_state: {
      mission_data: {
        satellite_name: 'ICEYE-X53',
        satellites: [{ id: 'SAT-1', name: 'ICEYE-X53', color: '#3B82F6' }],
        is_constellation: false,
        mission_type: 'imaging',
        imaging_type: 'optical',
        start_time: '2026-03-24T00:00:00Z',
        end_time: '2026-03-31T00:00:00Z',
        elevation_mask: 45,
        sensor_fov_half_angle_deg: 15,
        max_spacecraft_roll_deg: 45,
        total_passes: targets.length,
        targets: targets.map((target) => ({
          name: target.name,
          latitude: target.latitude,
          longitude: target.longitude,
          priority: target.priority,
          color: '#3B82F6',
        })),
        passes: targets.slice(0, 26).map((target, index) => ({
          target: target.name,
          satellite_name: 'ICEYE-X53',
          satellite_id: 'SAT-1',
          start_time: buildTimeForSlot(index).start,
          end_time: buildTimeForSlot(index).end,
          max_elevation: 58 - (index % 10),
          max_elevation_time: buildTimeForSlot(index).start,
          pass_type: 'ascending',
          incidence_angle_deg: 12 + (index % 7),
        })),
      },
    },
    planning_state: null,
    orders_state: { orders: [] },
    ui_state: null,
    czml_data: [{ id: 'document', name: 'Weekly Operator Simulation' }],
  }
}

function buildOpportunitiesResponse(targets: SimTarget[]) {
  return {
    success: true,
    opportunities: targets.map((target, index) => ({
      id: `opp-${target.id.toLowerCase()}`,
      satellite_id: 'SAT-1',
      target_id: target.name,
      start_time: buildTimeForSlot(index).start,
      end_time: buildTimeForSlot(index).end,
      duration_seconds: 300,
      incidence_angle: 10 + (index % 10),
      value: Math.max(10, Math.round(target.score)),
      priority: target.priority,
    })),
    count: targets.length,
  }
}

function computePlan(state: SimulationState): ComputedPlan {
  const desiredSize = desiredSizeForIteration(state.iteration)
  const rankedTargets = [...state.currentTargets].sort((a, b) => b.score - a.score)
  const selectedTargets = rankedTargets.slice(0, desiredSize)
  const selectedMap = new Map(selectedTargets.map((target, index) => [target.name, index]))
  const selectedNames = new Set(selectedTargets.map((target) => target.name))
  const committedByTarget = new Map(state.committed.map((item) => [item.target_id, item]))

  const kept: SimAcquisition[] = []
  const dropped: SimAcquisition[] = []

  for (const acquisition of state.committed) {
    if (selectedNames.has(acquisition.target_id)) {
      kept.push(acquisition)
    } else {
      dropped.push(acquisition)
    }
  }

  const added: SimAcquisition[] = []
  for (const target of selectedTargets) {
    if (!committedByTarget.has(target.name)) {
      added.push(buildAcquisitionForTarget(target, selectedMap.get(target.name) ?? 0))
    }
  }

  const moved =
    state.iteration >= 6 && kept.length > 0 && (added.length > 0 || dropped.length > 0)
      ? (() => {
          const candidate = kept[kept.length - 1]
          const fromStart = new Date(candidate.start_time)
          const fromEnd = new Date(candidate.end_time)
          const toStart = new Date(fromStart)
          const toEnd = new Date(fromEnd)
          toStart.setUTCMinutes(toStart.getUTCMinutes() + 30)
          toEnd.setUTCMinutes(toEnd.getUTCMinutes() + 30)
          return [
            {
              id: candidate.id,
              target_id: candidate.target_id,
              satellite_id: candidate.satellite_id,
              from_start: candidate.start_time,
              from_end: candidate.end_time,
              to_start: toStart.toISOString(),
              to_end: toEnd.toISOString(),
            },
          ]
        })()
      : []

  const afterMap = new Map<string, SimAcquisition>()
  for (const target of selectedTargets) {
    const existing = committedByTarget.get(target.name)
    if (existing) {
      const move = moved.find((item) => item.target_id === target.name)
      afterMap.set(
        target.name,
        move
          ? {
              ...existing,
              start_time: move.to_start,
              end_time: move.to_end,
            }
          : existing,
      )
    } else {
      afterMap.set(target.name, buildAcquisitionForTarget(target, selectedMap.get(target.name) ?? 0))
    }
  }

  const afterCount = afterMap.size

  return {
    mode:
      state.committed.length === 0
        ? 'from_scratch'
        : dropped.length > 0 || moved.length > 0
          ? 'repair'
          : 'incremental',
    desiredSize,
    beforeCount: state.committed.length,
    afterCount,
    kept,
    added,
    dropped,
    moved,
  }
}

function buildPlanningScheduleResponse(
  state: SimulationState,
  plan: ComputedPlan,
) {
  return {
    success: true,
    message: 'Planning complete',
    results: {
      roll_pitch_best_fit: {
        schedule: plan.added.map((item, index) => ({
          opportunity_id: `opp-${item.id}`,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start_time: item.start_time,
          end_time: item.end_time,
          delta_roll: 0.5 + index * 0.2,
          delta_pitch: 0,
          roll_angle: 2.2 + index * 0.3,
          pitch_angle: 0.2,
          maneuver_time: 12 + index,
          slack_time: 35,
          value: 90 + index,
          density: 1.0,
          incidence_angle: 12 + index,
        })),
        metrics: {
          algorithm: 'roll_pitch_best_fit',
          runtime_ms: 30 + state.iteration,
          opportunities_evaluated: state.currentTargets.length,
          opportunities_accepted: plan.added.length,
          opportunities_rejected: Math.max(0, state.currentTargets.length - plan.afterCount),
          total_value: plan.added.length * 95,
          mean_value: plan.added.length > 0 ? 95 : 0,
          total_imaging_time_s: plan.added.length,
          total_maneuver_time_s: plan.added.length * 10,
          schedule_span_s: plan.afterCount * 300,
          utilization: Math.min(1, plan.afterCount / 30),
          mean_density: 1,
          median_density: 1,
          mean_incidence_deg: 15,
        },
        target_statistics: {
          total_targets: state.currentTargets.length,
          targets_acquired: plan.afterCount,
          targets_missing: state.currentTargets.length - plan.afterCount,
          coverage_percentage: (plan.afterCount / state.currentTargets.length) * 100,
          acquired_target_ids: plan.added.map((item) => item.target_id),
          missing_target_ids: [],
        },
        planner_summary: {
          target_acquisitions: plan.added.map((item) => ({
            target_id: item.target_id,
            satellite_id: item.satellite_id,
            start_time: item.start_time,
            end_time: item.end_time,
            action: 'added' as const,
          })),
          targets_not_scheduled: [],
          horizon: {
            start: '2026-03-24T00:00:00Z',
            end: '2026-03-31T00:00:00Z',
          },
          satellites_used: ['SAT-1'],
          total_targets_with_opportunities: state.currentTargets.length,
          total_targets_covered: plan.afterCount,
        },
      },
    },
  }
}

function buildRepairResponse(state: SimulationState, plan: ComputedPlan) {
  const moved = plan.moved
  const moveWarnings =
    moved.length > 0
      ? [
          {
            type: 'slew_infeasible',
            severity: 'warning',
            description: `${moved[0].target_id} shifted later to keep the insertion feasible.`,
            acquisition_ids: [moved[0].id, ...(plan.added[0] ? [plan.added[0].id] : [])],
            involves_new_item: true,
            reason: 'The current sequence required one acquisition to move later in the week.',
            details: {
              available_time_s: 180,
              recommended_gap_s: 480,
            },
          },
        ]
      : []

  return {
    success: true,
    message: 'Repair complete',
    planning_mode: 'repair' as const,
    existing_acquisitions: {
      count: plan.beforeCount,
      by_state: { committed: plan.beforeCount },
      by_satellite: { 'SAT-1': plan.beforeCount },
      acquisition_ids: state.committed.map((item) => item.id),
      horizon_start: '2026-03-24T00:00:00Z',
      horizon_end: '2026-03-31T00:00:00Z',
    },
    fixed_count: 0,
    flex_count: plan.beforeCount,
    new_plan_items: plan.added.map((item) => ({
      opportunity_id: `opp-${item.id}`,
      satellite_id: item.satellite_id,
      target_id: item.target_id,
      start_time: item.start_time,
      end_time: item.end_time,
      roll_angle_deg: 1.2,
      pitch_angle_deg: 0.2,
      value: 99,
      quality_score: 0.97,
    })),
    repair_diff: {
      kept: plan.kept.map((item) => item.id),
      dropped: plan.dropped.map((item) => item.id),
      added: plan.added.map((item) => `opp-${item.id}`),
      moved: plan.moved.map((item) => ({
        id: item.id,
        from_start: item.from_start,
        from_end: item.from_end,
        to_start: item.to_start,
        to_end: item.to_end,
      })),
      reason_summary: {
        dropped: plan.dropped.map((item) => ({
          id: item.id,
          reason: 'Lower-value work removed to admit higher-priority arrivals.',
        })),
        moved: plan.moved.map((item) => ({
          id: item.id,
          reason: 'Shifted later to preserve maneuver feasibility.',
        })),
      },
      change_score: {
        num_changes: plan.added.length + plan.dropped.length + plan.moved.length,
        percent_changed:
          plan.beforeCount > 0
            ? ((plan.added.length + plan.dropped.length + plan.moved.length) / plan.beforeCount) *
              100
            : 0,
      },
      change_log: {
        kept_count: plan.kept.length,
        added: plan.added.map((item) => ({
          acquisition_id: `opp-${item.id}`,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start: item.start_time,
          end: item.end_time,
          reason_code: 'higher_value',
          reason_text: 'Higher-priority work inserted into the weekly plan.',
          replaces: plan.dropped.map((entry) => entry.id),
          value: 99,
        })),
        moved: plan.moved.map((item) => ({
          acquisition_id: item.id,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          from_start: item.from_start,
          from_end: item.from_end,
          to_start: item.to_start,
          to_end: item.to_end,
          reason_code: 'slew_feasible',
          reason_text: 'Shifted later to keep the insertion feasible.',
        })),
        dropped: plan.dropped.map((item) => ({
          acquisition_id: item.id,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start: item.start_time,
          end: item.end_time,
          reason_code: 'higher_value',
          reason_text: 'Removed from the weekly plan to make room for higher-value work.',
          replaced_by: plan.added.map((entry) => `opp-${entry.id}`),
        })),
      },
    },
    metrics_before: {},
    metrics_after: {},
    metrics_comparison: {
      score_before: plan.beforeCount * 90,
      score_after: plan.afterCount * 94,
      score_delta: plan.afterCount * 94 - plan.beforeCount * 90,
      conflicts_before: 0,
      conflicts_after: moveWarnings.length,
      acquisition_count_before: plan.beforeCount,
      acquisition_count_after: plan.afterCount,
    },
    conflicts_if_committed: moveWarnings,
    commit_preview: {
      will_create: plan.added.length,
      will_conflict_with: moveWarnings.length,
      conflict_details: [],
      warnings:
        moveWarnings.length > 0 ? ['One acquisition is being shifted later in the week.'] : [],
    },
    algorithm_metrics: {},
    plan_id: `weekly-repair-${state.iteration + 1}`,
    schedule_context: {},
    planner_summary: {
      target_acquisitions: [
        ...plan.kept.slice(0, 3).map((item) => ({
          target_id: item.target_id,
          satellite_id: item.satellite_id,
          start_time: item.start_time,
          end_time: item.end_time,
          action: 'kept' as const,
        })),
        ...plan.added.slice(0, 3).map((item) => ({
          target_id: item.target_id,
          satellite_id: item.satellite_id,
          start_time: item.start_time,
          end_time: item.end_time,
          action: 'added' as const,
        })),
      ],
      targets_not_scheduled: [],
      horizon: {
        start: '2026-03-24T00:00:00Z',
        end: '2026-03-31T00:00:00Z',
      },
      satellites_used: ['SAT-1'],
      total_targets_with_opportunities: state.currentTargets.length,
      total_targets_covered: plan.afterCount,
    },
  }
}

function applyPlanToState(state: SimulationState, plan: ComputedPlan) {
  const afterMap = new Map<string, SimAcquisition>()

  for (const kept of plan.kept) {
    const move = plan.moved.find((item) => item.id === kept.id)
    afterMap.set(
      kept.target_id,
      move
        ? {
            ...kept,
            start_time: move.to_start,
            end_time: move.to_end,
          }
        : kept,
    )
  }

  for (const added of plan.added) {
    afterMap.set(added.target_id, added)
  }

  state.committed = Array.from(afterMap.values()).sort((a, b) =>
    a.start_time.localeCompare(b.start_time),
  )
  state.history.push({
    iteration: state.iteration + 1,
    added_targets_in_request: state.addedSinceLastPlan,
    current_target_count: state.currentTargets.length,
    mode: plan.mode,
    desired_size: plan.desiredSize,
    before_count: plan.beforeCount,
    after_count: plan.afterCount,
    kept: plan.kept.length,
    added: plan.added.length,
    dropped: plan.dropped.length,
    moved: plan.moved.length,
  })
  state.iteration += 1
  state.addedSinceLastPlan = 0
  state.pendingPlan = null
}

function advanceTargets(state: SimulationState, pool: SimTarget[], addCount: number) {
  const nextTargets = pool.slice(state.nextTargetIndex, state.nextTargetIndex + addCount)
  state.currentTargets = [...state.currentTargets, ...nextTargets]
  state.nextTargetIndex += nextTargets.length
  state.addedSinceLastPlan = nextTargets.length
}

async function dismissCesiumErrorIfPresent(page: Page) {
  const okButton = page.getByRole('button', { name: 'OK' })
  if (await okButton.isVisible().catch(() => false)) {
    await okButton.click()
  }
}

async function demoPause(page: Page, multiplier = 1) {
  if (demoSlowMs > 0) {
    await page.waitForTimeout(demoSlowMs * multiplier)
  }
}

async function waitForVisible(locator: ReturnType<Page['locator']>, timeoutMs: number) {
  try {
    await locator.waitFor({ state: 'visible', timeout: timeoutMs })
    return true
  } catch {
    return false
  }
}

async function openLeftPanel(page: Page, panelName: string, readyLocator: ReturnType<Page['locator']>) {
  const panelButton = page.getByRole('button', { name: panelName, exact: true })

  await dismissCesiumErrorIfPresent(page)
  await panelButton.click()

  if (!(await waitForVisible(readyLocator, 1500))) {
    await dismissCesiumErrorIfPresent(page)
    await panelButton.click()
  }

  await expect(readyLocator).toBeVisible({ timeout: 10000 })
}

async function loadWorkspace(page: Page) {
  await openLeftPanel(page, 'Workspaces', page.getByText('Workspace Library'))

  await expect(page.getByRole('heading', { name: workspaceName, exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Load', exact: true }).click()

  await expect(page.getByText('Workspace loaded successfully')).toBeVisible()
  await expect(page.locator('div[title^="Selected workspace:"]')).toContainText(workspaceName)
  await demoPause(page, 2)
}

async function openApplyPage(
  page: Page,
  planKind: 'schedule' | 'repair',
) {
  await openLeftPanel(page, 'Planning', page.getByRole('button', { name: /Generate Mission Plan/i }))

  const waits = [
    page.waitForResponse((response) => response.url().includes('/api/v1/schedule/mode-selection')),
    page.waitForResponse((response) =>
      planKind === 'repair'
        ? response.url().includes('/api/v1/schedule/repair')
        : response.url().includes('/api/v1/planning/schedule'),
    ),
  ]

  await page.getByRole('button', { name: /Generate Mission Plan/i }).click()
  const [modeResponse, planResponse] = await Promise.all(waits)
  expect(modeResponse.ok()).toBeTruthy()
  expect(planResponse.ok()).toBeTruthy()

  await expect(page.getByRole('button', { name: /^Review Plan$/i })).toBeVisible()
  await demoPause(page, 2)
  await page.getByRole('button', { name: /^Review Plan$/i }).click()
  await demoPause(page, 2)
}

async function applyPlan(page: Page, planKind: 'direct' | 'repair') {
  const commitResponsePromise = page.waitForResponse((response) =>
    planKind === 'repair'
      ? response.url().includes('/api/v1/schedule/repair/commit')
      : response.url().includes('/api/v1/schedule/commit/direct') &&
        !response.url().includes('/api/v1/schedule/commit/direct/preview'),
  )
  await page.getByRole('button', { name: /Apply (Plan|Anyway)/i }).click()
  const commitResponse = await commitResponsePromise
  expect(commitResponse.ok()).toBeTruthy()
  await expect(page.getByRole('heading', { name: 'Schedule', exact: true }).first()).toBeVisible()
  await demoPause(page, 2)
}

async function expectApplyStats(
  page: Page,
  expected: [acquisitions: string, satellites: string, targets: string],
) {
  const statValues = page.locator(
    'div.grid.grid-cols-3.gap-2 .text-lg.font-bold.text-white.leading-tight',
  )
  await expect(statValues).toHaveCount(3)
  await expect(statValues.nth(0)).toHaveText(expected[0])
  await expect(statValues.nth(1)).toHaveText(expected[1])
  await expect(statValues.nth(2)).toHaveText(expected[2])
}

async function mockSimulationApis(page: Page, state: SimulationState, pool: SimTarget[]) {
  const appliedCommitSignatures = new Set<string>()

  await page.route('**/api/v1/workspaces?**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        workspaces: [workspaceSummary],
        total: 1,
      },
    })
  })

  await page.route(`**/api/v1/workspaces/${workspaceId}?**`, async (route) => {
    await route.fulfill({
      json: {
        success: true,
        workspace: buildWorkspaceData(state.currentTargets),
      },
    })
  })

  await page.route('**/api/v1/satellites**', async (route) => {
    await route.fulfill({ json: managedSatellitesResponse })
  })

  await page.route('**/api/v1/config/sar-modes**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        modes: {},
      },
    })
  })

  await page.route('**/api/v1/schedule/conflicts**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        conflicts: [],
        summary: {
          total: 0,
          by_type: {},
          by_severity: {},
        },
      },
    })
  })

  await page.route('**/api/v1/planning/opportunities**', async (route) => {
    await route.fulfill({ json: buildOpportunitiesResponse(state.currentTargets) })
  })

  await page.route('**/api/v1/schedule/horizon**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        horizon: {
          start: '2026-03-24T00:00:00Z',
          end: '2026-03-31T00:00:00Z',
          freeze_cutoff: '2026-03-24T00:00:00Z',
        },
        acquisitions: state.committed,
        statistics: {
          total_acquisitions: state.committed.length,
          by_state: state.committed.length > 0 ? { committed: state.committed.length } : {},
          by_satellite: state.committed.length > 0 ? { 'SAT-1': state.committed.length } : {},
        },
      },
    })
  })

  await page.route('**/api/v1/schedule/master**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        zoom: 'detail',
        total: state.committed.length,
        items: state.committed.map((item) => ({
          id: item.id,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start_time: item.start_time,
          end_time: item.end_time,
          state: item.state,
          lock_level: item.lock_level,
          workspace_id: workspaceId,
          mode: 'Optical',
        })),
        buckets: [],
        t_start: '2026-03-24T00:00:00Z',
        t_end: '2026-03-31T00:00:00Z',
      },
    })
  })

  await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
    const plan = computePlan(state)
    state.pendingPlan = plan

    await route.fulfill({
      json: {
        success: true,
        planning_mode: plan.mode,
        reason:
          plan.mode === 'from_scratch'
            ? 'No existing weekly schedule found. Building the initial baseline.'
            : plan.mode === 'incremental'
              ? 'Weekly schedule remains stable. Appending new requests incrementally.'
              : 'Higher-priority arrivals require a repair of the active weekly schedule.',
        workspace_id: workspaceId,
        existing_acquisition_count: plan.beforeCount,
        new_target_count: state.addedSinceLastPlan,
        conflict_count: plan.mode === 'repair' ? plan.moved.length : 0,
        current_target_ids: state.currentTargets.map((target) => target.name),
        existing_target_ids: state.committed.map((item) => item.target_id),
        request_payload_hash: `weekly-ops-${state.iteration + 1}`,
      },
    })
  })

  await page.route('**/api/v1/planning/schedule**', async (route) => {
    const plan = state.pendingPlan
    if (!plan || plan.mode === 'repair') {
      await route.fulfill({ status: 500, json: { detail: 'Unexpected planning schedule call' } })
      return
    }
    await route.fulfill({ json: buildPlanningScheduleResponse(state, plan) })
  })

  await page.route('**/api/v1/schedule/repair**', async (route) => {
    const plan = state.pendingPlan
    if (!plan || plan.mode !== 'repair') {
      await route.fulfill({ status: 500, json: { detail: 'Unexpected repair call' } })
      return
    }
    await route.fulfill({ json: buildRepairResponse(state, plan) })
  })

  await page.route('**/api/v1/schedule/commit/direct/preview**', async (route) => {
    const requestBody = route.request().postDataJSON() as { items?: unknown[] }
    const itemCount = Array.isArray(requestBody.items) ? requestBody.items.length : 0
    await route.fulfill({
      json: {
        success: true,
        message: 'Preview ready',
        new_items_count: itemCount,
        conflicts_count: 0,
        conflicts: [],
        warnings: [],
      },
    })
  })

  await page.route('**/api/v1/schedule/commit/direct**', async (route) => {
    const plan = state.pendingPlan
    if (!plan) {
      await route.fulfill({
        json: {
          success: true,
          message: 'Duplicate commit ignored',
          plan_id: `weekly-direct-noop-${state.iteration + 1}`,
          committed: 0,
          acquisition_ids: [],
        },
      })
      return
    }
    const signature = route.request().postData() ?? `direct-${state.iteration}`
    if (!appliedCommitSignatures.has(signature)) {
      appliedCommitSignatures.add(signature)
      applyPlanToState(state, plan)
    }
    await route.fulfill({
      json: {
        success: true,
        message: 'Committed successfully',
        plan_id: `weekly-direct-${state.iteration + 1}`,
        committed: plan.added.length,
        acquisition_ids: plan.added.map((item) => item.id),
      },
    })
  })

  await page.route('**/api/v1/schedule/repair/commit**', async (route) => {
    const plan = state.pendingPlan
    if (!plan) {
      await route.fulfill({
        json: {
          success: true,
          message: 'Duplicate repair commit ignored',
          plan_id: `weekly-repair-noop-${state.iteration + 1}`,
          committed: 0,
          dropped: 0,
          audit_log_id: `audit-weekly-noop-${state.iteration + 1}`,
          conflicts_after: 0,
          warnings: [],
          acquisition_ids: [],
        },
      })
      return
    }
    const signature = route.request().postData() ?? `repair-${state.iteration}`
    if (!appliedCommitSignatures.has(signature)) {
      appliedCommitSignatures.add(signature)
      applyPlanToState(state, plan)
    }
    await route.fulfill({
      json: {
        success: true,
        message: 'Repair plan committed',
        plan_id: `weekly-repair-${state.iteration + 1}`,
        committed: plan.added.length,
        dropped: plan.dropped.length,
        audit_log_id: `audit-weekly-${state.iteration + 1}`,
        conflicts_after: 0,
        warnings: [],
        acquisition_ids: plan.added.map((item) => item.id),
      },
    })
  })

  // Unused in this simulation, but the UI may ask for managed satellites again.
  await page.route('**/api/v1/mission/analyze**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        message: 'Mission analysis complete',
        data: {
          mission_data: buildWorkspaceData(state.currentTargets).analysis_state.mission_data,
          czml_data: [{ id: 'document', name: 'Weekly Operator Simulation' }],
        },
      },
    })
  })

  // Make the pool available for debugging in traces if needed.
  void pool
}

test.describe('Weekly operator schedule simulation', () => {
  test('simulates a 50-target baseline with many weekly incremental updates', async ({
    page,
  }, testInfo) => {
    test.setTimeout(demoSlowMs > 0 ? 300_000 : 180_000)

    const pool = generateTargetPool(86)
    const state: SimulationState = {
      iteration: 0,
      currentTargets: pool.slice(0, 50),
      nextTargetIndex: 50,
      addedSinceLastPlan: 0,
      committed: [],
      pendingPlan: null,
      history: [],
    }

    await mockSimulationApis(page, state, pool)
    await page.goto('/')
    await loadWorkspace(page)

    const totalPlanningRuns = additionPattern.length + 1

    for (let runIndex = 0; runIndex < totalPlanningRuns; runIndex += 1) {
      if (runIndex > 0) {
        advanceTargets(state, pool, additionPattern[runIndex - 1] ?? 0)
        await loadWorkspace(page)
      }

      const plan = computePlan(state)
      const screenshotName = checkpointIterations.has(runIndex)
        ? `weekly-operator-iteration-${String(runIndex + 1).padStart(2, '0')}.png`
        : null

      await openApplyPage(page, plan.mode === 'repair' ? 'repair' : 'schedule')
      await expectApplyStats(page, [String(plan.afterCount), '1', String(plan.afterCount)])
      await demoPause(page, 2)

      if (plan.mode === 'repair') {
        await expect(page.getByText(`${plan.kept.length} kept`, { exact: true })).toBeVisible()
        await expect(page.getByText(`${plan.added.length} added`, { exact: true })).toBeVisible()
        if (plan.dropped.length > 0) {
          await expect(page.getByText(`${plan.dropped.length} dropped`, { exact: true })).toBeVisible()
        }
      } else {
        await expect(page.getByRole('heading', { name: 'Ready to Schedule' })).toBeVisible()
      }
      await demoPause(page, 2)

      if (screenshotName) {
        await page.screenshot({
          path: testInfo.outputPath(screenshotName),
          fullPage: true,
        })
      }

      await applyPlan(page, plan.mode === 'repair' ? 'repair' : 'direct')
    }

    const summaryPath = testInfo.outputPath('weekly-operator-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          initial_targets: 50,
          planning_runs: state.history.length,
          addition_iterations: additionPattern.length,
          final_target_count: state.currentTargets.length,
          final_committed_count: state.committed.length,
          addition_pattern: additionPattern,
          history: state.history,
        },
        null,
        2,
      ),
    )

    expect(state.history).toHaveLength(totalPlanningRuns)
    expect(state.history[0]).toMatchObject({
      added_targets_in_request: 0,
      mode: 'from_scratch',
      before_count: 0,
      after_count: 18,
    })
    expect(state.history[1]).toMatchObject({
      added_targets_in_request: additionPattern[0],
    })
    expect(state.history.some((entry) => entry.mode === 'incremental')).toBeTruthy()
    expect(state.history.some((entry) => entry.mode === 'repair')).toBeTruthy()
    expect(state.currentTargets).toHaveLength(50 + additionPattern.reduce((sum, count) => sum + count, 0))
  })
})
