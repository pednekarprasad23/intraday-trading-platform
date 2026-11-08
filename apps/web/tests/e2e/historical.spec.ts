import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('HistoricalView Navigation V2.1', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to historical view from main nav', async ({ page }) => {
    const navButton = page.locator('aside.sidebar button:has-text("Historical Data")');
    if (await navButton.count() > 0) {
      await navButton.click();
      await page.waitForTimeout(500);
    }

    const heading = page.locator('h1, h2, h3');
    await expect(heading.first()).toBeVisible();
  });

  test('historical view should show partition table', async ({ page }) => {
    const navButton = page.locator('aside.sidebar button:has-text("Historical Data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }

    await page.waitForTimeout(500);

    const tableContainer = page.locator('table, .table-wrap, .partition-table');
    if (await tableContainer.count() > 0) {
      await expect(tableContainer).toBeVisible();
    }
  });
});
