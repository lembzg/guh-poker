# Handoff — lembzg

Updated: 2026-11-06T23:50:34+00:00
Status: blocked
Task: #27
Branch: lembzg/27-v0-reuse
Commit: 100edfb

## Done
- #4 merged (#17, 28977b5). #14 merged (#16, 3d44e62).
- Added docs/heads-up-preflop-complete-reference.md (100edfb) and updated #11 to use it: push/fold up to ~10bb, raise/limp/fold mix and BB vs limp when deeper, rake warning.
- Opened decision issue #27 on reusing v0 in bots/main and allowing eval7 for v0 only.

## In progress
- #27 is waiting for the captain's decision. No code on this branch beyond this handoff.

## Files touched
- .agent/handoffs/lembzg.md, docs/heads-up-preflop-complete-reference.md

## Tests
- Local tests were skipped for the final #16 rebase, at the human's request. CI passed on main, but it only runs static checks until #3 lands.
- Last local pytest: 95 passed, Python 3.12, on the stack before the #17 merge.
- Harness, seed 1, duplicate, 100bb, --hands 20000, commit 481ef5b. v0 vs random: +466.33 ± 41.07 bb/100. v0 vs always_call: +255.47 ± 13.88 bb/100. 0 illegal, 0 errors, v0 max 100.35 ms.

## Bugs / blockers
- No python command on this laptop and no requirements file yet. Tests ran in a throwaway Python 3.12 venv outside the repo.
- ae36707 on main is an empty duplicate of the #16 merge, from retries after GitHub 502s. Harmless; left in place rather than force-pushing main.

## Decisions & dependencies
- #27 proposes: v0 stays frozen as benchmark and backup entry, bots/main reuses ideas but not code, eval7 is allowed for bots/v0 only.
- Unverified: whether #19 inherits v0's opponent-model bugs (improvements.md item 4), and v0's results against the rest of the gauntlet.

## Next steps
1. Review PR #19, which is requested from lembzg. Check it against improvements.md item 4.
2. Get the decision on #27. If approved, record it as D-006 in docs/DECISIONS.md, add the all-in criterion to #11, and add v0 to the gauntlet.
3. Take #3 (requirements and pytest in CI, include numpy, pytest and eval7 if #27 is approved).
