import { writeFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page, TestInfo } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'
const liveOperatorEnabled = process.env.PLAYWRIGHT_LIVE_OPERATOR === '1'
const referenceWorkspaceId =
  process.env.LIVE_OPERATOR_REFERENCE_WORKSPACE_ID ||
  'fb48bc94-3d14-4652-bc03-4a3c9d0bb56a'

const weeklyAdditionPattern = [3, 1, 4, 2, 5, 1, 3, 2, 4, 1, 5, 2]
const weeklyCheckpointRuns = new Set([1, 6, 9, 13])
const incrementalCampaignPattern = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
const incrementalCampaignCheckpointRuns = new Set([1, 8, 16])
const customSatelliteName = 'CUSTOM-45DEG-450KM'

type Target = {
  name: string
  latitude: number
  longitude: number
  priority?: number
  color?: string
}

type CommitItem = {
  opportunity_id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  roll_angle_deg: number
  pitch_angle_deg?: number
  value?: number
  incidence_angle_deg?: number
}

type DirectScheduleItem = {
  opportunity_id?: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  roll_angle_deg?: number
  roll_angle?: number
  pitch_angle_deg?: number
  pitch_angle?: number
  value?: number
  incidence_angle_deg?: number
  incidence_angle?: number
}

type PlanningModeSelection = {
  success: boolean
  planning_mode: 'from_scratch' | 'incremental' | 'repair'
  reason: string
  workspace_id: string
  existing_acquisition_count: number
  new_target_count: number
  conflict_count: number
  current_target_ids: string[]
  existing_target_ids: string[]
}

type RepairPlanResponse = {
  success: boolean
  plan_id?: string
  new_plan_items: DirectScheduleItem[]
  repair_diff: {
    kept: string[]
    dropped: string[]
    added: string[]
    moved: Array<{ id: string }>
  }
  metrics_comparison: {
    acquisition_count_before: number
    acquisition_count_after: number
  }
}

type WeeklyRunSummary = {
  run: number
  targets_total: number
  opportunities: number
  mode: string
  before_count: number
  after_count: number
  commit: {
    committed: number
    dropped: number
  }
  plan_summary: Record<string, number>
  ui_checkpoint?: {
    heading: string
    stats: string[]
    coverage: string | null
    screenshot: string
  }
}

const modTargetsA: Target[] = [
  { name: 'Paris', latitude: 48.8566, longitude: 2.3522, priority: 4 },
  { name: 'Berlin', latitude: 52.52, longitude: 13.405, priority: 4 },
  { name: 'Madrid', latitude: 40.4168, longitude: -3.7038, priority: 4 },
]

const modTargetsIncremental: Target[] = [
  ...modTargetsA,
  { name: 'Rome', latitude: 41.9028, longitude: 12.4964, priority: 4 },
  { name: 'Vienna', latitude: 48.2082, longitude: 16.3738, priority: 4 },
]

const modTargetsSubset: Target[] = [
  { name: 'Paris', latitude: 48.8566, longitude: 2.3522, priority: 4 },
  { name: 'Madrid', latitude: 40.4168, longitude: -3.7038, priority: 4 },
]

const fallbackCustomSatellite = {
  name: customSatelliteName,
  line1: '1 99001U 25999A   25337.00000000  .00000000  00000+0  00000+0 0  9990',
  line2: '2 99001  45.0000 100.0000 0001000   0.0000   0.0000 15.38000000    10',
}

const liveIceyeSatellite = {
  name: 'ICEYE-X53',
  line1: '1 64584U 25135BJ  26064.28789825  .00007988  00000+0  63127-3 0  9993',
  line2: '2 64584  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499',
}

function generateFallbackTargetPool(count: number): Target[] {
  const centerLat = 24.7136
  const centerLon = 46.6753
  return Array.from({ length: count }, (_, index) => {
    const i = index + 1
    const radius = 0.18 + index * 0.022
    const angle = index * 0.62
    const lat = centerLat + Math.sin(angle) * radius
    const lon = centerLon + Math.cos(angle) * radius * 1.35
    return {
      name: `OPS_T${String(i).padStart(3, '0')}`,
      latitude: Number(lat.toFixed(4)),
      longitude: Number(lon.toFixed(4)),
      priority: 5,
      color: '#EF4444',
    }
  })
}

