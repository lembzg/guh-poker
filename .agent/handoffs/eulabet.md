# Handoff — eulabet

<!-- Only you edit your file. Overwrite (don't append) at each checkpoint. Format: .agent/RECOVERY.md -->

Updated: 2026-11-07T00:10:37+00:00
Status: in-progress
Task: #8 Arena adapter + pack (#19 awaiting lembzg approval)
Branch: eulabet/8-arena-adapter
Commit: none

## Done
- Merged: #15 equity, #18 harness, #23 gauntlet, #25/#28 EV engine (tool), #20 postflop, #21 MainBot, #30 pure-Python runtime.
- Rules + environment recorded in docs/PRODUCT.md, docs/ENVIRONMENT.md (organisers' site + repo Manchester-AI-Society/poker_bot_infrastructure).

## In progress
- #8: adapters/arena (their PokerBot/GameState ↔ our contract), build folder + arena pack/validate locally.

## Files touched
- adapters/arena/, tests/adapters/

## Tests
- main suite green except tests/bots/v0 eval7 test (eval7 not installable).

## Bugs / blockers
- Deadline 18:00 event day. Team name for arena pack still unknown (ask human).
- v0 needs eval7 → unusable in sandbox (told lembzg on #27/#8).

## Decisions & dependencies
- Organisers' infra cloned at scratchpad/infra (8b89346). Their history: post_small_blind/post_big_blind, call amount = chips added, bet/raise_to amount = street total, player ids seatN.

## Next steps
1. Finish adapter + tests; build bot folder; run arena validate/match/pack with Python 3.14 venv.
2. Ask human for team name; produce .pkl.
