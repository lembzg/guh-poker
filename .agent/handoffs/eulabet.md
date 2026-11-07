# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-07T11:37:30+00:00
Status: waiting
Task: Entry v2 packed (entry rate 0.80); human re-uploads. PR #54 awaits lembzg.
Branch: eulabet/final-allin-fix
Commit: 6678564

## Done
- v2 entry: results/submission/gemiclaudex.pkl sha256 ac7515a0066df0bfb92d03dc73985a49b4c4399144d95b589230d137717aac81 from eulabet/final-allin-fix @1876919 (HIDDEN_SB_ENTRY 0.80: +1.06 vs @shove, mean +0.08, 0 faults). v1 kept as gemiclaudex-v1-0.45.pkl.bak.
- BB-defence idea dropped: BB folds 32-33% vs 2.5x opens (≈equilibrium); loss is OOP postflop in called pots.
- Entry: results/submission/gemiclaudex.pkl (545 KB, sha256 a2f5d8ed2bd57e338f44f6971b967b3cd7b60463427dddf308e210af6f3a0258), packed by organisers' arena pack from eulabet/final-allin-fix @6678564 = lembzg final (1177bfe) + all-in censoring fix. Team name gemiclaudex (human chose GemiClaudEx; arena requires lowercase).
- Fix: bots/main/allin.py scales hidden-fold open-jam evidence by 0.45 instead of zeroing. A/B seeds 41+43, 16 opponents, 0 faults: vs @shove +2.36, mean +0.09, no regression. PR #54 ready, reviewer lembzg.
- Earlier today: #48 equity speed, #51 archetypes, #52 MDF dial (off), #53 per-street bluff (rejected, data on issue). Overnight sim (lembzg, 11.8M hands): keep defaults.
- Codex rivals (4) tested: combined beats balanced/cautious, ~even vs aggressive/mathematical across seeds.

## In progress
- Human uploads gemiclaudex.pkl via the submission form before 18:00.

## Files touched
- bots/main/allin.py, tests/bots/main/test_allin.py (this branch)

## Tests
- PATH=.venv/bin:$PATH ./scripts/check.sh → 227 passed, 2 skipped (lembzg's check.sh uses system python3; use venv).
- Sanity from packed folder (300 deals seed 77): starter +0.51, shove +3.22, random +4.65, 0 faults.

## Bugs / blockers
- Optional: BB preflop defence vs wide raisers (lembzg's preflop) — data on #45.

## Decisions & dependencies
- Entry = lembzg final + all-in fix. Re-upload only for a change that wins on fresh deals (2 seeds).

## Next steps
1. Confirm human uploaded; if lembzg merges #54/#45 later and changes anything, rebuild: python -m adapters.arena.build --team gemiclaudex --strategy combo --preflop-dir bots/myteam, then arena validate + pack.
