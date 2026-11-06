# Handoff — lembzg

Updated: 2026-11-06T22:38:56+00:00
Status: in-progress
Task: #14
Branch: lembzg/14-import-v0
Commit: 9ff1212

## Done
- Imported Quant byte-for-byte into bots/v0/ (bot.py, BOT_README.md, data/preflop.json).
- Added bots/v0/adapter.py (V0Bot), bots/v0/README.md, tests/bots/v0/.

## In progress
- #14 draft PR. Remaining: the v0 line in make_bot (needs #4), harness numbers (needs #6).

## Files touched
- bots/v0/, tests/bots/v0/ (no shared files)

## Tests
- pytest tests/bots/v0: 19 passed, 1 skipped (make_bot, waits on #4). Uses a contract stub in conftest.py.
- One-off, not in repo: 3,000 hands on the real Fullhouse engine, 5,918 decisions, 0 mismatches, 0 illegal.

## Bugs / blockers
- core/interface.py and make_bot don't exist yet (#4, unclaimed, captain's ticket). Adapter can't import without them outside tests.
- Local main has diverged from origin/main (old pre-pivot history). Left untouched; work is branched from origin/main.

## Decisions & dependencies
- eval7 is needed (listed in PR for #3). CLAUDE.md requires a decision issue for new deps; do this with the post-merge reuse proposal.

## Next steps
1. Land #4, then add the v0 line to make_bot and delete the stub in tests/bots/v0/conftest.py.
2. Once #6 lands, report bb/100 for v0 vs random and always_call in the PR.
3. Mark the PR ready. After merge, open the decision issue on reusing v0 in bots/main.
