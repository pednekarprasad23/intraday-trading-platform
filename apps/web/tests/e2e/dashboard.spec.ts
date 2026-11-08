import { test, expect } from '@playwright/test';

const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Dashboard V2.2 Command & Control', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should render command dashboard landing with summary KPIs and project cards', async ({ page }) => {
    await expect(page.locator('h2', { hasText: 'Command & Control Operations Dashboard' })).toBeVisible();
    await expect(page.locator('text=Summary Key Performance Indicators')).toBeVisible();
    await expect(page.locator('text=Project & Strategy Operating Cards')).toBeVisible();
    await expect(page.locator('text=Daily XAU Momentum')).toBeVisible();
    await expect(page.locator('text=XAUUSD Pullback Strategy')).toBeVisible();
    await expect(page.locator('text=NIFTY F&O Intraday Breakout')).toBeVisible();
  });

  test('should display recent activity and open positions sections', async ({ page }) => {
    await expect(page.locator('text=Open Positions')).toBeVisible();
    await expect(page.locator('text=Recent Activity & Orders')).toBeVisible();
  });

  test('should be responsive across multiple viewports', async ({ page }) => {
    // 1920x1080
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect(page.locator('h2', { hasText: 'Command & Control Operations Dashboard' })).toBeVisible();

    // 1366x768
    await page.setViewportSize({ width: 1366, height: 768 });
    await expect(page.locator('h2', { hasText: 'Command & Control Operations Dashboard' })).toBeVisible();

    // 390x844 (Mobile)
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.locator('h2', { hasText: 'Command & Control Operations Dashboard' })).toBeVisible();
  });

  test('should allow navigation from command dashboard to paper trading and back', async ({ page }) => {
    const paperNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Paper Trading' });
    await paperNav.click();
    await expect(page.locator('h1, h2, h3', { hasText: /Paper|Simulated/i }).first()).toBeVisible();

    const dashboardNav = page.locator('aside.sidebar button.nav-item', { hasText: 'Dashboard' });
    await dashboardNav.click();
    await expect(page.locator('h2', { hasText: 'Command & Control Operations Dashboard' })).toBeVisible();
  });
});
