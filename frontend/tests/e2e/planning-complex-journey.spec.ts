import { expect, test } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'

const demoSlowMs = Number(process.env.PW_DEMO_SLOW_MS ?? '0')

type ScenarioTarget = {
  name: string
  latitude: number
  longitude: number
  priority?: number
}

type CommittedAcquisition = {
  id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  state: string
  lock_level: 'none' | 'hard'
}

type JourneyState = {
  phase: 0 | 1 | 2
  analyzeTargets: ScenarioTarget[]
  committed: CommittedAcquisition[]
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
      description: 'Complex journey managed satellite',
      active: true,
      created_at: '2026-03-24T00:00:00Z',
      tle_updated_at: '2026-03-24T00:00:00Z',
      capabilities: ['optical'],
    },
  ],
  count: 1,
}

const emptyWorkspaceListResponse = {
  workspaces: [],
}

const alpha: ScenarioTarget = {
  name: 'Alpha',
  latitude: 24.7136,
  longitude: 46.6753,
  priority: 2,
}

const bravo: ScenarioTarget = {
  name: 'Bravo',
  latitude: 21.4858,
  longitude: 39.1925,
  priority: 3,
}

const charlie: ScenarioTarget = {
  name: 'Charlie',
  latitude: 25.2854,
  longitude: 51.531,
  priority: 2,
}

const delta: ScenarioTarget = {
  name: 'Delta',
  latitude: 25.2048,
  longitude: 55.2708,
  priority: 4,
}

const priorityEcho: ScenarioTarget = {
  name: 'PriorityEcho',
  latitude: 26.2235,
  longitude: 50.5876,
  priority: 1,
}

function buildAnalyzeResponse(targets: ScenarioTarget[]) {
  return {
    success: true,
    message: 'Mission analysis complete',
    data: {
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
        targets,
        passes: targets.map((target, index) => ({
          target: target.name,
          satellite_name: 'ICEYE-X53',
          satellite_id: 'SAT-1',
          start_time: `2026-03-24T0${index + 1}:00:00Z`,
          end_time: `2026-03-24T0${index + 1}:05:00Z`,
          max_elevation: 58 - index,
          max_elevation_time: `2026-03-24T0${index + 1}:02:30Z`,
          pass_type: 'ascending',
          incidence_angle_deg: 12 + index,
        })),
      },
      czml_data: [
        { id: 'document', name: 'Mission Analysis' },
        {
          id: 'sat_ICEYE-X53',
          name: 'ICEYE-X53',
          position: {
            cartographicDegrees: [0, 46.6753, 24.7136, 600],
          },
        },
      ],
    },
  }
}

function buildOpportunitiesResponse(targets: ScenarioTarget[]) {
  return {
    success: true,
    opportunities: targets.map((target, index) => ({
      id: `opp-${target.name.toLowerCase()}-${index + 1}`,
      satellite_id: 'SAT-1',
      target_id: target.name,
      start_time: `2026-03-24T0${index + 2}:00:00Z`,
      end_time: `2026-03-24T0${index + 2}:05:00Z`,
      duration_seconds: 300,
      incidence_angle: 15 + index,
      value: 100 - index * 4,
      priority: target.priority ?? index + 1,
    })),
    count: targets.length,
  }
}

function buildHorizonResponse(committed: CommittedAcquisition[]) {
  return {
    success: true,
    horizon: {
      start: '2026-03-24T00:00:00Z',
      end: '2026-03-31T00:00:00Z',
      freeze_cutoff: '2026-03-24T00:00:00Z',
    },
    acquisitions: committed,
    statistics: {
      total_acquisitions: committed.length,
      by_state: committed.length > 0 ? { committed: committed.length } : {},
      by_satellite: committed.length > 0 ? { 'SAT-1': committed.length } : {},
    },
  }
}

