import { expect, test } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'

type ScenarioTarget = {
  name: string
  latitude: number
  longitude: number
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
      sar_mode: 'stripmap',
      description: 'Playwright managed satellite',
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

const noScheduleHorizon = {
  success: true,
  horizon: {
    start: '2026-03-24T00:00:00Z',
    end: '2026-03-31T00:00:00Z',
    freeze_cutoff: '2026-03-24T00:00:00Z',
  },
  acquisitions: [],
  statistics: {
    total_acquisitions: 0,
    by_state: {},
    by_satellite: {},
  },
}

const cleanDirectPreviewResponse = {
  success: true,
  message: 'Preview ready',
  new_items_count: 0,
  conflicts_count: 0,
  conflicts: [],
  warnings: [],
}

const repairScheduleHorizon = {
  success: true,
  horizon: {
    start: '2026-03-24T00:00:00Z',
    end: '2026-03-31T00:00:00Z',
    freeze_cutoff: '2026-03-24T00:00:00Z',
  },
  acquisitions: [
    {
      id: 'acq-keep-1',
      satellite_id: 'SAT-1',
      target_id: 'LegacyKeep',
      start_time: '2026-03-24T02:00:00Z',
      end_time: '2026-03-24T02:05:00Z',
      state: 'committed',
      lock_level: 'none',
    },
    {
      id: 'acq-drop-1',
      satellite_id: 'SAT-1',
      target_id: 'LegacyDrop',
      start_time: '2026-03-24T02:10:00Z',
      end_time: '2026-03-24T02:15:00Z',
      state: 'committed',
      lock_level: 'none',
    },
  ],
  statistics: {
    total_acquisitions: 2,
    by_state: { committed: 2 },
    by_satellite: { 'SAT-1': 2 },
  },
}

const fromScratchPlanningResponse = {
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
        opportunities_evaluated: 3,
        opportunities_accepted: 2,
        opportunities_rejected: 1,
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
        total_targets: 3,
        targets_acquired: 2,
        targets_missing: 1,
        coverage_percentage: 66.7,
        acquired_target_ids: ['Alpha', 'Bravo'],
        missing_target_ids: ['Charlie'],
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
        targets_not_scheduled: [
          {
            target_id: 'Charlie',
            reason: 'No feasible opportunity in current horizon',
          },
        ],
        horizon: {
          start: '2026-03-24T00:00:00Z',
          end: '2026-03-31T00:00:00Z',
        },
        satellites_used: ['SAT-1'],
        total_targets_with_opportunities: 3,
        total_targets_covered: 2,
      },
    },
  },
}