async function ensureLiveServices(request: APIRequestContext) {
  const [frontendResponse, apiResponse] = await Promise.all([
    fetch(process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000'),
    request.get(`${apiBaseUrl}/api/v1/workspaces`),
  ])

  expect(frontendResponse.ok).toBeTruthy()
  expect(apiResponse.ok()).toBeTruthy()
}

async function apiGet<T>(
  request: APIRequestContext,
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
  timeout: number = 120_000,
): Promise<T> {
  const response = await request.get(`${apiBaseUrl}${path}`, {
    params,
    timeout,
  })
  expect(response.ok(), `GET ${path} failed with ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

async function apiPost<T>(
  request: APIRequestContext,
  path: string,
  data: unknown,
  timeout: number = 240_000,
): Promise<T> {
  let lastError: unknown

  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await request.post(`${apiBaseUrl}${path}`, {
        data,
        timeout,
      })
      expect(response.ok(), `POST ${path} failed with ${response.status()}`).toBeTruthy()
      return (await response.json()) as T
    } catch (error) {
      lastError = error
      const message = error instanceof Error ? error.message : String(error)
      const isTransientNetworkFailure =
        message.includes('socket hang up') ||
        message.includes('ECONNRESET') ||
        message.includes('fetch failed')

      if (!isTransientNetworkFailure || attempt === 3) {
        throw error
      }

      console.log(`[live-api] transient POST failure for ${path}, retrying (${attempt}/3)`)
      await new Promise((resolve) => setTimeout(resolve, attempt * 1000))
    }
  }

  throw lastError instanceof Error ? lastError : new Error(`POST ${path} failed`)
}

async function getCustomSatellite(request: APIRequestContext) {
  const response = await apiGet<{
    satellites?: Array<{ name?: string; line1?: string; line2?: string }>
  }>(request, '/api/v1/satellites')
  const match = response.satellites?.find((satellite) => satellite.name === customSatelliteName)

  return {
    name: match?.name || fallbackCustomSatellite.name,
    line1: match?.line1 || fallbackCustomSatellite.line1,
    line2: match?.line2 || fallbackCustomSatellite.line2,
  }
}

async function getReferenceTargetPool(request: APIRequestContext): Promise<Target[]> {
  try {
    const response = await request.get(`${apiBaseUrl}/api/v1/workspaces/${referenceWorkspaceId}`, {
      timeout: 60_000,
    })
    if (response.ok()) {
      const body = (await response.json()) as {
        workspace?: { scenario_config?: { targets?: Target[] } }
      }
      const targets = body.workspace?.scenario_config?.targets
      if (Array.isArray(targets) && targets.length >= 83) {
        return targets.slice(0, 83)
      }
    }
  } catch {
    // Fall back to a generated clustered pool if the reference workspace is missing.
  }

  return generateFallbackTargetPool(83)
}

async function createWorkspace(request: APIRequestContext, name: string) {
  const response = await apiPost<{ workspace_id: string }>(request, '/api/v1/workspaces', {
    name,
  })
  return response.workspace_id
}

async function analyzeWorkspace(
  request: APIRequestContext,
  workspaceId: string,
  satellite: { name: string; line1: string; line2: string },
  targets: Target[],
  options?: { startOffsetMs?: number },
) {
  const startOffsetMs = options?.startOffsetMs ?? 0
  const now = new Date(Date.now() + startOffsetMs)
  const end = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  return apiPost<{
    data?: { mission_data?: { passes?: unknown[]; targets?: Target[] } }
  }>(request, '/api/v1/mission/analyze', {
    workspace_id: workspaceId,
    satellites: [satellite],
    targets,
    start_time: now.toISOString(),
    end_time: end.toISOString(),
    imaging_type: 'optical',
  })
}

async function getOpportunitiesCount(request: APIRequestContext, workspaceId: string) {
  const response = await apiGet<{ opportunities?: unknown[]; count?: number }>(
    request,
    '/api/v1/planning/opportunities',
    { workspace_id: workspaceId },
  )
  return response.count ?? response.opportunities?.length ?? 0
}

async function getHorizon(
  request: APIRequestContext,
  workspaceId: string,
  includeFailed = false,
  durationDays = 7,
) {
  const now = new Date()
  const end = new Date(now.getTime() + durationDays * 24 * 60 * 60 * 1000)
  return apiGet<{
    acquisitions?: Array<{
      id: string
      satellite_id: string
      target_id: string
      start_time: string
      end_time: string
      state: string
      lock_level: string
    }>
    statistics?: {
      total_acquisitions?: number
      by_state?: Record<string, number>
      by_satellite?: Record<string, number>
    }
  }>(request, '/api/v1/schedule/horizon', {
    workspace_id: workspaceId,
    from: now.toISOString(),
    to: end.toISOString(),
    include_failed: includeFailed,
  })
}

function toCommitItems(schedule: DirectScheduleItem[]): CommitItem[] {
  return schedule.map((item, index) => ({
    opportunity_id: item.opportunity_id || `live_item_${index + 1}`,
    satellite_id: item.satellite_id,
    target_id: item.target_id,
    start_time: item.start_time,
    end_time: item.end_time,
    roll_angle_deg: item.roll_angle_deg ?? item.roll_angle ?? 0,
    pitch_angle_deg: item.pitch_angle_deg ?? item.pitch_angle ?? 0,
    value: item.value,
    incidence_angle_deg: item.incidence_angle_deg ?? item.incidence_angle,
  }))
}

async function runPlanningViaApi(
  request: APIRequestContext,
  workspaceId: string,
  targets: Target[],
  beforeCount: number,
  weights?: {
    weight_priority: number
    weight_geometry: number
    weight_timing: number
  },
) {
  const now = new Date()
  const end = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  const weightConfig = weights ?? {
    weight_priority: 40,
    weight_geometry: 40,
    weight_timing: 20,
  }

  const modeSelection = await apiPost<PlanningModeSelection>(
    request,
    '/api/v1/schedule/mode-selection',
    {
      workspace_id: workspaceId,
      horizon_from: now.toISOString(),
      horizon_to: end.toISOString(),
      ...weightConfig,
    },
  )

  if (modeSelection.planning_mode === 'repair') {
    const targetPriorities = Object.fromEntries(
      targets.map((target) => [target.name, target.priority ?? 5]),
    )

    const repair = await apiPost<RepairPlanResponse>(request, '/api/v1/schedule/repair', {
      planning_mode: 'repair',
      workspace_id: workspaceId,
      include_tentative: false,
      target_priorities: targetPriorities,
      ...weightConfig,
    })

    const dropped = repair.repair_diff?.dropped ?? []
    const moved = repair.repair_diff?.moved ?? []
    const added = repair.repair_diff?.added ?? []

    const commit =
      repair.plan_id && (dropped.length > 0 || added.length > 0 || moved.length > 0)
        ? await apiPost<{
            committed: number
            dropped: number
          }>(request, '/api/v1/schedule/repair/commit', {
            plan_id: repair.plan_id,
            workspace_id: workspaceId,
            drop_acquisition_ids: dropped,
            force: true,
          })
        : { committed: 0, dropped: 0 }

    return {
      modeSelection,
      planResponse: repair,
      commit,
      planSummary: {
        kept: repair.repair_diff?.kept?.length ?? 0,
        dropped: dropped.length,
        added: added.length,
        moved: moved.length,
        after_from_metrics: repair.metrics_comparison?.acquisition_count_after ?? beforeCount,
      },
    }
  }

  const planner = await apiPost<{
    results: {
      roll_pitch_best_fit: {
        schedule: DirectScheduleItem[]
        metrics?: {
          opportunities_accepted?: number
        }
        target_statistics?: {
          total_targets?: number
          targets_acquired?: number
        }
      }
    }
  }>(request, '/api/v1/planning/schedule', {
    workspace_id: workspaceId,
    algorithms: ['roll_pitch_best_fit'],
    mode: modeSelection.planning_mode,
    ...weightConfig,
  })

  const result = planner.results.roll_pitch_best_fit
  const schedule = result.schedule ?? []
  const commit =
    schedule.length > 0
      ? await apiPost<{ committed: number; acquisition_ids: string[] }>(
          request,
          '/api/v1/schedule/commit/direct',
          {
            workspace_id: workspaceId,
            items: toCommitItems(schedule),
            algorithm: 'roll_pitch_best_fit',
            force: true,
          },
        )
      : { committed: 0, acquisition_ids: [] }

  return {
    modeSelection,
    planResponse: planner,
    commit: {
      committed: commit.committed,
      dropped: 0,
    },
    planSummary: {
      scheduled_items: schedule.length,
      accepted: result.metrics?.opportunities_accepted ?? schedule.length,
      total_targets: result.target_statistics?.total_targets ?? targets.length,
      targets_acquired: result.target_statistics?.targets_acquired ?? schedule.length,
    },
  }
}

async function loadWorkspaceInUi(page: Page, workspaceName: string) {
  console.log(`[live-ui] load workspace: ${workspaceName}`)
  await page.goto('/', { waitUntil: 'networkidle' })
  console.log('[live-ui] root page loaded')
  await page.getByLabel('Workspaces').click()
  await expect(page.getByText('Workspace Library')).toBeVisible()
  console.log('[live-ui] workspace library open')
  const refreshButton = page.getByRole('button', { name: 'Refresh workspace list' })
  const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    if (await refreshButton.isVisible().catch(() => false)) {
      await refreshButton.click()
      console.log(`[live-ui] workspace list refresh requested (attempt ${attempt})`)
    }

    const workspaceCard = page
      .locator('div.rounded-lg')
      .filter({ has: page.getByText(workspaceName, { exact: true }) })
      .first()

    await expect(workspaceCard).toBeVisible({ timeout: 60_000 })
    console.log('[live-ui] workspace card visible')
    await workspaceCard.getByTitle('Load workspace').click({ force: true })

    try {
      await expect(headerWorkspaceBadge).toContainText(workspaceName, { timeout: 60_000 })
      console.log(`[live-ui] workspace loaded: ${workspaceName}`)
      return
    } catch (error) {
      const transientError = page.getByText(/Failed to (fetch|load workspace)/i).first()
      const sawTransientError = await transientError.isVisible().catch(() => false)

      if (attempt === 2) {
        throw error
      }

      if (sawTransientError) {
        console.log('[live-ui] transient workspace load error detected, retrying once')
      } else {
        console.log('[live-ui] workspace badge did not update, retrying once')
      }
    }
  }
}

async function runPlanningViaUi(
  page: Page,
  workspaceName: string,
  screenshotName: string,
  testInfo: TestInfo,
  options?: { autoCommit?: boolean; skipWorkspaceLoad?: boolean; scoringPreset?: string },
) {
  if (!options?.skipWorkspaceLoad) {
    await loadWorkspaceInUi(page, workspaceName)
  }
  console.log('[live-ui] open planning panel')
  const planningButton = page.getByLabel('Planning')
  const planningHeading = page.getByRole('heading', { name: 'Planning', exact: true }).first()

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    await planningButton.click()
    if (await planningHeading.isVisible().catch(() => false)) {
      break
    }
    console.log(`[live-ui] planning panel not visible yet, retrying (${attempt}/2)`)
    await page.waitForTimeout(1000)
  }
  await expect(planningHeading).toBeVisible({ timeout: 60_000 })

  const generateButton = page.getByRole('button', { name: /Generate Mission Plan/i })
  const rerunButton = page.locator('button', { hasText: 'Change Presets & Re-run' }).last()

  if (!(await generateButton.isVisible().catch(() => false))) {
    const rerunCount = await rerunButton.count()
    const rerunVisible = rerunCount > 0 && (await rerunButton.isVisible().catch(() => false))
    console.log(
      `[live-ui] planning action state before next run: generate=${false} rerunCount=${rerunCount} rerunVisible=${rerunVisible}`,
    )
  }

  if (!(await generateButton.isVisible().catch(() => false)) && (await rerunButton.count()) > 0) {
    console.log('[live-ui] clearing prior planning results before next run')
    await rerunButton.scrollIntoViewIfNeeded()
    await rerunButton.click()
    await page.waitForTimeout(500)
  }

  await expect(generateButton).toBeVisible({ timeout: 60_000 })

  if (options?.scoringPreset) {
    const presetButton = page.getByRole('button', { name: options.scoringPreset, exact: true })
    await expect(presetButton).toBeVisible({ timeout: 30_000 })
    await presetButton.click()
    console.log(`[live-ui] scoring preset selected: ${options.scoringPreset}`)
  }

  const modePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/v1/schedule/mode-selection'),
  )
  const planPromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      (response.url().includes('/api/v1/planning/schedule') ||
        response.url().includes('/api/v1/schedule/repair')),
  )

  console.log('[live-ui] generate mission plan')
  await generateButton.click()

  const modeResponse = await modePromise
  const planResponse = await planPromise
  expect(modeResponse.ok()).toBeTruthy()
  expect(planResponse.ok()).toBeTruthy()
  console.log('[live-ui] planning responses received')

  const modeJson = (await modeResponse.json()) as PlanningModeSelection
  const planJson = (await planResponse.json()) as Record<string, unknown>
  const nextButton = page.getByRole('button', { name: /^Next$/i })
  const noChangesButton = page.getByRole('button', { name: /No Changes to Apply/i })

  let actionState: 'review_ready' | 'no_changes' | 'pending' = 'pending'
  const waitDeadline = Date.now() + 60_000
  while (Date.now() < waitDeadline && actionState === 'pending') {
    if (await nextButton.isVisible().catch(() => false)) {
      actionState = 'review_ready'
      break
    }
    if (await noChangesButton.isVisible().catch(() => false)) {
      actionState = 'no_changes'
      break
    }
    await page.waitForTimeout(250)
  }

  expect(actionState).not.toBe('pending')

  if (actionState === 'review_ready') {
    await nextButton.click()
    await page.waitForTimeout(1500)
    console.log('[live-ui] apply page open')
  } else {
    console.log('[live-ui] no actionable changes returned by planner')
  }

  const applyHeading = page
    .getByRole('heading', { level: 3 })
    .filter({ hasText: /Ready to Apply|Review Changes|Conflicts Detected/ })
    .first()
  const heading =
    actionState === 'no_changes'
      ? 'No Changes to Apply'
      : (await applyHeading.textContent().catch(() => null)) ||
        (await page.locator('h3.text-sm.font-semibold.text-white').first().textContent()) ||
        ''

  const statValues = page.locator(
    'div.grid.grid-cols-3.gap-2 .text-lg.font-bold.text-white.leading-tight',
  )
  const stats = actionState === 'no_changes' ? [] : await statValues.allInnerTexts()
  const coverageText =
    actionState === 'no_changes'
      ? null
      : (await page
          .locator('text=/\\d+\\/\\d+ \\(\\d+%\\)/')
          .first()
          .textContent()
          .catch(() => null)) || null
  const badgeCounts = {
    added: await page.getByText('NEW', { exact: true }).count(),
    moved: await page.getByText('MOVED', { exact: true }).count(),
    removed: await page.getByText('REMOVED', { exact: true }).count(),
  }

  const screenshotPath = testInfo.outputPath(screenshotName)
  await page.screenshot({ path: screenshotPath, fullPage: true })
  console.log(`[live-ui] screenshot saved: ${screenshotName}`)

  let commitJson: Record<string, unknown> | undefined
  if (options?.autoCommit !== false && actionState === 'review_ready') {
    const commitPromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        (response.url().includes('/api/v1/schedule/commit/direct') ||
          response.url().includes('/api/v1/schedule/repair/commit')),
    )

    await page.getByRole('button', { name: /Apply (Plan|Anyway)/i }).click()
    const commitResponse = await commitPromise
    const commitStatus = commitResponse.status()
    const commitText = await commitResponse.text()
    console.log(`[live-ui] commit status: ${commitStatus}`)
    if (!commitResponse.ok()) {
      console.log(`[live-ui] commit body: ${commitText}`)
    }
    expect(commitResponse.ok(), commitText).toBeTruthy()
    commitJson = JSON.parse(commitText) as Record<string, unknown>
    console.log('[live-ui] commit response received')

    await page.waitForTimeout(2000)
  }

  return {
    modeSelection: modeJson,
    planResponse: planJson,
    commitResponse: commitJson,
    uiSummary: {
      actionState,
      heading,
      stats,
      coverage: coverageText,
      screenshot: screenshotPath,
      badgeCounts,
    },
  }
}

async function openScheduleTimeline(page: Page, testInfo?: TestInfo) {
  console.log('[live-ui] open schedule timeline')
  await page.getByRole('button', { name: 'Schedule', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Schedule', exact: true }).first()).toBeVisible()
  const schedulePanel = page
    .locator('div.h-full.flex.flex-col')
    .filter({
      has: page.getByRole('heading', { name: 'Schedule', exact: true }),
      has: page.locator('button', { hasText: /^Timeline/ }),
    })
    .filter({ hasNot: page.getByText('Workspace Library') })
    .last()
  const timelineTab = schedulePanel.locator('button', { hasText: /^Timeline/ }).first()

  await expect(timelineTab).toBeVisible({ timeout: 30_000 })
  await timelineTab.click({ force: true, timeout: 10_000 })
  console.log('[live-ui] timeline tab clicked')
  await page.waitForTimeout(5000)
  const timelineInfo = await page.evaluate(() => ({
    barCount: document.querySelectorAll('[data-acquisition-id]').length,
    bodyText: document.body.innerText.slice(0, 2500),
  }))
  console.log(`[live-ui] timeline bar count: ${timelineInfo.barCount}`)

  if (timelineInfo.barCount === 0 && testInfo) {
    const emptyPath = testInfo.outputPath('live-lock-timeline-empty.png')
    await page.screenshot({ path: emptyPath, fullPage: true })
  }

  expect(
    timelineInfo.barCount,
    `Expected live timeline bars after opening Schedule -> Timeline.\n${timelineInfo.bodyText}`,
  ).toBeGreaterThan(0)

  const firstBar = page.locator('[data-acquisition-id]').first()
  await firstBar.scrollIntoViewIfNeeded()
  await expect(firstBar).toBeVisible({ timeout: 10_000 })
  const acquisitionId = await firstBar.getAttribute('data-acquisition-id')
  expect(acquisitionId).toBeTruthy()
  console.log(`[live-ui] first visible timeline acquisition: ${acquisitionId}`)
  return acquisitionId as string
}

test.describe('Live operator drill', () => {
  test.skip(!liveOperatorEnabled, 'Set PLAYWRIGHT_LIVE_OPERATOR=1 to run live backend drills')

  test.beforeAll(async ({ request }) => {
    await ensureLiveServices(request)
  })

  test('runs a live weekly operator loop with real solver checkpoints', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(15 * 60 * 1000)

    const targetPool = await getReferenceTargetPool(request)
    const customSatellite = await getCustomSatellite(request)
    const workspaceName = `live_operator_weekly_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const currentTargets = targetPool.slice(0, 50)
    const report: {
      workspace_id: string
      workspace_name: string
      addition_pattern: number[]
      runs: WeeklyRunSummary[]
    } = {
      workspace_id: workspaceId,
      workspace_name: workspaceName,
      addition_pattern: weeklyAdditionPattern,
      runs: [],
    }
    let workspaceLoadedInUi = false

    for (let runIndex = 0; runIndex < weeklyAdditionPattern.length + 1; runIndex += 1) {
      if (runIndex > 0) {
        const nextCount = weeklyAdditionPattern[runIndex - 1] ?? 0
        const nextSliceEnd = Math.min(currentTargets.length + nextCount, targetPool.length)
        currentTargets.push(...targetPool.slice(currentTargets.length, nextSliceEnd))
      }

      const runNumber = runIndex + 1
      console.log(
        `[live-weekly] run ${runNumber}/${weeklyAdditionPattern.length + 1} start with ${currentTargets.length} targets`,
      )

      const analyze = await analyzeWorkspace(request, workspaceId, customSatellite, currentTargets)
      const passes =
        analyze.data?.mission_data?.passes && Array.isArray(analyze.data.mission_data.passes)
          ? analyze.data.mission_data.passes.length
          : 0
      expect(passes).toBeGreaterThan(0)

      const opportunities = await getOpportunitiesCount(request, workspaceId)
      const beforeHorizon = await getHorizon(request, workspaceId)
      const beforeCount = beforeHorizon.acquisitions?.length ?? 0

      const checkpointScreenshot = weeklyCheckpointRuns.has(runNumber)
        ? `live-weekly-run-${String(runNumber).padStart(2, '0')}.png`
        : null

      const result = checkpointScreenshot
        ? await runPlanningViaUi(page, workspaceName, checkpointScreenshot, testInfo, {
            skipWorkspaceLoad: workspaceLoadedInUi,
          })
        : await runPlanningViaApi(request, workspaceId, currentTargets, beforeCount)

      const afterHorizon = await getHorizon(request, workspaceId)
      const afterCount = afterHorizon.acquisitions?.length ?? 0

      const summary: WeeklyRunSummary = {
        run: runNumber,
        targets_total: currentTargets.length,
        opportunities,
        mode: result.modeSelection.planning_mode,
        before_count: beforeCount,
        after_count: afterCount,
        commit: {
          committed: Number(result.commitResponse?.committed ?? result.commit?.committed ?? 0),
          dropped: Number(result.commitResponse?.dropped ?? result.commit?.dropped ?? 0),
        },
        plan_summary: result.planSummary ?? {},
      }

      if ('uiSummary' in result && result.uiSummary) {
        summary.ui_checkpoint = result.uiSummary
      }

      report.runs.push(summary)
      console.log(
        `[live-weekly] run ${runNumber} complete: mode=${summary.mode} before=${beforeCount} after=${afterCount} committed=${summary.commit.committed} dropped=${summary.commit.dropped}`,
      )
      if ('uiSummary' in result && result.uiSummary) {
        workspaceLoadedInUi = true
      }

      if (result.modeSelection.planning_mode === 'repair') {
        const metricsAfter =
          Number(
            (result.planResponse as { metrics_comparison?: { acquisition_count_after?: number } })
              .metrics_comparison?.acquisition_count_after ?? afterCount,
          ) || afterCount
        expect(afterCount).toBe(metricsAfter)
      }

      if (result.modeSelection.planning_mode !== 'repair') {
        const planner = result.planResponse as {
          results?: {
            roll_pitch_best_fit?: {
              schedule?: unknown[]
            }
          }
        }
        const scheduleCount = planner.results?.roll_pitch_best_fit?.schedule?.length ?? 0
        expect(afterCount).toBe(beforeCount + scheduleCount)
      }
    }

    const summaryPath = testInfo.outputPath('live-operator-weekly-summary.json')
    writeFileSync(summaryPath, JSON.stringify(report, null, 2))

    await testInfo.attach('live-operator-weekly-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })

    expect(report.runs).toHaveLength(13)
    expect(report.runs[0]?.mode).toBe('from_scratch')
    expect(report.runs[0]?.targets_total).toBe(50)
    expect(report.runs.at(-1)?.targets_total).toBe(83)
  })

  test('walks through live from-scratch, incremental, and repair-removal apply states', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(12 * 60 * 1000)

    const workspaceName = `live_mode_matrix_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const matrixReport: {
      workspace_id: string
      workspace_name: string
      steps: Array<{
        name: string
        mode: string
        before_count: number
        after_count: number
        screenshot: string | null
        reason: string
      }>
    } = {
      workspace_id: workspaceId,
      workspace_name: workspaceName,
      steps: [],
    }
    let workspaceLoadedInUi = false

    await analyzeWorkspace(request, workspaceId, liveIceyeSatellite, modTargetsA, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    const beforeFromScratch = (await getHorizon(request, workspaceId)).acquisitions?.length ?? 0
    const fromScratch = await runPlanningViaUi(
      page,
      workspaceName,
      'live-mode-matrix-step-1-from-scratch.png',
      testInfo,
      { skipWorkspaceLoad: workspaceLoadedInUi },
    )
    workspaceLoadedInUi = true
    const afterFromScratch = (await getHorizon(request, workspaceId)).acquisitions?.length ?? 0
    expect(fromScratch.modeSelection.planning_mode).toBe('from_scratch')
    matrixReport.steps.push({
      name: 'from_scratch',
      mode: fromScratch.modeSelection.planning_mode,
      before_count: beforeFromScratch,
      after_count: afterFromScratch,
      screenshot: fromScratch.uiSummary?.screenshot ?? null,
      reason: fromScratch.modeSelection.reason,
    })

    await analyzeWorkspace(request, workspaceId, liveIceyeSatellite, modTargetsIncremental, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    const beforeIncremental = (await getHorizon(request, workspaceId)).acquisitions?.length ?? 0
    const incremental = await runPlanningViaUi(
      page,
      workspaceName,
      'live-mode-matrix-step-2-incremental.png',
      testInfo,
      { skipWorkspaceLoad: workspaceLoadedInUi },
    )
    const afterIncremental = (await getHorizon(request, workspaceId)).acquisitions?.length ?? 0
    expect(incremental.modeSelection.planning_mode).toBe('incremental')
    if (incremental.uiSummary?.actionState === 'no_changes') {
      expect(afterIncremental).toBe(beforeIncremental)
    } else {
      expect(afterIncremental).toBeGreaterThan(beforeIncremental)
    }
    matrixReport.steps.push({
      name: 'incremental',
      mode: incremental.modeSelection.planning_mode,
      before_count: beforeIncremental,
      after_count: afterIncremental,
      screenshot: incremental.uiSummary?.screenshot ?? null,
      reason: incremental.modeSelection.reason,
    })

    const repairBaselineHorizon = await getHorizon(request, workspaceId, false, 10)
    const committedTargetIds = Array.from(
      new Set((repairBaselineHorizon.acquisitions ?? []).map((acquisition) => acquisition.target_id)),
    )
    const targetCatalog = new Map(
      [...modTargetsIncremental, ...modTargetsSubset].map((target) => [target.name, target]),
    )
    const removableTargetId = committedTargetIds[0]
    const repairTargets = committedTargetIds
      .filter((targetId) => targetId !== removableTargetId)
      .map((targetId) => targetCatalog.get(targetId))
      .filter((target): target is Target => !!target)

    expect(removableTargetId).toBeTruthy()
    expect(repairTargets.length).toBeGreaterThan(0)

    await analyzeWorkspace(request, workspaceId, liveIceyeSatellite, repairTargets, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    const beforeRepair = (await getHorizon(request, workspaceId, false, 10)).acquisitions?.length ?? 0
    const repair = await runPlanningViaUi(
      page,
      workspaceName,
      'live-mode-matrix-step-3-repair-remove.png',
      testInfo,
      { skipWorkspaceLoad: workspaceLoadedInUi },
    )
    const afterRepair = (await getHorizon(request, workspaceId, false, 10)).acquisitions?.length ?? 0
    const repairPlan = repair.planResponse as RepairPlanResponse
    expect(repair.modeSelection.planning_mode).toBe('repair')
    expect(repairPlan.repair_diff.dropped.length).toBeGreaterThan(0)
    expect(repairPlan.repair_diff.added).toHaveLength(0)
    expect(afterRepair).toBe(beforeRepair - repairPlan.repair_diff.dropped.length)
    matrixReport.steps.push({
      name: 'repair_remove',
      mode: repair.modeSelection.planning_mode,
      before_count: beforeRepair,
      after_count: afterRepair,
      screenshot: repair.uiSummary?.screenshot ?? null,
      reason: repair.modeSelection.reason,
    })

    const summaryPath = testInfo.outputPath('live-mode-matrix-summary.json')
    writeFileSync(summaryPath, JSON.stringify(matrixReport, null, 2))
    await testInfo.attach('live-mode-matrix-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })

  test('captures a live repair apply page with both added and removed actions', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(10 * 60 * 1000)

    const workspaceName = `live_repair_add_remove_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const customSatellite = await getCustomSatellite(request)
    const targetPool = generateFallbackTargetPool(58)
    const baseTargets = targetPool.slice(0, 50)
    const expansionTargets = targetPool.slice(50).map((target) => ({
      ...target,
      priority: 1,
      color: '#22C55E',
    }))

    await analyzeWorkspace(request, workspaceId, customSatellite, baseTargets, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    const baselinePlan = await apiPost<{
      results: {
        roll_pitch_best_fit: {
          schedule: DirectScheduleItem[]
        }
      }
    }>(request, '/api/v1/planning/schedule', {
      workspace_id: workspaceId,
      algorithms: ['roll_pitch_best_fit'],
      mode: 'from_scratch',
      weight_priority: 40,
      weight_geometry: 40,
      weight_timing: 20,
    })
    const baselineSchedule = baselinePlan.results.roll_pitch_best_fit.schedule
    expect(baselineSchedule.length).toBeGreaterThan(0)
    await apiPost(request, '/api/v1/schedule/commit/direct', {
      workspace_id: workspaceId,
      items: toCommitItems(baselineSchedule),
      algorithm: 'roll_pitch_best_fit',
      force: true,
    })

    const removedTargetId = baselineSchedule[0]?.target_id
    expect(removedTargetId).toBeTruthy()
    const repairTargets = [
      ...baseTargets.filter((target) => target.name !== removedTargetId),
      ...expansionTargets,
    ]

    await analyzeWorkspace(request, workspaceId, customSatellite, repairTargets, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    const beforeRepair = (await getHorizon(request, workspaceId, false, 10)).acquisitions?.length ?? 0
    const liveRepair = await runPlanningViaUi(
      page,
      workspaceName,
      'live-repair-add-remove-page2.png',
      testInfo,
    )
    const afterRepair = (await getHorizon(request, workspaceId, false, 10)).acquisitions?.length ?? 0
    const repairPlan = liveRepair.planResponse as RepairPlanResponse
    const committed = Number((liveRepair.commitResponse as { committed?: number })?.committed ?? 0)
    const dropped = Number((liveRepair.commitResponse as { dropped?: number })?.dropped ?? 0)

    expect(liveRepair.modeSelection.planning_mode).toBe('repair')
    expect(repairPlan.repair_diff.added.length).toBeGreaterThan(0)
    expect(repairPlan.repair_diff.dropped.length).toBeGreaterThan(0)
    expect(afterRepair).toBe(beforeRepair + committed - dropped)

    const summaryPath = testInfo.outputPath('live-repair-add-remove-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          workspace_id: workspaceId,
          workspace_name: workspaceName,
          removed_target_id: removedTargetId,
          repair_diff: repairPlan.repair_diff,
          ui_checkpoint: liveRepair.uiSummary,
          commit: liveRepair.commitResponse,
        },
        null,
        2,
      ),
    )
    await testInfo.attach('live-repair-add-remove-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })

  test('preserves the loaded workspace across refresh and still finds live repair conflicts', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(10 * 60 * 1000)

    const workspaceName = `live_refresh_repair_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const customSatellite = await getCustomSatellite(request)
    const targetPool = generateFallbackTargetPool(53)
    const baseTargets = targetPool.slice(0, 50)
    const expansionTargets = targetPool.slice(50).map((target) => ({
      ...target,
      priority: 1,
      color: '#22C55E',
    }))

    await analyzeWorkspace(request, workspaceId, customSatellite, baseTargets, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    const baselinePlan = await apiPost<{
      results: {
        roll_pitch_best_fit: {
          schedule: DirectScheduleItem[]
        }
      }
    }>(request, '/api/v1/planning/schedule', {
      workspace_id: workspaceId,
      algorithms: ['roll_pitch_best_fit'],
      mode: 'from_scratch',
      weight_priority: 40,
      weight_geometry: 40,
      weight_timing: 20,
    })
    const baselineSchedule = baselinePlan.results.roll_pitch_best_fit.schedule
    expect(baselineSchedule.length).toBeGreaterThan(0)
    await apiPost(request, '/api/v1/schedule/commit/direct', {
      workspace_id: workspaceId,
      items: toCommitItems(baselineSchedule),
      algorithm: 'roll_pitch_best_fit',
      force: true,
    })

    const removedTargetId = baselineSchedule[0]?.target_id
    expect(removedTargetId).toBeTruthy()
    const repairTargets = [
      ...baseTargets.filter((target) => target.name !== removedTargetId),
      ...expansionTargets,
    ]

    await analyzeWorkspace(request, workspaceId, customSatellite, repairTargets, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })

    await loadWorkspaceInUi(page, workspaceName)
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')
    await expect(headerWorkspaceBadge).toContainText(workspaceName)

    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(headerWorkspaceBadge).toContainText(workspaceName)

    await page.getByLabel('Workspaces').click()
    const activeSummary = page
      .locator('div')
      .filter({
        has: page.getByText('Active Workspace'),
        hasText: 'Loaded from saved workspaces',
      })
      .first()
    await expect(activeSummary).toBeVisible()
    await expect(activeSummary).toContainText(workspaceName)

    await page.getByRole('button', { name: 'Planning', exact: true }).click()
    const generateButton = page.getByRole('button', { name: /Generate Mission Plan/i })
    await expect(generateButton).toBeVisible({ timeout: 60_000 })

    const modePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().includes('/api/v1/schedule/mode-selection'),
    )
    const repairPromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' && response.url().includes('/api/v1/schedule/repair'),
    )

    await generateButton.click()

    const modeResponse = await modePromise
    const repairResponse = await repairPromise
    expect(modeResponse.ok()).toBeTruthy()
    expect(repairResponse.ok()).toBeTruthy()

    const modeSelection = (await modeResponse.json()) as PlanningModeSelection
    const repairPlan = (await repairResponse.json()) as RepairPlanResponse
    const repairChangeCount =
      repairPlan.repair_diff.added.length +
      repairPlan.repair_diff.dropped.length +
      repairPlan.repair_diff.moved.length

    expect(modeSelection.planning_mode).toBe('repair')
    expect(repairChangeCount).toBeGreaterThan(0)

    await expect(page.getByRole('button', { name: /^Next$/i })).toBeVisible({ timeout: 60_000 })
    await page.getByRole('button', { name: /^Next$/i }).click()
    await page.waitForTimeout(1500)

    const applyHeading = page
      .getByRole('heading', { level: 3 })
      .filter({ hasText: /Ready to Apply|Review Changes|Conflicts Detected/ })
      .first()
    await expect(applyHeading).toBeVisible()
    const badgeCount =
      (await page.getByText('NEW', { exact: true }).count()) +
      (await page.getByText('REMOVED', { exact: true }).count()) +
      (await page.getByText('MOVED', { exact: true }).count())
    expect(badgeCount).toBeGreaterThan(0)

    const screenshotPath = testInfo.outputPath('live-refresh-repair-page2.png')
    await page.screenshot({ path: screenshotPath, fullPage: true })
    await testInfo.attach('live-refresh-repair-page2', {
      path: screenshotPath,
      contentType: 'image/png',
    })

    const persistedWorkspaces = await page.evaluate(() => localStorage.getItem('mission_workspaces'))
    const summaryPath = testInfo.outputPath('live-refresh-repair-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          workspace_id: workspaceId,
          workspace_name: workspaceName,
          mode_selection: modeSelection,
          repair_diff: repairPlan.repair_diff,
          persisted_workspaces: persistedWorkspaces,
        },
        null,
        2,
      ),
    )
    await testInfo.attach('live-refresh-repair-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })

  test('captures a live moved-only repair apply page without duplicate new or removed badges', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(12 * 60 * 1000)
    const qualityWeights = {
      weight_priority: 0,
      weight_geometry: 100,
      weight_timing: 0,
    }

    const workspaceName = `live_repair_moved_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const customSatellite = await getCustomSatellite(request)
    const targetPool = await getReferenceTargetPool(request)
    const targets = targetPool.slice(0, 12)

    await analyzeWorkspace(request, workspaceId, customSatellite, targets, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })

    const baseline = await runPlanningViaApi(request, workspaceId, targets, 0, qualityWeights)
    expect(baseline.modeSelection.planning_mode).toBe('from_scratch')

    const beforeRepair = (await getHorizon(request, workspaceId, false, 10)).acquisitions?.length ?? 0
    expect(beforeRepair).toBeGreaterThan(0)

    await analyzeWorkspace(request, workspaceId, customSatellite, targets, {
      startOffsetMs: 24 * 60 * 60 * 1000,
    })

    const liveRepair = await runPlanningViaUi(
      page,
      workspaceName,
      'live-repair-moved-page2.png',
      testInfo,
      { autoCommit: false, scoringPreset: 'Quality' },
    )
    const repairPlan = liveRepair.planResponse as RepairPlanResponse

    expect(liveRepair.modeSelection.planning_mode).toBe('repair')
    if ((repairPlan.repair_diff.moved.length ?? 0) > 0) {
      expect(repairPlan.repair_diff.change_log?.moved?.length ?? 0).toBeGreaterThan(0)
      expect(liveRepair.uiSummary?.badgeCounts.moved ?? 0).toBeGreaterThan(0)
      expect(liveRepair.uiSummary?.badgeCounts.added ?? 0).toBe(0)
      expect(liveRepair.uiSummary?.badgeCounts.removed ?? 0).toBe(0)

      await expect(page.getByText('MOVED', { exact: true }).first()).toBeVisible()
      await expect(page.getByText('NEW', { exact: true })).toHaveCount(0)
      await expect(page.getByText('REMOVED', { exact: true })).toHaveCount(0)

      const commitPromise = page.waitForResponse(
        (response) =>
          response.request().method() === 'POST' &&
          response.url().includes('/api/v1/schedule/repair/commit'),
      )
      await page.getByRole('button', { name: /Apply (Plan|Anyway)/i }).click()
      const commitResponse = await commitPromise
      expect(commitResponse.ok()).toBeTruthy()
      await page.waitForTimeout(2000)
    } else {
      expect(liveRepair.uiSummary?.actionState).toBe('no_changes')
      expect(liveRepair.uiSummary?.badgeCounts.added ?? 0).toBe(0)
      expect(liveRepair.uiSummary?.badgeCounts.removed ?? 0).toBe(0)
      expect(liveRepair.uiSummary?.badgeCounts.moved ?? 0).toBe(0)
    }

    const afterRepair = (await getHorizon(request, workspaceId, false, 10)).acquisitions?.length ?? 0
    expect(afterRepair).toBe(beforeRepair)

    const summaryPath = testInfo.outputPath('live-repair-moved-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          workspace_id: workspaceId,
          workspace_name: workspaceName,
          moved_targets: (repairPlan.repair_diff.change_log?.moved ?? []).map((entry) => entry.target_id),
          repair_diff: repairPlan.repair_diff,
          ui_checkpoint: liveRepair.uiSummary,
          before_count: beforeRepair,
          after_count: afterRepair,
        },
        null,
        2,
      ),
    )
    await testInfo.attach('live-repair-moved-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })

  test('runs a live uniform-priority incremental campaign with 50 initial targets and 15 expansion waves', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(18 * 60 * 1000)

    const workspaceName = `live_incremental_campaign_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const customSatellite = await getCustomSatellite(request)
    const targetPool = generateFallbackTargetPool(95)
    const currentTargets = targetPool.slice(0, 50)
    const report: {
      workspace_id: string
      workspace_name: string
      addition_pattern: number[]
      runs: WeeklyRunSummary[]
    } = {
      workspace_id: workspaceId,
      workspace_name: workspaceName,
      addition_pattern: incrementalCampaignPattern,
      runs: [],
    }
    let workspaceLoadedInUi = false

    for (let runIndex = 0; runIndex < incrementalCampaignPattern.length + 1; runIndex += 1) {
      if (runIndex > 0) {
        const nextCount = incrementalCampaignPattern[runIndex - 1] ?? 0
        const nextSliceEnd = Math.min(currentTargets.length + nextCount, targetPool.length)
        currentTargets.push(...targetPool.slice(currentTargets.length, nextSliceEnd))
      }

      const runNumber = runIndex + 1
      console.log(
        `[live-incremental] run ${runNumber}/${incrementalCampaignPattern.length + 1} start with ${currentTargets.length} targets`,
      )

      await analyzeWorkspace(request, workspaceId, customSatellite, currentTargets, {
        startOffsetMs: 6 * 60 * 60 * 1000,
      })
      const opportunities = await getOpportunitiesCount(request, workspaceId)
      const beforeHorizon = await getHorizon(request, workspaceId)
      const beforeCount = beforeHorizon.acquisitions?.length ?? 0
      const checkpointScreenshot = incrementalCampaignCheckpointRuns.has(runNumber)
        ? `live-incremental-campaign-run-${String(runNumber).padStart(2, '0')}.png`
        : null

      const result = checkpointScreenshot
        ? await runPlanningViaUi(page, workspaceName, checkpointScreenshot, testInfo, {
            skipWorkspaceLoad: workspaceLoadedInUi,
          })
        : await runPlanningViaApi(request, workspaceId, currentTargets, beforeCount)

      const afterHorizon = await getHorizon(request, workspaceId)
      const afterCount = afterHorizon.acquisitions?.length ?? 0
      const committed = Number(result.commitResponse?.committed ?? result.commit?.committed ?? 0)
      const dropped = Number(result.commitResponse?.dropped ?? result.commit?.dropped ?? 0)

      expect(result.modeSelection.planning_mode).toBe(runIndex === 0 ? 'from_scratch' : 'incremental')
      expect(afterCount).toBe(beforeCount + committed - dropped)

      const summary: WeeklyRunSummary = {
        run: runNumber,
        targets_total: currentTargets.length,
        opportunities,
        mode: result.modeSelection.planning_mode,
        before_count: beforeCount,
        after_count: afterCount,
        commit: {
          committed,
          dropped,
        },
        plan_summary: result.planSummary ?? {},
      }

      if ('uiSummary' in result && result.uiSummary) {
        summary.ui_checkpoint = result.uiSummary
      }

      report.runs.push(summary)
      console.log(
        `[live-incremental] run ${runNumber} complete: mode=${summary.mode} before=${beforeCount} after=${afterCount} committed=${summary.commit.committed} dropped=${summary.commit.dropped}`,
      )
      if ('uiSummary' in result && result.uiSummary) {
        workspaceLoadedInUi = true
      }
    }

    const summaryPath = testInfo.outputPath('live-incremental-campaign-summary.json')
    writeFileSync(summaryPath, JSON.stringify(report, null, 2))
    await testInfo.attach('live-incremental-campaign-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })

    expect(report.runs).toHaveLength(16)
    expect(report.runs[0]?.mode).toBe('from_scratch')
    expect(report.runs.slice(1).every((run) => run.mode === 'incremental')).toBeTruthy()
    expect(report.runs.at(-1)?.targets_total).toBe(95)
  })

  test('uses timeline double-click locking in the live UI and preserves the locked acquisition during repair', async ({
    page,
    request,
  }, testInfo) => {
    test.setTimeout(8 * 60 * 1000)

    const workspaceName = `live_lock_drill_${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const satellite = {
      name: 'ICEYE-X53',
      line1: '1 64584U 25135BJ  26064.28789825  .00007988  00000+0  63127-3 0  9993',
      line2: '2 64584  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499',
    }

    await analyzeWorkspace(request, workspaceId, satellite, modTargetsA, {
      startOffsetMs: 6 * 60 * 60 * 1000,
    })
    console.log('[live-lock] mission analysis complete')

    const initialPlan = await apiPost<{
      results: {
        roll_pitch_best_fit: {
          schedule: DirectScheduleItem[]
        }
      }
    }>(request, '/api/v1/planning/schedule', {
      workspace_id: workspaceId,
      algorithms: ['roll_pitch_best_fit'],
      mode: 'from_scratch',
      weight_priority: 40,
      weight_geometry: 40,
      weight_timing: 20,
    })

    const initialSchedule = initialPlan.results.roll_pitch_best_fit.schedule
    expect(initialSchedule.length).toBeGreaterThan(0)
    console.log(`[live-lock] initial schedule items: ${initialSchedule.length}`)

    await apiPost(request, '/api/v1/schedule/commit/direct', {
      workspace_id: workspaceId,
      items: toCommitItems(initialSchedule),
      algorithm: 'roll_pitch_best_fit',
      force: true,
    })
    console.log('[live-lock] initial schedule committed')

    await loadWorkspaceInUi(page, workspaceName)
    const liveAcquisitionId = await openScheduleTimeline(page, testInfo)
    console.log(`[live-lock] chosen acquisition: ${liveAcquisitionId}`)

    const baseHorizon = await getHorizon(request, workspaceId)
    const existing = baseHorizon.acquisitions?.find((item) => item.id === liveAcquisitionId)
    expect(existing).toBeTruthy()

    const lockResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'PATCH' &&
        response.url().includes(`/api/v1/schedule/acquisition/${liveAcquisitionId}/lock`),
    )

    await page.locator(`[data-acquisition-id="${liveAcquisitionId}"]`).dblclick()
    const lockResponse = await lockResponsePromise
    expect(lockResponse.ok()).toBeTruthy()
    console.log('[live-lock] UI double-click lock succeeded')

    const lockedHorizon = await getHorizon(request, workspaceId)
    const locked = lockedHorizon.acquisitions?.find((item) => item.id === liveAcquisitionId)
    expect(locked?.lock_level).toBe('hard')
    console.log('[live-lock] backend lock confirmed')

    await apiPost(request, '/api/v1/schedule/commit/direct', {
      workspace_id: workspaceId,
      items: [
        {
          opportunity_id: `synth_${Date.now()}`,
          satellite_id: existing?.satellite_id,
          target_id: 'conflict_tgt_live',
          start_time: existing?.start_time,
          end_time: existing?.end_time,
          roll_angle_deg: 5,
        },
      ],
      algorithm: 'live_conflict_injection',
      force: true,
    })
    console.log('[live-lock] conflicting acquisition injected')

    const liveRepair = await runPlanningViaUi(
      page,
      workspaceName,
      'live-lock-repair-page2.png',
      testInfo,
      { skipWorkspaceLoad: true },
    )
    console.log('[live-lock] repair flow committed via UI')

    const repairPlan = liveRepair.planResponse as RepairPlanResponse
    expect(liveRepair.modeSelection.planning_mode).toBe('repair')
    expect(repairPlan.repair_diff.kept).toContain(liveAcquisitionId)

    const fullHorizon = await getHorizon(request, workspaceId, true)
    const conflictAcquisition = fullHorizon.acquisitions?.find(
      (item) => item.target_id === 'conflict_tgt_live',
    )

    expect(conflictAcquisition).toBeTruthy()
    expect(conflictAcquisition?.state).toBe('failed')

    const postLock = fullHorizon.acquisitions?.find((item) => item.id === liveAcquisitionId)
    expect(postLock?.state).toBe('committed')
    expect(postLock?.lock_level).toBe('hard')

    const reportPath = testInfo.outputPath('live-lock-summary.json')
    writeFileSync(
      reportPath,
      JSON.stringify(
        {
          workspace_id: workspaceId,
          workspace_name: workspaceName,
          locked_acquisition_id: liveAcquisitionId,
          locked_target_id: existing?.target_id,
          dropped_conflict_id: conflictAcquisition?.id,
          repair_diff: repairPlan.repair_diff,
          ui_checkpoint: liveRepair.uiSummary,
        },
        null,
        2,
      ),
    )

    await testInfo.attach('live-lock-summary', {
      path: reportPath,
      contentType: 'application/json',
    })
  })
})
