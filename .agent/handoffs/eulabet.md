# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-06T21:48:31+00:00
Status: idle
Task: none
Branch: main
Commit: none

## Done
- Imported lucky72s/dyypholdem history into main; added the coordination framework (CLAUDE.md, docs/, scripts/, CI) and the initial ticket pool.

## In progress
- (none)

## Files touched
- (none on a branch)

## Tests
- ./scripts/check.sh → OK

## Bugs / blockers
- Upstream LFS data (models + tables) is gone, so the DeepStack bot can't run yet (D-003).

## Decisions & dependencies
- D-001..D-004. D-004 (release assets) awaits lembzg's confirmation.

## Next steps
1. Run ./scripts/status.sh, wait for the human's go, then claim the top unclaimed P0 ticket.
