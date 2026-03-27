import { writeFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page, TestInfo } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'
const frontendBaseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000'
const liveEnabled = process.env.PLAYWRIGHT_LIVE_OPERATOR === '1'

type SatelliteConfig = {
  name: string
  line1: string
  line2: string
}

type Target = {
  name: string
  latitude: number
  longitude: number
  priority?: number
}

type ScheduleItem = {
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
  success?: boolean
  planning_mode: 'from_scratch' | 'incremental' | 'repair'
  reason: string
  workspace_id?: string
  existing_acquisition_count?: number
  new_target_count?: number
  conflict_count?: number
}

type RepairPlanResponse = {
  success?: boolean
  plan_id?: string
  repair_diff: {
    kept: string[]
    dropped: string[]
    added: string[]
    moved: Array<{ id: string }>
    change_log?: {
      added?: Array<{ acquisition_id: string; target_id: string; satellite_id: string; start: string }>
      dropped?: Array<{ acquisition_id: string; target_id: string; satellite_id: string; start: string }>
      moved?: Array<{
        acquisition_id: string
        target_id: string
        satellite_id: string
        from_start: string
        to_start: string
      }>
    }
  }
  metrics_comparison?: {
    acquisition_count_before?: number
    acquisition_count_after?: number
  }
}

type WorkspaceSummary = {
  id: string
  name: string
  created_at?: string
  updated_at?: string
  satellites_count?: number
  targets_count?: number
}

type CommittedAcquisition = {
  id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  state: string
}

type ViewerState = {
  found: boolean
  trackedEntityId: string | null
  trackedEntityName: string | null
  selectedEntityId: string | null
  camera: {
    lat: number
    lon: number
    height: number
  } | null
  dataSources: Array<{
    name: string
    count: number
    satellites: number
    groundTracks: number
    visibleGroundTrackPaths: number
  }>
  slicedGroundTrackSegments: number
  slicedGroundTrackSegmentsBySatellite: Record<string, number>
}

const reviewTargets: Target[] = [
  { name: 'REV_01', latitude: 24.7136, longitude: 46.6753, priority: 5 },
  { name: 'REV_02', latitude: 25.2048, longitude: 55.2708, priority: 5 },
  { name: 'REV_03', latitude: 21.4858, longitude: 39.1925, priority: 4 },
  { name: 'REV_04', latitude: 29.3759, longitude: 47.9774, priority: 4 },
  { name: 'REV_05', latitude: 26.2235, longitude: 50.5876, priority: 4 },
  { name: 'REV_06', latitude: 23.5859, longitude: 58.4059, priority: 4 },
  { name: 'REV_07', latitude: 24.4539, longitude: 54.3773, priority: 3 },
  { name: 'REV_08', latitude: 25.2854, longitude: 51.531, priority: 3 },
  { name: 'REV_09', latitude: 24.8607, longitude: 67.0011, priority: 3 },
  { name: 'REV_10', latitude: 33.3152, longitude: 44.3661, priority: 3 },
  { name: 'REV_11', latitude: 35.6892, longitude: 51.389, priority: 2 },
  { name: 'REV_12', latitude: 31.7683, longitude: 35.2137, priority: 2 },
]

const multiSatPriorityTargets: Target[] = [
  { name: 'REV_PRIO_01', latitude: 24.6936, longitude: 46.6653, priority: 1 },
  { name: 'REV_PRIO_02', latitude: 24.7336, longitude: 46.7053, priority: 1 },
  { name: 'REV_PRIO_03', latitude: 24.7536, longitude: 46.6453, priority: 1 },
  { name: 'REV_PRIO_04', latitude: 24.6736, longitude: 46.7253, priority: 1 },
]

async function ensureLiveServices(request: APIRequestContext) {
  const [frontendResponse, apiResponse] = await Promise.all([
    fetch(frontendBaseUrl),
    request.get(`${apiBaseUrl}/api/v1/health`),
  ])

  expect(frontendResponse.ok).toBeTruthy()
  expect(apiResponse.ok()).toBeTruthy()
}

