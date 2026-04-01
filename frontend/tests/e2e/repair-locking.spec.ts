import { expect, test } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'

const workspaceId = 'ws-lock-proof'
const workspaceName = 'Lock Proof Workspace'

const workspaceSummary = {
  id: workspaceId,
  name: workspaceName,
  created_at: '2026-03-24T00:00:00Z',
  updated_at: '2026-03-24T00:00:00Z',
  mission_mode: 'planner',
  time_window_start: '2026-03-24T00:00:00Z',
  time_window_end: '2026-03-31T00:00:00Z',
  satellites_count: 1,
  targets_count: 3,
  last_run_status: 'ready',
  schema_version: '1.0',
  app_version: 'test',
}

const missionTargets = [
  { name: 'LegacyAnchor', latitude: 24.7136, longitude: 46.6753, priority: 1, color: '#3B82F6' },
  { name: 'LegacyFallback', latitude: 21.4858, longitude: 39.1925, priority: 3, color: '#3B82F6' },
  { name: 'PriorityAnchor', latitude: 25.2854, longitude: 51.531, priority: 1, color: '#3B82F6' },
]

const workspaceData = {
  ...workspaceSummary,
  last_run_timestamp: '2026-03-24T00:00:00Z',
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
    targets: missionTargets,
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
      total_passes: 3,
      targets: missionTargets,
      passes: missionTargets.map((target, index) => ({
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
  },
  planning_state: null,
  orders_state: { orders: [] },
  ui_state: null,
  czml_data: [{ id: 'document', name: 'Mission Analysis' }],
}

const opportunitiesResponse = {
  success: true,
  opportunities: [
    {
      id: 'opp-anchor-1',
      satellite_id: 'SAT-1',
      target_id: 'LegacyAnchor',
      start_time: '2026-03-24T02:00:00Z',
      end_time: '2026-03-24T02:05:00Z',
      duration_seconds: 300,
      incidence_angle: 14,
      value: 90,
      priority: 1,
    },
    {
      id: 'opp-fallback-1',
      satellite_id: 'SAT-1',
      target_id: 'LegacyFallback',
      start_time: '2026-03-24T02:10:00Z',
      end_time: '2026-03-24T02:15:00Z',
      duration_seconds: 300,
      incidence_angle: 18,
      value: 70,
      priority: 3,
    },
    {
      id: 'opp-priority-1',
      satellite_id: 'SAT-1',
      target_id: 'PriorityAnchor',
      start_time: '2026-03-24T03:30:00Z',
      end_time: '2026-03-24T03:35:00Z',
      duration_seconds: 300,
      incidence_angle: 12,
      value: 99,
      priority: 1,
    },
  ],
  count: 3,
}

type MockServerState = {
  anchorLockLevel: 'none' | 'hard'
}

function buildMasterScheduleItems(serverState: MockServerState) {
  return [
    {
      id: 'acq-anchor',
      satellite_id: 'SAT-1',
      target_id: 'LegacyAnchor',
      start_time: '2026-03-24T02:00:00Z',
      end_time: '2026-03-24T02:05:00Z',
      mode: 'Optical',
      state: 'committed',
      lock_level: serverState.anchorLockLevel,
      workspace_id: workspaceId,
      target_lat: 24.7136,
      target_lon: 46.6753,
      satellite_display_name: 'ICEYE-X53',
      off_nadir_deg: 6.2,
      geometry: { roll_deg: 6.2, pitch_deg: 0.4 },
    },
    {
      id: 'acq-fallback',
      satellite_id: 'SAT-1',
      target_id: 'LegacyFallback',
      start_time: '2026-03-24T02:10:00Z',
      end_time: '2026-03-24T02:15:00Z',
      mode: 'Optical',
      state: 'committed',
      lock_level: 'none',
      workspace_id: workspaceId,
      target_lat: 21.4858,
      target_lon: 39.1925,
      satellite_display_name: 'ICEYE-X53',
      off_nadir_deg: 8.5,
      geometry: { roll_deg: 8.5, pitch_deg: 0.6 },
    },
  ]
}

function buildRepairResponse(serverState: MockServerState) {
  const anchorLocked = serverState.anchorLockLevel === 'hard'
  const droppedTarget = anchorLocked ? 'LegacyFallback' : 'LegacyAnchor'
  const droppedAcquisitionId = anchorLocked ? 'acq-fallback' : 'acq-anchor'
  const keptTarget = anchorLocked ? 'LegacyAnchor' : 'LegacyFallback'
  const keptAcquisitionId = anchorLocked ? 'acq-anchor' : 'acq-fallback'
  const droppedWindow =
    droppedTarget === 'LegacyAnchor'
      ? ['2026-03-24T02:00:00Z', '2026-03-24T02:05:00Z']
      : ['2026-03-24T02:10:00Z', '2026-03-24T02:15:00Z']

  return {
    success: true,
    message: 'Repair complete',
    planning_mode: 'repair',
    existing_acquisitions: {
      count: 2,
      by_state: { committed: 2 },
      by_satellite: { 'SAT-1': 2 },
      acquisition_ids: ['acq-anchor', 'acq-fallback'],
      horizon_start: '2026-03-24T00:00:00Z',
      horizon_end: '2026-03-31T00:00:00Z',
    },
    fixed_count: anchorLocked ? 1 : 0,
    flex_count: anchorLocked ? 1 : 2,
    new_plan_items: [
      {
        opportunity_id: 'opp-priority-1',
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
      kept: [keptAcquisitionId],
      dropped: [droppedAcquisitionId],
      added: ['opp-priority-1'],
      moved: [],
      reason_summary: {
        dropped: [
          {
            id: droppedAcquisitionId,
            reason: anchorLocked
              ? 'Unlocked fallback replaced after preserving the hard-locked anchor'
              : 'Unlocked anchor replaced by higher-priority work',
          },
        ],
      },
      change_score: {
        num_changes: 2,
        percent_changed: 50,
      },
      change_log: {
        kept_count: 1,
        added: [
          {
            acquisition_id: 'opp-priority-1',
            satellite_id: 'SAT-1',
            target_id: 'PriorityAnchor',
            start: '2026-03-24T03:30:00Z',
            end: '2026-03-24T03:35:00Z',
            reason_code: 'higher_value',
            reason_text: anchorLocked
              ? 'Higher-priority target inserted while preserving the hard-locked anchor'
              : 'Higher-priority target inserted by replacing an unlocked acquisition',
            replaces: [droppedAcquisitionId],
            value: 99,
          },
        ],
        moved: [],
        dropped: [
          {
            acquisition_id: droppedAcquisitionId,
            satellite_id: 'SAT-1',
            target_id: droppedTarget,
            start: droppedWindow[0],
            end: droppedWindow[1],
            reason_code: 'higher_value',
            reason_text: anchorLocked
              ? 'Unlocked fallback replaced after preserving the hard-locked anchor'
              : 'Unlocked anchor replaced by higher-priority work',
            replaced_by: [],
          },
        ],
      },
    },
    metrics_before: {},
    metrics_after: {},
    metrics_comparison: {
      score_before: 160,
      score_after: 189,
      score_delta: 29,
      conflicts_before: 0,
      conflicts_after: 0,
      acquisition_count_before: 2,
      acquisition_count_after: 2,
    },
    conflicts_if_committed: [],
    commit_preview: {
      will_create: 1,
      will_conflict_with: 0,
      conflict_details: [],
      warnings: [],
    },
    algorithm_metrics: {},
    plan_id: anchorLocked ? 'repair-plan-locked' : 'repair-plan-unlocked',
    schedule_context: {},
    planner_summary: {
      target_acquisitions: [
        {
          target_id: keptTarget,
          satellite_id: 'SAT-1',
          start_time: anchorLocked ? '2026-03-24T02:00:00Z' : '2026-03-24T02:10:00Z',
          end_time: anchorLocked ? '2026-03-24T02:05:00Z' : '2026-03-24T02:15:00Z',
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
      total_targets_with_opportunities: 3,
      total_targets_covered: 2,
    },
  }
}

async function dismissCesiumErrorIfPresent(page: Page) {
  const okButton = page.getByRole('button', { name: 'OK' })
  if (await okButton.isVisible().catch(() => false)) {
    await okButton.click()
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
  const panelHeading = page.getByRole('heading', { name: panelName, exact: true }).first()

  await dismissCesiumErrorIfPresent(page)

  if (await readyLocator.isVisible().catch(() => false)) {
    return
  }

  await panelButton.click()

  if (!(await waitForVisible(readyLocator, 1500))) {
    if (await waitForVisible(panelHeading, 2000)) {
      await expect(readyLocator).toBeVisible({ timeout: 10000 })
      return
    }

    await dismissCesiumErrorIfPresent(page)
    await panelButton.click()
  }

  await expect(readyLocator).toBeVisible({ timeout: 10000 })
}

async function loadWorkspace(page: Page) {
  await page.goto('/')
  await openLeftPanel(page, 'Workspaces', page.getByText('Workspace Library'))

  const workspaceCard = page
    .locator('div.rounded-lg')
    .filter({ has: page.getByText(workspaceName, { exact: true }) })
    .first()

  await workspaceCard.getByTitle('Load workspace').click()

  await expect(page.getByText('Workspace loaded successfully')).toBeVisible()
  await expect(page.locator('div[title^="Selected workspace:"]')).toContainText(workspaceName)
}

async function openScheduleTimeline(page: Page) {
  await openLeftPanel(
    page,
    'Schedule',
    page.getByRole('heading', { name: 'Schedule', exact: true }).first(),
  )

  const timelineTab = page.getByRole('button', { name: /^Timeline\b/i })
  await expect(timelineTab).toBeVisible()
  await timelineTab.click()
  await expect(page.locator('[data-acquisition-id="acq-anchor"]')).toBeVisible({ timeout: 10000 })
}

async function openPlanningApply(page: Page, testInfo: TestInfo, screenshotName: string) {
  await openLeftPanel(page, 'Planning', page.getByRole('button', { name: /Generate Mission Plan/i }))

  const generateResponsePromise = Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/v1/schedule/mode-selection')),
    page.waitForResponse((response) => response.url().includes('/api/v1/schedule/repair')),
  ])

  const generateButton = page.getByRole('button', { name: /Generate Mission Plan/i })
  try {
    await generateButton.click({ timeout: 5000 })
  } catch {
    await generateButton.click({ force: true })
  }
  const [modeResponse, repairResponse] = await generateResponsePromise
  expect(modeResponse.ok()).toBeTruthy()
  expect(repairResponse.ok()).toBeTruthy()

  await expect(page.getByRole('button', { name: /^Next$/i })).toBeVisible()
  await page.getByRole('button', { name: /^Next$/i }).click()

  await page.screenshot({
    path: testInfo.outputPath(screenshotName),
    fullPage: true,
  })
}

function assignmentRows(page: Page, targetName: string, badgeText: 'NEW' | 'REMOVED' | 'MOVED') {
  const kind =
    badgeText === 'NEW' ? 'added' : badgeText === 'REMOVED' ? 'removed' : 'moved'

  return page.locator(`[data-assignment-kind="${kind}"][data-target-id="${targetName}"]`)
}

async function mockRepairLockApis(page: Page, serverState: MockServerState) {
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
        workspace: workspaceData,
      },
    })
  })

  await page.route('**/api/v1/satellites**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        satellites: [
          {
            id: 'SAT-1',
            name: 'ICEYE-X53',
            color: '#3B82F6',
            imaging_type: 'optical',
          },
        ],
      },
    })
  })

  await page.route('**/api/v1/config/sar-modes**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        modes: {},
      },
    })
  })

  await page.route('**/api/v1/planning/opportunities**', async (route) => {
    await route.fulfill({ json: opportunitiesResponse })
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

  await page.route('**/api/v1/schedule/master**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        zoom: 'detail',
        total: 2,
        items: buildMasterScheduleItems(serverState),
        buckets: [],
        t_start: '2026-03-24T00:00:00Z',
        t_end: '2026-03-31T00:00:00Z',
      },
    })
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
        acquisitions: buildMasterScheduleItems(serverState).map((item) => ({
          id: item.id,
          satellite_id: item.satellite_id,
          target_id: item.target_id,
          start_time: item.start_time,
          end_time: item.end_time,
          state: item.state,
          lock_level: item.lock_level,
          order_id: item.order_id,
        })),
        statistics: {
          total_acquisitions: 2,
          by_state: { committed: 2 },
          by_satellite: { 'SAT-1': 2 },
        },
      },
    })
  })

  await page.route('**/api/v1/schedule/mode-selection**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        planning_mode: 'repair',
        reason: 'Existing schedule must be repaired around current acquisitions and priorities.',
        workspace_id: workspaceId,
        existing_acquisition_count: 2,
        new_target_count: 1,
        conflict_count: 0,
        current_target_ids: missionTargets.map((target) => target.name),
        existing_target_ids: ['LegacyAnchor', 'LegacyFallback'],
        request_payload_hash: 'lock-proof-repair',
      },
    })
  })

  await page.route('**/api/v1/schedule/repair**', async (route) => {
    await route.fulfill({ json: buildRepairResponse(serverState) })
  })

  await page.route('**/api/v1/schedule/acquisition/*/lock**', async (route) => {
    const url = new URL(route.request().url())
    const acquisitionId = url.pathname.split('/').slice(-2, -1)[0]
    const lockLevel = (url.searchParams.get('lock_level') || 'none') as 'none' | 'hard'

    if (acquisitionId === 'acq-anchor') {
      serverState.anchorLockLevel = lockLevel
    }

    await route.fulfill({
      json: {
        success: true,
        message: lockLevel === 'hard' ? 'Acquisition locked' : 'Acquisition unlocked',
        acquisition_id: acquisitionId,
        lock_level: lockLevel,
      },
    })
  })
}

