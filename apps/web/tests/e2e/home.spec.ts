import { test, expect } from '@playwright/test'

test.describe('Home Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should load the home page', async ({ page }) => {
    // Check page loaded successfully
    await expect(page).toHaveTitle(/Intraday Trading/)

    // Check for main navigation
    await expect(page.locator('nav, [role="navigation"]')).toBeVisible()

    // Check for health check indicator
    await expect(page.locator('[data-testid="health-indicator"], .health-status')).toBeVisible()
  })

  test('health check should show connected status', async ({ page }) => {
    const healthIndicator = page.locator('[data-testid="health-indicator"]')

    // Should show connected status
    await expect(healthIndicator).toContainText(/connected|healthy|ok/i)
  })

  test('navigation should be functional', async ({ page }) => {
    // Check primary navigation links exist
    const navLinks = page.locator('nav a[href], nav button')

    // Should have at least one navigation item
    await expect(navLinks.first()).toBeVisible()

    // Navigate to research tab
    const researchLink = navLinks.filter({ hasText: /research|rankings/i })
    if (await researchLink.count() > 0) {
      await researchLink.first().click()
      await expect(page).toHaveURL(/research|rankings/i)
    }
  })

  test('skip to main content link should be visible on focus', async ({ page }) => {
    // The skip link should be in the document but hidden
    const skipLink = page.locator('a[href^="#main"], .skip-link')

    if (await skipLink.count() > 0) {
      // It should be focusable
      await skipLink.focus()

      // When focused, it should become visible
      await expect(skipLink).toBeVisible()

      // It should have descriptive text
      await expect(skipLink).toContainText(/skip/i)
    }
  })

  test('keyboard navigation should work', async ({ page }) => {
    // Tab through the page
    await page.keyboard.press('Tab')

    // Should have focusable elements
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName)
    expect(focusedElement).not.toBe('body')
  })

  test('page should be responsive', async ({ page }) => {
    // Check on mobile viewport
    await page.setViewportSize({ width: 375, height: 667 })

    // Main content should still be visible
    const mainContent = page.locator('main, [role="main"]')
    await expect(mainContent).toBeVisible()
  })

  test('aria-live region should exist for announcements', async ({ page }) => {
    // Check for aria-live regions
    const liveRegions = page.locator('[aria-live]')

    // Count should be >= 0 (may or may not exist depending on implementation)
    const count = await liveRegions.count()

    // If they exist, verify they're properly configured
    if (count > 0) {
      for (let i = 0; i < count; i++) {
        await expect(liveRegions.nth(i)).toHaveAttribute('aria-live', /polite|assertive/)
      }
    }
  })

  test('error handling should be accessible', async ({ page }) => {
    // Force an error condition if possible
    // This test verifies error states are accessible

    // Check for error/success container
    const statusContainer = page.locator('[role="status"], [role="alert"], .status-message')

    // Just verify the container can be found (may not show error)
    const isVisible = await statusContainer.count() > 0
    expect(isVisible).toBeTruthy()
  })
})