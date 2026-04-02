import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'
const frontendBaseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000'
const liveEnabled = process.env.PLAYWRIGHT_LIVE_OPERATOR === '1'
const customSatelliteName = 'CUSTOM-45DEG-450KM'

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

type Pass = {
  target: string
  start_time: string
  end_time: string
  max_elevation_time: string
}

type AcquisitionTimeWindowRequest = {
  enabled: boolean
  start_time: string
  end_time: string
  timezone: 'UTC'
  reference: 'off_nadir_time'
}

type AnalyzeResponse = {
  data?: {
    mission_data?: {
      passes?: Pass[]
      acquisition_time_window?: AcquisitionTimeWindowRequest
    }
  }
}

type DiscoveredWindow = {
  start: string
  end: string
  startMinute: number
  endMinute: number
  count: number
}

const gulfTargets: Target[] = [
  { name: 'Dubai', latitude: 25.2048, longitude: 55.2708, priority: 5 },
  { name: 'Abu Dhabi', latitude: 24.4539, longitude: 54.3773, priority: 5 },
  { name: 'Doha', latitude: 25.2854, longitude: 51.531, priority: 5 },
  { name: 'Manama', latitude: 26.2285, longitude: 50.586, priority: 5 },
  { name: 'Kuwait City', latitude: 29.3759, longitude: 47.9774, priority: 5 },
  { name: 'Muscat', latitude: 23.588, longitude: 58.3829, priority: 5 },
  { name: 'Riyadh', latitude: 24.7136, longitude: 46.6753, priority: 5 },
  { name: 'Jeddah', latitude: 21.4858, longitude: 39.1925, priority: 5 },
  { name: 'Bandar Abbas', latitude: 27.1865, longitude: 56.2808, priority: 5 },
  { name: 'Salalah', latitude: 17.0151, longitude: 54.0924, priority: 5 },
]

function normalizeMinute(minute: number) {
  return ((minute % 1440) + 1440) % 1440
}

function formatMinute(minute: number) {
  const normalized = normalizeMinute(minute)
  const hours = String(Math.floor(normalized / 60)).padStart(2, '0')
  const minutes = String(normalized % 60).padStart(2, '0')
  return `${hours}:${minutes}`
}

function getUtcMinuteOfDay(timestamp: string) {
  const value = new Date(timestamp)
  return value.getUTCHours() * 60 + value.getUTCMinutes()
}

function containsMinute(minute: number, startMinute: number, endMinute: number) {
  return startMinute < endMinute
    ? minute >= startMinute && minute <= endMinute
    : minute >= startMinute || minute <= endMinute
}

function buildWindow(
  startMinute: number,
  endMinute: number,
  passMinutes: number[],
): DiscoveredWindow {
  const normalizedStart = normalizeMinute(startMinute)
  const normalizedEnd = normalizeMinute(endMinute)
  return {
    start: formatMinute(normalizedStart),
    end: formatMinute(normalizedEnd),
    startMinute: normalizedStart,
    endMinute: normalizedEnd,
    count: passMinutes.filter((minute) => containsMinute(minute, normalizedStart, normalizedEnd))
      .length,
  }
}

function findSubsetWindow(passMinutes: number[]): DiscoveredWindow | null {
  const uniqueMinutes = [...new Set(passMinutes)].sort((left, right) => left - right)

  for (const width of [30, 60, 90, 120, 180]) {
    for (const minute of uniqueMinutes) {
      const startMinute = normalizeMinute(minute - Math.floor(width / 2))
      const endMinute = normalizeMinute(startMinute + width)
      if (startMinute >= endMinute) continue

      const candidate = buildWindow(startMinute, endMinute, passMinutes)
      if (candidate.count > 0 && candidate.count < passMinutes.length) {
        return candidate
      }
    }
  }

  return null
}

