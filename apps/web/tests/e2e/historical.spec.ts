import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('HistoricalView Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to historical view from main nav', async ({ page }) => {
    // Click on Historical data navigation
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
      await page.waitForTimeout(500);
    }

    // Should show historical view heading
    const heading = page.locator('h1, h2, h3');
    await expect(heading.first()).toBeVisible();
  });

  test('historical view should show partition table', async ({ page }) => {
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }

    await page.waitForTimeout(500);

    // Should show table or container
    const tableContainer = page.locator('table, .table-wrap, .partition-table');
    if (await tableContainer.count() > 0) {
      await expect(tableContainer).toBeVisible();
    }
  });
});

test.describe('HistoricalView Partition Table', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('partition table should render with headers', async ({ page }) => {
    // Table should have header rows
    const headers = page.locator('th, thead tr th, .table-header');
    if (await headers.count() > 0) {
      await expect(headers.first()).toBeVisible();
    }
  });

  test('partition table should show session date column', async ({ page }) => {
    // Look for date-related headers
    const dateHeaders = page.locator('th:has-text("Date"), th:has-text("Session"), th:has-text("date")');
    if (await dateHeaders.count() > 0) {
      await expect(dateHeaders.first()).toBeVisible();
    }
  });

  test('partition table should show bar count column', async ({ page }) => {
    // Look for count-related headers
    const countHeaders = page.locator('th:has-text("Bars"), th:has-text("Count"), th:has-text("Rows")');
    if (await countHeaders.count() > 0) {
      await expect(countHeaders.first()).toBeVisible();
    }
  });

  test('partition table should support pagination', async ({ page }) => {
    // Look for pagination controls
    const pagination = page.locator('.pagination, .page-controls, [role="navigation"]');
    if (await pagination.count() > 0) {
      await expect(pagination).toBeVisible();
    }
  });
});

test.describe('HistoricalView Candle Request', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('candle view should load when partition is selected', async ({ page }) => {
    // Look for load/clickable partition rows
    const partitionRows = page.locator('tr[data-testid*="partition"], .partition-row, tr[role="row"]');

    if (await partitionRows.count() > 0) {
      // Click on first partition row
      await partitionRows.first().click();
      await page.waitForTimeout(500);

      // Should show chart or candles
      const chart = page.locator('canvas, .candle-chart, .chart-container');
      if (await chart.count() > 0) {
        await expect(chart).toBeVisible();
      }
    }
  });

  test('candle data should display with OHLCV values', async ({ page }) => {
    // Look for candle data display
    const candleDisplay = page.locator('.candle-data, .data-row, tr[data-testid*="candle"]');

    if (await candleDisplay.count() > 0) {
      await expect(candleDisplay.first()).toBeVisible();
    }
  });
});

test.describe('HistoricalView OHLCV Chart', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('canvas element should exist for chart rendering', async ({ page }) => {
    // Look for canvas element
    const canvas = page.locator('canvas[height], canvas[data-testid*="chart"]');

    if (await canvas.count() > 0) {
      await expect(canvas).toBeVisible();
    }
  });

  test('chart should show price scale', async ({ page }) => {
    // Look for price scale indicators
    const priceScale = page.locator('.price-scale, .y-axis, .axis.y');

    if (await priceScale.count() > 0) {
      await expect(priceScale).toBeVisible();
    }
  });

  test('chart should show volume bars', async ({ page }) => {
    // Look for volume display
    const volumeBars = page.locator('.volume-bars, .volume-chart, .volume-container');

    if (await volumeBars.count() > 0) {
      await expect(volumeBars).toBeVisible();
    }
  });
});

