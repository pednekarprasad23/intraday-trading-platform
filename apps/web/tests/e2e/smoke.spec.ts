import { test, expect } from '@playwright/test';

test.describe('Intraday Trading Platform Smoke Test', () => {
  test('Application loads and renders main views', async ({ page }) => {
    await page.goto('/');

    await expect(page.locator('body')).toBeVisible();
    await expect(page.locator('header, .topbar').first()).toBeVisible();
    await expect(page.locator('aside, nav').first()).toBeVisible();
  });

  test('Responsive viewport check (Mobile)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    await expect(page.locator('body')).toBeVisible();
  });
});
