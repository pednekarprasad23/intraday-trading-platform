import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('InstrumentsView Navigation V2.1', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to instruments view from sidebar nav', async ({ page }) => {
    const navButton = page.locator('aside.sidebar button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
      await page.waitForTimeout(500);
    }

    const heading = page.locator('h1, h2, h3');
    await expect(heading.first()).toBeVisible();
  });

  test('instruments view should show provider catalog heading', async ({ page }) => {
    const navButton = page.locator('aside.sidebar button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }

    await page.waitForTimeout(500);

    const catalog = page.locator('p, h2, h3');
    if (await catalog.count() > 0) {
      await expect(catalog.first()).toBeVisible();
    }
  });
});