async function apiGet<T>(request: APIRequestContext, path: string, params?: Record<string, string>) {
  const response = await request.get(`${apiBaseUrl}${path}`, {
    params,
    timeout: 180_000,
  })
  expect(response.ok(), `GET ${path} failed with ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

async function apiPost<T>(request: APIRequestContext, path: string, data: unknown) {
  const response = await request.post(`${apiBaseUrl}${path}`, {
    data,
    timeout: 240_000,
  })
  expect(response.ok(), `POST ${path} failed with ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

async function createWorkspace(request: APIRequestContext, name: string) {
  const response = await apiPost<{ workspace_id?: string; workspaceId?: string }>(
    request,
    '/api/v1/workspaces',
    { name },
  )
  const workspaceId = response.workspace_id ?? response.workspaceId
  expect(workspaceId).toBeTruthy()
  return workspaceId as string
}

async function getSatellites(request: APIRequestContext, names: string[]) {
  const response = await apiGet<{ satellites?: SatelliteConfig[] }>(request, '/api/v1/satellites')
  const satellites = response.satellites ?? []
  const selected = names.map((name) => satellites.find((satellite) => satellite.name === name) ?? null)
  expect(selected.every(Boolean)).toBeTruthy()
  return selected as SatelliteConfig[]
}

async function listWorkspaces(request: APIRequestContext) {
  const response = await apiGet<{ workspaces?: WorkspaceSummary[] }>(request, '/api/v1/workspaces')
  return response.workspaces ?? []
}

async function analyzeWorkspace(
  request: APIRequestContext,
  workspaceId: string,
  satellites: SatelliteConfig[],
  targets: Target[],
) {
  const now = new Date(Date.now() + 6 * 60 * 60 * 1000)
  const end = new Date(now.getTime() + 5 * 24 * 60 * 60 * 1000)
  return apiPost(request, '/api/v1/mission/analyze', {
    workspace_id: workspaceId,
    satellites,
    targets,
    start_time: now.toISOString(),
    end_time: end.toISOString(),
    imaging_type: 'optical',
  })
}

async function planAndCommitSchedule(request: APIRequestContext, workspaceId: string) {
  const now = new Date()
  const horizonEnd = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)

  const mode = await apiPost<{
    planning_mode: 'from_scratch' | 'incremental' | 'repair'
  }>(request, '/api/v1/schedule/mode-selection', {
    workspace_id: workspaceId,
    horizon_from: now.toISOString(),
    horizon_to: horizonEnd.toISOString(),
    weight_priority: 40,
    weight_geometry: 40,
    weight_timing: 20,
  })

  expect(mode.planning_mode).toBe('from_scratch')

  const planner = await apiPost<{
    results: {
      roll_pitch_best_fit: {
        schedule: ScheduleItem[]
      }
    }
  }>(request, '/api/v1/planning/schedule', {
    workspace_id: workspaceId,
    algorithms: ['roll_pitch_best_fit'],
    mode: mode.planning_mode,
    weight_priority: 40,
    weight_geometry: 40,
    weight_timing: 20,
  })

  const schedule = planner.results.roll_pitch_best_fit.schedule ?? []
  expect(schedule.length).toBeGreaterThan(0)

  const commitItems = schedule.map((item, index) => ({
    opportunity_id: item.opportunity_id || `live_schedule_item_${index + 1}`,
    satellite_id: item.satellite_id,
    target_id: item.target_id,
    start_time: item.start_time,
    end_time: item.end_time,
    roll_angle_deg: item.roll_angle_deg ?? item.roll_angle ?? 0,
    pitch_angle_deg: item.pitch_angle_deg ?? item.pitch_angle ?? 0,
    value: item.value,
    incidence_angle_deg: item.incidence_angle_deg ?? item.incidence_angle,
  }))

  await apiPost(request, '/api/v1/schedule/commit/direct', {
    workspace_id: workspaceId,
    items: commitItems,
    algorithm: 'roll_pitch_best_fit',
    force: true,
  })

  return getCommittedSchedule(request, workspaceId)
}

async function getPlanningModeSelection(request: APIRequestContext, workspaceId: string) {
  const now = new Date()
  const horizonEnd = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  return apiPost<PlanningModeSelection>(request, '/api/v1/schedule/mode-selection', {
    workspace_id: workspaceId,
    horizon_from: now.toISOString(),
    horizon_to: horizonEnd.toISOString(),
    weight_priority: 40,
    weight_geometry: 40,
    weight_timing: 20,
  })
}

async function waitForPlanningMode(
  request: APIRequestContext,
  workspaceId: string,
  expectedMode: PlanningModeSelection['planning_mode'],
  timeoutMs = 60_000,
) {
  const startedAt = Date.now()
  let lastModeSelection: PlanningModeSelection | null = null

  while (Date.now() - startedAt < timeoutMs) {
    lastModeSelection = await getPlanningModeSelection(request, workspaceId)
    if (lastModeSelection.planning_mode === expectedMode) {
      return lastModeSelection
    }

    await new Promise((resolve) => setTimeout(resolve, 2_000))
  }

  throw new Error(
    `Expected planning mode ${expectedMode} for workspace ${workspaceId}, got ${JSON.stringify(lastModeSelection)}`,
  )
}

function normalizeSatelliteName(satelliteId: string) {
  return satelliteId.replace(/^sat_/, '')
}

async function getCommittedSchedule(request: APIRequestContext, workspaceId: string) {
  const now = new Date()
  const horizonEnd = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  const horizon = await apiGet<{
    acquisitions?: CommittedAcquisition[]
    statistics?: {
      by_satellite?: Record<string, number>
    }
  }>(request, '/api/v1/schedule/horizon', {
    workspace_id: workspaceId,
    from: now.toISOString(),
    to: horizonEnd.toISOString(),
  })

  const acquisitions = (horizon.acquisitions ?? []).filter((item) => item.state === 'committed')
  const bySatellite = horizon.statistics?.by_satellite ?? {}
  const satelliteNames = Object.entries(bySatellite)
    .filter(([, count]) => (count ?? 0) > 0)
    .map(([name]) => name)

  return {
    acquisitions,
    bySatellite,
    satelliteNames,
  }
}

async function ensureMultiSatelliteScheduleWorkspace(request: APIRequestContext) {
  const reusableWorkspace = (await listWorkspaces(request))
    .filter(
      (workspace) =>
        workspace.name.startsWith('live-multisat-schedule-') &&
        (workspace.satellites_count ?? 0) >= 2 &&
        (workspace.targets_count ?? 0) >= reviewTargets.length,
    )
    .sort((a, b) => {
      const left = new Date(a.updated_at ?? a.created_at ?? 0).getTime()
      const right = new Date(b.updated_at ?? b.created_at ?? 0).getTime()
      return right - left
    })

  for (const workspace of reusableWorkspace) {
    const schedule = await getCommittedSchedule(request, workspace.id)
    if (schedule.satelliteNames.length >= 2 && schedule.acquisitions.length > 0) {
      return {
        workspaceId: workspace.id,
        workspaceName: workspace.name,
        reusedWorkspace: true,
        ...schedule,
      }
    }
  }

  const workspaceName = `live-multisat-schedule-${Date.now()}`
  const workspaceId = await createWorkspace(request, workspaceName)
  const satellites = await getSatellites(request, ['ICEYE-X66', 'ICEYE-X67'])

  await analyzeWorkspace(request, workspaceId, satellites, reviewTargets)
  const schedule = await planAndCommitSchedule(request, workspaceId)

  expect(schedule.satelliteNames.length).toBeGreaterThanOrEqual(2)

  return {
    workspaceId,
    workspaceName,
    reusedWorkspace: false,
    ...schedule,
  }
}

async function loadWorkspaceInUi(page: Page, workspaceName: string) {
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.getByLabel('Workspaces').click()
  await expect(page.getByText('Workspace Library')).toBeVisible()

  const workspaceCard = page
    .locator('div.rounded-lg')
    .filter({ has: page.getByText(workspaceName, { exact: true }) })
    .first()

  await expect(workspaceCard).toBeVisible({ timeout: 60_000 })
  await workspaceCard.getByTitle('Load workspace').click()
  await expect(page.getByText('Workspace loaded successfully')).toBeVisible({ timeout: 60_000 })
  await expect(page.locator('div[title^="Selected workspace:"]')).toContainText(workspaceName, {
    timeout: 60_000,
  })
}

async function openScheduleTimeline(page: Page) {
  const scheduleButton = page.getByRole('button', { name: 'Schedule', exact: true })
  const scheduleHeading = page.getByRole('heading', { name: 'Schedule', exact: true }).first()

  const headingVisible = await scheduleHeading.isVisible().catch(() => false)
  if (!headingVisible) {
    await scheduleButton.click()
    const visibleAfterFirstClick = await scheduleHeading.isVisible().catch(() => false)
    if (!visibleAfterFirstClick) {
      await scheduleButton.click()
    }
  }

  await expect(scheduleHeading).toBeVisible({ timeout: 10_000 })

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
  await timelineTab.click({ force: true })
  await expect(page.locator('[data-acquisition-id]').first()).toBeVisible({ timeout: 30_000 })
}

async function waitForScheduleMapReady(page: Page, timeoutMs = 20_000) {
  await expect
    .poll(
      async () =>
        page.evaluate(async () => {
          type DebugEntity = { id?: string }
          type DebugViewer = {
            entities?: {
              values?: DebugEntity[]
            }
            dataSources?: {
              length?: number
            }
          }
          type GlobeDebug = {
            viewerDataSources?: number
          }

          const viewer = (globalThis as typeof globalThis & { __primaryViewer?: DebugViewer })
            .__primaryViewer
          const globeDebug = (globalThis as typeof globalThis & { __primaryGlobeDebug?: GlobeDebug })
            .__primaryGlobeDebug
          const slicedCount =
            viewer?.entities?.values?.filter?.(
              (entity) => typeof entity.id === 'string' && entity.id.endsWith('_ground_track_sliced'),
            ).length ?? 0

          return {
            viewerDataSources: globeDebug?.viewerDataSources ?? viewer?.dataSources?.length ?? 0,
            slicedCount,
          }
        }),
      { timeout: timeoutMs },
    )
    .toMatchObject({
      viewerDataSources: expect.any(Number),
    })

  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          type DebugEntity = { id?: string }
          type DebugViewer = {
            entities?: {
              values?: DebugEntity[]
            }
          }

          const viewer = (globalThis as typeof globalThis & { __primaryViewer?: DebugViewer })
            .__primaryViewer
          return (
            viewer?.entities?.values?.filter?.(
              (entity) => typeof entity.id === 'string' && entity.id.endsWith('_ground_track_sliced'),
            ).length ?? 0
          )
        }),
      { timeout: timeoutMs },
    )
    .toBeGreaterThan(0)
}

