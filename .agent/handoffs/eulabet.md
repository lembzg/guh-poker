# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-06T23:17:23+00:00
Status: in-progress
Task: #22 Harness gauntlet (in review: #19 #20 #21)
Branch: eulabet/22-gauntlet
Commit: e6f3b6c

## Done
- #10 equity (#15) and #6 harness (#18) merged. Reviewed+approved captain's #17 (flagged float raise_to in clamp_to_legal).
- #13: bots/main/opponent.py (OpponentModel, classify), tests/bots/main/test_opponent.py (15 tests). docs/API.md: additive bluff_rate() + classify().

## In progress
- PR #21 (#5 MainBot): bot.py (thread time guard, clamp, guarded imports) + fallback.py. Integrated rehearsal (#17+#13+#12+#5, fallback preflop), 6k dup hands seed 31: vs random +521±67, always_call +533±38, always_raise_pot +975±109, hackathon +281±68; max 14 ms, 0 illegal.
- PR #20 (#12 postflop): ready; needs #17 merged first. Harness: +63±25 bb/100 vs hackathon (check/call postflop: -38±24), 20k dup hands, seed 21; test bot lives in scratchpad only.
- PR #19 (contract label): needs lembzg's approval AND #17 merged first (imports core.interface).

## Files touched
- bots/main/postflop.py, tests/bots/main/test_postflop.py (branch eulabet/12-postflop)
- bots/main/opponent.py, tests/bots/main/test_opponent.py, docs/API.md

## Tests
- Full suite 58 passed (with #17's core/interface.py + core/cards.py copied in UNTRACKED; never commit them; delete once #17 merges).
- range_estimate: 0.1 ms preflop, 1.4 ms river.

## Bugs / blockers
- NEW (user, 2026-11-06): tournament allows 3 min per decision. Unverified: per-decision vs time bank, hardware, hands per match. MainBot default budget is 500 ms → raise once confirmed.
- PR #19 can't merge before #17 (core.interface missing on main → ImportError).
- requirements.txt (numpy, pytest) pending on #3.

## Decisions & dependencies
- Ported from v0: shrinkage K=20, min samples 12, labels. Priors and label thresholds are HU guesses → tune with harness.
- Uses core.equity private helpers (_rank_matrix, _hand_class, _preflop_ranking, card maps); both modules are mine.
- Blinds for pot-fraction replay are learned from range_estimate states (default 1/2).

## Next steps
1. When #17 merges: rm core/interface.py core/cards.py (untracked copies), git rebase origin/main, pytest, push, merge #19 after approval.
2. When #16 (v0) merges: run v0 vs the 4 baselines (20k hands, duplicate), post to docs/PRODUCT.md → Results.
3. After #17/#19/#20 merge: #5 MainBot wiring or #11 preflop are the remaining P0s (check status.sh for owners).
