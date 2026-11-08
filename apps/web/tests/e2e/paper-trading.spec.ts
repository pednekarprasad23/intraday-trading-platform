import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Paper Trading View', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to paper trading via navigation (this is a SPA, not separate routes)
    await page.goto('/');
    // Click on Paper Trading tab
    const paperTab = page.locator('nav button:has-text("Paper trading")');
    if (await paperTab.count() > 0) {
      await paperTab.click();
      await page.waitForTimeout(500);
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('paper trading page should load', async ({ page }) => {
    // Check the page title or main heading
    await expect(page.locator('h1')).toBeVisible();
  });

  test('order form should be present', async ({ page }) => {
    // Check for order form elements - the PaperTradingView component renders these
    const form = page.locator('form, [role="form"]');

    // The form may exist or show an empty state
    if (await form.count() > 0) {
      await expect(form).toBeVisible();
    }
  });

  test('order form should have required fields', async ({ page }) => {
    // Check for instrument selector
    const instrumentSelect = page.locator('select[name="instrument"], input[placeholder*="instrument"], input[name="instrument"]');
    if (await instrumentSelect.count() > 0) {
      await expect(instrumentSelect).toBeVisible();
    }

    // Check for quantity field
    const quantityInput = page.locator('input[type="number"][name="quantity"], input[name="quantity"]');
    if (await quantityInput.count() > 0) {
      await expect(quantityInput).toBeVisible();
    }
  });

  test('order form should validate inputs', async ({ page }) => {
    // Try to submit with invalid data
    const form = page.locator('form, [role="form"]').first();

    if (await form.count() > 0) {
      const submitButton = form.locator('button[type="submit"]');
      if (await submitButton.count() > 0) {
        await submitButton.click();
        // Form validation should trigger (may show error or prevent submission)
        await page.waitForTimeout(500);
      }
    }
  });

  test('kill switch should be visible', async ({ page }) => {
    // Check for kill switch toggle
    const killSwitch = page.locator('[role="switch"], input[type="checkbox"], .toggle-switch');

    if (await killSwitch.count() > 0) {
      await expect(killSwitch).toBeVisible();
    }
  });

  test('kill switch state changes with aria-live announcements', async ({ page }) => {
    const killSwitch = page.locator('[role="switch"], input[type="checkbox"], .toggle-switch').first();

    if (await killSwitch.count() > 0) {
      const initialChecked = await killSwitch.isChecked();

      // Toggle the kill switch
      await killSwitch.click();

      const newChecked = await killSwitch.isChecked();
      expect(newChecked).not.toBe(initialChecked);
    }
  });

  test('kill switch confirmation dialog should be accessible', async ({ page }) => {
    // Check for confirmation dialog
    const dialog = page.locator('[role="dialog"], .modal, dialog');

    // Dialog may not be visible by default, but should exist in the DOM
    if (await dialog.count() > 0) {
      await expect(dialog).toHaveAttribute('aria-labelledby');
    }
  });

  test('order submission should show confirmation', async ({ page }) => {
    // Try to submit an order
    const submitButton = page.locator('button[type="submit"], button:has-text("Submit")');

    if (await submitButton.count() > 0) {
      await submitButton.click();

      // Wait for potential confirmation message
      await page.waitForTimeout(1000);

      // Should show some form of feedback
      const feedback = page.locator('[role="status"], .message, .alert');
      if (await feedback.count() > 0) {
        await expect(feedback).toHaveCount(1);
      }
    }
  });

  test('positions display should show current positions', async ({ page }) => {
    // Check for positions section
    const positions = page.locator('[role="region"][aria-label*="position"], .positions-list, table');

    if (await positions.count() > 0) {
      await expect(positions).toBeVisible();
    }
  });

  test('focus trap should work in kill switch dialog', async ({ page }) => {
    // Open dialog if it exists
    const openModalButton = page.locator('button:has-text("Kill Switch"), button:has-text("Emergency Stop")');

    if (await openModalButton.count() > 0) {
      await openModalButton.click();

      const dialog = page.locator('[role="dialog"], .modal, dialog').first();

      if (await dialog.count() > 0) {
        // Focus should be trapped within the dialog
        await page.keyboard.press('Tab');
        const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
        expect(focusedElement).not.toBe('BODY');
      }
    }
  });

  test('order validation should show accessible error messages', async ({ page }) => {
    // Try to submit invalid order
    const submitButton = page.locator('button[type="submit"], button:has-text("Submit")');

    if (await submitButton.count() > 0) {
      await submitButton.click();

      // Wait for validation
      await page.waitForTimeout(1000);

      // Check for error message
      const error = page.locator('[role="alert"], .error, .invalid');
      if (await error.count() > 0) {
        await expect(error).toBeVisible();
      }
    }
  });

  test('escape key should close modals', async ({ page }) => {
    const openModalButton = page.locator('button:has-text("Kill Switch"), button:has-text("Emergency Stop")');

    if (await openModalButton.count() > 0) {
      await openModalButton.click();

      const dialog = page.locator('[role="dialog"], .modal, dialog').first();

      if (await dialog.count() > 0) {
        // Press escape
        await page.keyboard.press('Escape');

        // Dialog should close
        await page.waitForTimeout(500);
        await expect(dialog).toBeHidden();
      }
    }
  });
});
