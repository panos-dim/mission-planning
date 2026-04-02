import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

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

type WorkspaceSummary = {
  id: string
  name: string
}

type HorizonAcquisition = {
  id: string
  satellite_id: string
  target_id: string
  start_time: string
  end_time: string
  state: string
  lock_level: 'none' | 'hard'
}

const lockTargets: Target[] = [
  { name: 'LOCK_JEDDAH', latitude: 21.4858, longitude: 39.1925, priority: 5 },
  { name: 'LOCK_RIYADH', latitude: 24.7136, longitude: 46.6753, priority: 5 },
  { name: 'LOCK_KUWAIT', latitude: 29.3759, longitude: 47.9774, priority: 5 },
  { name: 'LOCK_MANAMA', latitude: 26.2235, longitude: 50.5876, priority: 5 },
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

async function getCommittedSchedule(request: APIRequestContext, workspaceId: string) {
  const now = new Date()
  const horizonEnd = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000)
  const horizon = await apiGet<{
    acquisitions?: HorizonAcquisition[]
  }>(request, '/api/v1/schedule/horizon', {
    workspace_id: workspaceId,
    from: now.toISOString(),
    to: horizonEnd.toISOString(),
  })

  return (horizon.acquisitions ?? []).filter((item) => item.state === 'committed')
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
    opportunity_id: item.opportunity_id || `live_lock_item_${index + 1}`,
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

  const acquisitions = await getCommittedSchedule(request, workspaceId)
  expect(acquisitions.length).toBeGreaterThan(0)
  return acquisitions
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

async function waitForScheduleMapReady(page: Page, timeoutMs = 25_000) {
  await expect
    .poll(
      async () =>
        page.evaluate(() => {
          type DebugEntity = { id?: string }
          type DebugViewer = {
            entities?: {
              values?: DebugEntity[]
            }
            dataSources?: {
              length?: number
            }
          }

          const viewer = (globalThis as typeof globalThis & { __primaryViewer?: DebugViewer })
            .__primaryViewer

          return {
            viewerDataSources: viewer?.dataSources?.length ?? 0,
            slicedCount:
              viewer?.entities?.values?.filter?.(
                (entity) => typeof entity.id === 'string' && entity.id.endsWith('_ground_track_sliced'),
              ).length ?? 0,
            schedulePins:
              viewer?.entities?.values?.filter?.(
                (entity) => typeof entity.id === 'string' && entity.id.startsWith('sched_target_'),
              ).length ?? 0,
          }
        }),
      { timeout: timeoutMs },
    )
    .toMatchObject({
      viewerDataSources: expect.any(Number),
      slicedCount: expect.any(Number),
      schedulePins: expect.any(Number),
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
              (entity) => typeof entity.id === 'string' && entity.id.startsWith('sched_target_'),
            ).length ?? 0
          )
        }),
      { timeout: timeoutMs },
    )
    .toBeGreaterThan(0)
}

async function getEntityScreenPosition(page: Page, entityId: string) {
  return page.evaluate((id) => {
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
    if (!viewer) return null

    const entity = viewer.entities.getById(id)
    if (!entity?.position) return null

    const position = entity.position.getValue(viewer.clock.currentTime)
    if (!position) return null

    viewer.scene.requestRender()
    const canvasCoords = viewer.scene.cartesianToCanvasCoordinates(position)
    if (!canvasCoords) return null

    const rect = viewer.canvas.getBoundingClientRect()
    return {
      x: rect.left + canvasCoords.x,
      y: rect.top + canvasCoords.y,
    }
  }, entityId)
}

async function hasLockBadge(page: Page, targetId: string) {
  return page.evaluate((target) => {
    type DebugViewer = {
      entities?: {
        getById?: (id: string) => unknown
      }
    }

    const viewer = (globalThis as typeof globalThis & { __primaryViewer?: DebugViewer })
      .__primaryViewer
    return Boolean(viewer?.entities?.getById?.(`sched_lock_${target}`))
  }, targetId)
}

async function waitForLockLevel(
  request: APIRequestContext,
  workspaceId: string,
  acquisitionId: string,
  expected: 'none' | 'hard',
  timeoutMs = 30_000,
) {
  await expect
    .poll(
      async () => {
        const acquisitions = await getCommittedSchedule(request, workspaceId)
        return acquisitions.find((item) => item.id === acquisitionId)?.lock_level ?? null
      },
      { timeout: timeoutMs },
    )
    .toBe(expected)
}

function pickTargetForLockTest(acquisitions: HorizonAcquisition[]) {
  const counts = acquisitions.reduce<Record<string, number>>((acc, acquisition) => {
    acc[acquisition.target_id] = (acc[acquisition.target_id] ?? 0) + 1
    return acc
  }, {})

  return acquisitions.find((acquisition) => counts[acquisition.target_id] === 1) ?? acquisitions[0] ?? null
}

test.describe('Live schedule map lock mode', () => {
  test.skip(!liveEnabled, 'Set PLAYWRIGHT_LIVE_OPERATOR=1 to run live lock-mode verification.')

  test('locks and unlocks a schedule target from the map while lock mode stays active', async ({
    page,
    request,
  }) => {
    test.setTimeout(6 * 60 * 1000)
    test.slow()

    await ensureLiveServices(request)

    const workspaceName = `live-map-lock-${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const satellites = await getSatellites(request, ['ICEYE-X66'])

    await analyzeWorkspace(request, workspaceId, satellites, lockTargets)
    const acquisitions = await planAndCommitSchedule(request, workspaceId)
    const targetAcquisition = pickTargetForLockTest(acquisitions)
    expect(targetAcquisition).toBeTruthy()

    await loadWorkspaceInUi(page, workspaceName)
    await openScheduleTimeline(page)
    await waitForScheduleMapReady(page)

    await page.getByRole('button', { name: 'Fit All Targets', exact: true }).click()
    await page.waitForTimeout(1500)

    const entityId = `sched_target_${targetAcquisition!.target_id}`
    let clickPosition: { x: number; y: number } | null = null
    await expect
      .poll(
        async () => {
          clickPosition = await getEntityScreenPosition(page, entityId)
          return clickPosition !== null
        },
        { timeout: 25_000 },
      )
      .toBe(true)

    await page.getByRole('button', { name: 'Lock Mode', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Exit Lock Mode', exact: true })).toBeVisible()

    await page.mouse.click(clickPosition!.x, clickPosition!.y)
    await waitForLockLevel(request, workspaceId, targetAcquisition!.id, 'hard')
    await expect
      .poll(async () => hasLockBadge(page, targetAcquisition!.target_id), {
        timeout: 10_000,
      })
      .toBe(true)

    await expect(page.getByRole('button', { name: 'Exit Lock Mode', exact: true })).toBeVisible()

    let unlockClickPosition: { x: number; y: number } | null = null
    await expect
      .poll(
        async () => {
          unlockClickPosition = await getEntityScreenPosition(page, entityId)
          return unlockClickPosition !== null
        },
        { timeout: 10_000 },
      )
      .toBe(true)

    await page.mouse.click(unlockClickPosition!.x, unlockClickPosition!.y)
    await waitForLockLevel(request, workspaceId, targetAcquisition!.id, 'none')
    await expect
      .poll(async () => hasLockBadge(page, targetAcquisition!.target_id), {
        timeout: 10_000,
      })
      .toBe(false)
  })
})