async function openPlanningApply(page: Page, testInfo: TestInfo, screenshotName: string) {
  await page.getByRole('button', { name: 'Planning', exact: true }).click()
  await expect(
    page.getByText('Run Feasibility Analysis first to enable scheduling.'),
  ).toHaveCount(0, { timeout: 60_000 })
  const generateButton = page.getByRole('button', { name: /Generate Mission Plan/i })
  await expect(generateButton).toBeVisible({ timeout: 60_000 })

  const modeRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'POST' && request.url().includes('/api/v1/schedule/mode-selection'),
    { timeout: 15_000 },
  )
  const planRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === 'POST' &&
      (request.url().includes('/api/v1/schedule/repair') ||
        request.url().includes('/api/v1/planning/schedule')),
    { timeout: 15_000 },
  )
  const modeResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/v1/schedule/mode-selection'),
  )
  const planResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      (response.url().includes('/api/v1/schedule/repair') ||
        response.url().includes('/api/v1/planning/schedule')),
  )

  await generateButton.click()

  await Promise.all([modeRequestPromise, planRequestPromise])

  const modeResponse = await modeResponsePromise
  const planResponse = await planResponsePromise
  expect(modeResponse.ok()).toBeTruthy()
  expect(planResponse.ok()).toBeTruthy()

  const modeSelection = (await modeResponse.json()) as PlanningModeSelection
  const repairPlan = (await planResponse.json()) as RepairPlanResponse

  await expect(page.getByRole('button', { name: /^Next$/i })).toBeVisible({ timeout: 60_000 })
  await page.getByRole('button', { name: /^Next$/i }).click()
  await page.waitForTimeout(1500)

  const heading = page
    .getByRole('heading', { level: 3 })
    .filter({ hasText: /Ready to Apply|Review Changes|Conflicts Detected/ })
    .first()
  await expect(heading).toBeVisible()

  const stats = await page
    .locator('div.grid.grid-cols-3.gap-2 .text-lg.font-bold.text-white.leading-tight')
    .allInnerTexts()

  const badgeCounts = {
    added: await page.getByText('NEW', { exact: true }).count(),
    moved: await page.getByText('MOVED', { exact: true }).count(),
    removed: await page.getByText('REMOVED', { exact: true }).count(),
  }

  const screenshotPath = testInfo.outputPath(screenshotName)
  await page.screenshot({ path: screenshotPath })
  await testInfo.attach(screenshotName.replace(/\.png$/, ''), {
    path: screenshotPath,
    contentType: 'image/png',
  })

  return {
    modeSelection,
    repairPlan,
    heading: (await heading.textContent()) ?? '',
    stats,
    badgeCounts,
    screenshotPath,
  }
}

