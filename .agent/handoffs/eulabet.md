# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-06T22:49:42+00:00
Status: in-review
Task: #6 Local HU harness
Branch: eulabet/6-harness
Commit: ea724da

## Done
- #10 equity engine merged (#15).
- #6: harness/engine.py (HU NLHE rules), match.py (play_match, duplicate, CI, latency), opponents.py (random, always_call, always_raise_pot, hackathon), run.py (CLI per docs/API.md), _types.py (local copy of the contract until #4).
- tests/harness/test_harness.py: 24 tests; whole suite 43 passed.

## In progress
- PR #18: merge once CI is green.

## Files touched
- harness/, tests/harness/

## Tests
- .venv/bin/python -m pytest -q → 43 passed; ./scripts/check.sh → OK
- Throughput ~20-30k hands/s with trivial bots.

## Bugs / blockers
- requirements.txt (numpy, pytest) still pending on #3 (captain). 'main' bot can't run until #4/#5 land (bots.make_bot missing).

## Decisions & dependencies
- Engine rules: fold only legal facing a bet (fold-when-check → check, counted illegal); call with 0 to call = check (legal); overbets beyond opponent's stack allowed, uncalled part refunded.
- Duplicate: hands rounded up to even; same bot instances across both seatings; CI over deal pairs.
- harness.match.make_bot resolves harness opponents locally, everything else via bots.make_bot (#4).

## Next steps
1. Merge #18 when CI is green; run ./scripts/status.sh.
2. When #16 (v0) merges: run v0 vs all four opponents (20k hands, duplicate) and post results in docs/PRODUCT.md → Results.
3. Next ticket candidate: #13 opponent model (per docs/PLAN.md), or #12 after the v0 reuse decision.
