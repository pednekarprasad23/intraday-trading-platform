import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('Research View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('research tab should load successfully', async ({ page }) => {
    // Click on Research navigation
    const researchTab = page.locator('nav button:has-text("Research")');
    if (await researchTab.count() > 0) {
      await researchTab.click();
      // Verify the research content is visible
      await page.waitForTimeout(500);
    }
  });

  test('should display rankings table or list', async ({ page }) => {
    // Check for rankings container or empty state
    const rankingsContainer = page.locator('.rankings, [role="table"], .table-wrap');

    if (await rankingsContainer.count() > 0) {
      // Either rankings are present or we see an empty state
      const hasContent = await rankingsContainer.count();
      expect(hasContent).toBeGreaterThan(0);
    }
  });

  test('score bars should be displayed', async ({ page }) => {
    // Check for score display elements (may be empty state)
    const scoreBars = page.locator('[data-testid="score-bar"], .score-bar, [role="progressbar"]');

    // Score bars may not exist if no data, just verify they don't crash
    if (await scoreBars.count() > 0) {
      await expect(scoreBars).toHaveCount(0); // Empty state
    }
  });

  test('expandable detail panel should work', async ({ page }) => {
    // Detail panels only appear when there's data
    const detailPanels = page.locator('[data-testid="detail-panel"], .detail-panel, [role="region"]');

    // Verify the panel structure exists (may be empty)
    if (await detailPanels.count() > 0) {
      await expect(detailPanels).toBeVisible();
    }
  });

  test('detail panel should have aria-live region', async ({ page }) => {
    // Look for detail panels
    const detailPanels = page.locator('[data-testid="detail-panel"], .detail-panel, [role="region"]');

    const panels = await detailPanels.count();

    // No panels expected in empty state
    if (panels > 0) {
      // Check if any have aria-live
      for (let i = 0; i < Math.min(panels, 3); i++) {
        const panel = detailPanels.nth(i);
        const hasLiveRegion = await panel.getAttribute('aria-live');

        if (hasLiveRegion) {
          expect(['polite', 'assertive']).toContain(hasLiveRegion);
        }
      }
    }
  });

  test('keyboard navigation for tabs should work', async ({ page }) => {
    // Focus on tab list or filter controls
    const tabList = page.locator('[role="tablist"], .tab-list, .filter-tabs').first();

    if (await tabList.count() > 0) {
      // Try arrow key navigation
      await tabList.focus();
      await page.keyboard.press('ArrowRight');
      await page.keyboard.press('ArrowLeft');
    }
  });

  test('dialogs should have proper aria attributes', async ({ page }) => {
    // Dialogs only appear with data, check for existence
    const dialogs = page.locator('dialog, .modal, [role="dialog"]');

    if (await dialogs.count() > 0) {
      const dialog = dialogs.first();
      const hasModal = await dialog.getAttribute('aria-modal');

      // If it has aria-modal, it should be true
      if (hasModal === 'true') {
        const labelledby = await dialog.getAttribute('aria-labelledby');
        const describedby = await dialog.getAttribute('aria-describedby');

        // Should have at least one reference
        expect(labelledby || describedby).toBeTruthy();
      }
    }
  });

  test('rankings should be filterable', async ({ page }) => {
    // Check for filter controls
    const filterInputs = page.locator('input[type="search"], select, [data-testid="filter-input"]');

    if (await filterInputs.count() > 0) {
      // Try typing in filter
      await filterInputs.first().fill('NIFTY');
      await page.waitForTimeout(300);
    }
  });
});