function findOvernightWindow(passMinutes: number[]): DiscoveredWindow | null {
  const uniqueMinutes = [...new Set(passMinutes)].sort((left, right) => left - right)

  for (const width of [120, 180, 240, 300, 360]) {
    for (const minute of uniqueMinutes) {
      const endMinute = normalizeMinute(minute + 15)
      const startMinute = normalizeMinute(endMinute - width)
      if (startMinute <= endMinute) continue

      const candidate = buildWindow(startMinute, endMinute, passMinutes)
      if (candidate.count > 0 && candidate.count < passMinutes.length) {
        return candidate
      }
    }
  }

  return null
}

function findEmptyWindow(passMinutes: number[]): DiscoveredWindow | null {
  for (const width of [60, 120, 180]) {
    for (let startMinute = 0; startMinute < 1440; startMinute += 30) {
      const endMinute = normalizeMinute(startMinute + width)
      if (startMinute >= endMinute) continue

      const candidate = buildWindow(startMinute, endMinute, passMinutes)
      if (candidate.count === 0) {
        return candidate
      }
    }
  }

  return null
}

function serializePass(pass: Pass) {
  return [pass.target, pass.start_time, pass.end_time, pass.max_elevation_time].join('|')
}

function filterPassesByWindow(passes: Pass[], window: DiscoveredWindow) {
  return passes.filter((pass) =>
    containsMinute(getUtcMinuteOfDay(pass.max_elevation_time), window.startMinute, window.endMinute),
  )
}

