import { test, expect } from '@playwright/test';

const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Orders & Signals V2.3 Observability', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to orders and signals views from sidebar', async ({ page }) => {
    const ordersNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Orders & Lifecycle' });
    await ordersNav.click();
    await expect(page.locator('h2', { hasText: 'Orders & Execution Lifecycle' })).toBeVisible();

    const signalsNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Signals Stream' });
    await signalsNav.click();
    await expect(page.locator('h2', { hasText: 'Research Signals Stream' })).toBeVisible();
  });

  test('should support filtering and order inspection', async ({ page }) => {
    const ordersNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Orders & Lifecycle' });
    await ordersNav.click();
    await expect(page.locator('h2', { hasText: 'Orders & Execution Lifecycle' })).toBeVisible();

    const stateSelect = page.locator('select');
    await expect(stateSelect).toBeVisible();
    await stateSelect.selectOption('filled');
  });

  test('should be responsive across viewports', async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    const ordersNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Orders & Lifecycle' });
    await ordersNav.click();
    await expect(page.locator('h2', { hasText: 'Orders & Execution Lifecycle' })).toBeVisible();

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator('h2', { hasText: 'Orders & Execution Lifecycle' })).toBeVisible();
  });
});