test.describe('Repair lock behavior', () => {
test('opens details when a timeline acquisition is selected', async ({
    page,
  }, testInfo) => {
    const serverState: MockServerState = { anchorLockLevel: 'none' }
    await mockRepairLockApis(page, serverState)
    await loadWorkspace(page)

    await openScheduleTimeline(page)
    const detailsHeading = page.getByRole('heading', { name: 'Details' })
    if (await detailsHeading.isVisible().catch(() => false)) {
      await page.getByLabel('Close Details panel').click()
      await expect(detailsHeading).not.toBeVisible()
    }

    await page.locator('[data-acquisition-id="acq-anchor"]').click()

    await expect(page.locator('[data-active-acquisition-strip]')).toHaveCount(0)
    await expect(detailsHeading).toBeVisible()
    await expect
      .poll(
        async () =>
          page.locator('[data-selection-indicator]').evaluate((el) => getComputedStyle(el).opacity),
      )
      .toBe('1')

    const acquisitionHero = page.getByTestId('inspector-acquisition-hero')
    await expect(acquisitionHero).toBeVisible()
    await expect(acquisitionHero).toContainText('LegacyAnchor')
    await expect(acquisitionHero).toContainText('ICEYE-X53')

    const lockResponsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/v1/schedule/acquisition/acq-anchor/lock'),
    )
    await page.getByRole('button', { name: 'Protect', exact: true }).click()
    const lockResponse = await lockResponsePromise
    expect(lockResponse.ok()).toBeTruthy()

    await expect(page.getByRole('button', { name: 'Unlock', exact: true })).toBeVisible()
    await expect(page.getByText('Hard locked', { exact: true })).toBeVisible()
    await expect(
      page.getByText('Protected from repair changes until you unlock it.', { exact: true }),
    ).toBeVisible()

    await page.screenshot({
      path: testInfo.outputPath('schedule-handoff-active-strip.png'),
      fullPage: true,
    })
  })

  test('replaces an unlocked acquisition when higher-priority work is added', async ({
    page,
  }, testInfo) => {
    const serverState: MockServerState = { anchorLockLevel: 'none' }
    await mockRepairLockApis(page, serverState)
    await loadWorkspace(page)

    await openScheduleTimeline(page)

    await openPlanningApply(page, testInfo, 'repair-unlocked-page2.png')

    await expect(page.getByRole('heading', { name: 'Review Changes' })).toBeVisible()
    await expect(assignmentRows(page, 'LegacyAnchor', 'REMOVED')).toHaveCount(1)
    await expect(assignmentRows(page, 'LegacyAnchor', 'REMOVED').first()).toBeVisible()
    await expect(assignmentRows(page, 'PriorityAnchor', 'NEW')).toHaveCount(1)
    await expect(assignmentRows(page, 'PriorityAnchor', 'NEW').first()).toBeVisible()
    await expect(page.getByText('REMOVED', { exact: true })).toHaveCount(1)
  })

  test('preserves a hard-locked acquisition after timeline double-click and replaces a different unlocked one', async ({
    page,
  }, testInfo) => {
    const serverState: MockServerState = { anchorLockLevel: 'none' }
    await mockRepairLockApis(page, serverState)
    await loadWorkspace(page)

    await openScheduleTimeline(page)

    const lockResponsePromise = page.waitForResponse((response) =>
      response.url().includes('/api/v1/schedule/acquisition/acq-anchor/lock'),
    )

    await page.locator('[data-acquisition-id="acq-anchor"]').dblclick()
    const lockResponse = await lockResponsePromise
    expect(lockResponse.ok()).toBeTruthy()

    await expect(page.getByText('1 locked', { exact: true })).toBeVisible()
    expect(serverState.anchorLockLevel).toBe('hard')

    await openPlanningApply(page, testInfo, 'repair-locked-page2.png')

    await expect(page.getByRole('heading', { name: 'Review Changes' })).toBeVisible()
    await expect(assignmentRows(page, 'LegacyFallback', 'REMOVED')).toHaveCount(1)
    await expect(assignmentRows(page, 'LegacyFallback', 'REMOVED').first()).toBeVisible()
    await expect(assignmentRows(page, 'LegacyAnchor', 'REMOVED')).toHaveCount(0)
    await expect(assignmentRows(page, 'PriorityAnchor', 'NEW')).toHaveCount(1)
    await expect(assignmentRows(page, 'PriorityAnchor', 'NEW').first()).toBeVisible()
    await expect(page.getByText('REMOVED', { exact: true })).toHaveCount(1)
  })
})
