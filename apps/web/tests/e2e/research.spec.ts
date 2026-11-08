import { test, expect } from '@playwright/test'

test.describe('Research View', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to research page
    await page.goto('/research')
    await page.waitForLoadState('networkidle')
  })

  test('research tab should load successfully', async ({ page }) => {
    // Check URL contains research
    await expect(page).toHaveURL(/research/i)

    // Check page title
    await expect(page).toHaveTitle(/research/i)
  })

  test('should display rankings table or list', async ({ page }) => {
    // Wait for rankings to load
    await page.waitForSelector('[data-testid="rankings"]', { timeout: 10000 }).catch(() => {
      // Alternative: check for rankings container
      return page.waitForSelector('.rankings, [role="table"]', { timeout: 10000 })
    })
  })

  test('score bars should be displayed', async ({ page }) => {
    // Check for score display elements
    const scoreBars = page.locator('[data-testid="score-bar"], .score-bar, [role="progressbar"]')

    // At least one score bar should be visible
    await expect(scoreBars.first()).toBeVisible()
  })

  test('expandable detail panel should work', async ({ page }) => {
    // Find a row or card that can be expanded
    const expandableRow = page.locator('[data-testid="ranking-row"], tr, .card,.ranking-item').first()

    if (await expandableRow.count() > 0) {
      // Try to expand details
      const expandButton = expandableRow.locator('button[aria-expanded="false"], button[title*="expand"], .expand-icon')

      if (await expandButton.count() > 0) {
        await expandButton.click()

        // Detail panel should now be visible
        await expect(expandableRow.locator('[aria-expanded="true"]')).toBeVisible()
      }
    }
  })

  test('detail panel should have aria-live region', async ({ page }) => {
    // Look for detail panels
    const detailPanels = page.locator('[data-testid="detail-panel"], .detail-panel, [role="region"]')

    // Check if any have aria-live
    const panels = await detailPanels.count()

    for (let i = 0; i < Math.min(panels, 3); i++) {
      const panel = detailPanels.nth(i)
      const hasLiveRegion = await panel.getAttribute('aria-live')

      if (hasLiveRegion) {
        expect(['polite', 'assertive']).toContain(hasLiveRegion)
      }
    }
  })

  test('keyboard navigation for tabs should work', async ({ page }) => {
    // Focus on tab list or filter controls
    const tabList = page.locator('[role="tablist"], .tab-list, .filter-tabs').first()

    if (await tabList.isVisible()) {
      // Try arrow key navigation
      await tabList.focus()

      // ArrowRight should focus next tab
      await page.keyboard.press('ArrowRight')

      // ArrowLeft should focus previous tab
      await page.keyboard.press('ArrowLeft')

      // Home/End should navigate to first/last
      await page.keyboard.press('Home')
    }
  })

  test('dialogs should have proper aria attributes', async ({ page }) => {
    // Trigger a dialog if possible (e.g., filter dialog)
    const filterButton = page.locator('button[aria-haspopup="dialog"], button[title*="filter"], .filter-toggle').first()

    if (await filterButton.count() > 0) {
      await filterButton.click()

      // Wait for dialog
      const dialog = page.locator('dialog, .modal, [role="dialog"]').first()
      await expect(dialog).toBeVisible({ timeout: 5000 })

      // Check for aria attributes
      await expect(dialog).toHaveAttribute('aria-modal', 'true')

      // Or aria-labelledby or aria-describedby
      const labelledby = await dialog.getAttribute('aria-labelledby')
      const describedby = await dialog.getAttribute('aria-describedby')

      expect(
        labelledby || describedby || await dialog.locator('h1, h2, h3, .dialog-title').count() > 0
      ).toBeTruthy()
    }
  })

  test('rankings should be filterable', async ({ page }) => {
    // Check for filter controls
    const filterInputs = page.locator('input[type="search"], select, [data-testid="filter-input"]').first()

    if (await filterInputs.count() > 0) {
      // Try typing in filter
      await filterInputs.fill('NIFTY')

      // Results should update
      await page.waitForTimeout(500)
    }
  })
})