async function readPrimaryViewerState(page: Page): Promise<ViewerState> {
  return page.evaluate(() => {
    function getPrimaryViewer() {
      const rootEl = document.querySelector('#root') || document.body
      let rootFiber: unknown = null

      for (const key of Object.keys(rootEl)) {
        if (key.startsWith('__reactContainer$')) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          rootFiber = (rootEl as any)[key].stateNode.current
        } else if (key.startsWith('__reactFiber$')) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          rootFiber = (rootEl as any)[key]
        }
      }

      if (!rootFiber) return null

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const queue: any[] = [rootFiber]
      while (queue.length) {
        const fiber = queue.shift()
        const props = fiber?.memoizedProps
        if (props?.viewerRef?.current?.cesiumElement && props?.viewportId === 'primary') {
          return props.viewerRef.current.cesiumElement
        }
        if (fiber?.child) queue.push(fiber.child)
        if (fiber?.sibling) queue.push(fiber.sibling)
      }

      return null
    }

    const viewer = getPrimaryViewer()
    if (!viewer) {
      return {
        found: false,
        trackedEntityId: null,
        trackedEntityName: null,
        selectedEntityId: null,
        camera: null,
        dataSources: [],
        slicedGroundTrackSegments: 0,
        slicedGroundTrackSegmentsBySatellite: {},
      }
    }

    const dataSources = []
    for (let i = 0; i < viewer.dataSources.length; i += 1) {
      const dataSource = viewer.dataSources.get(i)
      const entities = dataSource.entities.values
      dataSources.push({
        name: dataSource.name,
        count: entities.length,
        satellites: entities.filter(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity: any) =>
            typeof entity.id === 'string' &&
            entity.id.startsWith('sat_') &&
            !entity.id.includes('ground_track'),
        ).length,
        groundTracks: entities.filter(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity: any) => typeof entity.id === 'string' && entity.id.includes('ground_track'),
        ).length,
        visibleGroundTrackPaths: entities.filter(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (entity: any) =>
            typeof entity.id === 'string' &&
            entity.id.includes('ground_track') &&
            entity.path &&
            entity.path.show &&
            (typeof entity.path.show.getValue === 'function'
              ? entity.path.show.getValue(viewer.clock.currentTime)
              : Boolean(entity.path.show)),
        ).length,
      })
    }

    const cartographic = viewer.camera.positionCartographic
    const slicedGroundTrackSegmentsBySatellite = viewer.entities.values.reduce(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (segments: Record<string, number>, entity: any) => {
        if (typeof entity.id !== 'string' || !entity.id.endsWith('_ground_track_sliced')) {
          return segments
        }
        const ownerSatId = entity.id.slice(0, -'_ground_track_sliced'.length)
        segments[ownerSatId] = (segments[ownerSatId] ?? 0) + 1
        return segments
      },
      {},
    )

    return {
      found: true,
      trackedEntityId: viewer.trackedEntity?.id ?? null,
      trackedEntityName: viewer.trackedEntity?.name ?? null,
      selectedEntityId: viewer.selectedEntity?.id ?? null,
      camera: {
        lat: Number(((cartographic.latitude * 180) / Math.PI).toFixed(3)),
        lon: Number(((cartographic.longitude * 180) / Math.PI).toFixed(3)),
        height: Math.round(cartographic.height),
      },
      dataSources,
      slicedGroundTrackSegments: viewer.entities.values.filter(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (entity: any) => typeof entity.id === 'string' && entity.id.endsWith('_ground_track_sliced'),
      ).length,
      slicedGroundTrackSegmentsBySatellite,
    }
  })
}

