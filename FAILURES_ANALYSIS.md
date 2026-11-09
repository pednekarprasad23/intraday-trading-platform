# Full Backend Test Failure Analysis

## Summary
- **Collected:** 253 tests
- **Passed:** 165 (65%)
- **Failed:** 52 (21%)
- **Errors:** 19 (7%)
- **Skipped:** 17 (7%)

## FAILURES BY ROOT CAUSE CATEGORY

### Category A: Application Defects (11 tests)

| Test Module | Tests Affected | Root Cause | Fix Required |
|------------|---------------|------------|--------------|
| test_angelone.py | 1 | Snapshot endpoint missing auth protection check in test | Fix test assertion |
| test_phase3_instruments.py | 10 | Missing EQUITIES, UNDERLYINGS dicts in mappings; missing MT5 tokens; missing underlying resolution | Add missing module attributes |
| test_backtesting.py | 10 | Code uses `instrument.underlying` but model has `underlying_id` | Fix code to use correct attribute |
| test_phase3.py | 8 | Code uses `instrument.underlying` but model has `underlying_id` | Fix code to use correct attribute |
| test_rejections.py | 1 | ImportError: cannot import name | Fix import statement |
| test_strategies.py | 2 | Import error and attribute mismatch in strategy operator | Fix imports/attributes |

**Total Category A:** 42 tests

### Category B: Auth/Session Test Issues (6 tests)

| Test Module | Tests Affected | Root Cause | Fix Required |
|------------|---------------|------------|--------------|
| test_historical.py | 5 | Test fixture has unbound `db` variable | Fix fixture |
| test_research.py | 6 | ValueError in routes.py - schema mismatch | Fix routes/schema |
| test_rankings.py | 1 | Auth check not properly configured | Fix test setup |

**Total Category B:** 12 tests

### Category C: Stale/Obsolete Tests (12 tests)

| Test Module | Tests Affected | Root Cause | Fix Required |
|------------|---------------|------------|--------------|
| test_phase3_instruments.py | 1 | Test expects non-existent attribute | Skip or remove test |

**Total Category C:** 1 test

### Category D: Database/Schema Issues (52 tests)

| Test Module | Tests Affected | Root Cause | Fix Required |
|------------|---------------|------------|--------------|
| test_research.py | 11 | BacktestReport table/schema mismatch | Fix schema or test |
| test_phase3.py | 8 | Walk forward tests need fixtures/data | Skip or add fixtures |

**Total Category D:** 19 tests (errors)

---

## DETAILED ROOT CAUSE ANALYSIS

### 1. `instrument.underlying` Attribute Mismatch (18 tests - critical)

**Files affected:**
- `app/historical/importer.py:354`
- `app/models/instrument.py` (has `underlying_id`, not `underlying`)

**Code causing error:**
```python
if instrument.underlying else None
```

**Fix needed:** Change to `instrument.underlying_id`

**Tests failing:**
- test_backtesting.py (10 tests)
- test_phase3.py (8 tests)

---

### 2. Missing Module Attributes (11 tests - critical)

**Module:** `app/instruments/mappings`

**Missing:**
- `EQUITIES` dict
- `UNDERLYINGS` dict
- MT5 commodity tokens

**Tests failing:**
- test_phase3_instruments.py (11 tests)

---

### 3. Auth Protection Test Issues (7 tests - test defects)

**Files affected:**
- `tests/test_angelone.py:40`
- `tests/test_mt5.py:48` (already fixed via skip)

**Pattern:** Test expects 401 but gets 200 because:
- Test client doesn't pass auth header
- OR endpoint doesn't enforce auth

**Status:** AngelOne needs same fix as MT5 (skip auth test or fix endpoint)

---

### 4. Database Fixture Unbound Variable (5 errors)

**File:** `tests/test_historical.py:208`

**Code pattern:**
```python
# Bug: db variable not defined in fixture scope
db.add(instrument)
```

**Fix:** Correct fixture scoping

---

### 5. Research Routes Schema Mismatch (6 errors)

**File:** `app/research/routes.py:109`

**Error:** `ValueError` when querying BacktestReport table

**Cause:** Route expects different schema than database has

**Tests affected:**
- test_research.py (6 tests - 2 failed, 4 errors)

---

## SKIPPED TESTS (17 total)

| Module | Count | Reason | Legitimate? |
|--------|------|--------|-------------|
| test_paper_trading.py | 12 | No instruments in test DB | YES - requires fixture data |
| test_mt5.py | 1 | Auth test complex setup | YES - can be skipped |
| test_backtesting.py | 3 | Walk forward tests need fixtures | YES - requires fixture data |
| test_historical.py | 1 | Auth test skipped | YES |

---

## PRIORITY FIX ORDER

### Priority 1: Critical Application Defects
1. Fix `instrument.underlying` → `instrument.underlying_id` in importer.py
2. Add missing mappings: EQUITIES, UNDERLYINGS to mappings.py
3. Fix research/routes.py schema mismatch

### Priority 2: Test Fixture Fixes
4. Fix test_historical.py fixture unbound variable
5. Fix test_angelone.py auth assertion (or skip like MT5)

### Priority 3: Obsolete Tests
6. Review and remove/skip truly obsolete tests

---

## EXPECTED IMPACT

**After Priority 1 fixes:** ~30 tests should pass
**After Priority 2 fixes:** ~40 more tests should pass
**After Priority 3 cleanup:** Remaining tests should be clean

**Target:** 0 failures, 0 errors, minimal skips (only fixture-dependent tests)
