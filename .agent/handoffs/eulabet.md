# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-07T16:15:04+00:00
Status: frozen
Task: FROZEN entry = v2 (sha256 ac7515a0…, code @1876919). Format is 400 hands (200 deals) round 1, 1200 (600 deals) top-5 final; v3 slower gates reverted (200-deal A/B -0.04±0.05, -0.30 vs @call). Upload is the human's call.
Branch: eulabet/final-allin-fix
Commit: 37f190c

## Done
- FORMAT (organisers, final word 2026-11-07 ~16:00): round 1 all-vs-all 400 hands; top 5 play 1200 hands. Broadcast shows biggest-swing hands. (Earlier "30/60 games" was superseded.) Startup counts toward first-move think time.
- v3 entry: results/submission/gemiclaudex.pkl sha256 5343f32633896e7408b51b7429238d36aadeb36171a77de58fed711fec645dcf (arena checksum 480495adaaad) from eulabet/final-allin-fix @37f190c. Change: postflop Beta prior 5→7, gates 1.5x (station/folder 15, sticky 30, hf 22, auto 37, BARREL_MIN_OBS 22). A/B fresh paired seeds, 16 opps: 30 deals +0.09±0.03 (60 seeds), 60 deals +0.03±0.05 (40 seeds). Faster gates (0.6x) −0.09±0.06, rejected. v2 kept as gemiclaudex-v2-0.80.pkl.bak, v1 as gemiclaudex-v1-0.45.pkl.bak.
- Short-match baseline (v2, 30 deals): +2.07 bb/hand mean; positive vs every external opponent; only loss vs our own old combo build.
- OOP dials (A realization 0.90, B check-raise) A/B: no gain, kept off on branch eulabet/oop-play (not merged).
- v2: HIDDEN_SB_ENTRY 0.80 (+1.06 vs @shove, no regression). Overnight sim (lembzg): keep defaults.

## In progress
- Human decides when to upload gemiclaudex.pkl (deadline 18:00).

## Files touched
- bots/main/allin.py, bots/main/postflop.py, tests/bots/main/test_allin.py, tests/bots/main/test_postflop.py (this branch)

## Tests
- PATH=.venv/bin:$PATH ./scripts/check.sh → 227 passed, 2 skipped.
- Short-match tooling: scratchpad diag/short.sh <botdir> <deals> <seed_from> <seed_to> <out>; diag/agg.py a.txt b.txt (paired diff). Gauntlet needs a source folder (bot.py), not a pkl.

## Decisions & dependencies
- Entry = lembzg final + all-in fix + slower gates. Re-pack only for a change that wins on fresh paired seeds.

## Next steps
1. If lembzg merges #54/#45 and changes anything, rebuild: python -m adapters.arena.build --team gemiclaudex --strategy combo --preflop-dir bots/myteam --out <dir>, then arena validate + pack.
2. Optional C (preflop 3-bet-or-fold) is lembzg's area; untested.
