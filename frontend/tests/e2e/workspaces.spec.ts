import { expect, test } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

const apiBaseUrl = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000'

type WorkspaceSummary = {
  id: string
  name: string
}

type WorkspaceListResponse = {
  workspaces: WorkspaceSummary[]
}

async function ensureServices() {
  const [frontendResponse, apiResponse] = await Promise.all([
    fetch(process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3000'),
    fetch(`${apiBaseUrl}/api/v1/workspaces`),
  ])

  if (!frontendResponse.ok) {
    throw new Error(`Frontend unavailable: ${frontendResponse.status}`)
  }

  if (!apiResponse.ok) {
    throw new Error(`API unavailable: ${apiResponse.status}`)
  }
}

async function listWorkspaces(request: APIRequestContext): Promise<WorkspaceSummary[]> {
  const response = await request.get(`${apiBaseUrl}/api/v1/workspaces`)
  expect(response.ok()).toBeTruthy()
  const body = (await response.json()) as WorkspaceListResponse
  return body.workspaces
}

async function createWorkspace(request: APIRequestContext, name: string) {
  const response = await request.post(`${apiBaseUrl}/api/v1/workspaces`, {
    data: { name },
  })
  expect(response.ok()).toBeTruthy()
  const body = (await response.json()) as { workspaceId: string }
  return body.workspaceId
}

async function deleteWorkspace(request: APIRequestContext, workspaceId: string) {
  await request.delete(`${apiBaseUrl}/api/v1/workspaces/${workspaceId}`)
}

test.describe('Workspaces tab', () => {
  test.beforeAll(async () => {
    await ensureServices()
  })

  test('refresh re-fetches the workspace list and shows visible sync feedback', async ({
    page,
  }) => {
    let listResponseCount = 0
    await page.route('**/api/v1/workspaces**', async (route) => {
      const request = route.request()
      if (request.method() === 'GET' && request.url().includes('/api/v1/workspaces')) {
        listResponseCount += 1
        if (listResponseCount >= 2) {
          await new Promise((resolve) => setTimeout(resolve, 500))
        }
      }
      await route.continue()
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

  test('creates and deletes a workspace from the UI', async ({ page, request }) => {
    const workspaceName = `pw-ui-${Date.now()}`
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')

    await page.goto('/')
    await page.getByLabel('Workspaces').click()
    await page.getByRole('button', { name: 'New Workspace' }).click()
    await page.getByPlaceholder('Workspace name...').fill(workspaceName)
    await page.getByRole('button', { name: 'Create' }).click()

    await expect(page.getByText(`Workspace "${workspaceName}" created`)).toBeVisible()
    await expect(page.getByText('Active Workspace')).toBeVisible()
    await expect(headerWorkspaceBadge).toContainText(workspaceName)
    await expect(page.getByText('Selected', { exact: true })).toBeVisible()

    const currentList = await listWorkspaces(request)
    const created = currentList.find((workspace) => workspace.name === workspaceName)
    expect(created).toBeTruthy()

    page.once('dialog', (dialog) => dialog.accept())
    await page.getByLabel(`Delete workspace ${workspaceName}`).click()
    await expect(page.getByText(`Workspace "${workspaceName}" deleted`)).toBeVisible()

    const remaining = await listWorkspaces(request)
    expect(remaining.some((workspace) => workspace.name === workspaceName)).toBeFalsy()
  })

  test('loads an existing workspace and clears the active selection after reload', async ({
    page,
    request,
  }) => {
    const workspaceName = `pw-load-${Date.now()}`
    const workspaceId = await createWorkspace(request, workspaceName)
    const headerWorkspaceBadge = page.locator('div[title^="Selected workspace:"]')

    try {
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
      await expect(headerWorkspaceBadge).toContainText('Default Workspace')

      await page.getByLabel('Workspaces').click()
      await expect(page.getByText('Using the default unsaved workspace')).toBeVisible()
      const reloadedCard = page
        .locator('div.rounded-lg')
        .filter({ has: page.getByText(workspaceName, { exact: true }) })
        .first()
      await expect(reloadedCard.getByText('Active', { exact: true })).toHaveCount(0)

      const persisted = await page.evaluate(() => localStorage.getItem('mission_workspaces'))
      expect(persisted).toContain('"version":1')
      expect(persisted).not.toContain('activeWorkspace')
    } finally {
      await deleteWorkspace(request, workspaceId)
    }
  })
})