const fromScratchResponse = {
  success: true,
  message: 'Planning complete',
  results: {
    roll_pitch_best_fit: {
      schedule: [
        {
          opportunity_id: 'opp-alpha-1',
          satellite_id: 'SAT-1',
          target_id: 'Alpha',
          start_time: '2026-03-24T02:00:00Z',
          end_time: '2026-03-24T02:05:00Z',
          delta_roll: 0,
          delta_pitch: 0,
          roll_angle: 2.5,
          pitch_angle: 0.5,
          maneuver_time: 12,
          slack_time: 34,
          value: 98,
          density: 1.2,
          incidence_angle: 15,
        },
        {
          opportunity_id: 'opp-bravo-1',
          satellite_id: 'SAT-1',
          target_id: 'Bravo',
          start_time: '2026-03-24T03:00:00Z',
          end_time: '2026-03-24T03:05:00Z',
          delta_roll: 1,
          delta_pitch: 0,
          roll_angle: 3.1,
          pitch_angle: 0.2,
          maneuver_time: 18,
          slack_time: 40,
          value: 92,
          density: 1.1,
          incidence_angle: 18,
        },
      ],
      metrics: {
        algorithm: 'roll_pitch_best_fit',
        runtime_ms: 24,
        opportunities_evaluated: 2,
        opportunities_accepted: 2,
        opportunities_rejected: 0,
        total_value: 190,
        mean_value: 95,
        total_imaging_time_s: 2,
        total_maneuver_time_s: 30,
        schedule_span_s: 3900,
        utilization: 0.2,
        mean_density: 1.15,
        median_density: 1.15,
        mean_incidence_deg: 16.5,
      },
      target_statistics: {
        total_targets: 2,
        targets_acquired: 2,
        targets_missing: 0,
        coverage_percentage: 100,
        acquired_target_ids: ['Alpha', 'Bravo'],
        missing_target_ids: [],
      },
      planner_summary: {
        target_acquisitions: [
          {
            target_id: 'Alpha',
            satellite_id: 'SAT-1',
            start_time: '2026-03-24T02:00:00Z',
            end_time: '2026-03-24T02:05:00Z',
            action: 'added',
          },
          {
            target_id: 'Bravo',
            satellite_id: 'SAT-1',
            start_time: '2026-03-24T03:00:00Z',
            end_time: '2026-03-24T03:05:00Z',
            action: 'added',
          },
        ],
        targets_not_scheduled: [],
        horizon: {
          start: '2026-03-24T00:00:00Z',
          end: '2026-03-31T00:00:00Z',
        },
        satellites_used: ['SAT-1'],
        total_targets_with_opportunities: 2,
        total_targets_covered: 2,
      },
    },
  },
}

const incrementalResponse = {
  success: true,
  message: 'Planning complete',
  results: {
    roll_pitch_best_fit: {
      schedule: [
        {
          opportunity_id: 'opp-charlie-3',
          satellite_id: 'SAT-1',
          target_id: 'Charlie',
          start_time: '2026-03-24T04:10:00Z',
          end_time: '2026-03-24T04:15:00Z',
          delta_roll: 0.8,
          delta_pitch: 0,
          roll_angle: 2.2,
          pitch_angle: 0.3,
          maneuver_time: 10,
          slack_time: 45,
          value: 95,
          density: 1.0,
          incidence_angle: 14,
        },
        {
          opportunity_id: 'opp-delta-4',
          satellite_id: 'SAT-1',
          target_id: 'Delta',
          start_time: '2026-03-24T05:05:00Z',
          end_time: '2026-03-24T05:10:00Z',
          delta_roll: 1.3,
          delta_pitch: 0.1,
          roll_angle: 3.4,
          pitch_angle: 0.5,
          maneuver_time: 16,
          slack_time: 33,
          value: 88,
          density: 0.9,
          incidence_angle: 19,
        },
      ],
      metrics: {
        algorithm: 'roll_pitch_best_fit',
        runtime_ms: 31,
        opportunities_evaluated: 4,
        opportunities_accepted: 2,
        opportunities_rejected: 2,
        total_value: 183,
        mean_value: 91.5,
        total_imaging_time_s: 2,
        total_maneuver_time_s: 26,
        schedule_span_s: 3600,
        utilization: 0.25,
        mean_density: 0.95,
        median_density: 0.95,
        mean_incidence_deg: 16.5,
      },
      target_statistics: {
        total_targets: 4,
        targets_acquired: 4,
        targets_missing: 0,
        coverage_percentage: 100,
        acquired_target_ids: ['Alpha', 'Bravo', 'Charlie', 'Delta'],
        missing_target_ids: [],
      },
      planner_summary: {
        target_acquisitions: [
          {
            target_id: 'Charlie',
            satellite_id: 'SAT-1',
            start_time: '2026-03-24T04:10:00Z',
            end_time: '2026-03-24T04:15:00Z',
            action: 'added',
          },
          {
            target_id: 'Delta',
            satellite_id: 'SAT-1',
            start_time: '2026-03-24T05:05:00Z',
            end_time: '2026-03-24T05:10:00Z',
            action: 'added',
          },
        ],
        targets_not_scheduled: [],
        horizon: {
          start: '2026-03-24T00:00:00Z',
          end: '2026-03-31T00:00:00Z',
        },
        satellites_used: ['SAT-1'],
        total_targets_with_opportunities: 4,
        total_targets_covered: 4,
      },
    },
  },
}