async function ensureLiveServices(request: APIRequestContext) {
  const [frontendResponse, apiResponse] = await Promise.all([
    fetch(frontendBaseUrl),
    request.get(`${apiBaseUrl}/api/v1/health`),
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
  const response = await request.post(`${apiBaseUrl}${path}`, {
    data,
    timeout,
  })
  expect(response.ok(), `POST ${path} failed with ${response.status()}`).toBeTruthy()
  return (await response.json()) as T
}

async function createWorkspace(request: APIRequestContext, name: string) {
  const response = await apiPost<{ workspace_id: string }>(request, '/api/v1/workspaces', { name })
  return response.workspace_id
}

async function getCustomSatellite(request: APIRequestContext) {
  const response = await apiGet<{ satellites?: SatelliteConfig[] }>(request, '/api/v1/satellites')
  const satellite = response.satellites?.find((item) => item.name === customSatelliteName)
  expect(satellite).toBeTruthy()
  return satellite as SatelliteConfig
}

async function analyzeWorkspace(
  request: APIRequestContext,
  workspaceId: string,
  satellite: SatelliteConfig,
  targets: Target[],
  startTime: Date,
  endTime: Date,
  acquisitionTimeWindow?: AcquisitionTimeWindowRequest,
) {
  const response = await apiPost<AnalyzeResponse>(request, '/api/v1/mission/analyze', {
    workspace_id: workspaceId,
    satellites: [satellite],
    targets,
    start_time: startTime.toISOString(),
    end_time: endTime.toISOString(),
    mission_type: 'imaging',
    imaging_type: 'optical',
    ...(acquisitionTimeWindow ? { acquisition_time_window: acquisitionTimeWindow } : {}),
  })

  return {
    response,
    missionData: response.data?.mission_data,
    passes: response.data?.mission_data?.passes ?? [],
  }
}

async function getOpportunitiesCount(request: APIRequestContext, workspaceId: string) {
  const response = await apiGet<{ opportunities?: unknown[]; count?: number }>(
    request,
    '/api/v1/planning/opportunities',
    { workspace_id: workspaceId },
  )
  return response.count ?? response.opportunities?.length ?? 0
}

async function loadWorkspaceInUi(page: Page, workspaceName: string) {
  await page.goto('/', { waitUntil: 'networkidle' })
  await page.getByLabel('Workspaces').click()
  await expect(page.getByText('Workspace Library')).toBeVisible()

  const refreshButton = page.getByRole('button', { name: 'Refresh workspace list' })
  const selectedWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    if (await refreshButton.isVisible().catch(() => false)) {
      await refreshButton.click()
    }

    const workspaceCard = page
      .locator('div.rounded-lg')
      .filter({ has: page.getByText(workspaceName, { exact: true }) })
      .first()

    await expect(workspaceCard).toBeVisible({ timeout: 60_000 })
    await workspaceCard.getByTitle('Load workspace').click({ force: true })

    try {
      await expect(selectedWorkspaceBadge).toContainText(workspaceName, { timeout: 60_000 })
      return
    } catch (error) {
      if (attempt === 2) throw error
    }
  }
}

async function openFeasibilityResults(page: Page) {
  const resultsButton = page.getByTitle('Feasibility Results')
  await expect(resultsButton).toBeVisible({ timeout: 30_000 })
  await resultsButton.click({ force: true })
}

async function discoverScenario(request: APIRequestContext, satellite: SatelliteConfig) {
  const workspaceId = await createWorkspace(request, `live-acq-window-discovery-${Date.now()}`)
  const startTime = new Date(Date.now() + 5 * 60 * 1000)

  for (const horizonDays of [2, 3, 4, 5]) {
    const endTime = new Date(startTime.getTime() + horizonDays * 24 * 60 * 60 * 1000)
    const analysis = await analyzeWorkspace(
      request,
      workspaceId,
      satellite,
      gulfTargets,
      startTime,
      endTime,
    )
    const passMinutes = analysis.passes.map((pass) => getUtcMinuteOfDay(pass.max_elevation_time))

    if (analysis.passes.length === 0) continue

    const subsetWindow = findSubsetWindow(passMinutes)
    const overnightWindow = findOvernightWindow(passMinutes)
    const emptyWindow = findEmptyWindow(passMinutes)

    if (subsetWindow && overnightWindow && emptyWindow) {
      return {
        workspaceId,
        startTime,
        endTime,
        horizonDays,
        passes: analysis.passes,
        subsetWindow,
        overnightWindow,
        emptyWindow,
      }
    }
  }

  throw new Error('Could not discover a live acquisition time window scenario with subset + overnight + empty cases')
}

test.describe('live acquisition time window feasibility', () => {
  test.skip(!liveEnabled, 'Set PLAYWRIGHT_LIVE_OPERATOR=1 to run live acquisition window verification')

  test('applies backend feasibility filtering and surfaces accurate UI results', async ({
    page,
    request,
  }) => {
    test.setTimeout(12 * 60 * 1000)

    await ensureLiveServices(request)

    const satellite = await getCustomSatellite(request)
    const scenario = await discoverScenario(request, satellite)

    expect(scenario.passes.length).toBeGreaterThan(1)

    const baselineOpportunityCount = await getOpportunitiesCount(request, scenario.workspaceId)
    expect(baselineOpportunityCount).toBe(scenario.passes.length)

    const expectedSubsetPasses = filterPassesByWindow(scenario.passes, scenario.subsetWindow)
    const expectedOvernightPasses = filterPassesByWindow(scenario.passes, scenario.overnightWindow)
    const expectedEmptyPasses = filterPassesByWindow(scenario.passes, scenario.emptyWindow)

    expect(expectedSubsetPasses.length).toBe(scenario.subsetWindow.count)
    expect(expectedOvernightPasses.length).toBe(scenario.overnightWindow.count)
    expect(expectedEmptyPasses.length).toBe(0)

    const filteredWorkspaceName = `live-acq-window-filtered-${Date.now()}`
    const overnightWorkspaceName = `live-acq-window-overnight-${Date.now()}`
    const emptyWorkspaceName = `live-acq-window-empty-${Date.now()}`

    const filteredWorkspaceId = await createWorkspace(request, filteredWorkspaceName)
    const overnightWorkspaceId = await createWorkspace(request, overnightWorkspaceName)
    const emptyWorkspaceId = await createWorkspace(request, emptyWorkspaceName)

    const filteredWindowRequest: AcquisitionTimeWindowRequest = {
      enabled: true,
      start_time: scenario.subsetWindow.start,
      end_time: scenario.subsetWindow.end,
      timezone: 'UTC',
      reference: 'off_nadir_time',
    }
    const overnightWindowRequest: AcquisitionTimeWindowRequest = {
      enabled: true,
      start_time: scenario.overnightWindow.start,
      end_time: scenario.overnightWindow.end,
      timezone: 'UTC',
      reference: 'off_nadir_time',
    }
    const emptyWindowRequest: AcquisitionTimeWindowRequest = {
      enabled: true,
      start_time: scenario.emptyWindow.start,
      end_time: scenario.emptyWindow.end,
      timezone: 'UTC',
      reference: 'off_nadir_time',
    }

    const filteredAnalysis = await analyzeWorkspace(
      request,
      filteredWorkspaceId,
      satellite,
      gulfTargets,
      scenario.startTime,
      scenario.endTime,
      filteredWindowRequest,
    )
    const overnightAnalysis = await analyzeWorkspace(
      request,
      overnightWorkspaceId,
      satellite,
      gulfTargets,
      scenario.startTime,
      scenario.endTime,
      overnightWindowRequest,
    )
    const emptyAnalysis = await analyzeWorkspace(
      request,
      emptyWorkspaceId,
      satellite,
      gulfTargets,
      scenario.startTime,
      scenario.endTime,
      emptyWindowRequest,
    )

    expect(filteredAnalysis.missionData?.acquisition_time_window).toEqual(filteredWindowRequest)
    expect(overnightAnalysis.missionData?.acquisition_time_window).toEqual(overnightWindowRequest)
    expect(emptyAnalysis.missionData?.acquisition_time_window).toEqual(emptyWindowRequest)

    expect(filteredAnalysis.passes.map(serializePass).sort()).toEqual(
      expectedSubsetPasses.map(serializePass).sort(),
    )
    expect(overnightAnalysis.passes.map(serializePass).sort()).toEqual(
      expectedOvernightPasses.map(serializePass).sort(),
    )
    expect(emptyAnalysis.passes).toHaveLength(0)

    expect(await getOpportunitiesCount(request, filteredWorkspaceId)).toBe(expectedSubsetPasses.length)
    expect(await getOpportunitiesCount(request, overnightWorkspaceId)).toBe(expectedOvernightPasses.length)
    expect(await getOpportunitiesCount(request, emptyWorkspaceId)).toBe(0)

    await loadWorkspaceInUi(page, filteredWorkspaceName)
    await openFeasibilityResults(page)
    await expect(
      page.getByText(`Time window active: ${scenario.subsetWindow.start}-${scenario.subsetWindow.end}`),
    ).toBeVisible({ timeout: 60_000 })
    await expect(page.getByText(`${expectedSubsetPasses.length} windows`)).toBeVisible({
      timeout: 60_000,
    })

    await loadWorkspaceInUi(page, overnightWorkspaceName)
    await openFeasibilityResults(page)
    await expect(
      page.getByText(
        `Time window active: ${scenario.overnightWindow.start}-${scenario.overnightWindow.end}`,
      ),
    ).toBeVisible({ timeout: 60_000 })
    await expect(page.getByText(`${expectedOvernightPasses.length} windows`)).toBeVisible({
      timeout: 60_000,
    })

    await loadWorkspaceInUi(page, emptyWorkspaceName)
    await openFeasibilityResults(page)
    await expect(
      page.getByText(`Time window active: ${scenario.emptyWindow.start}-${scenario.emptyWindow.end}`),
    ).toBeVisible({ timeout: 60_000 })
    await expect(
      page.getByText('No opportunities found inside the selected acquisition time window.'),
    ).toBeVisible({ timeout: 60_000 })
  })
})
