import { test, expect } from '@playwright/test';

const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Risk Operations V2.5', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to Risk & Controls view and display Risk Operations Console', async ({ page }) => {
    const riskNav = page.locator('button', { hasText: 'Risk & Controls' }).first();
    await riskNav.click();
    await expect(page.locator('h2', { hasText: 'Risk Operations Console' })).toBeVisible();

    await expect(page.locator('main').getByText('Execution Mode')).toBeVisible();
    await expect(page.locator('text=PAPER / SIMULATION')).toBeVisible();
    await expect(page.locator('text=Available Capital')).toBeVisible();
    await expect(page.locator('text=Kill Switch State & Audit')).toBeVisible();
  });

  test('should open kill switch trigger modal on emergency button click', async ({ page }) => {
    const riskNav = page.locator('button', { hasText: 'Risk & Controls' }).first();
    await riskNav.click();
    await expect(page.locator('h2', { hasText: 'Risk Operations Console' })).toBeVisible();

    const triggerBtn = page.locator('button', { hasText: 'Trigger Emergency Kill Switch' });
    if (await triggerBtn.count() > 0) {
      await triggerBtn.click();
      await expect(page.locator('h3', { hasText: 'Trigger Emergency Kill Switch' })).toBeVisible();
      await page.locator('button', { hasText: 'Cancel' }).click();
    }
  });

  test('should be responsive across viewports', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    const toggleButton = page.locator('.mobile-nav > button');
    await toggleButton.click();

    const riskNav = page.locator('#mobile-menu button', { hasText: 'Risk & Controls' });
    await riskNav.click();
    await expect(page.locator('h2', { hasText: 'Risk Operations Console' })).toBeVisible();
  });
});