const repairConflictResponse = {
  success: true,
  message: 'Repair complete',
  planning_mode: 'repair',
  existing_acquisitions: {
    count: 2,
    by_state: { committed: 2 },
    by_satellite: { 'SAT-1': 2 },
    acquisition_ids: ['acq-keep-1', 'acq-drop-1'],
    horizon_start: '2026-03-24T00:00:00Z',
    horizon_end: '2026-03-31T00:00:00Z',
  },
  fixed_count: 1,
  flex_count: 1,
  new_plan_items: [
    {
      opportunity_id: 'opp-added-1',
      satellite_id: 'SAT-1',
      target_id: 'PriorityAnchor',
      start_time: '2026-03-24T03:30:00Z',
      end_time: '2026-03-24T03:35:00Z',
      roll_angle_deg: 1.4,
      pitch_angle_deg: 0.4,
      value: 99,
      quality_score: 0.97,
    },
  ],
  repair_diff: {
    kept: ['acq-keep-1'],
    dropped: ['acq-drop-1'],
    added: ['opp-added-1'],
    moved: [],
    reason_summary: {
      dropped: [{ id: 'acq-drop-1', reason: 'Replaced by higher-value alternative' }],
    },
    change_score: {
      num_changes: 2,
      percent_changed: 50,
    },
    change_log: {
      kept_count: 1,
      added: [
        {
          acquisition_id: 'opp-added-1',
          satellite_id: 'SAT-1',
          target_id: 'PriorityAnchor',
          start: '2026-03-24T03:30:00Z',
          end: '2026-03-24T03:35:00Z',
          reason_code: 'higher_value',
          reason_text: 'Higher-value target admitted into the schedule',
          replaces: ['acq-drop-1'],
          value: 99,
        },
      ],
      moved: [],
      dropped: [
        {
          acquisition_id: 'acq-drop-1',
          satellite_id: 'SAT-1',
          target_id: 'LegacyDrop',
          start: '2026-03-24T02:10:00Z',
          end: '2026-03-24T02:15:00Z',
          reason_code: 'higher_value',
          reason_text: 'Replaced by higher-value alternative',
          replaced_by: [],
        },
      ],
    },
  },
  metrics_before: {},
  metrics_after: {},
  metrics_comparison: {
    score_before: 140,
    score_after: 165,
    score_delta: 25,
    conflicts_before: 0,
    conflicts_after: 1,
    acquisition_count_before: 2,
    acquisition_count_after: 2,
  },
  conflicts_if_committed: [
    {
      type: 'temporal_overlap',
      severity: 'error',
      description: 'SAT-1: PriorityAnchor overlaps another protected acquisition by 12.0s',
      acquisition_ids: ['acq-keep-1', 'opp-added-1'],
      reason:
        'Two acquisitions on the same satellite overlap in time. The satellite cannot image two targets simultaneously.',
      details: {
        overlap_seconds: 12,
        satellite_id: 'SAT-1',
      },
    },
  ],
  commit_preview: {
    will_create: 1,
    will_conflict_with: 1,
    conflict_details: [],
    warnings: [],
  },
  algorithm_metrics: {},
  plan_id: 'repair-plan-conflict',
  schedule_context: {},
  planner_summary: {
    target_acquisitions: [
      {
        target_id: 'LegacyKeep',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T02:00:00Z',
        end_time: '2026-03-24T02:05:00Z',
        action: 'kept',
      },
      {
        target_id: 'PriorityAnchor',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T03:30:00Z',
        end_time: '2026-03-24T03:35:00Z',
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
}

const repairMovedResponse = {
  success: true,
  message: 'Repair complete',
  planning_mode: 'repair',
  existing_acquisitions: {
    count: 2,
    by_state: { committed: 2 },
    by_satellite: { 'SAT-1': 2 },
    acquisition_ids: ['acq-keep-1', 'acq-move-1'],
    horizon_start: '2026-03-24T00:00:00Z',
    horizon_end: '2026-03-31T00:00:00Z',
  },
  fixed_count: 1,
  flex_count: 1,
  new_plan_items: [
    {
      opportunity_id: 'opp-move-1',
      satellite_id: 'SAT-1',
      target_id: 'RescheduledBravo',
      start_time: '2026-03-24T04:15:00Z',
      end_time: '2026-03-24T04:20:00Z',
      roll_angle_deg: 1.1,
      pitch_angle_deg: 0.3,
      value: 88,
      quality_score: 0.91,
    },
  ],
  repair_diff: {
    kept: ['acq-keep-1'],
    dropped: [],
    added: [],
    moved: [
      {
        id: 'acq-move-1',
        from_start: '2026-03-24T03:45:00Z',
        from_end: '2026-03-24T03:50:00Z',
        to_start: '2026-03-24T04:15:00Z',
        to_end: '2026-03-24T04:20:00Z',
        from_roll_deg: 1.4,
        to_roll_deg: 1.1,
      },
    ],
    reason_summary: {
      moved: [{ id: 'acq-move-1', reason: 'Shifted to accommodate a better sequence' }],
    },
    change_score: {
      num_changes: 1,
      percent_changed: 50,
    },
    change_log: {
      kept_count: 1,
      added: [],
      dropped: [],
      moved: [
        {
          acquisition_id: 'acq-move-1',
          satellite_id: 'SAT-1',
          target_id: 'RescheduledBravo',
          from_start: '2026-03-24T03:45:00Z',
          from_end: '2026-03-24T03:50:00Z',
          to_start: '2026-03-24T04:15:00Z',
          to_end: '2026-03-24T04:20:00Z',
          reason_code: 'sequence_optimization',
          reason_text: 'Shifted to a better time slot to reduce downstream conflicts',
        },
      ],
    },
  },
  metrics_before: {},
  metrics_after: {},
  metrics_comparison: {
    score_before: 150,
    score_after: 154,
    score_delta: 4,
    conflicts_before: 0,
    conflicts_after: 0,
    acquisition_count_before: 2,
    acquisition_count_after: 2,
  },
  conflicts_if_committed: [
    {
      type: 'slew_infeasible',
      severity: 'warning',
      description: 'SAT-1 has a tight 8.0s repointing window after RescheduledBravo',
      acquisition_ids: ['acq-move-1'],
      reason:
        'The gap between consecutive acquisitions may be too short for the satellite to repoint safely.',
      details: {
        available_time_s: 8,
        required_time_s: 10,
        satellite_id: 'SAT-1',
      },
    },
  ],
  commit_preview: {
    will_create: 0,
    will_conflict_with: 1,
    conflict_details: [],
    warnings: [],
  },
  algorithm_metrics: {},
  plan_id: 'repair-plan-moved',
  schedule_context: {},
  planner_summary: {
    target_acquisitions: [
      {
        target_id: 'LegacyKeep',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T02:00:00Z',
        end_time: '2026-03-24T02:05:00Z',
        action: 'kept',
      },
      {
        target_id: 'RescheduledBravo',
        satellite_id: 'SAT-1',
        start_time: '2026-03-24T04:15:00Z',
        end_time: '2026-03-24T04:20:00Z',
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
}

function buildAnalyzeResponse(requestBody: Record<string, unknown>) {
  const requestTargets = Array.isArray(requestBody.targets) ? requestBody.targets : []
  const requestSatellites =
    Array.isArray(requestBody.satellites) && requestBody.satellites.length > 0
      ? (requestBody.satellites as Array<Record<string, unknown>>)
      : requestBody.tle
        ? [requestBody.tle as Record<string, unknown>]
        : []
  const satelliteName =
    typeof requestSatellites[0]?.name === 'string' ? String(requestSatellites[0].name) : 'ICEYE-X53'

  return {
    success: true,
    message: 'Mission analysis complete',
    data: {
      mission_data: {
        satellite_name: satelliteName,
        satellites: [{ id: 'SAT-1', name: satelliteName, color: '#3B82F6' }],
        is_constellation: false,
        mission_type: String(requestBody.mission_type || 'imaging'),
        imaging_type: String(requestBody.imaging_type || 'optical'),
        start_time: String(requestBody.start_time || '2026-03-24T00:00:00Z'),
        end_time: String(requestBody.end_time || '2026-03-31T00:00:00Z'),
        elevation_mask: Number(requestBody.elevation_mask || 45),
        sensor_fov_half_angle_deg: 15,
        max_spacecraft_roll_deg: Number(requestBody.max_spacecraft_roll_deg || 45),
        total_passes: requestTargets.length,
        targets: requestTargets,
        passes: requestTargets.map((target, index) => ({
          target: String((target as Record<string, unknown>).name || `Target-${index + 1}`),
          satellite_name: satelliteName,
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
          name: satelliteName,
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
      value: 100 - index * 5,
      priority: 1 + index,
    })),
    count: targets.length,
  }
}

async function mockCommonApis(page: Page, targets: ScenarioTarget[]) {
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

  await page.route('**/api/v1/config/sar-modes**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        modes: {},
      },
    })
  })

  await page.route('**/api/v1/mission/analyze**', async (route) => {
    const requestBody = route.request().postDataJSON() as Record<string, unknown>
    await route.fulfill({ json: buildAnalyzeResponse(requestBody) })
  })

  await page.route('**/api/v1/planning/opportunities**', async (route) => {
    await route.fulfill({ json: buildOpportunitiesResponse(targets) })
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

  await page.route('**/api/v1/schedule/commit/direct/preview**', async (route) => {
    const requestBody = route.request().postDataJSON() as { items?: unknown[] }
    const itemCount = Array.isArray(requestBody.items) ? requestBody.items.length : 0
    await route.fulfill({
      json: {
        ...cleanDirectPreviewResponse,
        new_items_count: itemCount,
      },
    })
  })
}

async function addTarget(page: Page, target: ScenarioTarget) {
  await page.getByPlaceholder('Target name *').fill(target.name)
  await page.getByPlaceholder('Lat').fill(String(target.latitude))
  await page.getByPlaceholder('Lon').fill(String(target.longitude))
  await page.getByRole('button', { name: 'Add target', exact: true }).click()
}

async function dismissCesiumErrorIfPresent(page: Page) {
  const cesiumErrorOkButton = page.getByRole('button', { name: 'OK' })
  if (await cesiumErrorOkButton.isVisible().catch(() => false)) {
    await cesiumErrorOkButton.click()
  }
}

function assignmentRow(page: Page, targetName: string, badgeText: 'NEW' | 'REMOVED' | 'MOVED') {
  const kind =
    badgeText === 'NEW' ? 'added' : badgeText === 'REMOVED' ? 'removed' : 'moved'

  return page.locator(`[data-assignment-kind="${kind}"][data-target-id="${targetName}"]`).first()
}

function assignmentFilter(page: Page, label: 'All' | 'New' | 'Moved' | 'Removed', count: number) {
  return page.getByRole('button', {
    name: new RegExp(`^${label}\\s*${count}$`),
  })
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

async function openPlanningApplyStep(
  page: Page,
  targets: ScenarioTarget[],
  testInfo: TestInfo,
  screenshotName: string,
) {
  await page.goto('/')
  await openLeftPanel(page, 'Feasibility Analysis', page.getByRole('button', { name: 'Create Order' }))

  await page.getByRole('button', { name: 'Create Order' }).click()

  for (const target of targets) {
    await addTarget(page, target)
  }

  await openLeftPanel(
    page,
    'Feasibility Analysis',
    page.getByRole('button', { name: /Run Feasibility Analysis/i }),
  )

  const analyzeButton = page.getByRole('button', { name: /Run Feasibility Analysis/i })
  const analyzeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && response.url().includes('/api/v1/mission/analyze'),
  )
  const opportunitiesResponsePromise = page.waitForResponse((response) =>
    response.url().includes('/api/v1/planning/opportunities'),
  )

  await expect(analyzeButton).toBeEnabled()
  await analyzeButton.click()
  const analyzeResponse = await analyzeResponsePromise
  expect(analyzeResponse.ok()).toBeTruthy()
  const opportunitiesResponse = await opportunitiesResponsePromise
  expect(opportunitiesResponse.ok()).toBeTruthy()
  await expect(
    page.getByRole('heading', { name: 'Feasibility Results', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('button', { name: /Generate Mission Plan/i })).toBeVisible()

  await openLeftPanel(page, 'Planning', page.getByRole('button', { name: /Generate Mission Plan/i }))
  const generateButton = page.getByRole('button', { name: /Generate Mission Plan/i })
  await expect(generateButton).toBeEnabled()
  try {
    await generateButton.click({ timeout: 5000 })
  } catch {
    await dismissCesiumErrorIfPresent(page)
    await generateButton.click({ force: true })
  }

  await expect(page.getByRole('button', { name: /^Next$/i })).toBeVisible()
  await page.getByRole('button', { name: /^Next$/i }).click()

  await page.screenshot({
    path: testInfo.outputPath(screenshotName),
    fullPage: true,
  })
}

test.describe('Planning apply confirmation UI', () => {
  test('hands off from feasibility to planning while keeping results visible', async ({ page }) => {
    const targets = [{ name: 'Alpha', latitude: 24.7136, longitude: 46.6753 }]

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: noScheduleHorizon })
    })

    await page.goto('/')
    await openLeftPanel(page, 'Feasibility Analysis', page.getByRole('button', { name: 'Create Order' }))
    await page.getByRole('button', { name: 'Create Order' }).click()
    await addTarget(page, targets[0])
    await openLeftPanel(
      page,
      'Feasibility Analysis',
      page.getByRole('button', { name: /Run Feasibility Analysis/i }),
    )

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
    await expect(page.getByRole('button', { name: /Generate Mission Plan/i })).toBeEnabled()
  })

  test('shows a clean added-only apply summary for a new schedule', async ({ page }, testInfo) => {
    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
      { name: 'Charlie', latitude: 25.2854, longitude: 51.531 },
    ]

    let planningRequestBody: unknown = null

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: noScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'from_scratch',
          reason: 'No existing schedule found for workspace. Building new optimized schedule.',
          workspace_id: 'default',
          existing_acquisition_count: 0,
          new_target_count: 3,
          conflict_count: 0,
          current_target_ids: [],
          existing_target_ids: [],
          request_payload_hash: 'from-scratch-hash',
        },
      })
    })
    await page.route('**/api/v1/planning/schedule**', async (route) => {
      planningRequestBody = route.request().postDataJSON()
      await route.fulfill({ json: fromScratchPlanningResponse })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-from-scratch.png')

    expect(planningRequestBody).toMatchObject({
      mode: 'from_scratch',
      algorithms: ['roll_pitch_best_fit'],
      workspace_id: 'default',
    })

    await expect(page.getByText('Operations Snapshot', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
    await expect(page.getByText('No conflicts', { exact: true })).toBeVisible()
    await expect(page.getByText('2 new', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Apply Plan' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Target Assignments' })).toBeVisible()
    await expect(assignmentFilter(page, 'All', 2)).toBeVisible()
    await expect(assignmentFilter(page, 'New', 2)).toBeVisible()
    await expect(page.getByRole('button', { name: /^Moved/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /^Removed/ })).toHaveCount(0)
    await expect(assignmentRow(page, 'Alpha', 'NEW')).toBeVisible()
    await expect(assignmentRow(page, 'Bravo', 'NEW')).toBeVisible()
    await expect(page.getByText('NEW', { exact: true })).toHaveCount(2)
  })

  test('shows conflict-driven added and removed actions for repair plans', async (
    { page },
    testInfo,
  ) => {
    const targets = [
      { name: 'LegacyKeep', latitude: 24.7136, longitude: 46.6753 },
      { name: 'LegacyDrop', latitude: 21.4858, longitude: 39.1925 },
      { name: 'PriorityAnchor', latitude: 25.2854, longitude: 51.531 },
    ]

    let repairRequestBody: unknown = null

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: repairScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'repair',
          reason: 'Higher-priority targets require repairing the current schedule.',
          workspace_id: 'default',
          existing_acquisition_count: 2,
          new_target_count: 1,
          conflict_count: 1,
          current_target_ids: ['LegacyKeep', 'LegacyDrop', 'PriorityAnchor'],
          existing_target_ids: ['LegacyKeep', 'LegacyDrop'],
          request_payload_hash: 'repair-conflict-hash',
        },
      })
    })
    await page.route('**/api/v1/schedule/repair**', async (route) => {
      repairRequestBody = route.request().postDataJSON()
      await route.fulfill({ json: repairConflictResponse })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-repair-conflict.png')

    expect(repairRequestBody).toMatchObject({
      planning_mode: 'repair',
      workspace_id: 'default',
    })

    await expect(page.getByText('Operations Snapshot', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Conflicts Detected' })).toBeVisible()
    await expect(page.getByText('1 kept', { exact: true })).toBeVisible()
    await expect(page.getByText('1 added', { exact: true })).toBeVisible()
    await expect(page.getByText('1 dropped', { exact: true })).toBeVisible()
    await expect(page.getByText('Conflicts (1)', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Apply Anyway' })).toBeVisible()
    await expect(assignmentRow(page, 'PriorityAnchor', 'NEW')).toBeVisible()
    await expect(assignmentRow(page, 'LegacyDrop', 'REMOVED')).toBeVisible()
    await expect(assignmentFilter(page, 'All', 2)).toBeVisible()
    await expect(assignmentFilter(page, 'New', 1)).toBeVisible()
    await expect(assignmentFilter(page, 'Removed', 1)).toBeVisible()
    await expect(page.getByRole('button', { name: /^Moved/ })).toHaveCount(0)
    await expect(page.getByText('NEW', { exact: true })).toHaveCount(1)
    await expect(page.getByText('REMOVED', { exact: true })).toHaveCount(1)
    await expect(page.getByText(/Caution:/)).toBeVisible()

    await assignmentFilter(page, 'Removed', 1).click()
    await expect(assignmentRow(page, 'LegacyDrop', 'REMOVED')).toBeVisible()
    await expect(assignmentRow(page, 'PriorityAnchor', 'NEW')).toHaveCount(0)

    await assignmentFilter(page, 'New', 1).click()
    await expect(assignmentRow(page, 'PriorityAnchor', 'NEW')).toBeVisible()
    await expect(assignmentRow(page, 'LegacyDrop', 'REMOVED')).toHaveCount(0)
  })

  test('shows moved actions and review state when a repair reschedules work', async (
    { page },
    testInfo,
  ) => {
    const targets = [
      { name: 'LegacyKeep', latitude: 24.7136, longitude: 46.6753 },
      { name: 'RescheduledBravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: repairScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'repair',
          reason: 'Reshuffling existing acquisitions produces a better sequence.',
          workspace_id: 'default',
          existing_acquisition_count: 2,
          new_target_count: 0,
          conflict_count: 0,
          current_target_ids: ['LegacyKeep', 'RescheduledBravo'],
          existing_target_ids: ['LegacyKeep', 'RescheduledBravo'],
          request_payload_hash: 'repair-moved-hash',
        },
      })
    })
    await page.route('**/api/v1/schedule/repair**', async (route) => {
      await route.fulfill({ json: repairMovedResponse })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-repair-moved.png')

    await expect(page.getByText('Operations Snapshot', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Review Changes' })).toBeVisible()
    await expect(page.getByText('1 kept', { exact: true })).toBeVisible()
    await expect(page.getByText('1 moved', { exact: true })).toBeVisible()
    await expect(assignmentFilter(page, 'All', 1)).toBeVisible()
    await expect(assignmentFilter(page, 'Moved', 1)).toBeVisible()
    await expect(page.getByRole('button', { name: /^New/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /^Removed/ })).toHaveCount(0)
    await expect(page.getByText('MOVED', { exact: true })).toHaveCount(1)
    await expect(assignmentRow(page, 'RescheduledBravo', 'MOVED')).toBeVisible()
    await expect(page.getByText('Conflicts (1)', { exact: true })).toBeVisible()
    await expect(page.getByText('Slew Infeasible', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Apply Plan' })).toBeVisible()
    await expect(page.getByText(/Mar 24, 03:45.*→.*Mar 24, 04:15/)).toBeVisible()
  })

  test('persists and surfaces backend conflicts after a forced direct apply', async ({
    page,
  }, testInfo) => {
    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    const overlappingPlanningResponse = {
      ...fromScratchPlanningResponse,
      results: {
        roll_pitch_best_fit: {
          ...fromScratchPlanningResponse.results.roll_pitch_best_fit,
          schedule: [
            fromScratchPlanningResponse.results.roll_pitch_best_fit.schedule[0],
            {
              ...fromScratchPlanningResponse.results.roll_pitch_best_fit.schedule[1],
              start_time: '2026-03-24T02:04:00Z',
              end_time: '2026-03-24T02:08:00Z',
            },
          ],
        },
      },
    }

    let commitBody: Record<string, unknown> | null = null
    let commitApplied = false

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/master**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          zoom: 'detail',
          total: 0,
          items: [],
          buckets: [],
          t_start: '2026-03-24T00:00:00Z',
          t_end: '2026-03-31T00:00:00Z',
        },
      })
    })
    await page.route('**/api/v1/schedule/target-locations**', async (route) => {
      await route.fulfill({ json: { success: true, targets: [] } })
    })
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: noScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'from_scratch',
          reason: 'No existing schedule found for workspace. Building new optimized schedule.',
          workspace_id: 'default',
          existing_acquisition_count: 0,
          new_target_count: 2,
          conflict_count: 0,
          current_target_ids: [],
          existing_target_ids: [],
          request_payload_hash: 'forced-direct-apply-hash',
        },
      })
    })
    await page.route('**/api/v1/planning/schedule**', async (route) => {
      await route.fulfill({ json: overlappingPlanningResponse })
    })
    await page.route('**/api/v1/schedule/commit/direct/preview**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          message: 'Preview found 1 conflict',
          new_items_count: 2,
          conflicts_count: 1,
          conflicts: [
            {
              type: 'temporal_overlap',
              severity: 'error',
              description: 'SAT-1: Alpha and Bravo overlap by 60.0s',
              acquisition_ids: ['new:opp-alpha-1', 'new:opp-bravo-1'],
              reason:
                'Two acquisitions on the same satellite overlap in time. The satellite cannot image two targets simultaneously.',
              details: {
                overlap_seconds: 60,
                satellite_id: 'SAT-1',
                acq1_target: 'Alpha',
                acq2_target: 'Bravo',
              },
            },
          ],
          warnings: [],
        },
      })
    })
    await page.route('**/api/v1/schedule/commit/direct', async (route) => {
      commitBody = route.request().postDataJSON() as Record<string, unknown>
      commitApplied = true
      await route.fulfill({
        json: {
          success: true,
          message: 'Committed with persisted conflicts',
          plan_id: 'forced-conflict-plan',
          committed: 2,
          acquisition_ids: ['acq-alpha-1', 'acq-bravo-1'],
          conflicts_detected: 1,
          conflict_ids: ['conflict-1'],
        },
      })
    })
    await page.route('**/api/v1/schedule/conflicts**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          conflicts: commitApplied
            ? [
                {
                  id: 'conflict-1',
                  detected_at: '2026-03-24T02:09:00Z',
                  type: 'temporal_overlap',
                  severity: 'error',
                  description: 'SAT-1: Alpha and Bravo overlap by 60.0s',
                  acquisition_ids: ['acq-alpha-1', 'acq-bravo-1'],
                  details: {
                    overlap_seconds: 60,
                    satellite_id: 'SAT-1',
                    acq1_target: 'Alpha',
                    acq2_target: 'Bravo',
                  },
                },
              ]
            : [],
          summary: {
            total: commitApplied ? 1 : 0,
            by_type: commitApplied ? { temporal_overlap: 1 } : {},
            by_severity: commitApplied ? { error: 1 } : {},
          },
        },
      })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-forced-conflict.png')

    await expect(page.getByRole('heading', { name: 'Conflicts Detected' })).toBeVisible()
    await expect(page.getByText('Time Overlap', { exact: true })).toBeVisible()

    const commitResponsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/v1/schedule/commit/direct'),
    )
    await page.getByRole('button', { name: 'Apply Anyway' }).click()
    const commitResponse = await commitResponsePromise
    expect(commitResponse.ok()).toBeTruthy()

    expect(commitBody).toMatchObject({
      workspace_id: 'default',
      algorithm: 'roll_pitch_best_fit',
      force: true,
    })

    await openLeftPanel(page, 'Conflicts', page.getByText('1 errors', { exact: true }))
    await expect(page.getByText('1 errors', { exact: true })).toBeVisible()
    await expect(page.getByText('Time Overlap', { exact: true })).toBeVisible()
    await expect(page.getByText(/Alpha and Bravo overlap by 60.0s/)).toBeVisible()
  })

  test('submits only one direct commit when apply is triggered twice quickly', async ({
    page,
  }, testInfo) => {
    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    let commitRequestCount = 0

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: noScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'from_scratch',
          reason: 'No existing schedule found for workspace. Building new optimized schedule.',
          workspace_id: 'default',
          existing_acquisition_count: 0,
          new_target_count: 2,
          conflict_count: 0,
          current_target_ids: [],
          existing_target_ids: [],
          request_payload_hash: 'double-apply-guard-hash',
        },
      })
    })
    await page.route('**/api/v1/planning/schedule**', async (route) => {
      await route.fulfill({ json: fromScratchPlanningResponse })
    })
    await page.route('**/api/v1/schedule/commit/direct', async (route) => {
      commitRequestCount += 1
      await page.waitForTimeout(750)
      await route.fulfill({
        json: {
          success: true,
          message: 'Committed once',
          plan_id: 'single-apply-plan',
          committed: 2,
          acquisition_ids: ['acq-alpha-1', 'acq-bravo-1'],
          conflicts_detected: 0,
          conflict_ids: [],
        },
      })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-double-submit-guard.png')

    const applyButton = page.getByRole('button', { name: 'Apply Plan' })
    await expect(applyButton).toBeVisible()

    await applyButton.evaluate((button) => {
      ;(button as HTMLButtonElement).click()
      ;(button as HTMLButtonElement).click()
    })

    await expect
      .poll(() => commitRequestCount, { timeout: 5000 })
      .toBe(1)
    await expect(page.getByRole('button', { name: /Apply Plan/i })).toHaveCount(0)
  })

  test('keeps the review flow open when backend apply fails with a stale schedule conflict', async ({
    page,
  }, testInfo) => {
    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: noScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'from_scratch',
          reason: 'No existing schedule found for workspace. Building new optimized schedule.',
          workspace_id: 'default',
          existing_acquisition_count: 0,
          new_target_count: 2,
          conflict_count: 0,
          current_target_ids: [],
          existing_target_ids: [],
          request_payload_hash: 'stale-apply-review-hash',
        },
      })
    })
    await page.route('**/api/v1/planning/schedule**', async (route) => {
      await route.fulfill({ json: fromScratchPlanningResponse })
    })
    await page.route('**/api/v1/schedule/commit/direct', async (route) => {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        json: {
          detail: {
            message: 'Schedule state changed before apply. Refresh conflicts and review the latest plan.',
          },
        },
      })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-stale-conflict.png')

    await expect(page.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()

    const commitResponsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/v1/schedule/commit/direct'),
    )
    await page.getByRole('button', { name: 'Apply Plan' }).click()
    const commitResponse = await commitResponsePromise
    expect(commitResponse.status()).toBe(409)

    await expect(page.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
    await expect(
      page.getByText(
        'Schedule state changed before apply. Refresh conflicts and review the latest plan.',
        { exact: true },
      ),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Apply Plan' })).toBeVisible()
  })

  test('blocks a second operator after another session commits first', async ({ browser }, testInfo) => {
    test.setTimeout(180000)

    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    let scheduleCommitted = false
    let successfulCommitCount = 0

    const operatorAContext = await browser.newContext()
    const operatorBContext = await browser.newContext()
    const operatorAPage = await operatorAContext.newPage()
    const operatorBPage = await operatorBContext.newPage()

    const mockOperatorApis = async (page: Page) => {
      await mockCommonApis(page, targets)
      await page.route('**/api/v1/schedule/horizon**', async (route) => {
        await route.fulfill({ json: noScheduleHorizon })
      })
      await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
        await route.fulfill({
          json: {
            success: true,
            planning_mode: 'from_scratch',
            reason: 'No existing schedule found for workspace. Building new optimized schedule.',
            workspace_id: 'default',
            existing_acquisition_count: 0,
            new_target_count: 2,
            conflict_count: 0,
            current_target_ids: [],
            existing_target_ids: [],
            request_payload_hash: 'two-operator-race-hash',
          },
        })
      })
      await page.route('**/api/v1/planning/schedule**', async (route) => {
        await route.fulfill({ json: fromScratchPlanningResponse })
      })
      await page.route('**/api/v1/schedule/commit/direct', async (route) => {
        if (!scheduleCommitted) {
          scheduleCommitted = true
          successfulCommitCount += 1
          await route.fulfill({
            json: {
              success: true,
              message: 'Committed before competing operator apply',
              plan_id: 'operator-a-plan',
              committed: 2,
              acquisition_ids: ['acq-alpha-1', 'acq-bravo-1'],
              conflicts_detected: 0,
              conflict_ids: [],
            },
          })
          return
        }

        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          json: {
            detail: {
              message:
                'Schedule state changed before apply. Refresh conflicts and review the latest plan.',
            },
          },
        })
      })
    }

    try {
      await Promise.all([mockOperatorApis(operatorAPage), mockOperatorApis(operatorBPage)])

      await openPlanningApplyStep(
        operatorAPage,
        targets,
        testInfo,
        'planning-apply-two-operator-a.png',
      )
      await openPlanningApplyStep(
        operatorBPage,
        targets,
        testInfo,
        'planning-apply-two-operator-b.png',
      )

      await expect(operatorAPage.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
      await expect(operatorBPage.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()

      const operatorACommitResponse = operatorAPage.waitForResponse((response) =>
        response.url().includes('/api/v1/schedule/commit/direct'),
      )
      await operatorAPage.getByRole('button', { name: 'Apply Plan' }).click()
      expect((await operatorACommitResponse).ok()).toBeTruthy()

      await expect.poll(() => successfulCommitCount, { timeout: 5000 }).toBe(1)

      const operatorBCommitResponse = operatorBPage.waitForResponse((response) =>
        response.url().includes('/api/v1/schedule/commit/direct'),
      )
      await operatorBPage.getByRole('button', { name: 'Apply Plan' }).click()
      expect((await operatorBCommitResponse).status()).toBe(409)

      await expect(
        operatorBPage.getByText(
          'Schedule state changed before apply. Refresh conflicts and review the latest plan.',
          { exact: true },
        ),
      ).toBeVisible()
      await expect(operatorBPage.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
      await expect(operatorBPage.getByRole('button', { name: 'Apply Plan' })).toBeVisible()
    } finally {
      await operatorAContext.close().catch(() => undefined)
      await operatorBContext.close().catch(() => undefined)
    }
  })

  test('fails closed when a delayed apply returns stale after another operator commits', async ({
    browser,
  }, testInfo) => {
    test.setTimeout(180000)

    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    let successfulCommitCount = 0
    let releaseDelayedCommit: (() => void) | null = null
    const delayedCommitStarted = new Promise<void>((resolve) => {
      releaseDelayedCommit = resolve
    })
    let delayedRouteRelease: (() => void) | null = null
    const delayedRouteReady = new Promise<void>((resolve) => {
      delayedRouteRelease = resolve
    })

    const operatorAContext = await browser.newContext()
    const operatorBContext = await browser.newContext()
    const operatorAPage = await operatorAContext.newPage()
    const operatorBPage = await operatorBContext.newPage()

    const mockSharedOperatorApis = async (page: Page, requestHash: string) => {
      await mockCommonApis(page, targets)
      await page.route('**/api/v1/schedule/horizon**', async (route) => {
        await route.fulfill({ json: noScheduleHorizon })
      })
      await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
        await route.fulfill({
          json: {
            success: true,
            planning_mode: 'from_scratch',
            reason: 'No existing schedule found for workspace. Building new optimized schedule.',
            workspace_id: 'default',
            existing_acquisition_count: 0,
            new_target_count: 2,
            conflict_count: 0,
            current_target_ids: [],
            existing_target_ids: [],
            request_payload_hash: requestHash,
          },
        })
      })
      await page.route('**/api/v1/planning/schedule**', async (route) => {
        await route.fulfill({ json: fromScratchPlanningResponse })
      })
    }

    try {
      await Promise.all([
        mockSharedOperatorApis(operatorAPage, 'delayed-race-operator-a-hash'),
        mockSharedOperatorApis(operatorBPage, 'delayed-race-operator-b-hash'),
      ])

      await operatorAPage.route('**/api/v1/schedule/commit/direct', async (route) => {
        delayedRouteRelease?.()
        await delayedCommitStarted
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          json: {
            detail: {
              message:
                'Schedule state changed before apply. Refresh conflicts and review the latest plan.',
            },
          },
        })
      })

      await operatorBPage.route('**/api/v1/schedule/commit/direct', async (route) => {
        successfulCommitCount += 1
        await route.fulfill({
          json: {
            success: true,
            message: 'Competing operator committed while delayed request was in flight',
            plan_id: 'operator-b-plan',
            committed: 2,
            acquisition_ids: ['acq-alpha-1', 'acq-bravo-1'],
            conflicts_detected: 0,
            conflict_ids: [],
          },
        })
      })

      await openPlanningApplyStep(
        operatorAPage,
        targets,
        testInfo,
        'planning-apply-delayed-race-operator-a.png',
      )
      await openPlanningApplyStep(
        operatorBPage,
        targets,
        testInfo,
        'planning-apply-delayed-race-operator-b.png',
      )

      const operatorACommitResponse = operatorAPage.waitForResponse((response) =>
        response.url().includes('/api/v1/schedule/commit/direct'),
      )
      await operatorAPage.getByRole('button', { name: 'Apply Plan' }).click()
      await delayedRouteReady
      await expect(operatorAPage.getByRole('button', { name: 'Applying…' })).toBeVisible()

      const operatorBCommitResponse = operatorBPage.waitForResponse((response) =>
        response.url().includes('/api/v1/schedule/commit/direct'),
      )
      await operatorBPage.getByRole('button', { name: 'Apply Plan' }).click()
      expect((await operatorBCommitResponse).ok()).toBeTruthy()
      await expect.poll(() => successfulCommitCount, { timeout: 5000 }).toBe(1)

      releaseDelayedCommit?.()
      expect((await operatorACommitResponse).status()).toBe(409)

      await expect(operatorAPage.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
      await expect(
        operatorAPage.getByText(
          'Schedule state changed before apply. Refresh conflicts and review the latest plan.',
          { exact: true },
        ),
      ).toBeVisible()
      await expect(operatorAPage.getByRole('button', { name: 'Apply Plan' })).toBeVisible()
    } finally {
      await operatorAContext.close().catch(() => undefined)
      await operatorBContext.close().catch(() => undefined)
    }
  })

  test('keeps review open and allows safe retry after a dropped apply request', async ({
    page,
  }, testInfo) => {
    const targets = [
      { name: 'Alpha', latitude: 24.7136, longitude: 46.6753 },
      { name: 'Bravo', latitude: 21.4858, longitude: 39.1925 },
    ]

    let commitAttempts = 0

    await mockCommonApis(page, targets)
    await page.route('**/api/v1/schedule/horizon**', async (route) => {
      await route.fulfill({ json: noScheduleHorizon })
    })
    await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          planning_mode: 'from_scratch',
          reason: 'No existing schedule found for workspace. Building new optimized schedule.',
          workspace_id: 'default',
          existing_acquisition_count: 0,
          new_target_count: 2,
          conflict_count: 0,
          current_target_ids: [],
          existing_target_ids: [],
          request_payload_hash: 'transport-retry-hash',
        },
      })
    })
    await page.route('**/api/v1/planning/schedule**', async (route) => {
      await route.fulfill({ json: fromScratchPlanningResponse })
    })
    await page.route('**/api/v1/schedule/commit/direct', async (route) => {
      commitAttempts += 1
      if (commitAttempts === 1) {
        await route.abort('failed')
        return
      }

      await route.fulfill({
        json: {
          success: true,
          message: 'Committed after retry',
          plan_id: 'transport-retry-plan',
          committed: 2,
          acquisition_ids: ['acq-alpha-1', 'acq-bravo-1'],
          conflicts_detected: 0,
          conflict_ids: [],
        },
      })
    })

    await openPlanningApplyStep(page, targets, testInfo, 'planning-apply-transport-retry.png')

    await page.getByRole('button', { name: 'Apply Plan' }).click()

    await expect
      .poll(() => commitAttempts, { timeout: 5000 })
      .toBe(1)
    await expect(
      page.getByText('Apply request did not complete. Verify schedule state before retrying.', {
        exact: true,
      }),
    ).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Ready to Apply' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Apply Plan' })).toBeVisible()

    const retryCommitResponse = page.waitForResponse((response) =>
      response.url().includes('/api/v1/schedule/commit/direct'),
    )
    await page.getByRole('button', { name: 'Apply Plan' }).click()
    expect((await retryCommitResponse).ok()).toBeTruthy()

    await expect
      .poll(() => commitAttempts, { timeout: 5000 })
      .toBe(2)
    await expect(page.getByRole('button', { name: /Apply Plan/i })).toHaveCount(0)
  })
})
