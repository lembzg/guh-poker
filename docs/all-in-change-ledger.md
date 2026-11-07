# Change Ledger — all-in correctness (#39)

## Scope gate

| Field | Record |
|---|---|
| Requested outcome | Research the best applicable heads-up all-in logic, fix confirmed gaps, validate and push reviewable branches. |
| Target workspace / surface | Desktop guh-poker; MainBot, v0 adapter, combined arena candidate, local EV scorer. |
| Acceptance checks | Correct contestable-pot arithmetic, actual unequal stacks, equity-based terminal calls, remaining-stack sizing, unbeatable fallback hands, no fabricated terminal folds; regressions, quality gate, stdlib-only arena build, duplicate multi-seed measurements, independent review. |
| Non-goals | Full NLHE solver, replacing ordinary preflop charts, claiming universal optimality, ICM, broad opponent-model repairs (#35), merging or submitting tournament entry. |
| Constraints / safety boundaries | No new runtime dependency. Preserve current integration candidate. Separate additive shared-contract PR; implementation stacked on it. |
| Repository documentation contract | CLAUDE.md, .agent/RECOVERY.md, README.md, docs/API.md, ARCHITECTURE.md, PRODUCT.md, ENVIRONMENT.md, scripts/check.sh; no AGENTS.md found. Contracts in docs/API.md before consumers; research and results in docs/; own handoff only. |
| Documentation decision | Add research/design in docs/ALL_IN.md, link architecture; update API and environment mapping; record measurements in PRODUCT.md. |
| Material questions and answers | None. User authorizes fixes and push; no merge requested. |
| Low-risk defaults | Optimize chip EV for documented stack-reset, no-rake HU event. Range priors are explicit assumptions, not solved GTO. Existing optional stack metadata defaults to equal stacks for compatibility. |

## Event log

| # | Time | Role | Status | Event / evidence | Files or commands | Result / next step |
|---:|---|---|---|---|---|---|
| 1 | 2026-11-07 | scope owner | scoped | Read repository contract and recovery brief; clean checkout at 9a9575a. Task #39 created. | CLAUDE.md; scripts/resume.sh | Preserve combo integration; use stacked branches. |
| 2 | 2026-11-07 | researcher | verified | Consulted PokerStars pot odds, HRC HU Nash limits, TDA raise rules, GTO Wizard SPR, and organisers engine @8b89346. | Sources to be linked in ALL_IN.md | All-in calls realize full equity; no implied-odds or survival cushion; subtract unmatched excess. |
| 3 | 2026-11-07 | implementer | planned | Add optional opponent starting stack to shared GameState before consumers. No positional argument changes. | core/interface.py; docs/API.md | Separate shared/contract draft PR. |
