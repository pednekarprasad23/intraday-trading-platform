# Paper Trading Test Skill

## Purpose

Run paper trading risk and order lifecycle regression tests for Phase 4.

## When to Use

- After changes to paper trading API routes
- Before Phase 4 completion
- To verify risk checks and kill switch functionality

## Command

```bash
cd apps/api && pytest tests/test_paper_trading.py -v
```

## Expected Results

- All tests should pass
- Kill switch state management should work correctly
- Capital and position limit checks should enforce limits
- Order lifecycle should transition through valid states
- Risk events should be created and persisted

## Integration with Phase 4

This skill is part of Phase 4 (Paper observation and risk controls).

Run before final integration to ensure paper trading functionality is complete.

---

**Author:** Claude Code  
**Date:** 2026-11-08  
**Version:** 1.0
