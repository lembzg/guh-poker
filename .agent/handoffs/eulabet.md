# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-06T23:57:22+00:00
Status: in-review
Task: #26 EV engine follow-up (PR pending); #19 opponent model awaiting lembzg approval
Branch: eulabet/26-ev-check
Commit: 48bab66

## Done
- Merged: #10 equity (#15), #6 harness (#18), #22 gauntlet (#23), #24 EV engine (#25), #12 postflop (#20), #5 MainBot (#21). Milestone "MainBot plays legal hands" ✅.
- #26: ev.py OOP check model (opp bets after our check; best of fold/call/check-raise) + draw-aware opp strength (equity vs random). 14 EV tests.

## In progress
- PR #19 (#13 opponent model): rebased, CI green, needs lembzg contract approval. Pinged with status (also: clamp float raise_to, v0 test needs eval7).
- #26 PR: tool only, not wired. A/B (EV as whole postflop policy vs current, 4k dup seed 51): hackathon 119±90 vs 210±84; equity_bot 86±74 vs 159±55. Current postflop stays.

## Files touched
- bots/main/ev.py, tests/bots/main/test_ev.py

## Tests
- main: 138 pass + 1 fail (tests/bots/v0 raise test needs eval7, not installed; Python 3.14 can't build it).

## Bugs / blockers
- eval7 can't build on local Python 3.14 → v0 can't be measured here.
- User: friend is improving v0 / preflop (improvements.md) → stay off bots/v0 and #11.
- Tournament: 3 min per decision (unverified details) — docs/PRODUCT.md.

## Decisions & dependencies
- EV engine as full policy loses to postflop.py heuristics vs betting bots; wins big vs always_call. Use selectively later (sizing / vs stations) with harness A/B.

## Next steps
1. Merge #26 PR after CI. Merge #19 once approved; then gauntlet main (python -m harness.gauntlet --a main) and record in docs/PRODUCT.md Results.
2. Options: selective EV use in postflop.py (vs stations, confident stats); harness clock/timeouts simulation.
