# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-06T22:34:11+00:00
Status: in-progress
Task: #10 Equity engine
Branch: eulabet/10-equity
Commit: none

## Done
- Claimed #10; branch created from origin/main.

## In progress
- core/equity.py per docs/API.md → Equity (rank7, equity, range_from_classes, top_percent_range).

## Files touched
- (none yet)

## Tests
- (none yet)

## Bugs / blockers
- core/cards.py (#4) not landed: copy card helpers locally in core/equity.py.

## Decisions & dependencies
- #14 (v0 bot) may contain an evaluator; check it before optimising rank7.

## Next steps
1. Implement rank7 + tests, then equity (Monte Carlo), then range helpers + tools/equity preflop ranking table.
2. Measure speed (target 2000 samples < 20 ms) and report in PR.