const mixedRepairResponse = {
  success: true,
  message: 'Repair complete',
  planning_mode: 'repair',
  existing_acquisitions: {
    count: 4,
    by_state: { committed: 4 },
    by_satellite: { 'SAT-1': 4 },
    acquisition_ids: ['acq-alpha-1', 'acq-bravo-1', 'acq-charlie-1', 'acq-delta-1'],
    horizon_start: '2026-03-24T00:00:00Z',
    horizon_end: '2026-03-31T00:00:00Z',
  },
  fixed_count: 1,
  flex_count: 3,
  new_plan_items: [
    {
      opportunity_id: 'opp-priority-echo-1',
      satellite_id: 'SAT-1',
      target_id: 'PriorityEcho',
      start_time: '2026-03-24T03:28:00Z',
      end_time: '2026-03-24T03:33:00Z',
      roll_angle_deg: 1.1,
      pitch_angle_deg: 0.2,
      value: 99,
      quality_score: 0.98,
    },
  ],
  repair_diff: {
    kept: ['acq-alpha-1', 'acq-delta-1'],
    dropped: ['acq-bravo-1'],
    added: ['opp-priority-echo-1'],
    moved: [
      {
        id: 'acq-charlie-1',
        from_start: '2026-03-24T04:10:00Z',
        from_end: '2026-03-24T04:15:00Z',
        to_start: '2026-03-24T04:42:00Z',
        to_end: '2026-03-24T04:47:00Z',
        from_roll_deg: 2.2,
        to_roll_deg: 2.8,
      },
    ],
    reason_summary: {
      dropped: [{ id: 'acq-bravo-1', reason: 'Replaced by a higher-priority target' }],
      moved: [{ id: 'acq-charlie-1', reason: 'Shifted later to maintain slew feasibility' }],
    },
    change_score: {
      num_changes: 3,
      percent_changed: 75,
    },
    change_log: {
      kept_count: 2,
      added: [
        {
          acquisition_id: 'opp-priority-echo-1',
          satellite_id: 'SAT-1',
          target_id: 'PriorityEcho',
          start: '2026-03-24T03:28:00Z',
          end: '2026-03-24T03:33:00Z',
          reason_code: 'higher_value',
          reason_text: 'Higher-priority target inserted into the schedule',
          replaces: ['acq-bravo-1'],
          value: 99,
        },
      ],
      moved: [
        {
          acquisition_id: 'acq-charlie-1',
          satellite_id: 'SAT-1',
          target_id: 'Charlie',
          from_start: '2026-03-24T04:10:00Z',
          from_end: '2026-03-24T04:15:00Z',
          to_start: '2026-03-24T04:42:00Z',
          to_end: '2026-03-24T04:47:00Z',
          reason_code: 'slew_feasible',
          reason_text: 'Shifted later to keep the new insertion feasible',
        },
      ],
      dropped: [
        {
          acquisition_id: 'acq-bravo-1',
          satellite_id: 'SAT-1',
          target_id: 'Bravo',
          start: '2026-03-24T03:00:00Z',
          end: '2026-03-24T03:05:00Z',
          reason_code: 'higher_value',
          reason_text: 'Removed to make room for PriorityEcho',
          replaced_by: ['opp-priority-echo-1'],
        },
      ],
    },
  },
  metrics_before: {},
  metrics_after: {},
  metrics_comparison: {
    score_before: 373,
    score_after: 392,
    score_delta: 19,
    conflicts_before: 0,
    conflicts_after: 1,
    acquisition_count_before: 4,
    acquisition_count_after: 4,
  },
  conflicts_if_committed: [
    {
      type: 'slew_infeasible',
      severity: 'warning',
      description: 'Charlie was moved later to maintain a safe slew gap after PriorityEcho',
      acquisition_ids: ['opp-priority-echo-1', 'acq-charlie-1'],
      involves_new_item: true,
      reason: 'The original Charlie slot was too close to the new high-priority insertion.',
      details: {
        available_time_s: 120,
        recommended_gap_s: 420,
      },
    },
  ],
  commit_preview: {
    will_create: 1,
    will_conflict_with: 1,
    conflict_details: [],
    warnings: ['Charlie is being shifted later to keep the schedule feasible.'],
  },
  algorithm_metrics: {},
  plan_id: 'complex-repair-plan',
  schedule_context: {},
  planner_summary: {
    target_acquisitions: [
      {
        target_id: 'Alpha',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T02:00:00Z',
        end_time: '2026-03-24T02:05:00Z',
        action: 'kept',
      },
      {
        target_id: 'PriorityEcho',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T03:28:00Z',
        end_time: '2026-03-24T03:33:00Z',
        action: 'added',
      },
      {
        target_id: 'Delta',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T05:05:00Z',
        end_time: '2026-03-24T05:10:00Z',
        action: 'kept',
      },
    ],
    targets_not_scheduled: [],
    horizon: {
      start: '2026-03-24T00:00:00Z',
      end: '2026-03-31T00:00:00Z',
    },
    satellites_used: ['SAT-1'],
    total_targets_with_opportunities: 5,
    total_targets_covered: 4,
  },
}

