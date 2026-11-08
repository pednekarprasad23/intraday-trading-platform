# Browser Smoke MANUAL RELEASE GATE

**Created:** 2026-11-08  
**Status:** PENDING (manual verification required)  
**Purpose:** Define exact steps and pass criteria for browser-based UI verification

---

## Overview

This document defines the manual browser smoke test procedure for all phases. Due to environment limitations (no local browser available), these tests must be executed manually on a workstation with the local application running.

**Critical:** These tests verify the *actual rendered UI*, not just that routes load. This is the only way to catch CSS issues, navigation problems, and visual regressions.

---

## Pass Criteria

All tests below must PASS before proceeding to Phase 6 or production deployment:

1. **Navigation:** All views reachable from main navigation
2. **Layout:** No CSS breaks, responsive behavior intact
3. **Data Rendering:** API responses render correctly (no empty states where data exists)
4. **Interactions:** All buttons, forms, and filters work as expected
5. **State:** Loading, empty, and error states display correctly
6. **Disclaimers:** Simulated/not-traded messaging visible on paper trading

---

## Phase 1: Historical View

### Test Steps

1. Open browser to `http://localhost:8080` (or configured port)
2. Navigate to **Historical View** from main nav
3. Verify page loads without errors
4. Check partition table displays (should show recovered NIFTY 2026-11-09 26000 CE partition if present)
5. Select a partition and load candles
6. Verify OHLCV chart renders with volume bars
7. Test pagination (previous/next buttons)
8. Test date/time filters
9. Verify table view toggle works
10. Check responsive layout on different screen sizes

### Expected Results

- [ ] Page loads within 2 seconds
- [ ] Partition table shows all available partitions with instrument metadata
- [ ] Chart renders OHLCV candles (open, high, low, close) + volume bars
- [ ] Pagination controls navigate through candle data
- [ ] Date filter restricts to selected session
- [ ] Timeframe filter restricts to selected bar interval
- [ ] No console errors in browser DevTools
- [ ] Mobile view (if tested): layout adapts appropriately

### Known Gaps

- **Gap visualization:** Backend has `/gaps` endpoint, frontend calculates gaps but no visual marker exists. This is tracked separately and NOT blocking.

---

## Phase 2: Research Rankings

### Test Steps

1. Navigate to **Research** from main nav
2. Verify rankings table loads with candidates
3. Check latest rankings display
4. Click on a ranking row to open details
5. Verify ranking details modal shows:
   - Composite score
   - Score breakdown (sub-scores)
   - Rejection status and reasons
   - Strategy commentary
   - Evidence chain (metrics, sources)
6. Test pagination controls
7. Test filter by `strategy_id`
8. Test `rejected_only` filter

### Expected Results

- [ ] Rankings table displays candidates with scores
- [ ] Ranking details modal opens on click
- [ ] Composite score visible and formatted correctly
- [ ] Score breakdown shows sub-score values
- [ ] Rejection reasons visible (if rejected)
- [ ] Strategy commentary rendered
- [ ] Evidence chain shows metrics and sources
- [ ] Pagination works correctly
- [ ] Filters restrict results as expected

---

## Phase 3: Instruments View

### Test Steps

1. Navigate to **Instruments** from main nav
2. Verify instrument table loads
3. Test search filter (search for "NIFTY", "RELIANCE", etc.)
4. Test asset class filter (INDEX, FUTURE, EQUITY, CURRENCY)
5. Test exchange filter (NSE, BSE, MT5)
6. Test active status filter
7. Check summary statistics display
8. Verify instrument details visible in table
9. Test pagination

### Expected Results

- [ ] Instruments table displays all mapped instruments
- [ ] Search filter restricts results correctly
- [ ] Asset class filter works (4 categories: INDEX, FUTURE, EQUITY, CURRENCY)
- [ ] Exchange filter works (NSE, BSE, MT5)
- [ ] Active status filter toggles between active/inactive
- [ ] Summary statistics show correct counts
- [ ] Instrument details include: canonical symbol, display name, underlying, option type, strike price, lot size, tick size
- [ ] Pagination navigates through results

---

## Phase 4: Paper Trading

### Test Steps

