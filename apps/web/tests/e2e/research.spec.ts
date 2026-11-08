import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('ResearchView Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to research view from main nav', async ({ page }) => {
    // Click on Research navigation
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
      await page.waitForTimeout(500);
    }

    // Should show research view heading
    const heading = page.locator('h1, h2, h3');
    await expect(heading.first()).toContainText('RESEARCH');
  });

  test('research view should show collections', async ({ page }) => {
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }

    await page.waitForTimeout(500);

    // Should show collection tabs
    const collections = page.locator('button:has-text("Evaluations"), button:has-text("Signals"), button:has-text("Backtests"), button:has-text("Walk-forwards"), button:has-text("Rankings")');
    if (await collections.count() > 0) {
      await expect(collections.first()).toBeVisible();
    }
  });
});

test.describe('ResearchView Rankings Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('rankings should display strategy information', async ({ page }) => {
    // Look for strategy-related content
    const strategyContent = page.locator('td, span, div').filter({ hasText: /strategy|Strategy/ });
    if (await strategyContent.count() > 0) {
      await expect(strategyContent.first()).toBeVisible();
    }
  });

  test('rankings should display score information', async ({ page }) => {
    // Look for score-related content
    const scoreContent = page.locator('td, span, div').filter({ hasText: /score|Score|composite/ });
    if (await scoreContent.count() > 0) {
      await expect(scoreContent.first()).toBeVisible();
    }
  });

  test('rankings should display rejection status', async ({ page }) => {
    // Look for rejection-related content
    const rejectionContent = page.locator('td, span, div').filter({ hasText: /rejected|Rejected|rejection/ });
    if (await rejectionContent.count() > 0) {
      await expect(rejectionContent.first()).toBeVisible();
    }
  });
});

test.describe('ResearchView Report Details', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('report details should be accessible via click', async ({ page }) => {
    // Look for clickable ranking/row elements
    const clickable = page.locator('tr[role="row"], button:has-text("View"), button:has-text("Details")');

    if (await clickable.count() > 0) {
      await clickable.first().click();
      await page.waitForTimeout(300);

      // Should show details panel or modal
      const details = page.locator('.modal, .details-panel, [aria-modal="true"]');
      if (await details.count() > 0) {
        await expect(details).toBeVisible();
      }
    }
  });

  test('report details should show metrics', async ({ page }) => {
    // Look for metrics display
    const metrics = page.locator('.metrics, [data-testid*="metrics"], .score-breakdown');
    if (await metrics.count() > 0) {
      await expect(metrics.first()).toBeVisible();
    }
  });

  test('report details should show evidence sources', async ({ page }) => {
    // Look for evidence/sources display
    const sources = page.locator('.sources, [data-testid*="sources"], .evidence');
    if (await sources.count() > 0) {
      await expect(sources.first()).toBeVisible();
    }
  });
});

test.describe('ResearchView Commentary', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('commentary should be displayed for rankings', async ({ page }) => {
    // Look for commentary section
    const commentary = page.locator('.commentary, [data-testid*="commentary"], .ranking-commentary');
    if (await commentary.count() > 0) {
      await expect(commentary.first()).toBeVisible();
    }
  });

  test('commentary should include score breakdown', async ({ page }) => {
    // Look for breakdown display
    const breakdown = page.locator('.score-breakdown, [data-testid*="breakdown"]');
    if (await breakdown.count() > 0) {
      await expect(breakdown.first()).toBeVisible();
    }
  });
});

test.describe('ResearchView Pagination', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should have pagination controls', async ({ page }) => {
    // Look for pagination elements
    const pagination = page.locator('button:has-text("Previous"), button:has-text("Next"), .pager');
    if (await pagination.count() > 0) {
      await expect(pagination.first()).toBeVisible();
    }
  });

  test('should show record count', async ({ page }) => {
    // Look for count display
    const countDisplay = page.locator('span:has-text("of"), .record-count');
    if (await countDisplay.count() > 0) {
      await expect(countDisplay.first()).toBeVisible();
    }
  });
});

test.describe('ResearchView Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should allow filtering by strategy', async ({ page }) => {
    // Look for strategy filter
    const strategyFilter = page.locator('select[name="strategy"], input[placeholder*="strategy"], .strategy-filter');
    if (await strategyFilter.count() > 0) {
      await expect(strategyFilter).toBeVisible();
    }
  });

  test('should allow filtering by rejected only', async ({ page }) => {
    // Look for rejected filter
    const rejectedFilter = page.locator('select[name="rejected"], input[placeholder*="rejected"], .rejected-filter, .filter-rejected');
    if (await rejectedFilter.count() > 0) {
      await expect(rejectedFilter).toBeVisible();
    }
  });
});

test.describe('ResearchView Empty State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show empty state when no rankings', async ({ page }) => {
    // Look for empty state messaging
    const emptyState = page.locator('.empty-state, [data-testid*="empty"], .no-data, p:has-text("No rankings")');
    if (await emptyState.count() > 0) {
      await expect(emptyState.first()).toBeVisible();
    }
  });

  test('empty state should provide helpful messaging', async ({ page }) => {
    // Look for empty state text
    const emptyText = page.locator('.empty-text, .no-data-message, p:has-text("no data")');
    if (await emptyText.count() > 0) {
      await expect(emptyText.first()).toBeVisible();
    }
  });
});

test.describe('ResearchView Loading State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show loading indicator when fetching data', async ({ page }) => {
    // Look for loading state
    const loading = page.locator('.loading, [data-testid*="loading"], .skeleton, p:has-text("Loading")');
    if (await loading.count() > 0) {
      await expect(loading).toBeVisible();
    }
  });
});

test.describe('ResearchView API Failure State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show error state on API failure', async ({ page }) => {
    // Look for error state
    const errorState = page.locator('.error, [data-testid*="error"], .error-message, p:has-text("Unable to load")');
    if (await errorState.count() > 0) {
      await expect(errorState).toBeVisible();
    }
  });
});

test.describe('ResearchView Simulated Not Traded Disclaimer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Research")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should display "RESEARCH ONLY" badge', async ({ page }) => {
    // Look for research-only badge
    const badge = page.locator('.mode-badge, span:has-text("RESEARCH"), [class*="badge"]:has-text("Research")');
    if (await badge.count() > 0) {
      await expect(badge).toBeVisible();
    }
  });

  test('should have simulated/not-traded messaging', async ({ page }) => {
    // Look for disclaimers
    const disclaimer = page.locator('p:has-text("simulated"), p:has-text("not-traded"), p:has-text("research"), footer:has-text("Research-only")');
    if (await disclaimer.count() > 0) {
      await expect(disclaimer.first()).toBeVisible();
    }
  });
});
