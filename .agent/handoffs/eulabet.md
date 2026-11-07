# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-07T08:13:26+00:00
Status: idle
Task: none open (all EulaBet tickets closed); lembzg owns final candidate #44/#45
Branch: eulabet/overnight
Commit: 931666d

## Done
- #42 merged (research rules, #40/#35 closed). #48 merged (#47: incremental evaluator, equity 31-52% faster; fixes #45 CI benchmark without changing threshold — lembzg asked to rebase #45 and confirm).
- Merged: #15 equity, #18 harness, #23 gauntlet, #25/#28 EV tool, #20 postflop, #21 MainBot, #30 pure-Python runtime, #31 arena adapter, #38 arena gauntlet. #19 opponent model merged by lembzg.
- PR #42 (#40 research rules + #35 hidden SB folds): CI green, needs lembzg approval (contract label, additive API.md).
- PR #34 combined prototype (lembzg added --strategy combo build).
- eulabet/overnight = main + #42 + #34 + #32 merged; candidate builds, arena validate OK, vs starter +1.235 (1000 deals seed 11).
- adapters/arena/overnight.sh: builds candidate + opponents, runs arena gauntlet per seed (default seeds 101-120, 2000 deals).

## In progress
- Partner runs overnight.sh (ARENA_ROOT = clone of organisers' repo with Python 3.14 venv).

## Files touched
- adapters/arena/overnight.sh (this branch only)

## Tests
- overnight branch: 171 passed (core, bots/main, adapters, harness). Only failing test repo-wide: tests/bots/v0 eval7 (not ours).

## Bugs / blockers
- Team name unknown → no .pkl uploaded yet. Deadline 18:00 event day (2026-11-07).
- Combined bot weakest vs raise-or-fold 'hackathon' bot (~+0.2..+0.4, n.s.); lembzg's preflop vs frequent 3x openers (comment on #32).

## Decisions & dependencies
- Entry = combined bot (lembzg #32 preflop + MainBot postflop with #42 rules) — pending team decision #27.
- Arena: our seat is fixed per half (button 200 hands, then BB 200 hands, fresh process); act() only hook; no showdown cards.

## Next steps
1. Read overnight results (results/arena/overnight/summary.txt on partner's machine); confirm no losing matchup.
2. Get #42 approved/merged, then #34/#32 per #27; rebuild: python -m adapters.arena.build --team <name> --strategy combo --preflop-dir bots/myteam
3. arena validate + arena pack --team <name>; upload EARLY; re-upload after any improvement.