test.use({
  launchOptions: {
    slowMo: demoSlowMs > 0 ? demoSlowMs : 0,
  },
})

if (demoSlowMs > 0) {
  test.setTimeout(120_000)
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

  if (await readyLocator.isVisible().catch(() => false)) {
    return
  }

  await panelButton.click()

  if (!(await waitForVisible(readyLocator, 1500))) {
    await dismissCesiumErrorIfPresent(page)
    await panelButton.click()
  }

  await expect(readyLocator).toBeVisible({ timeout: 10000 })
}

async function addTarget(page: Page, target: ScenarioTarget) {
  await page.getByPlaceholder('Target name *').first().fill(target.name)
  await page.getByPlaceholder('Lat').first().fill(String(target.latitude))
  await page.getByPlaceholder('Lon').first().fill(String(target.longitude))
  await page.getByRole('button', { name: 'Add target', exact: true }).first().click()
}

async function startOrderAndAnalyze(page: Page, targets: ScenarioTarget[]) {
  await openLeftPanel(page, 'Feasibility Analysis', page.getByRole('button', { name: 'Create Order' }))
  await demoPause(page)
  await page.getByRole('button', { name: 'Create Order' }).click()
  await demoPause(page)

  for (const target of targets) {
    await addTarget(page, target)
    await demoPause(page, 0.6)
  }

  await openLeftPanel(
    page,
    'Feasibility Analysis',
    page.getByRole('button', { name: /Run Feasibility Analysis/i }),
  )
  await demoPause(page)

  const analyzeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && response.url().includes('/api/v1/mission/analyze'),
  )
  const opportunitiesResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/v1/planning/opportunities'),
  )

  await page.getByRole('button', { name: /Run Feasibility Analysis/i }).click()
  const analyzeResponse = await analyzeResponsePromise
  expect(analyzeResponse.ok()).toBeTruthy()
  const opportunitiesResponse = await opportunitiesResponsePromise
  expect(opportunitiesResponse.ok()).toBeTruthy()

  await expect(
    page.getByRole('heading', { name: 'Feasibility Results', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: /Generate Mission Plan/i })).toBeVisible()
  await demoPause(page, 1.25)
}

async function openApplyPage(
  page: Page,
  testInfo: TestInfo,
  screenshotName: string,
  planKind: 'schedule' | 'repair',
) {
  await openLeftPanel(page, 'Planning', page.getByRole('button', { name: /Generate Mission Plan/i }))
  await demoPause(page)

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
  await demoPause(page)

  await expect(page.getByRole('button', { name: /^Next$/i })).toBeVisible()
  await page.getByRole('button', { name: /^Next$/i }).click()
  await demoPause(page, 1.5)

  await page.screenshot({
    path: testInfo.outputPath(screenshotName),
    fullPage: true,
  })
}

