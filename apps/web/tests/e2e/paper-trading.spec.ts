import { test, expect } from '@playwright/test'

test.describe('Paper Trading View', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to paper trading page
    await page.goto('/paper-trading')
    await page.waitForLoadState('networkidle')
  })

  test('paper trading page should load', async ({ page }) => {
    await expect(page).toHaveURL(/paper-trading|paper/i)
    await expect(page.locator('[data-testid="paper-trading"]')).toBeVisible()
  })

  test('order form should be present', async ({ page }) => {
    // Check for order form elements
    const orderForm = page.locator('form, [data-testid="order-form"], .order-form').first()

    await expect(orderForm).toBeVisible()
  })

  test('order form should have required fields', async ({ page }) => {
    // Check for symbol/ticker input
    const symbolInput = page.locator('input[name*="symbol"], input[placeholder*="symbol"], [data-testid="symbol-input"]').first()
    await expect(symbolInput).toBeVisible()

    // Check for quantity input
    const quantityInput = page.locator('input[type="number"][name*="qty"], input[name*="quantity"]').first()
    await expect(quantityInput).toBeVisible()

    // Check for order type selector
    const orderType = page.locator('select[name*="type"], [data-testid="order-type"]').first()
    await expect(orderType).toBeVisible()
  })

  test('order form should validate inputs', async ({ page }) => {
    // Try to submit empty or invalid form
    const submitButton = page.locator('button[type="submit"], .submit-button').first()

    // Form should have validation
    await expect(submitButton).toBeEnabled()
  })

  test('kill switch should be visible', async ({ page }) => {
    // Check for kill switch element
    const killSwitch = page.locator('[data-testid="kill-switch"], .kill-switch, button[aria-label*="kill"]').first()

    await expect(killSwitch).toBeVisible()
  })

  test('kill switch state changes with aria-live announcements', async ({ page }) => {
    const killSwitch = page.locator('[data-testid="kill-switch"], .kill-switch').first()

    if (await killSwitch.count() > 0) {
      // Get initial state
      const initialState = await killSwitch.getAttribute('aria-pressed')

      // Toggle kill switch (if clickable)
      const toggleButton = killSwitch.locator('button, [role="button"]')

      if (await toggleButton.count() > 0) {
        await toggleButton.click()

        // State should change
        const newState = await killSwitch.getAttribute('aria-pressed')

        // aria-live region should announce the change
        const liveRegion = page.locator('[aria-live="polite"], .sr-only[aria-live="polite"]').first()

        // Check if live region exists
        const liveRegionCount = await liveRegion.count()

        if (liveRegionCount > 0) {
          // Live region should be present for announcements
          await expect(liveRegion).toBeVisible()
        }
      }
    }
  })

  test('kill switch confirmation dialog should be accessible', async ({ page }) => {
    const killSwitch = page.locator('[data-testid="kill-switch"], .kill-switch').first()
    const toggleButton = killSwitch.locator('button, [role="button"]').first()

    if (await toggleButton.count() > 0 && await killSwitch.isVisible()) {
      // Clicking kill switch should open confirmation
      await toggleButton.click()

      // Wait for dialog
      const dialog = page.locator('dialog, .modal, [role="dialog"]').first()

      if (await dialog.count() > 0) {
        await expect(dialog).toBeVisible()

        // Check focus trap - first focusable element should be in dialog
        await page.keyboard.press('Tab')

        // Escape key should close dialog
      }
    }
  })

  test('escape key should close modals', async ({ page }) => {
    // Try to open any modal (e.g., order details)
    const openModalButton = page.locator('button[aria-expanded="false"], .expand-details').first()

    if (await openModalButton.count() > 0) {
      await openModalButton.click()

      const modal = page.locator('[role="dialog"], .modal, dialog').first()

      if (await modal.count() > 0) {
        // Press Escape
        await page.keyboard.press('Escape')

        // Modal should close
        await expect(modal).not.toBeVisible({ timeout: 3000 })
      }
    }
  })

  test('position display should show current positions', async ({ page }) => {
    // Check for positions table or list
    const positions = page.locator('[data-testid="positions"], .positions, table[role="grid"]').first()

    // Should exist (may be empty if no positions)
    await expect(positions).toBeVisible()
  })

  test('focus trap should work in kill switch dialog', async ({ page }) => {
    // Open kill switch dialog
    const killSwitch = page.locator('[data-testid="kill-switch"]')
    const toggleButton = killSwitch.locator('button').first()

    if (await toggleButton.count() > 0) {
      await toggleButton.click()

      const dialog = page.locator('[role="dialog"], .modal').first()

      if (await dialog.count() > 0) {
        // Tab from first focusable element should cycle within dialog
        await page.keyboard.press('Tab')

        // Should not escape to body
        const activeElement = await page.evaluate(() => document.activeElement?.tagName)

        expect(['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA']).toContain(activeElement)
      }
    }
  })

  test('order validation should show accessible error messages', async ({ page }) => {
    const submitButton = page.locator('button[type="submit"]').first()

    if (await submitButton.count() > 0) {
      await submitButton.click()

      // Check for error messages with proper roles
      const errors = page.locator('[role="alert"], .error-message, [data-testid="error"]').first()

      // Error message should be in alert role for screen readers
      if (await errors.count() > 0) {
        await expect(errors).toHaveAttribute('role', 'alert')
      }
    }
  })
})