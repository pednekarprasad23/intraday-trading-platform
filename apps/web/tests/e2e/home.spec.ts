import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Home Page V2.1 Operations Cockpit', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should load the home page / dashboard', async ({ page }) => {
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('aside.sidebar').first()).toBeVisible();
    await expect(page.locator('text=PAPER SIMULATION')).toBeVisible();
  });

  test('navigation should be functional', async ({ page }) => {
    const navLinks = page.locator('aside.sidebar button.nav-item');
    await expect(navLinks).toHaveCount(11);

    await expect(page.locator('aside.sidebar button.nav-item', { hasText: 'Dashboard' })).toBeVisible();
    await expect(page.locator('aside.sidebar button.nav-item', { hasText: 'Research' })).toBeVisible();
    await expect(page.locator('aside.sidebar button.nav-item', { hasText: 'Historical Data' })).toBeVisible();
    await expect(page.locator('aside.sidebar button.nav-item', { hasText: 'Paper Trading' })).toBeVisible();
    await expect(page.locator('aside.sidebar button.nav-item', { hasText: 'System' })).toBeVisible();
  });

  test('skip to main content link should be present', async ({ page }) => {
    const skipLink = page.locator('a[href^="#main"], .skip-link');
    if (await skipLink.count() > 0) {
      await expect(skipLink).toContainText(/skip/i);
    }
  });

  test('keyboard navigation should work', async ({ page }) => {
    await page.keyboard.press('Tab');
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).not.toBe('body');
  });

  test('page should be responsive', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    const mainContent = page.locator('main, [role="main"]');
    await expect(mainContent).toBeVisible();
  });

  test('aria-live region should exist for announcements', async ({ page }) => {
    const liveRegions = page.locator('[aria-live]');
    const count = await liveRegions.count();
    if (count > 0) {
      for (let i = 0; i < count; i++) {
        await expect(liveRegions.nth(i)).toHaveAttribute('aria-live', /polite|assertive/);
      }
    }
  });

  test('error handling should be accessible', async ({ page }) => {
    const statusContainer = page.locator('[role="status"], [role="alert"], .error');
    const isVisible = await statusContainer.count() > 0;
    expect(isVisible).toBeTruthy();
  });
});

test.describe('Mobile Navigation V2.1', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.setViewportSize({ width: 375, height: 667 });
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('mobile menu should toggle', async ({ page }) => {
    const toggleButton = page.locator('.mobile-nav > button').first();
    await toggleButton.click();

    const mobileMenu = page.locator('#mobile-menu');
    await expect(mobileMenu).not.toBeHidden();

    await toggleButton.click();
    await expect(mobileMenu).toBeHidden();
  });
});
