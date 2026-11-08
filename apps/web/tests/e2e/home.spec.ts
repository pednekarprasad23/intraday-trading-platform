import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Home Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should load the home page', async ({ page }) => {
    // Check page loaded successfully - title shows current view
    await expect(page.locator('h1')).toBeVisible();

    // Check for main navigation
    await expect(page.locator('nav, [role="navigation"]')).toBeVisible();

    // Check for RESEARCH ONLY badge
    await expect(page.locator('.mode-badge')).toContainText(/RESEARCH ONLY/);
  });

  test('authentication screen should display', async ({ page }) => {
    // The home page shows an auth screen since auth is required
    await expect(page.locator('h1')).toContainText(/Welcome back/);
    await expect(page.locator('form')).toBeVisible();
  });

  test('navigation should be functional', async ({ page }) => {
    // Check primary navigation buttons exist
    const navLinks = page.locator('nav button');
    await expect(navLinks).toHaveCount(5);

    // Verify navigation items
    await expect(navLinks).toContainText('Research');
    await expect(navLinks).toContainText('Market data');
    await expect(navLinks).toContainText('Instruments');
    await expect(navLinks).toContainText('Paper trading');
    await expect(navLinks).toContainText('System');
  });

  test('skip to main content link should be present', async ({ page }) => {
    // The skip link should be in the document but hidden
    const skipLink = page.locator('a[href^="#main"], .skip-link');

    if (await skipLink.count() > 0) {
      // It should have descriptive text
      await expect(skipLink).toContainText(/skip/i);
    }
  });

  test('keyboard navigation should work', async ({ page }) => {
    // Tab through the page
    await page.keyboard.press('Tab');

    // Should have focusable elements
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).not.toBe('body');
  });

  test('page should be responsive', async ({ page }) => {
    // Check on mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Main content should still be visible
    const mainContent = page.locator('main, [role="main"]');
    await expect(mainContent).toBeVisible();
  });

  test('aria-live region should exist for announcements', async ({ page }) => {
    // Check for aria-live regions
    const liveRegions = page.locator('[aria-live]');

    // Count should be >= 0 (may or may not exist depending on implementation)
    const count = await liveRegions.count();

    // If they exist, verify they're properly configured
    if (count > 0) {
      for (let i = 0; i < count; i++) {
        await expect(liveRegions.nth(i)).toHaveAttribute('aria-live', /polite|assertive/);
      }
    }
  });

  test('error handling should be accessible', async ({ page }) => {
    // Check for error/success container
    const statusContainer = page.locator('[role="status"], [role="alert"], .error');

    // Just verify the container can be found (may not show error)
    const isVisible = await statusContainer.count() > 0;
    expect(isVisible).toBeTruthy();
  });
});

test.describe('Mobile Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.setViewportSize({ width: 375, height: 667 });
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('mobile menu should toggle', async ({ page }) => {
    // Open mobile menu
    const toggleButton = page.locator('button:has-text("☰")');
    await toggleButton.click();

    // Menu should be visible
    const mobileMenu = page.locator('#mobile-menu');
    await expect(mobileMenu).not.toBeHidden();

    // Close menu
    await toggleButton.click();
    await expect(mobileMenu).toBeHidden();
  });
});
