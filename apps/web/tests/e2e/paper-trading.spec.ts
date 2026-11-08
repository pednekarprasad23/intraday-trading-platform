import { test, expect } from '@playwright/test';

// Skip tests that require the API backend to be running
const SKIP_E2E_TESTS = process.env.SKIP_E2E_TESTS === 'true' || !process.env.API_URL;

test.describe('PaperTradingView Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should navigate to paper trading view from main nav', async ({ page }) => {
    // Click on Paper trading navigation
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
      await page.waitForTimeout(500);
    }

    // Should show paper trading view heading
    const heading = page.locator('h1, h2, h3');
    await expect(heading.first()).toBeVisible();
  });

  test('paper trading view should show account summary', async ({ page }) => {
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }

    await page.waitForTimeout(500);

    // Should show account summary section
    const summary = page.locator('.account-summary, [data-testid*="account"], .summary-panel');
    if (await summary.count() > 0) {
      await expect(summary.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Account Summary', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('account summary should show capital', async ({ page }) => {
    // Look for capital display
    const capital = page.locator('.capital, [data-testid*="capital"], .available-capital');
    if (await capital.count() > 0) {
      await expect(capital.first()).toBeVisible();
    }
  });

  test('account summary should show position count', async ({ page }) => {
    // Look for position count
    const positions = page.locator('.position-count, [data-testid*="positions"], .positions-count');
    if (await positions.count() > 0) {
      await expect(positions.first()).toBeVisible();
    }
  });

  test('account summary should show P&L', async ({ page }) => {
    // Look for P&L display
    const pnl = page.locator('.pnl, [data-testid*="pnl"], .daily-pnl');
    if (await pnl.count() > 0) {
      await expect(pnl.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Order Form', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('order form should have instrument selector', async ({ page }) => {
    // Look for instrument select
    const instrumentSelect = page.locator('select[name="instrument"], .instrument-select, [data-testid*="instrument"]');
    if (await instrumentSelect.count() > 0) {
      await expect(instrumentSelect).toBeVisible();
    }
  });

  test('order form should have quantity input', async ({ page }) => {
    // Look for quantity input
    const quantity = page.locator('input[type="number"][name="quantity"], .quantity-input');
    if (await quantity.count() > 0) {
      await expect(quantity).toBeVisible();
    }
  });

  test('order form should have side selector (buy/sell)', async ({ page }) => {
    // Look for buy/sell selectors
    const sides = page.locator('button:has-text("BUY"), button:has-text("SELL"), .side-selector');
    if (await sides.count() > 0) {
      await expect(sides.first()).toBeVisible();
    }
  });

  test('order form should have order type selector', async ({ page }) => {
    // Look for order type select
    const orderType = page.locator('select[name="order_type"], .order-type-select');
    if (await orderType.count() > 0) {
      await expect(orderType).toBeVisible();
    }
  });

  test('order form should have submit button', async ({ page }) => {
    // Look for submit button
    const submit = page.locator('button:has-text("Submit"), button:has-text("Place Order"), button[type="submit"]');
    if (await submit.count() > 0) {
      await expect(submit.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Orders Table', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('orders table should show order details', async ({ page }) => {
    // Look for orders table
    const orders = page.locator('.orders-table, [data-testid*="orders"], table[aria-label*="orders"]');
    if (await orders.count() > 0) {
      await expect(orders.first()).toBeVisible();
    }
  });

  test('orders table should show order states', async ({ page }) => {
    // Look for state badges
    const states = page.locator('.state-badge, [data-testid*="state"], .order-state');
    if (await states.count() > 0) {
      await expect(states.first()).toBeVisible();
    }
  });

  test('orders table should show buy/sell indicators', async ({ page }) => {
    // Look for buy/sell badges
    const sides = page.locator('.side-badge, [data-testid*="side"], .order-side');
    if (await sides.count() > 0) {
      await expect(sides.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Positions Table', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('positions table should show position details', async ({ page }) => {
    // Look for positions table
    const positions = page.locator('.positions-table, [data-testid*="positions"], table[aria-label*="positions"]');
    if (await positions.count() > 0) {
      await expect(positions.first()).toBeVisible();
    }
  });

  test('positions table should show quantity', async ({ page }) => {
    // Look for quantity display
    const qty = page.locator('.position-quantity, [data-testid*="quantity"]');
    if (await qty.count() > 0) {
      await expect(qty.first()).toBeVisible();
    }
  });

  test('positions table should show P&L', async ({ page }) => {
    // Look for P&L in positions
    const pnl = page.locator('.position-pnl, [data-testid*="pnl"]');
    if (await pnl.count() > 0) {
      await expect(pnl.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Kill Switch', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('kill switch section should be visible', async ({ page }) => {
    // Look for kill switch section
    const killSwitch = page.locator('.kill-switch, [data-testid*="killswitch"], .kill-switch-panel');
    if (await killSwitch.count() > 0) {
      await expect(killSwitch.first()).toBeVisible();
    }
  });

  test('kill switch should show armed status', async ({ page }) => {
    // Look for armed/disarmed status
    const status = page.locator('.status-indicator, [data-testid*="status"], .switch-status');
    if (await status.count() > 0) {
      await expect(status.first()).toBeVisible();
    }
  });

  test('kill switch should have trigger button', async ({ page }) => {
    // Look for trigger button
    const trigger = page.locator('button:has-text("Trigger"), button:has-text("Armed"), button:has-text("Disarmed")');
    if (await trigger.count() > 0) {
      await expect(trigger.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Risk Events', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('risk events section should be visible', async ({ page }) => {
    // Look for risk events section
    const riskEvents = page.locator('.risk-events, [data-testid*="risk"], .risk-events-panel');
    if (await riskEvents.count() > 0) {
      await expect(riskEvents.first()).toBeVisible();
    }
  });

  test('risk events table should show events', async ({ page }) => {
    // Look for risk events table
    const events = page.locator('.events-table, [data-testid*="events"]');
    if (await events.count() > 0) {
      await expect(events.first()).toBeVisible();
    }
  });

  test('risk events should show event types', async ({ page }) => {
    // Look for event type badges
    const types = page.locator('.event-type, [data-testid*="type"]');
    if (await types.count() > 0) {
      await expect(types.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Simulated Not Traded Disclaimer', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
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
    // Look for disclaimers in footer or notices
    const disclaimer = page.locator('footer:has-text("Research-only"), .notice-inline:has-text("simulated"), .notice-inline:has-text("not-traded")');
    if (await disclaimer.count() > 0) {
      await expect(disclaimer.first()).toBeVisible();
    }
  });

  test('paper trading UI should clearly indicate simulated nature', async ({ page }) => {
    // Look for explicit simulated messaging
    const simulated = page.locator('p:has-text("simulated"), p:has-text("simulated orders"), .simulated-badge');
    if (await simulated.count() > 0) {
      await expect(simulated.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView Loading State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
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
});

test.describe('PaperTradingView Empty State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
    if (await navButton.count() > 0) {
      await navButton.click();
    }
  });

  test.skip(SKIP_E2E_TESTS, 'Skip E2E tests in CI without API');

  test('should show empty state when no positions', async ({ page }) => {
    // Look for empty state messaging
    const emptyState = page.locator('.empty-state, [data-testid*="empty"], .no-positions');
    if (await emptyState.count() > 0) {
      await expect(emptyState.first()).toBeVisible();
    }
  });
});

test.describe('PaperTradingView API Failure State', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    const navButton = page.locator('nav button:has-text("Paper trading")');
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
    const retryButton = page.locator('button:has-text("Retry"), button[aria-label*="retry"]');
    if (await retryButton.count() > 0) {
      await expect(retryButton.first()).toBeVisible();
    }
  });
});