async function applyPlan(page: Page, commitKind: 'direct' | 'repair') {
  const commitResponsePromise = page.waitForResponse((response) =>
    commitKind === 'repair'
      ? response.url().includes('/api/v1/schedule/repair/commit')
      : response.url().includes('/api/v1/schedule/commit/direct'),
  )

  await page.getByRole('button', { name: /Apply (Plan|Anyway)/i }).click()
  const commitResponse = await commitResponsePromise
  expect(commitResponse.ok()).toBeTruthy()

  await expect(page.getByRole('heading', { name: 'Schedule', exact: true }).first()).toBeVisible()
  await demoPause(page, 1.25)
}

function assignmentRow(page: Page, targetName: string, badgeText: 'NEW' | 'REMOVED' | 'MOVED') {
  const assignmentList = page
    .getByRole('heading', { name: 'Target Assignments', exact: true })
    .locator('xpath=following-sibling::div[1]')

  return assignmentList.locator(':scope > div').filter({
    hasText: targetName,
    has: page.getByText(badgeText, { exact: true }),
  })
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

async function mockComplexJourneyApis(page: Page, state: JourneyState) {
  await page.route('**/api/v1/workspaces**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: emptyWorkspaceListResponse })
      return
    }
    await route.fulfill({ status: 404, json: { detail: 'Not mocked in this test' } })
  })

  await page.route('**/api/v1/satellites**', async (route) => {
    await route.fulfill({ json: managedSatellitesResponse })
  })

  await page.route('**/api/v1/mission/analyze**', async (route) => {
    const requestBody = route.request().postDataJSON() as { targets?: ScenarioTarget[] }
    state.analyzeTargets = Array.isArray(requestBody.targets) ? requestBody.targets : []
    await route.fulfill({ json: buildAnalyzeResponse(state.analyzeTargets) })
  })

  await page.route('**/api/v1/planning/opportunities**', async (route) => {
    await route.fulfill({ json: buildOpportunitiesResponse(state.analyzeTargets) })
  })

  await page.route('**/api/v1/schedule/horizon**', async (route) => {
    await route.fulfill({ json: buildHorizonResponse(state.committed) })
  })

  await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
    const response =
      state.phase === 0
        ? {
            success: true,
            planning_mode: 'from_scratch',
            reason: 'No committed schedule exists yet. Build a new plan from current opportunities.',
            workspace_id: 'default',
            existing_acquisition_count: 0,
            new_target_count: state.analyzeTargets.length,
            conflict_count: 0,
            current_target_ids: state.analyzeTargets.map((target) => target.name),
            existing_target_ids: [],
            request_payload_hash: 'complex-step-1',
          }
        : state.phase === 1
          ? {
              success: true,
              planning_mode: 'incremental',
              reason:
                'Existing schedule is healthy. Add the newly introduced work without rebuilding everything.',
              workspace_id: 'default',
              existing_acquisition_count: state.committed.length,
              new_target_count: 2,
              conflict_count: 0,
              current_target_ids: state.analyzeTargets.map((target) => target.name),
              existing_target_ids: state.committed.map((item) => item.target_id),
              request_payload_hash: 'complex-step-2',
            }
          : {
              success: true,
              planning_mode: 'repair',
              reason:
                'The new high-priority target forces a repair: one acquisition will be removed and another must move.',
              workspace_id: 'default',
              existing_acquisition_count: state.committed.length,
              new_target_count: 1,
              conflict_count: 1,
              current_target_ids: state.analyzeTargets.map((target) => target.name),
              existing_target_ids: state.committed.map((item) => item.target_id),
              request_payload_hash: 'complex-step-3',
            }

    await route.fulfill({ json: response })
  })

  await page.route('**/api/v1/planning/schedule**', async (route) => {
    if (state.phase === 0) {
      await route.fulfill({ json: fromScratchResponse })
      return
    }

    if (state.phase === 1) {
      await route.fulfill({ json: incrementalResponse })
      return
    }

    await route.fulfill({ status: 500, json: { detail: 'Unexpected planning/schedule call' } })
  })

  await page.route('**/api/v1/schedule/repair**', async (route) => {
    await route.fulfill({ json: mixedRepairResponse })
  })

  await page.route('**/api/v1/schedule/commit/direct**', async (route) => {
    const requestBody = route.request().postDataJSON() as {
      items?: Array<{
        target_id: string
        satellite_id: string
        start_time: string
        end_time: string
      }>
    }
    const items = Array.isArray(requestBody.items) ? requestBody.items : []

    const created = items.map((item, index) => ({
      id:
        item.target_id === 'Alpha'
          ? 'acq-alpha-1'
          : item.target_id === 'Bravo'
            ? 'acq-bravo-1'
            : item.target_id === 'Charlie'
              ? 'acq-charlie-1'
              : item.target_id === 'Delta'
                ? 'acq-delta-1'
                : `acq-${item.target_id.toLowerCase()}-${index + 1}`,
      satellite_id: item.satellite_id,
      target_id: item.target_id,
      start_time: item.start_time,
      end_time: item.end_time,
      state: 'committed',
      lock_level: 'none' as const,
    }))

    state.committed = [...state.committed, ...created]
    state.phase = state.phase === 0 ? 1 : 2

    await route.fulfill({
      json: {
        success: true,
        message: 'Committed successfully',
        plan_id: state.phase === 1 ? 'journey-plan-step-1' : 'journey-plan-step-2',
        committed: created.length,
        acquisition_ids: created.map((item) => item.id),
      },
    })
  })

  await page.route('**/api/v1/schedule/repair/commit**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        message: 'Repair plan committed',
        plan_id: 'complex-repair-plan',
        committed: 1,
        dropped: 1,
        audit_log_id: 'audit-complex-repair',
        conflicts_after: 0,
        warnings: [],
        acquisition_ids: ['acq-priority-echo-1'],
      },
    })
  })
}

