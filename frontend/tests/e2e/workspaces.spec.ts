import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

type WorkspaceSummary = {
  id: string
  name: string
  created_at?: string
  updated_at?: string
  mission_mode?: string
  satellites_count?: number
  targets_count?: number
}

type MockWorkspaceState = {
  nextId: number
  workspaces: WorkspaceSummary[]
}

function buildWorkspaceDetail(workspace: WorkspaceSummary) {
  return {
    id: workspace.id,
    name: workspace.name,
    mission_mode: workspace.mission_mode ?? 'planner',
    created_at: workspace.created_at ?? '2026-03-24T00:00:00Z',
    updated_at: workspace.updated_at ?? '2026-03-24T00:00:00Z',
    satellites_count: workspace.satellites_count ?? 0,
    targets_count: workspace.targets_count ?? 0,
    last_run_status: 'ready',
    schema_version: '1.0',
    app_version: 'test',
    scenario_config: {
      satellites: [],
      targets: [],
      constraints: {},
    },
    analysis_state: null,
    planning_state: null,
    orders_state: { orders: [] },
    ui_state: null,
    czml_data: [],
  }
}

async function mockWorkspaceApis(
  page: Page,
  options?: {
    initialWorkspaces?: WorkspaceSummary[]
    onListRequest?: () => Promise<void> | void
  },
) {
  const state: MockWorkspaceState = {
    nextId: (options?.initialWorkspaces?.length ?? 0) + 1,
    workspaces: [...(options?.initialWorkspaces ?? [])],
  }

  await page.route('**/api/v1/workspaces/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const workspaceId = url.pathname.split('/').pop() ?? ''

    if (request.method() === 'GET') {
      const workspace = state.workspaces.find((entry) => entry.id === workspaceId)
      if (!workspace) {
        await route.fulfill({ status: 404, json: { detail: 'Workspace not found' } })
        return
      }
      await route.fulfill({
        json: {
          success: true,
          workspace: buildWorkspaceDetail(workspace),
        },
      })
      return
    }

    if (request.method() === 'DELETE') {
      state.workspaces = state.workspaces.filter((entry) => entry.id !== workspaceId)
      await route.fulfill({
        json: {
          success: true,
          workspace_id: workspaceId,
        },
      })
      return
    }

    await route.fulfill({ status: 405, json: { detail: 'Method not allowed' } })
  })

  await page.route('**/api/v1/workspaces?**', async (route) => {
    const request = route.request()
    if (request.method() === 'GET') {
      await options?.onListRequest?.()
      await route.fulfill({
        json: {
          success: true,
          workspaces: state.workspaces,
          total: state.workspaces.length,
        },
      })
      return
    }
    await route.fulfill({ status: 405, json: { detail: 'Method not allowed' } })
  })

  await page.route('**/api/v1/workspaces', async (route) => {
    const request = route.request()
    if (request.method() === 'POST') {
      const body = request.postDataJSON() as { name?: string }
      const timestamp = '2026-03-24T00:00:00Z'
      const workspace = {
        id: `ws-${state.nextId++}`,
        name: body.name || `Workspace ${state.nextId}`,
        created_at: timestamp,
        updated_at: timestamp,
        mission_mode: 'planner',
        satellites_count: 0,
        targets_count: 0,
      }
      state.workspaces.push(workspace)
      await route.fulfill({
        json: {
          success: true,
          workspaceId: workspace.id,
          workspace_id: workspace.id,
          workspace: buildWorkspaceDetail(workspace),
        },
      })
      return
    }
    await route.fulfill({ status: 405, json: { detail: 'Method not allowed' } })
  })

  await page.route('**/api/v1/satellites**', async (route) => {
    await route.fulfill({ json: { success: true, satellites: [] } })
  })

  await page.route('**/api/v1/config/sar-modes**', async (route) => {
    await route.fulfill({ json: { success: true, modes: {} } })
  })

  await page.route('**/api/v1/schedule/horizon**', async (route) => {
    await route.fulfill({
      json: {
        success: true,
        horizon: {
          start: '2026-04-01T00:00:00Z',
          end: '2026-04-08T00:00:00Z',
          freeze_cutoff: '2026-04-01T00:00:00Z',
        },
        acquisitions: [],
        statistics: {
          total_acquisitions: 0,
          by_state: {},
          by_satellite: {},
        },
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

  return state
}

test.describe('Workspaces tab', () => {
  test('refresh re-fetches the workspace list and shows visible sync feedback', async ({
    page,
  }) => {
    let listResponseCount = 0
    await mockWorkspaceApis(page, {
      initialWorkspaces: [{ id: 'ws-1', name: 'Ops Workspace' }],
      onListRequest: async () => {
        listResponseCount += 1
        if (listResponseCount >= 2) {
          await new Promise((resolve) => setTimeout(resolve, 500))
        }
      },
    })

    await page.goto('/')
    await page.getByLabel('Workspaces').click()

    await expect(page.getByText('Workspace Library')).toBeVisible()
    await expect(page.getByLabel('Import workspace')).toBeVisible()
    await expect(page.getByLabel('Refresh workspace list')).toBeVisible()

    const refreshResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'GET' && response.url().includes('/api/v1/workspaces'),
    )

    await page.getByLabel('Refresh workspace list').click()

    await expect(page.getByText('Refreshing workspace list from the server...')).toBeVisible()
    const refreshResponse = await refreshResponsePromise
    expect(refreshResponse.ok()).toBeTruthy()
    await expect(page.getByText('Refreshing workspace list from the server...')).toBeHidden()
    await expect(page.getByText(/^Updated /)).toBeVisible()
    expect(listResponseCount).toBeGreaterThanOrEqual(2)
  })

  test('creates and deletes a workspace from the UI', async ({ page }) => {
    const workspaceName = `pw-ui-${Date.now()}`
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')
    const state = await mockWorkspaceApis(page)

    await page.goto('/')
    await page.getByLabel('Workspaces').click()
    await page.getByRole('button', { name: 'New Workspace' }).click()
    await page.getByPlaceholder('Workspace name...').fill(workspaceName)
    await page.getByRole('button', { name: 'Create', exact: true }).click()

    await expect(page.getByText(`Workspace "${workspaceName}" created`)).toBeVisible()
    await expect(page.getByText('Active Workspace')).toBeVisible()
    await expect(headerWorkspaceBadge).toContainText(workspaceName)
    await expect(page.getByText('Selected', { exact: true })).toBeVisible()

    const created = state.workspaces.find((workspace) => workspace.name === workspaceName)
    expect(created).toBeTruthy()

    page.once('dialog', (dialog) => dialog.accept())
    await page.getByLabel(`Delete workspace ${workspaceName}`).click()
    await expect(page.getByText(`Workspace "${workspaceName}" deleted`)).toBeVisible()

    expect(state.workspaces.some((workspace) => workspace.name === workspaceName)).toBeFalsy()
  })

  test('loads an existing workspace and preserves the active selection after reload', async ({
    page,
  }) => {
    const workspaceName = `pw-load-${Date.now()}`
    const workspaceId = 'ws-load-1'
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')
    await mockWorkspaceApis(page, {
      initialWorkspaces: [{ id: workspaceId, name: workspaceName }],
    })

    await page.goto('/')
    await page.getByLabel('Workspaces').click()

    const workspaceCard = page
      .locator('div.rounded-lg')
      .filter({ has: page.getByText(workspaceName, { exact: true }) })
      .first()

    await workspaceCard.getByTitle('Load workspace').click()

    await expect(page.getByText('Workspace loaded successfully')).toBeVisible()
    await expect(headerWorkspaceBadge).toContainText(workspaceName)
    await expect(page.getByText('Active Workspace')).toBeVisible()

    await page.reload({ waitUntil: 'networkidle' })
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
    await expect(activeSummary).toContainText('Loaded from saved workspaces')

    const persisted = await page.evaluate(() => localStorage.getItem('mission_workspaces'))
    expect(persisted).toContain('"version":1')
    expect(persisted).toContain(`"activeWorkspace":"${workspaceId}"`)
  })
})
