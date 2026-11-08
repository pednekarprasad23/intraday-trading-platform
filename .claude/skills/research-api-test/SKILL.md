# Research API Test Skill

## Purpose

Run research ranking API regression tests for Phase 2.

## When to Use

- After changes to research ranking endpoints
- Before Phase 2 completion
- To verify deterministic scoring and reproducibility

## Command

```bash
cd apps/api && pytest tests/test_research.py -v
```

## Expected Results

- All tests should pass
- Rankings should be deterministic (same input = same output)
- Authentication should be enforced
- Pagination should work correctly

## Integration with Phase 2

This skill is part of Phase 2-A (Research ranking contract and reproducibility).

Run before final integration to ensure ranking endpoints work correctly.

---

**Author:** Claude Code  
**Date:** 2026-11-08  
**Version:** 1.0
