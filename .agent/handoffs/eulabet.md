# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-06T22:39:02+00:00
Status: in-review
Task: #10 Equity engine
Branch: eulabet/10-equity
Commit: 6c63ff1

## Done
- core/equity.py: rank7 (pure Python), vectorised numpy evaluator, equity (MC in 1024-sample chunks, time budget, exact on river), range_from_classes, top_percent_range.
- tools/equity/gen_preflop_ranking.py → core/data/preflop_ranking.json (169 classes, 200k samples each, seed 1, ~47 s).
- tests/core/test_equity.py: 19 tests pass.

## In progress
- PR #15 ready for merge once CI is green.

## Files touched
- core/equity.py, core/data/preflop_ranking.json, tools/equity/, tests/core/test_equity.py

## Tests
- .venv/bin/python -m pytest -q → 19 passed; ./scripts/check.sh → OK
- Latency (2000 samples, top-30% range, M-series laptop): preflop 2.8 ms, flop 2.1, turn 1.8, river (exact) 0.2.

## Bugs / blockers
- Needs numpy (and pytest for tests) in requirements.txt; that file is owned by #3 (captain). Local: python3 -m venv .venv && .venv/bin/pip install numpy pytest.

## Decisions & dependencies
- Card helpers copied locally (private) until core/cards.py (#4) lands; swap to core.cards afterwards.
- Range key order: higher card first by rank, ties broken by suit order cdhs (s highest).
- Empty/all-dead range → treated as any two cards. Non-positive weights ignored.

## Next steps
1. Merge #15 when CI is green; then ./scripts/status.sh and pick the next P0 ticket.
2. After #4 lands: replace local card helpers in core/equity.py with core.cards.
