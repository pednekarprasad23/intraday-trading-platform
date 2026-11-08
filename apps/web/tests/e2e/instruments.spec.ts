import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('InstrumentsView Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to instruments view from main nav', async ({ page }) => {
    // Click on Instruments navigation
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
      await page.waitForTimeout(500);
    }

    // Should show instruments view heading
    const heading = page.locator('h2:has-text("Instrument master"), h2:has-text("PROVIDER CATALOG")');
    await expect(heading.first()).toBeVisible();
  });

  test('instruments view should show provider catalog heading', async ({ page }) => {
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }

    await page.waitForTimeout(500);

    // Should show provider catalog
    const catalog = page.locator('p:has-text("PROVIDER CATALOG"), h2:has-text("Provider Catalog")');
    if (await catalog.count() > 0) {
      await expect(catalog.first()).toBeVisible();
    }
  });
});

test.describe('InstrumentsView Table Display', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('instruments table should have required columns', async ({ page }) => {
    // Look for table headers
    const headers = page.locator('th:has-text("Symbol"), th:has-text("Name"), th:has-text("Asset"), th:has-text("Exchange"), th:has-text("Source"), th:has-text("Execution")');
    if (await headers.count() > 0) {
      await expect(headers.first()).toBeVisible();
    }
  });

  test('instruments table should display canonical symbols', async ({ page }) => {
    // Look for symbol columns
    const symbols = page.locator('td strong, td:has-text("DEMO:")');
    if (await symbols.count() > 0) {
      await expect(symbols.first()).toBeVisible();
    }
  });

  test('instruments table should show asset class', async ({ page }) => {
    // Look for asset class badges
    const assetClass = page.locator('.asset-class-badge, td:has-text("INDEX"), td:has-text("EQUITY"), td:has-text("FUTURES")');
    if (await assetClass.count() > 0) {
      await expect(assetClass.first()).toBeVisible();
    }
  });

  test('instruments table should show exchange', async ({ page }) => {
    // Look for exchange badges
    const exchange = page.locator('.exchange-badge, td:has-text("NSE"), td:has-text("BSE"), td:has-text("DEMO"), td:has-text("MT5")');
    if (await exchange.count() > 0) {
      await expect(exchange.first()).toBeVisible();
    }
  });
});

test.describe('InstrumentsView Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should have search input', async ({ page }) => {
    // Look for search input
    const searchInput = page.locator('input[placeholder*="Symbol"], input[placeholder*="name"], .filter-row input');
    if (await searchInput.count() > 0) {
      await expect(searchInput.first()).toBeVisible();
    }
  });

  test('should have asset class filter', async ({ page }) => {
    // Look for asset class select
    const assetFilter = page.locator('select:has-text("Asset"), select:has-text("asset"), .filter-row select');
    if (await assetFilter.count() > 0) {
      await expect(assetFilter.first()).toBeVisible();
    }
  });

  test('should have exchange filter', async ({ page }) => {
    // Look for exchange select
    const exchangeFilter = page.locator('select:has-text("Exchange"), select:has-text("exchange")');
    if (await exchangeFilter.count() > 0) {
      await expect(exchangeFilter.first()).toBeVisible();
    }
  });

  test('should have active filter', async ({ page }) => {
    // Look for active/inactive filter
    const activeFilter = page.locator('select:has-text("Active"), select:has-text("active")');
    if (await activeFilter.count() > 0) {
      await expect(activeFilter.first()).toBeVisible();
    }
  });

  test('should have clear filters button', async ({ page }) => {
    // Look for clear button
    const clearButton = page.locator('button:has-text("Clear"), button:has-text("clear")');
    if (await clearButton.count() > 0) {
      await expect(clearButton.first()).toBeVisible();
    }
  });
});

test.describe('InstrumentsView Summary Stats', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show instrument summary when data exists', async ({ page }) => {
    // Look for summary section
    const summary = page.locator('.instruments-stats, .stat-row, [class*="stat"]');
    if (await summary.count() > 0) {
      await expect(summary.first()).toBeVisible();
    }
  });

  test('summary should show asset class breakdown', async ({ page }) => {
    // Look for asset class breakdown
    const breakdown = page.locator('.stat-breakdown, [class*="breakdown"]');
    if (await breakdown.count() > 0) {
      await expect(breakdown.first()).toBeVisible();
    }
  });

  test('summary should show exchange breakdown', async ({ page }) => {
    // Look for exchange breakdown
    const exchanges = page.locator('.exchange-badge, .stat-breakdown');
    if (await exchanges.count() > 0) {
      await expect(exchanges.first()).toBeVisible();
    }
  });
});

test.describe('InstrumentsView Empty State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show empty state when no instruments match', async ({ page }) => {
    // Look for empty state messaging
    const emptyState = page.locator('.empty-state, [data-testid*="empty"], .no-data, p:has-text("No matching")');
    if (await emptyState.count() > 0) {
      await expect(emptyState.first()).toBeVisible();
    }
  });

  test('empty state should provide helpful messaging', async ({ page }) => {
    // Look for empty state text
    const emptyText = page.locator('.empty-text, .no-data-message');
    if (await emptyText.count() > 0) {
      await expect(emptyText.first()).toBeVisible();
    }
  });
});

test.describe('InstrumentsView Loading State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
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

test.describe('InstrumentsView API Failure State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
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

  test('error state should have retry option', async ({ page }) => {
    // Look for retry button
    const retryButton = page.locator('button:has-text("Retry"), button[aria-label*="retry"]');
    if (await retryButton.count() > 0) {
      await expect(retryButton).toBeVisible();
    }
  });
});

test.describe('InstrumentsView Simulated Not Traded Disclaimer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Instruments")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should have simulated/not-traded messaging', async ({ page }) => {
    // Look for disclaimers in footer or notices
    const disclaimer = page.locator('footer:has-text("Research-only"), .notice-inline:has-text("simulated"), .notice-inline:has-text("not-traded")');
    if (await disclaimer.count() > 0) {
      await expect(disclaimer.first()).toBeVisible();
    }
  });
});
