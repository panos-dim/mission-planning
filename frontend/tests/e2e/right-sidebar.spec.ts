import { expect, test } from '@playwright/test'

test.describe('Right sidebar panels', () => {
  test('opens the simplified details and map layers panels', async ({ page }) => {
    await page.goto('/')

    const detailsButton = page.locator('button[title="Details"]')
    await expect(detailsButton).toBeVisible()
    await detailsButton.click()

    await expect(page.getByRole('heading', { name: 'Details' })).toBeVisible()
    await expect(page.getByText('Select an object to view its properties')).toBeVisible()

    const layersButton = page.locator('button[title="Map Layers"]')
    await expect(layersButton).toBeVisible()
    await layersButton.click()

    await expect(page.getByRole('heading', { name: 'Map Layers' })).toBeVisible()
    await expect(page.getByText('Choose which map aids stay visible while planning.')).toBeVisible()
    await expect(page.getByText('Core', { exact: true })).toBeVisible()
    await expect(page.getByText('Globe', { exact: true })).toBeVisible()
    await expect(page.getByText('Effects', { exact: true })).toBeVisible()
  })
})