test.describe('Live multi-satellite schedule review', () => {
  test.skip(!liveEnabled, 'Set PLAYWRIGHT_LIVE_OPERATOR=1 to run live schedule review drills.')

  test('reviews committed acquisitions across two satellites in schedule mode after refresh', async ({
    page,
    request,
  }, testInfo: TestInfo) => {
    test.setTimeout(240_000)
    test.slow()

    await ensureLiveServices(request)
    const {
      workspaceId,
      workspaceName,
      acquisitions,
      bySatellite,
      satelliteNames,
      reusedWorkspace,
    } = await ensureMultiSatelliteScheduleWorkspace(request)

    const firstSatelliteName = satelliteNames[0]
    const secondSatelliteName = satelliteNames[1]
    const firstSelection =
      acquisitions.find(
        (item) => normalizeSatelliteName(item.satellite_id) === normalizeSatelliteName(firstSatelliteName),
      ) ?? null
    const secondSelection =
      acquisitions.find(
        (item) => normalizeSatelliteName(item.satellite_id) === normalizeSatelliteName(secondSatelliteName),
      ) ?? null

    expect(firstSelection).toBeTruthy()
    expect(secondSelection).toBeTruthy()

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

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce((total, dataSource) => total + dataSource.satellites, 0)
      }, { timeout: 60_000 })
      .toBeGreaterThanOrEqual(2)

    await page.getByRole('button', { name: 'Fit All Targets' }).click()
    await page.waitForTimeout(2200)

    const fitState = await readPrimaryViewerState(page)
    expect(fitState.camera).not.toBeNull()
    expect(fitState.camera!.lat).toBeGreaterThan(20)
    expect(fitState.camera!.lat).toBeLessThan(36)
    expect(fitState.camera!.lon).toBeGreaterThan(34)
    expect(fitState.camera!.lon).toBeLessThan(68)

    await page.locator('button[title="Map Layers"]').click()
    await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()
    const groundTrackCheckbox = page.getByRole('checkbox', { name: /Ground Track/ })
    await expect(groundTrackCheckbox).toBeChecked()

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce((total, dataSource) => total + dataSource.visibleGroundTrackPaths, 0)
      })
      .toBeGreaterThan(0)

    await page.getByLabel('Close Map Layers panel').click()
    await openScheduleTimeline(page)
    await waitForScheduleMapReady(page)

    const detailsHeading = page.getByRole('heading', { name: 'Details' })
    if (await detailsHeading.isVisible().catch(() => false)) {
      await page.getByLabel('Close Details panel').click()
      await expect(detailsHeading).not.toBeVisible()
    }

    const firstBar = page.locator(`[data-acquisition-id="${firstSelection!.id}"]`)
    await firstBar.scrollIntoViewIfNeeded()
    await firstBar.click()

    await expect(detailsHeading).toBeVisible()

    const acquisitionHero = page.getByTestId('inspector-acquisition-hero')
    await expect(acquisitionHero).toBeVisible()
    await expect(acquisitionHero).toContainText(firstSelection!.target_id)
    await expect(acquisitionHero).toContainText(normalizeSatelliteName(firstSatelliteName))

    const secondBar = page.locator(`[data-acquisition-id="${secondSelection!.id}"]`)
    await secondBar.scrollIntoViewIfNeeded()
    await secondBar.click()

    await expect(acquisitionHero).toContainText(secondSelection!.target_id)
    await expect(acquisitionHero).toContainText(normalizeSatelliteName(secondSatelliteName))

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return {
          selectedEntityId: state.selectedEntityId,
          slicedGroundTrackSegments: state.slicedGroundTrackSegments,
        }
      }, { timeout: 15_000 })
      .toMatchObject({
        selectedEntityId: `sched_target_${secondSelection!.target_id}`,
      })

    const selectedState = await readPrimaryViewerState(page)
    expect(selectedState.slicedGroundTrackSegments).toBeGreaterThan(0)

    await page
      .getByLabel('Open Map Focus panel')
      .evaluate((button: HTMLButtonElement) => button.click())
    await expect(page.getByLabel('Collapse Map Focus panel')).toBeVisible()
    const firstSatelliteFilter = page.locator(`[data-satellite-filter="${firstSelection!.satellite_id}"]`)
    const secondSatelliteFilter = page.locator(`[data-satellite-filter="${secondSelection!.satellite_id}"]`)
    await expect(firstSatelliteFilter).toBeVisible()
    await expect(secondSatelliteFilter).toBeVisible()

    const firstSatelliteCzmlId = `sat_${firstSelection!.satellite_id}`
    const secondSatelliteCzmlId = `sat_${secondSelection!.satellite_id}`

    await firstSatelliteFilter.click()
    await expect(page.getByText(new RegExp(`Reviewing ${firstSelection!.satellite_id} only`))).toBeVisible()
    await expect
      .poll(async () => (await readPrimaryViewerState(page)).slicedGroundTrackSegmentsBySatellite, {
        timeout: 15_000,
      })
      .toMatchObject({
        [firstSatelliteCzmlId]: expect.any(Number),
      })

    const isolatedFirstState = await readPrimaryViewerState(page)
    expect(Object.keys(isolatedFirstState.slicedGroundTrackSegmentsBySatellite)).toEqual([
      firstSatelliteCzmlId,
    ])

    await secondSatelliteFilter.click()
    await expect(page.getByText(new RegExp(`Reviewing ${secondSelection!.satellite_id} only`))).toBeVisible()
    await expect
      .poll(async () => (await readPrimaryViewerState(page)).slicedGroundTrackSegmentsBySatellite, {
        timeout: 15_000,
      })
      .toMatchObject({
        [secondSatelliteCzmlId]: expect.any(Number),
      })

    const isolatedSecondState = await readPrimaryViewerState(page)
    expect(Object.keys(isolatedSecondState.slicedGroundTrackSegmentsBySatellite)).toEqual([
      secondSatelliteCzmlId,
    ])

    await page.getByRole('button', { name: 'Show all' }).click()
    await expect(page.getByText(/^Reviewing .* only$/)).toHaveCount(0)
    await expect
      .poll(async () => Object.keys((await readPrimaryViewerState(page)).slicedGroundTrackSegmentsBySatellite), {
        timeout: 15_000,
      })
      .toEqual(expect.arrayContaining([firstSatelliteCzmlId, secondSatelliteCzmlId]))

    await page
      .getByLabel('Collapse Map Focus panel')
      .evaluate((button: HTMLButtonElement) => button.click())
    await page.locator('button[title="Map Layers"]').click()
    await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()
    await expect(page.getByRole('checkbox', { name: /Ground Track/ })).toBeChecked()
    await page.getByLabel('Close Map Layers panel').click()

    const screenshotPath = testInfo.outputPath('multi-satellite-schedule-review.png')
    await page.screenshot({ path: screenshotPath })
    await testInfo.attach('multi-satellite-schedule-review', {
      path: screenshotPath,
      contentType: 'image/png',
    })

    const summaryPath = testInfo.outputPath('multi-satellite-schedule-review-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          workspaceId,
          workspaceName,
          reusedWorkspace,
          persistedWorkspaces: await page.evaluate(() => localStorage.getItem('mission_workspaces')),
          bySatellite,
          firstSelection,
          secondSelection,
          fitState,
          selectedState,
        },
        null,
        2,
      ),
    )
    await testInfo.attach('multi-satellite-schedule-review-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })

  test('shows live multi-satellite repair actions and keeps schedule-map focus coherent', async ({
    page,
    request,
  }, testInfo: TestInfo) => {
    test.setTimeout(10 * 60 * 1000)
    test.slow()

    await ensureLiveServices(request)

    const workspaceName = `live-multisat-repair-${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const satellites = await getSatellites(request, ['ICEYE-X66', 'ICEYE-X67'])
    const baseTargets = reviewTargets

    await analyzeWorkspace(request, workspaceId, satellites, baseTargets)
    const baseline = await planAndCommitSchedule(request, workspaceId)

    const droppedTargetIds = [...new Set(baseline.acquisitions.map((item) => item.target_id))].slice(0, 3)
    expect(droppedTargetIds.length).toBeGreaterThan(0)

    const repairTargets = [
      ...baseTargets.filter((target) => !droppedTargetIds.includes(target.name)),
      ...multiSatPriorityTargets,
    ]

    await analyzeWorkspace(request, workspaceId, satellites, repairTargets)
    await waitForPlanningMode(request, workspaceId, 'repair')

    await loadWorkspaceInUi(page, workspaceName)
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')
    await expect(headerWorkspaceBadge).toContainText(workspaceName)

    const applyPage = await openPlanningApply(
      page,
      testInfo,
      'multi-satellite-repair-apply-page2.png',
    )

    expect(applyPage.modeSelection.planning_mode).toBe('repair')
    expect(applyPage.repairPlan.repair_diff.added.length).toBeGreaterThan(0)
    expect(applyPage.repairPlan.repair_diff.dropped.length).toBeGreaterThan(0)
    expect(applyPage.badgeCounts.added).toBeGreaterThan(0)
    expect(applyPage.badgeCounts.removed).toBeGreaterThan(0)
    expect(applyPage.stats[1]).toBe('2')

    const assignmentRows = page.locator('[data-assignment-kind]')
    await expect(assignmentRows.filter({ has: page.getByText('NEW', { exact: true }) }).first()).toBeVisible()
    await expect(
      assignmentRows.filter({ has: page.getByText('REMOVED', { exact: true }) }).first(),
    ).toBeVisible()

    const commitPromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' && response.url().includes('/api/v1/schedule/repair/commit'),
    )
    await page.getByRole('button', { name: /Apply (Plan|Anyway)/i }).click()
    const commitResponse = await commitPromise
    expect(commitResponse.ok()).toBeTruthy()
    await page.waitForTimeout(2000)

    const afterRepair = await getCommittedSchedule(request, workspaceId)
    expect(afterRepair.satelliteNames.length).toBeGreaterThanOrEqual(2)

    await openScheduleTimeline(page)
    await waitForScheduleMapReady(page)

    const preferredTargetId =
      applyPage.repairPlan.repair_diff.change_log?.added?.[0]?.target_id ??
      applyPage.repairPlan.repair_diff.change_log?.moved?.[0]?.target_id ??
      afterRepair.acquisitions[0]?.target_id
    expect(preferredTargetId).toBeTruthy()

    const followupSelection =
      afterRepair.acquisitions.find((item) => item.target_id === preferredTargetId) ?? afterRepair.acquisitions[0]
    expect(followupSelection).toBeTruthy()

    const followupBar = page.locator(`[data-acquisition-id="${followupSelection!.id}"]`)
    await followupBar.scrollIntoViewIfNeeded()
    await followupBar.click()

    const detailsHeading = page.getByRole('heading', { name: 'Details' })
    await expect(detailsHeading).toBeVisible()
    const acquisitionHero = page.getByTestId('inspector-acquisition-hero')
    await expect(acquisitionHero).toContainText(followupSelection!.target_id)
    await expect(acquisitionHero).toContainText(normalizeSatelliteName(followupSelection!.satellite_id))

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return {
          selectedEntityId: state.selectedEntityId,
          slicedGroundTrackSegments: state.slicedGroundTrackSegments,
        }
      }, { timeout: 20_000 })
      .toMatchObject({
        selectedEntityId: `sched_target_${followupSelection!.target_id}`,
      })

    const selectedState = await readPrimaryViewerState(page)
    expect(selectedState.slicedGroundTrackSegments).toBeGreaterThan(0)

    await page.locator('button[title="Map Layers"]').click()
    await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()
    await expect(page.getByRole('checkbox', { name: /Ground Track/ })).toBeChecked()

    const summaryPath = testInfo.outputPath('multi-satellite-repair-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          workspaceId,
          workspaceName,
          droppedTargetIds,
          modeSelection: applyPage.modeSelection,
          repairDiff: applyPage.repairPlan.repair_diff,
          uiSummary: {
            heading: applyPage.heading,
            stats: applyPage.stats,
            badgeCounts: applyPage.badgeCounts,
            screenshot: applyPage.screenshotPath,
          },
          followupSelection,
          selectedState,
        },
        null,
        2,
      ),
    )
    await testInfo.attach('multi-satellite-repair-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })

  test('keeps three-satellite paths coherent through fit, tracking, refresh, and repair', async ({
    page,
    request,
  }, testInfo: TestInfo) => {
    test.setTimeout(12 * 60 * 1000)
    test.slow()

    await ensureLiveServices(request)

    const workspaceName = `live-multisat-trisat-${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const satellites = await getSatellites(request, [
      'CUSTOM-45DEG-450KM',
      'ICEYE-X66',
      'ICEYE-X67',
    ])

    await analyzeWorkspace(request, workspaceId, satellites, reviewTargets)
    const baseline = await planAndCommitSchedule(request, workspaceId)
    expect(new Set(baseline.acquisitions.map((item) => item.satellite_id)).size).toBeGreaterThanOrEqual(2)

    await loadWorkspaceInUi(page, workspaceName)
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')
    await expect(headerWorkspaceBadge).toContainText(workspaceName)

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce((total, dataSource) => total + dataSource.satellites, 0)
      })
      .toBe(3)

    await page.getByRole('button', { name: 'Fit All Targets' }).click()
    await page.waitForTimeout(2200)

    const fitState = await readPrimaryViewerState(page)
    expect(fitState.camera).not.toBeNull()
    expect(fitState.camera!.lat).toBeGreaterThan(20)
    expect(fitState.camera!.lat).toBeLessThan(36)
    expect(fitState.camera!.lon).toBeGreaterThan(34)
    expect(fitState.camera!.lon).toBeLessThan(68)

    await page.locator('button[title="Map Layers"]').click()
    await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()
    const groundTrackCheckbox = page.getByRole('checkbox', { name: /Ground Track/ })
    await expect(groundTrackCheckbox).toBeChecked()

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce(
          (total, dataSource) => total + dataSource.visibleGroundTrackPaths,
          0,
        )
      })
      .toBeGreaterThan(0)

    await groundTrackCheckbox.click()
    await expect(groundTrackCheckbox).not.toBeChecked()
    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce(
          (total, dataSource) => total + dataSource.visibleGroundTrackPaths,
          0,
        )
      })
      .toBe(0)

    await groundTrackCheckbox.click()
    await expect(groundTrackCheckbox).toBeChecked()
    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce(
          (total, dataSource) => total + dataSource.visibleGroundTrackPaths,
          0,
        )
      })
      .toBeGreaterThan(0)

    await page.getByRole('button', { name: 'Track Satellite' }).click()
    await page.waitForTimeout(1500)
    const trackedState = await readPrimaryViewerState(page)
    expect(trackedState.trackedEntityId).toMatch(/^sat_/)

    await page.getByLabel('Close Map Layers panel').click()

    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(headerWorkspaceBadge).toContainText(workspaceName)
    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return state.dataSources.reduce((total, dataSource) => total + dataSource.satellites, 0)
      })
      .toBe(3)

    const droppedTargetIds = [...new Set(baseline.acquisitions.map((item) => item.target_id))].slice(0, 2)
    expect(droppedTargetIds.length).toBeGreaterThan(0)

    const repairTargets = [
      ...reviewTargets.filter((target) => !droppedTargetIds.includes(target.name)),
      ...multiSatPriorityTargets.slice(0, 3),
    ]

    await analyzeWorkspace(request, workspaceId, satellites, repairTargets)
    await waitForPlanningMode(request, workspaceId, 'repair')

    const applyPage = await openPlanningApply(
      page,
      testInfo,
      'three-satellite-repair-apply-page2.png',
    )

    expect(applyPage.modeSelection.planning_mode).toBe('repair')
    expect(applyPage.repairPlan.repair_diff.added.length).toBeGreaterThan(0)
    expect(applyPage.repairPlan.repair_diff.dropped.length).toBeGreaterThan(0)
    expect(applyPage.badgeCounts.added).toBeGreaterThan(0)
    expect(applyPage.badgeCounts.removed).toBeGreaterThan(0)

    const commitPromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().includes('/api/v1/schedule/repair/commit'),
    )
    await page.getByRole('button', { name: /Apply (Plan|Anyway)/i }).click()
    const commitResponse = await commitPromise
    expect(commitResponse.ok()).toBeTruthy()

    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(headerWorkspaceBadge).toContainText(workspaceName)
    await openScheduleTimeline(page)
    await waitForScheduleMapReady(page, 25_000)

    const afterRepair = await getCommittedSchedule(request, workspaceId)
    const followupSelection =
      afterRepair.acquisitions.find((item) => !droppedTargetIds.includes(item.target_id)) ??
      afterRepair.acquisitions[0]
    expect(followupSelection).toBeTruthy()

    const followupBar = page.locator(`[data-acquisition-id="${followupSelection!.id}"]`)
    await followupBar.scrollIntoViewIfNeeded()
    await followupBar.click()

    const detailsHeading = page.getByRole('heading', { name: 'Details' })
    await expect(detailsHeading).toBeVisible()
    const acquisitionHero = page.getByTestId('inspector-acquisition-hero')
    await expect(acquisitionHero).toContainText(followupSelection!.target_id)
    await expect(acquisitionHero).toContainText(normalizeSatelliteName(followupSelection!.satellite_id))

    await expect
      .poll(async () => {
        const state = await readPrimaryViewerState(page)
        return {
          selectedEntityId: state.selectedEntityId,
          slicedGroundTrackSegments: state.slicedGroundTrackSegments,
        }
      }, { timeout: 25_000 })
      .toMatchObject({
        selectedEntityId: `sched_target_${followupSelection!.target_id}`,
      })

    await expect
      .poll(async () => (await readPrimaryViewerState(page)).slicedGroundTrackSegments, {
        timeout: 25_000,
      })
      .toBeGreaterThan(0)

    const scheduleState = await readPrimaryViewerState(page)

    await page.locator('button[title="Map Layers"]').click()
    await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()
    await expect(page.getByRole('checkbox', { name: /Ground Track/ })).toBeChecked()

    const screenshotPath = testInfo.outputPath('three-satellite-repair-review.png')
    await page.screenshot({ path: screenshotPath })
    await testInfo.attach('three-satellite-repair-review', {
      path: screenshotPath,
      contentType: 'image/png',
    })

    const summaryPath = testInfo.outputPath('three-satellite-repair-summary.json')
    writeFileSync(
      summaryPath,
      JSON.stringify(
        {
          workspaceId,
          workspaceName,
          droppedTargetIds,
          trackedState,
          fitState,
          modeSelection: applyPage.modeSelection,
          repairDiff: applyPage.repairPlan.repair_diff,
          followupSelection,
          scheduleState,
        },
        null,
        2,
      ),
    )
    await testInfo.attach('three-satellite-repair-summary', {
      path: summaryPath,
      contentType: 'application/json',
    })
  })
})