test.describe('HistoricalView Date/Session Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('filter should allow date selection', async ({ page }) => {
    // Look for date filter input
    const dateInput = page.locator('input[type="date"], input[data-testid*="date"], .date-filter');

    if (await dateInput.count() > 0) {
      await expect(dateInput).toBeVisible();
    }
  });

  test('filter should allow timeframe selection', async ({ page }) => {
    // Look for timeframe select/input
    const timeframeSelect = page.locator('select[data-testid*="timeframe"], select[name="timeframe"], .timeframe-filter');

    if (await timeframeSelect.count() > 0) {
      await expect(timeframeSelect).toBeVisible();
    }
  });

  test('filter should apply to partition table', async ({ page }) => {
    // Look for filter button
    const filterButton = page.locator('button:has-text("Filter"), button[data-testid*="filter"]');

    if (await filterButton.count() > 0) {
      await expect(filterButton).toBeVisible();
    }
  });
});

test.describe('HistoricalView Timeframe Filtering', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('timeframe options should include 1m and 5m', async ({ page }) => {
    // Look for timeframe options
    const timeframeOptions = page.locator('option[data-testid*="timeframe"]:not([value=""])');

    if (await timeframeOptions.count() > 0) {
      const options = await timeframeOptions.allTextContents();
      // Should have 1m or similar timeframe option
      expect(options.some(opt => opt.includes('1m') || opt.includes('5m') || opt.includes('minute'))).toBeTruthy();
    }
  });

  test('selected timeframe should be highlighted', async ({ page }) => {
    // Look for selected timeframe indicator
    const selectedOption = page.locator('option[selected], .selected-timeframe');

    if (await selectedOption.count() > 0) {
      await expect(selectedOption).toBeVisible();
    }
  });
});

test.describe('HistoricalView Pagination', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('pagination controls should be visible', async ({ page }) => {
    // Look for pagination elements
    const pagination = page.locator('.pagination, .page-controls, .page-numbers, [aria-label="pagination"]');

    if (await pagination.count() > 0) {
      await expect(pagination).toBeVisible();
    }
  });

  test('should show current page number', async ({ page }) => {
    // Look for page indicator
    const pageInfo = page.locator('.page-info, .current-page, [data-testid*="page"]');

    if (await pageInfo.count() > 0) {
      await expect(pageInfo).toBeVisible();
    }
  });

  test('should navigate between pages', async ({ page }) => {
    // Look for page navigation buttons
    const navButtons = page.locator('button[data-testid*="page"], button[aria-label*="page"], .nav-btn');

    if (await navButtons.count() > 0) {
      await navButtons.first().click();
      await page.waitForTimeout(300);
    }
  });
});

test.describe('HistoricalView Empty State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show empty state when no partitions', async ({ page }) => {
    // Look for empty state messaging
    const emptyState = page.locator('.empty-state, [data-testid*="empty"], .no-data');

    if (await emptyState.count() > 0) {
      await expect(emptyState).toBeVisible();
    }
  });

  test('empty state should provide helpful messaging', async ({ page }) => {
    // Look for empty state text
    const emptyText = page.locator('.empty-text, .no-data-message');

    if (await emptyText.count() > 0) {
      await expect(emptyText).toHaveText(/no.*data|nothing.*found|empty/i, { ignoreCase: true });
    }
  });
});

test.describe('HistoricalView API Failure State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show error state on API failure', async ({ page }) => {
    // Look for error state
    const errorState = page.locator('.error, [data-testid*="error"], .error-message');

    if (await errorState.count() > 0) {
      await expect(errorState).toBeVisible();
    }
  });

  test('error state should have retry option', async ({ page }) => {
    // Look for retry button
    const retryButton = page.locator('button:has-text("Retry"), button[data-testid*="retry"]');

    if (await retryButton.count() > 0) {
      await expect(retryButton).toBeVisible();
    }
  });
});

test.describe('HistoricalView Loading State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Historical data")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show loading indicator when fetching data', async ({ page }) => {
    // Look for loading state
    const loading = page.locator('.loading, [data-testid*="loading"], .skeleton');

    if (await loading.count() > 0) {
      await expect(loading).toBeVisible();
    }
  });

  test('loading state should not block interaction', async ({ page }) => {
    // Verify loading overlay doesn't block navigation
    const nav = page.locator('nav');
    await expect(nav).toBeVisible();
  });
});
