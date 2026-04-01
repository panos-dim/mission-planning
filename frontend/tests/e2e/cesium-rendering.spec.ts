import { expect, test } from '@playwright/test'

test.describe('Cesium globe rendering', () => {
  test('renders the globe without initialization errors', async ({ page }, testInfo) => {
    test.slow()

    const runtimeErrors: string[] = []

    page.on('console', (message) => {
      const text = message.text()
      if (
        message.type() === 'error' ||
        text.includes('Error constructing CesiumWidget') ||
        text.includes('initialization failed')
      ) {
        runtimeErrors.push(`[${message.type()}] ${text}`)
      }
    })

    page.on('pageerror', (error) => {
      runtimeErrors.push(`[pageerror] ${error.message}`)
    })

    await page.route('**/api/v1/workspaces?**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          workspaces: [
            {
              id: 'default',
              name: 'Default Workspace',
              satellites_count: 1,
              targets_count: 0,
            },
          ],
          total: 1,
        },
      })
    })

    await page.route('**/api/v1/workspaces/default?**', async (route) => {
      await route.fulfill({
        json: {
          success: true,
          workspace: {
            id: 'default',
            name: 'Default Workspace',
            mission_mode: 'OPTICAL',
            satellites: [],
            targets: [],
          },
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

    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('canvas').first()).toBeVisible()
    await page.waitForTimeout(5000)

    const globeState = await page.evaluate(() => {
      const canvas = document.querySelector('canvas')
      const bodyText = document.body.innerText

      if (!(canvas instanceof HTMLCanvasElement)) {
        return {
          hasCanvas: false,
          width: 0,
          height: 0,
          canvasCount: 0,
          hasCesiumErrorText: bodyText.includes('Error constructing CesiumWidget'),
          hasWebgl2: false,
        }
      }

      return {
        hasCanvas: true,
        width: canvas.clientWidth,
        height: canvas.clientHeight,
        canvasCount: document.querySelectorAll('canvas').length,
        hasCesiumErrorText: bodyText.includes('Error constructing CesiumWidget'),
        hasWebgl2: !!canvas.getContext('webgl2'),
      }
    })

    expect(globeState.hasCanvas).toBeTruthy()
    expect(globeState.width).toBeGreaterThan(0)
    expect(globeState.height).toBeGreaterThan(0)
    expect(globeState.canvasCount).toBeGreaterThanOrEqual(1)
    expect(globeState.hasCesiumErrorText).toBeFalsy()
    expect(globeState.hasWebgl2).toBeTruthy()
    expect(runtimeErrors).toEqual([])

    const screenshotPath = testInfo.outputPath('cesium-globe.png')
    await page.screenshot({ path: screenshotPath, fullPage: true })
    await testInfo.attach('cesium-globe', {
      path: screenshotPath,
      contentType: 'image/png',
    })
  })
})
