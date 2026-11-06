# Intraday Trading Platform

Phase 1 implementation: local research-only foundation. **Live trading is unavailable.**

- [Local setup and test commands](docs/LOCAL_DEVELOPMENT.md)
- [Current project status](docs/PROJECT_STATUS.md)
- [Approved architecture decisions](docs/ARCHITECTURE_DECISIONS.md)
- [Changelog](docs/CHANGELOG.md)

The original blueprint below is preserved. The approved Phase 1 decisions supersede its Next.js and immediate cloud-deployment assumptions.

## Original blueprint

This bundle contains the approved Version 1.0 planning documents for a single-user, cloud-hosted, AI-assisted intraday trading intelligence platform.

## Documents
- `docs/01-PRD.md` – product scope, user journeys, requirements and acceptance criteria.
- `docs/02-SYSTEM-ARCHITECTURE.md` – logical architecture, cloud topology, data flows, APIs, execution state machine and security.
- `docs/03-DATABASE-DESIGN.md` – entities, columns, relationships, indexes, retention and migration order.
- `docs/04-FIRST-DEVELOPMENT-SPRINT.md` – first sprint tasks, cloud baseline, API contracts and acceptance tests.

## Important safety boundary
The platform is initially research/paper-trading only. AI output cannot place orders. Live trading requires separate broker onboarding, current regulatory review, static-IP/network validation, risk controls, order reconciliation and explicit manual approval.

## How to use with a coding assistant
1. Put this folder in the root of a private Git repository.
2. Ask the coding assistant to read all four documents before generating code.
3. Implement only one sprint task at a time.
4. Require tests and a short implementation summary for each task.
5. Update the documents through reviewed changes when architecture decisions change.
6. Never provide broker passwords, API keys, TOTP seeds or live tokens to an LLM prompt.

## Baseline assumptions requiring confirmation
- Cloud vendor and region are not yet selected.
- Historical provider is not yet selected; licensing, cost, history depth and instrument coverage must be verified.
- Exact Qwen model identifier and Salad endpoint will be configured after checking current availability.
- Angel One and MT5 instrument eligibility and order requirements must be validated per account and contract.