1. Navigate to **Paper Trading** from main nav
2. Verify "RESEARCH ONLY · SIMULATED · NO BROKER ORDER" badge visible in header
3. Check account summary displays (capital, P&L, exposure)
4. Test order form:
   - Select instrument from dropdown
   - Enter quantity
   - Select side (buy/sell)
   - Submit order
5. Verify orders table displays submitted orders
6. Verify positions table updates after filled orders
7. Test Kill Switch panel:
   - Check status indicator (ARMED/TRIGGERED)
   - Trigger kill switch (should require reason)
   - Verify orders blocked when TRIGGERED
   - Reset kill switch (should require operator confirmation)
8. Check risk events display
9. Verify footer disclaimer: "Research-only environment · Historical results and simulated outcomes are not broker fills or investment advice."

### Expected Results

- [ ] Header badge clearly visible: "RESEARCH ONLY · SIMULATED · NO BROKER ORDER"
- [ ] Account summary shows current capital and exposure
- [ ] Order form accepts input and submits orders
- [ ] Orders table displays order history with state transitions
- [ ] Positions table updates when orders fill
- [ ] Kill switch status indicator shows ARMED (green) or TRIGGERED (red)
- [ ] Triggering kill switch requires audit reason
- [ ] Triggered kill switch blocks new orders
- [ ] Reset kill switch requires operator confirmation
- [ ] Risk events display capital/exposure/position-limit events
- [ ] Footer disclaimer visible on all paper trading pages

### Safety Checks

- [ ] NO broker order submission paths visible
- [ ] NO live trading credentials displayed
- [ ] NO confirmation dialogs attempting real orders
- [ ] All order states clearly marked as simulated

---

## Phase 5: Backtesting

### Test Steps

1. Navigate to **Backtesting** (if exists in UI) or verify via API
2. Check backtest reports table loads (if any exist)
3. Verify walk-forward reports display (if any exist)
4. Test backtest report detail view
5. Verify report provenance visible (strategy, cost, sessions used)

### Expected Results

- [ ] Backtest reports table displays persisted reports
- [ ] Walk-forward reports display with metrics
- [ ] Report detail view shows full provenance
- [ ] Evidence chain visible (metrics, sources, rankings)

---

## Browser Smoke Test Report Template

Use this template to document test results:

```markdown
## Browser Smoke Test Report

**Date:** YYYY-MM-DD  
**Tester:** [Name]  
**Environment:** localhost:port or preview URL

### Phase 1: Historical View

- [ ] Navigation works
- [ ] Partition table renders
- [ ] Chart displays candles
- [ ] Pagination functional
- [ ] Filters work
- [ ] No console errors

**Issues Found:** [List any]

### Phase 2: Research Rankings

- [ ] Rankings table renders
- [ ] Details modal opens
- [ ] Evidence chain visible
- [ ] Pagination functional

**Issues Found:** [List any]

### Phase 3: Instruments View

- [ ] Instruments table renders
- [ ] Search filter works
- [ ] Asset class filter works
- [ ] Exchange filter works
- [ ] Pagination functional

**Issues Found:** [List any]

### Phase 4: Paper Trading

- [ ] Header badge visible
- [ ] Order form submits
- [ ] Orders table displays
- [ ] Positions update
- [ ] Kill switch functional
- [ ] Footer disclaimer visible
- [ ] No broker paths visible

**Issues Found:** [List any]

### Phase 5: Backtesting

- [ ] Reports table displays
- [ ] Report details show provenance
- [ ] Evidence chain visible

**Issues Found:** [List any]

### Overall Assessment

**Status:** [PASS / FAIL / BLOCKING ISSUES]

**Notes:** [Any additional observations]
```

---

## Automation Notes

If browser automation becomes available in the future, consider:

1. **Playwright:** Existing E2E tests use Playwright but require local browser installation
2. **Selenium:** Alternative for cross-browser testing
3. **Cypress:** Modern alternative with better dev experience
4. **Puppeteer:** Chrome-focused automation

**Current Status:** Manual verification required due to environment limitations.

---

## Forward Tracking

This MANUAL RELEASE GATE is tracked forward from Phase 1 due to environment limitations. All phases must pass browser smoke before proceeding to:

- Phase 6 or next major phase
- Production deployment
- Customer-facing preview

**Dependencies:** Browser access to localhost or preview environment.
