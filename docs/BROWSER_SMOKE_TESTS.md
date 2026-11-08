# Browser Smoke Tests

**Date:** 2026-11-08  
**Status:** MANUAL RELEASE GATE  
**Purpose:** Manual verification procedure for all UI views

---

## Overview

Due to environment limitations (no local browser in development container), these tests must be executed manually on a workstation with the local application running.

**Critical:** These tests verify the actual rendered UI, not just that routes load. This is the only way to catch CSS issues, navigation problems, and visual regressions.

---

## Pre-Flight Checklist

Before starting browser tests:

1. [ ] Docker containers running: `docker ps | grep intraday`
2. [ ] API healthy: `curl http://localhost:8000/api/v1/monitoring/health`
3. [ ] Web proxy running: `curl http://localhost:8080`
4. [ ] No console errors in browser DevTools
5. [ ] Authentication disabled (development) or valid credentials available

---

## Test Procedure

### 1. Dashboard / Home View

**URL:** `http://localhost:8080`

**Expected Results:**
- [ ] Page loads within 3 seconds
- [ ] Navigation bar visible (Home, Historical, Research, Instruments, Paper Trading)
- [ ] No 404 errors
- [ ] No JavaScript console errors
- [ ] Responsive layout (test at 1280px, 768px, 375px widths)

**Actions:**
1. Open browser to `http://localhost:8080`
2. Check page renders without errors
3. Open DevTools Console (F12) - verify no errors
4. Resize browser to mobile width - verify responsive

---

### 2. Historical View

**URL:** `http://localhost:8080/historical`

**Expected Results:**
- [ ] Partition table displays available data
- [ ] OHLCV chart renders when partition selected
- [ ] Volume bars visible below candles
- [ ] Pagination controls functional
- [ ] Date/time filters work
- [ ] Table view toggle works

**Actions:**
1. Navigate to Historical view from main nav
2. Verify partition table shows recovered data (if available)
3. Select a partition
4. Verify chart renders candles
5. Test pagination (previous/next)
6. Toggle between chart and table view

---

### 3. Research Rankings

**URL:** `http://localhost:8080/research`

**Expected Results:**
- [ ] Rankings table displays candidates
- [ ] Score breakdown visible
- [ ] Rejection reasons shown (if rejected)
- [ ] Details modal opens on row click
- [ ] Pagination works
- [ ] "RESEARCH ONLY" badge visible

**Actions:**
1. Navigate to Research view
2. Verify rankings table loads
3. Click on ranking row
4. Verify details modal opens with score breakdown
5. Check for simulated/not-traded messaging

---

### 4. Instruments View

**URL:** `http://localhost:8080/instruments`

**Expected Results:**
- [ ] Instrument table displays all mappings
- [ ] Search filter works
- [ ] Asset class filter works
- [ ] Exchange filter works
- [ ] Summary statistics visible
- [ ] Pagination functional

**Actions:**
1. Navigate to Instruments view
2. Test search for "NIFTY"
3. Test asset class filter (INDEX, FUTURE, EQUITY)
4. Test exchange filter (NSE, BSE, MT5)
5. Verify summary statistics correct

---

### 5. Paper Trading

**URL:** `http://localhost:8080/paper-trading`

**Expected Results:**
- [ ] Header badge: "RESEARCH ONLY · SIMULATED · NO BROKER ORDER"
- [ ] Account summary displays
- [ ] Order form accepts input
- [ ] Orders table updates on submission
- [ ] Positions table shows filled orders
- [ ] Kill switch panel visible
- [ ] Kill switch status indicator (ARMED = green, TRIGGERED = red)
- [ ] Footer disclaimer: "Research-only environment · Historical results and simulated outcomes are not broker fills or investment advice."

**Actions:**
1. Navigate to Paper Trading view
2. Verify header badge visible
3. Check account summary
4. Enter quantity and submit test order
5. Verify order appears in Orders table
6. Test Kill Switch panel
7. Check footer disclaimer

**Safety Check:**
- [ ] NO broker order submission dialogs
- [ ] NO live trading credentials displayed
- [ ] All order states marked as simulated

---

### 6. System/Operations (if available)

**URL:** `http://localhost:8080/operations` or API endpoint

**Expected Results:**
- [ ] Health check endpoint responsive
- [ ] Metrics available
- [ ] Backup list shows recent backups

---

## Browser Smoke Test Report Template

```markdown
## Browser Smoke Test Report

**Date:** YYYY-MM-DD  
**Tester:** [Name]  
**Browser:** Chrome/Firefox/Safari [Version]  
**Environment:** localhost:8080

### View Test Results

| View | Load Time | CSS OK | JS Errors | Navigation | Interactive |
|------|-----------|--------|-----------|------------|-------------|
| Home | <3s | Yes | None | OK | OK |
| Historical | | | | | |
| Research | | | | | |
| Instruments | | | | | |
| Paper Trading | | | | | |

### Issues Found

[List any visual bugs, broken links, or functional issues]

### Overall Assessment

**Status:** PASS / FAIL / BLOCKING ISSUES

**Notes:**
```

---

## Known Limitations

### Gap Visualization

**Status:** PARTIAL

**Details:**
- Backend has `/gaps` endpoint
- Frontend calculates gaps for candle spacing
- No dedicated visual gap marker
- **Impact:** Visual representation of missing data incomplete

### Browser Automation

**Status:** NOT AVAILABLE

**Details:**
- No automated browser test infrastructure
- Manual verification required
- **Recommendation:** Invest in Playwright/Selenium for CI

---

## Evidence Requirements

For release sign-off, provide:

1. [ ] Screenshots of each view (Home, Historical, Research, Instruments, Paper Trading)
2. [ ] DevTools Console screenshot showing no errors
3. [ ] Mobile responsive test (1280px, 768px, 375px)
4. [ ] Paper Trading safety check verification

---

**Last Updated:** 2026-11-08  
**Next Review:** Before each release
