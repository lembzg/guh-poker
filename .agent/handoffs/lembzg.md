# Handoff — lembzg

Updated: 2026-11-07T01:35:58.868763+00:00
Status: ready
Task: #33 Report-only overnight sparring/tuning; DO NOT START until user explicitly asks
Branch: lembzg/33-overnight-runner
Commit: 5eeba1d Freeze reviewed bot revisions and reject hidden strategy errors (#33)

## Done
- Published PR #46 on lembzg/33-overnight-runner; stacked on #34. CI green, working tree clean before this metadata checkpoint.
- Added tools/tune/ Python3.14 runner, copied-only parameter variants, eight-family search, shifted validation, locked 14-family final audit, paired match-cluster inference, durable raw results and morning reports.
- Added frozen source/rules/default/interface checks, optional --bot-ref, restart/deadline/resource guards and Linux worker group recovery. No production strategy/config/table edits.
- docs/OVERNIGHT.md contains exact CachyOS/uv setup, safe preparation, explicit later start, output interpretation, rules and limits. README links it.

## In progress
- No implementation work remains. Published draft PR #46 with green CI; waiting for explicit user instruction before any real sparring, tuning, validate, or pack-with-validation command.

## Files touched
- tools/tune/; tests/tools/tune/; docs/OVERNIGHT.md; README.md navigation; this handoff.

## Tests
- Focused Python3.14 suite with optional real-SDK no-game packing: 29 passed. Ruff and scripts/check.sh passed.
- Actual CLI prepare/plan/report tested: 32 candidates frozen; zero game jobs, no state/timer. Run without --start refused.
- Alternative --bot-ref preparation tested on eulabet/overnight; five configurations packed with validate=False and no act calls. No games played.
- Synthetic full coordinator test covers search/validation/test locking and immutable source; fake-arena telemetry test uses fabricated records only.

## Bugs / blockers
- No real match has been run for this task, by the user's explicit instruction. Live packed qualification occurs only after --start. Linux/CachyOS gameplay remains to be exercised on the PC.
- PC is CachyOS, i7-12700F, RTX3060; memory detected at runtime. CPU-only arena; no GPU dependency.
- #42/#43 and other bot work are unmerged. Choose the reviewed bot/helper source before preparation; do not merge or select unreviewed changes automatically.

## Decisions & dependencies
- Runner branch starts at verified #34 head 9a9575a and is independent of current main checkout's #39 work. Main checkout untouched.
- Source arena pinned to 8b893461c0d020ae8ed9c78aed298cd698e025a0; Python3.14; only arena requirements; no numpy/eval7 runtime. Rules downloaded/verified from official site.
- Results-only: never apply parameters, alter production files, merge, upload or submit. No overnight process, automation or timer has been started.

## Next steps
1. User clones this branch on PC and follows docs/OVERNIGHT.md setup/prepare/plan only.
2. Before bed, only after the user explicitly says run, execute the documented --start command on the PC with sleep inhibition; use prepared reviewed source.
3. In morning, read MORNING_REPORT.md, recommendation.json and CSV/SQLite data. Do not apply changes or retune unless separately requested.
