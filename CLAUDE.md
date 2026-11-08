# Claude Code Instructions

## Remote Git Policy

REMOTE GIT IS A BACKUP AND RECOVERY CHECKPOINT, NOT THE LIVE AGENT COORDINATION MECHANISM.

During an approved work run:

- Work locally without continuous commit/push
- Use Orchestrator file/directory ownership
- Do not create branches, worktrees, or stashes for routine checkpoints
- Do not repeatedly inspect Git unless needed to diagnose issues
- Do not use Git as real-time inter-agent synchronization
- No two agents may edit the same file concurrently

Commit and push are mandatory ONLY immediately before Claude returns control to the user for:

- Completion report
- Approval request
- Clarification needed
- Blocker requiring user input
- Design decision requiring user input
- Next-phase authorization
- Stopping the approved run

At that final return boundary:

1. Finish all safely completable approved work
2. Run required validation
3. Review the final diff
4. Check for secrets and artifacts
5. Stage intended files
6. Create coherent commit(s)
7. Push to origin
8. Verify the remote SHA
9. Update the progress ledger
10. Return to the user

NEVER force-push.

## Orchestration Guidelines

### Standard Engineering Lifecycle (Compound Engineering Hybrid)
Substantive engineering tasks must follow the standardized lifecycle:
ANALYZE → PLAN → EXECUTE → VERIFY → REVIEW → LEARN → CHECKPOINT

1. **Analyze (Graphify-Lite Pre-Check):** Before modifying shared/sensitive modules, run static analysis via `python tools/code_graph.py` (`depends-on`, `callers`, `symbol`, `hotspots`).
2. **Plan:** Determine task decomposition, specialist ownership (no two agents edit the same file concurrently), and shared contracts.
3. **Execute:** Specialist agents make the smallest correct change preserving behavior, security, and trading safety.
4. **Verify:** Run focused tests first, then full backend regression suite (golden baseline: 253 passed, 0 failed, 0 errors).
5. **Review:** Reviewer/QA checks correctness, regression risk, security, and trading safety.
6. **Learn (Knowledge Capture Threshold):** Capture persistent lessons ONLY when non-obvious, reusable, verified, and structural. Distinguish Memory (facts/constraints) from Skills (reputable procedures in `.claude/skills/`). Verify against current code to prevent staleness.

### Orchestrator Responsibilities
- Architecture and task decomposition
- Dependency ordering and ownership boundaries
- Shared contract management
- Branch/worktree strategy
- Integration sequence
- QA gates and reviewer gates
- Git checkpoints and phase gates

### Specialist Agent Roles
- **BACKEND AGENT:** API routes, services, database models, migrations
- **FRONTEND AGENT:** React components, UI/UX, accessibility, state management
- **MARKET/QUANT AGENT:** Market data logic, instrument contracts, trading calculations
- **QA AGENT:** Test suites, regression tests, E2E tests, smoke tests
- **REVIEWER AGENT:** Security review, financial correctness, code quality

### File Ownership Rules
- NO TWO AGENTS may modify the same file concurrently
- When multiple tasks depend on shared files/schemas/APIs:
  - Orchestrator owns the shared contract first
  - Establish the contract
  - Commit/push the contract checkpoint
  - Then allow dependent agents to proceed

### Skills Usage
- Reuse existing skills rather than creating new ones
- Update skills when procedures change
- Skills are reusable procedures, NOT test substitutes
- Document skills in `.claude/skills/`

### Regression Testing
- Run impacted tests BEFORE making changes
- Add tests for new behavior
- Add regression tests for bugs
- Preserve existing test coverage
- Avoid duplicate/equivalent tests

### Phase Boundaries
- Complete ALL tasks in a phase before advancing
- Never start the next phase until approval
- Each phase has defined gates (Z-n tasks)
- Update progress ledger after phase completion

## Context Discipline

- Do not load entire repository unnecessarily
- Inspect only files relevant to the assigned task
- Summarize large outputs (Git logs, test logs, diffs)
- Reuse repository instructions instead of repeating in prompts
- Use subagents only for independent scoped work
- Return concise completion reports

## Financial/Trading Safety

Treat all trading calculations, market data, and financial logic as high-integrity code. Changes involving:

- Instruments, lot sizes, expiry dates
- Option types, strikes, Greeks, IV
- P&L calculations, risk, slippage
- Backtesting, transaction costs

Must have deterministic tests. Never silently substitute assumptions.

## Production Authentication

Production auth MUST remain fail-closed. Development mode (AUTH_DISABLED=true) is for local testing only and must not be deployed to production.

## Broker Order Policy

No broker/demo/live order submission is authorized. All trading UI must be clearly marked as simulated/not-traded/research-only.
