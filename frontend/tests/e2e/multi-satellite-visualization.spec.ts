import { writeFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page, TestInfo } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'
const liveVisualizationEnabled = process.env.PLAYWRIGHT_LIVE_OPERATOR === '1'
const frontendBaseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000'

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
}

const multisatTargets: Target[] = [
  { name: 'MSAT_01', latitude: 24.7136, longitude: 46.6753, priority: 5 },
  { name: 'MSAT_02', latitude: 25.2048, longitude: 55.2708, priority: 4 },
  { name: 'MSAT_03', latitude: 21.4858, longitude: 39.1925, priority: 4 },
  { name: 'MSAT_04', latitude: 29.3759, longitude: 47.9774, priority: 3 },
  { name: 'MSAT_05', latitude: 26.2235, longitude: 50.5876, priority: 3 },
  { name: 'MSAT_06', latitude: 23.5859, longitude: 58.4059, priority: 2 },
]

async function ensureLiveServices(request: APIRequestContext) {
  const [frontendResponse, apiResponse] = await Promise.all([
    fetch(frontendBaseUrl),
    request.get(`${apiBaseUrl}/api/v1/health`),
  ])

  expect(frontendResponse.ok).toBeTruthy()
  expect(apiResponse.ok()).toBeTruthy()
}

async function apiGet<T>(request: APIRequestContext, path: string): Promise<T> {
  const response = await request.get(`${apiBaseUrl}${path}`, { timeout: 120_000 })
  expect(response.ok(), `GET ${path} failed with ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

async function apiPost<T>(request: APIRequestContext, path: string, data: unknown): Promise<T> {
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

async function deleteWorkspace(request: APIRequestContext, workspaceId: string) {
  await request.delete(`${apiBaseUrl}/api/v1/workspaces/${workspaceId}`, { timeout: 120_000 })
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
  const end = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000)
  return apiPost(request, '/api/v1/mission/analyze', {
    workspace_id: workspaceId,
    satellites,
    targets,
    start_time: now.toISOString(),
    end_time: end.toISOString(),
    imaging_type: 'optical',
  })
}

async function loadWorkspaceInUi(page: Page, workspaceName: string) {
  await page.goto('/')
  await page.getByLabel('Workspaces').click()
  await expect(page.getByText('Workspace Library')).toBeVisible()

  const workspaceCard = page
    .locator('div.rounded-lg')
    .filter({ has: page.getByText(workspaceName, { exact: true }) })
    .first()

  await expect(workspaceCard).toBeVisible({ timeout: 60_000 })
  await workspaceCard.getByRole('button', { name: 'Load', exact: true }).click()
  await expect(page.getByText('Workspace loaded successfully')).toBeVisible({ timeout: 60_000 })
}

async function set3DMode(page: Page) {
  const switchTo3D = page.getByRole('button', { name: 'Switch to 3D' })
  if (await switchTo3D.isVisible().catch(() => false)) {
    await switchTo3D.click()
  }
  await expect(page.getByRole('button', { name: 'Switch to 2D' })).toBeVisible()
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
    }
  })
}

test.describe('Live multi-satellite Cesium visualization', () => {
  test.skip(!liveVisualizationEnabled, 'Set PLAYWRIGHT_LIVE_OPERATOR=1 to run live visualization drills.')

  test('renders a two-satellite workspace with fit, path toggles, and tracking', async ({
    page,
    request,
  }, testInfo: TestInfo) => {
    test.slow()

    await ensureLiveServices(request)

    const workspaceName = `live-multisat-visual-${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)

    try {
      const satellites = await getSatellites(request, ['CUSTOM-45DEG-450KM', 'ICEYE-X44'])
      await analyzeWorkspace(request, workspaceId, satellites, multisatTargets)

      await loadWorkspaceInUi(page, workspaceName)

      await expect
        .poll(async () => {
          const state = await readPrimaryViewerState(page)
          return state.dataSources[0]?.satellites ?? 0
        })
        .toBe(2)

      await expect
        .poll(async () => {
          const state = await readPrimaryViewerState(page)
          return state.dataSources[0]?.groundTracks ?? 0
        })
        .toBe(2)

      await expect(page.getByRole('button', { name: 'Satellites' })).toBeVisible()
      await expect
        .poll(async () => {
          const bodyText = await page.evaluate(() => document.body.innerText)
          return bodyText.includes('CUSTOM-45DEG-450KM') && bodyText.includes('ICEYE-X44')
        })
        .toBe(true)

      await set3DMode(page)

      await page.getByRole('button', { name: 'Fit All Targets' }).click()
      await page.waitForTimeout(2200)

      const fitState = await readPrimaryViewerState(page)
      expect(fitState.camera).not.toBeNull()
      expect(fitState.camera!.lat).toBeGreaterThan(20)
      expect(fitState.camera!.lat).toBeLessThan(31)
      expect(fitState.camera!.lon).toBeGreaterThan(37)
      expect(fitState.camera!.lon).toBeLessThan(60)
      expect(fitState.camera!.height).toBeLessThan(6_000_000)

      const fitScreenshot = testInfo.outputPath('multi-satellite-fit.png')
      await page.screenshot({ path: fitScreenshot, fullPage: true })
      await testInfo.attach('multi-satellite-fit', {
        path: fitScreenshot,
        contentType: 'image/png',
      })

      await page.locator('button[title="Map Layers"]').click()
      await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()

      const satellitePathCheckbox = page.getByRole('checkbox', { name: /Ground Track/ })
      await expect(satellitePathCheckbox).toBeChecked()
      await satellitePathCheckbox.click()

      await expect
        .poll(async () => {
          const state = await readPrimaryViewerState(page)
          return state.dataSources[0]?.visibleGroundTrackPaths ?? -1
        })
        .toBe(0)

      await satellitePathCheckbox.click()

      await expect
        .poll(async () => {
          const state = await readPrimaryViewerState(page)
          return state.dataSources[0]?.visibleGroundTrackPaths ?? -1
        })
        .toBe(2)

      await page.getByRole('button', { name: 'Close Map Layers panel' }).click()
      await page.getByRole('button', { name: 'Track Satellite' }).click()

      await expect
        .poll(async () => {
          const state = await readPrimaryViewerState(page)
          return state.trackedEntityId
        })
        .toMatch(/^sat_/)

      const trackedState = await readPrimaryViewerState(page)
      expect(trackedState.trackedEntityName).toBeTruthy()

      const summaryPath = testInfo.outputPath('multi-satellite-visualization-summary.json')
      writeFileSync(
        summaryPath,
        JSON.stringify(
          {
            workspaceId,
            workspaceName,
            satellites: satellites.map((satellite) => satellite.name),
            viewerAfterFit: fitState,
            viewerAfterTrack: trackedState,
          },
          null,
          2,
        ),
      )
      await testInfo.attach('multi-satellite-visualization-summary', {
        path: summaryPath,
        contentType: 'application/json',
      })
    } finally {
      await deleteWorkspace(request, workspaceId)
    }
  })
})
