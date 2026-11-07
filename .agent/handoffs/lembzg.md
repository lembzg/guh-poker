# Handoff — lembzg

Updated: 2026-11-07T00:43:33.116053+00:00
Status: ready
Task: #27 Combined prototype integration fixes (PR #34)
Branch: lembzg/34-combo-fixes
Commit: a0b17c8 Make combined arena bot reproducibly buildable (#27)

## Done
- PR #34 integration fix: merged latest main at 8ab7c46 for #19, added --strategy combo / --preflop-dir build, preserved default MainBot build.
- Combo wrapper records the actual fallback action and keeps the returned action unchanged on bookkeeping errors. Added response-conversion, routing and builder regression tests.
- docs/ENVIRONMENT.md documents the combined build, dependency on #32, upload-envelope unpacking and evaluation limits.

## In progress
- Implementation and local verification complete. PR #34 remains a draft pending entry selection and tuning.

## Files touched
- adapters/arena/{build,combo_bot_example,translate}.py; tests/adapters/; docs/ENVIRONMENT.md; this handoff.

## Tests
- Python 3.12 dev venv: python -m pytest -q -> 179 passed.
- Python 3.14 without numpy/eval7: adapters + MainBot wiring/fallback/postflop/opponent tests -> 70 passed.
- ./scripts/check.sh -> OK; git diff --check -> clean.
- Arena @8b89346: source validate -> 40 hands, zero faults; pack with fresh-process validation -> 521 KB.
- Packed payload only: random seed 101 and starter seed 102, 200 duplicate deals each -> 800 total hands, zero faults, 10.5s / 9.5s aggregate thinking.

## Bugs / blockers
- #32 is still unmerged: use --preflop-dir pointing to its bots/myteam helpers; no tables were changed or bundled into this PR.
- No tuning or paired improvement evidence added. #35 remains separate. Existing hidden fold / last-hand inference limitations remain.

## Decisions & dependencies
- User asked to fix PR #34. Scope chosen: reproducible integration and reliability, preserving strategy thresholds and draft status.
- Python 3.14 arena/dev environments and infra remain in /private/tmp/claude-501/-Users-arryl-Desktop-guh-poker/bdb98b8b-e1f1-428f-90b3-812c4dd5d3bb/scratchpad/.
- Verified artifact and report: /Users/arryl/Documents/Codex/2026-11-07/here-s-what-to-run-overnight/outputs/pr34/.

## Next steps
1. Check PR #34 CI on its updated head and inspect final diff.
2. Select the tournament entry and actual team name; rebuild and pack after any strategy changes.
3. Run paired tournament-length tuning across diverse opponents, then confirm selected variants with fresh seeds (#33).