test.describe('Complex planning operator journey', () => {
  test('walks through from-scratch, incremental, and mixed repair apply screens in sequence', async ({
    page,
  }, testInfo) => {
    const state: JourneyState = {
      phase: 0,
      analyzeTargets: [],
      committed: [],
    }

    await mockComplexJourneyApis(page, state)
    await page.goto('/')

    await startOrderAndAnalyze(page, [alpha, bravo])
    await openApplyPage(page, testInfo, 'complex-journey-step-1-from-scratch.png', 'schedule')

    await expect(page.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
    await expectApplyStats(page, ['2', '1', '2'])
    await expect(page.getByText('2 new', { exact: true })).toBeVisible()
    await expect(assignmentRow(page, 'Alpha', 'NEW')).toBeVisible()
    await expect(assignmentRow(page, 'Bravo', 'NEW')).toBeVisible()
    await applyPlan(page, 'direct')
    await page.reload()

    await startOrderAndAnalyze(page, [alpha, bravo, charlie, delta])
    await openApplyPage(page, testInfo, 'complex-journey-step-2-incremental.png', 'schedule')

    await expect(page.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
    await expectApplyStats(page, ['4', '1', '4'])
    await expect(page.getByText('2 new', { exact: true })).toBeVisible()
    await expect(assignmentRow(page, 'Charlie', 'NEW')).toBeVisible()
    await expect(assignmentRow(page, 'Delta', 'NEW')).toBeVisible()
    await applyPlan(page, 'direct')
    await page.reload()

    await startOrderAndAnalyze(page, [alpha, bravo, charlie, delta, priorityEcho])
    await openApplyPage(page, testInfo, 'complex-journey-step-3-repair-mixed.png', 'repair')

    await expect(page.getByRole('heading', { name: 'Review Changes' })).toBeVisible()
    await expectApplyStats(page, ['4', '1', '4'])
    await expect(page.getByText('2 kept', { exact: true })).toBeVisible()
    await expect(page.getByText('1 added', { exact: true })).toBeVisible()
    await expect(page.getByText('1 dropped', { exact: true })).toBeVisible()
    await expect(page.getByText('1 moved', { exact: true })).toBeVisible()
    await expect(assignmentRow(page, 'PriorityEcho', 'NEW')).toBeVisible()
    await expect(assignmentRow(page, 'Bravo', 'REMOVED')).toBeVisible()
    await expect(assignmentRow(page, 'Charlie', 'MOVED')).toBeVisible()
    await expect(page.getByText(/Charlie was moved later/)).toBeVisible()
  })
})
