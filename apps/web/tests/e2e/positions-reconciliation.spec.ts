import { test, expect } from '@playwright/test';

const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Positions & Reconciliation V2.4', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to positions and reconciliation views from sidebar', async ({ page }) => {
    const positionsNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Positions' });
    await positionsNav.click();
    await expect(page.locator('h2', { hasText: 'Positions & P&L' })).toBeVisible();

    const reconcileNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Reconciliation' });
    await reconcileNav.click();
    await expect(page.locator('h2', { hasText: 'Reconciliation Console' })).toBeVisible();
  });

  test('should display correlation quality legend in reconciliation console', async ({ page }) => {
    const reconcileNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Reconciliation' });
    await reconcileNav.click();
    await expect(page.locator('h2', { hasText: 'Reconciliation Console' })).toBeVisible();

    await expect(page.locator('text=EXACT')).toBeVisible();
    await expect(page.locator('text=STRONG')).toBeVisible();
    await expect(page.locator('text=AMBIGUOUS')).toBeVisible();
  });
});
