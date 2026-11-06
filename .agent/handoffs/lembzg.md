# Handoff — lembzg

Updated: 2026-11-06T23:30:00+00:00
Status: in-review
Task: #14
Branch: lembzg/14-import-v0
Commit: 481ef5b

## Done
- Imported Quant byte-for-byte into bots/v0/ (bot.py, BOT_README.md, data/preflop.json).
- Added bots/v0/adapter.py (V0Bot), bots/v0/README.md, tests/bots/v0/.
- Registered v0 in make_bot and deleted the contract stub in tests/bots/v0/conftest.py.
- Rebased onto origin/main (43b4fdc). Still stacked on the #4 commit, because #17 isn't merged.
- Reported harness bb/100 in PR #16 and marked it ready.

## In progress
- PR #16 waits on #17. Merge #17 first, rebase #16 so its diff shows only #14, then squash-merge it.

## Files touched
- bots/v0/, tests/bots/v0/, the v0 line in bots/__init__.py

## Tests
- pytest, Python 3.12 with numpy, pytest and eval7: 95 passed, including 20 in tests/bots/v0 against the real core/interface.py.
- check.sh passes, but only runs static checks. Neither it nor CI runs pytest until #3 lands.
- Harness, seed 1, duplicate, 100bb, --hands 20000, commit 481ef5b. v0 vs random: +466.33 ± 41.07 bb/100. v0 vs always_call: +255.47 ± 13.88 bb/100. 0 illegal, 0 errors, v0 max 100.35 ms.
- One-off, not in repo: 3,000 hands on the real Fullhouse engine, 5,918 decisions, 0 mismatches, 0 illegal.

## Bugs / blockers
- No python command on this laptop and no requirements file yet. Tests ran in a throwaway Python 3.12 venv outside the repo.

## Decisions & dependencies
- eval7 is needed (listed in PR for #3). CLAUDE.md requires a decision issue for new deps; do this with the post-merge reuse proposal.

## Next steps
1. Merge #17 (contract PR, approved; needs the human's go-ahead).
2. Rebase #16 on origin/main, re-run tests, squash-merge.
3. After merge, open the decision issue on reusing v0 in bots/main, including the eval7 dependency.
