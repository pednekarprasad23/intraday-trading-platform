---
name: historical-api-test
description: Run historical API regression tests
---

# Historical API Test Skill

## Purpose
Run the historical market-data API regression tests to verify candle endpoint functionality.

## When to Use
- After any changes to historical API routes or models
- Before merging phase1/historical-api branch
- As part of Phase 1 integration testing

## Preconditions
- Python environment available
- pytest installed
- Database accessible for test runs

## Inputs
None (runs full historical test suite)

## Procedure
```bash
cd apps/api
pytest tests/test_historical.py -v --tb=short
```

## Pass Criteria
- All tests pass
- No regressions in existing tests
- New API tests for authentication, pagination, and constraints pass

## Fail Criteria
- Any test fails
- Import errors in test file
- Database connection failures

## Failure Handling
- Review test output for specific failures
- Check if changes introduced breaking changes
- Verify authentication decorators are correct
- Check pagination constraints

## Artifacts
- Test output with pass/fail counts
- Any generated test databases (in tmp paths)

## Escalation Condition
- If tests fail due to model changes, verify migration is correct
- If tests fail due to route changes, check query logic
