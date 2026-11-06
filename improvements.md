# Improvements: heads-up leak analysis of v0

Written 2026-11-06 for the GUH heads-up tournament. Scope: v0 ("Quant", our Fullhouse bot) as imported in #14 (`bots/v0/` on `lembzg/14-import-v0`, commit `8c49ad9`), plus `core/equity.py` (#10) and the contracts in `docs/API.md`.

**How to read the numbers.** Everything here comes from reading the code and computing EVs from v0's own charts with `core/equity`. None of it is a harness result yet. Appendix A gives the method behind every number. Per CLAUDE.md, confirm a claim with `python -m harness.run ... --duplicate` before the strategy change that relies on it merges.

## Summary

v0 is a safe base: it's legal, takes about 1ms per decision, and made no illegal actions in the 3,000-hand Fullhouse check. But its heads-up branch is still tuned for 6-max, its preflop play never looks at the opponent model, and a counting bug distorts its opponent reads. The items below are ordered by chips at stake.

## 1. Preflop ranges are still 6-max (#11)

| Spot | v0 | Rough HU baseline at 100bb | Why it matters |
|---|---|---|---|
| SB open | 46% | ~80% | Every fold gives up 0.5bb |
| BB facing an open | Folds 58.5%, whatever the size | Folds ~35-40% vs 2.5x | A pure-bluff min-raise profits above 50% folds |
| SB facing a 3-bet | Folds 90% of its opens | Continues ~50% | A 3-bet bluff to 7.5bb profits above 65% folds |

- **Cost:** a bot that 3-bets a lot makes roughly +1.7bb per v0 open, about 40 bb/100, from that spot alone (A.3). The harness's `always_raise_pot` 3-bets to exactly 7.5bb over a 2.5bb open.
- **Other gaps:** v0 folds 83% of its 3-bets to a 4-bet, and raises only 14% against a limp.
- **Why:** heads-up spots without a heads-up chart fall back to 6-max ones. Facing a 3-bet it uses the generic `_VS_3BET_4BET` (KK+, AKs, A5s) and `_VS_3BET_CALL` (QQ-TT, AQs, AJs, KQs, AKo). Facing a 4-bet it uses `_VS_4BET_CALL` (QQ+, AKs, AKo). Facing a limp it uses the 6-max `_ISO["BB"]` chart. `_preflop_chart_action` never reads opponent stats or the size of the raise.
- **Fix:** use HU charts for the real stack depth. Then let the thresholds move with opponent stats: their open %, fold to open, 3-bet %, fold to 3-bet, and open size. Preflop gives one observation per hand, so these stats settle fastest.

## 2. All-ins use fixed charts (a small standalone module)

- **Always-jam bot (100bb every hand):** v0 wins 382 bb/100, while the best response wins 767 (A.4).
  - Nearly all of the gap is on the SB, where v0 makes +0.77bb per hand against the best response's +7.80bb. v0 opens 46% and folds 90% of those to the jam. It should play every hand with about 50%+ equity against a random hand and call.
  - In the BB, v0 makes +6.86bb per hand against the best response's +7.55bb.
- **Bot that jams only its top 10%:** v0's BB still calls 41.5% of the time and loses 25.5bb per call compared with folding (A.5).
- **Why:** above 15bb effective, `_preflop_chart_action` ignores whether a raise is all-in. A 100bb shove is just "vs_raise" or "vs_3bet".
  - BB calls it with its normal 3-bet plus call ranges, which include hands like 54s and 96s. 32 of its 550 calling combos are -EV even against any two cards.
  - SB uses the 6-max vs-3-bet chart.
- **Fix:** call a jam only if equity against their jam range beats the pot odds. Take that range as their top f%, where f is their observed jam frequency, shrunk toward a prior. `core/equity` already accepts a range and does this in a few ms. This one function covers both the classic jam bot and the "jam premiums only" LLM bot.

## 3. Postflop equity is measured against a random hand (#12)

- **Example:** K7o on K♥8♠3♣ has 85% equity against a random hand, but 14% against a plausible check-raise range of sets, two pair and better Kx (A.6).
- **What v0 does with that:**
  - It calls raises when equity is pot odds + 3% (`_CALL_CUSHION`).
  - It re-raises anything it rates at 78% or more (`_VALUE_RAISE_EQ`), so overpairs and top pair good kicker get stacks in against value raises.
  - Its overcommit guard (`_postflop_overcommit_guard`) only covers weak one-pair hands. K7o's 85% also sits exactly on the guard's 0.85 stack-off threshold (`_STACKOFF_EQ`), so whether it folds to a stack-off raise there comes down to Monte Carlo noise.
- **Fix:** narrow their range by how often they take each action. After each bet or raise, keep the top f% of their previous range by board strength, where f is how often they take that action on that street. Simple bots mostly raise for value, so this is the biggest postflop fix.

## 4. The opponent model doesn't work heads-up (#13)

- **Counting bug:** `_fold_entry` counts every action after the hand's first raise as "facing a bet", including checks and the opponent's own c-bets. So fold-to-bet reads far too low. The bluff gate (`_all_opps_foldy`), which needs more than 55%, rarely opens, and "station" fires too easily.
- **Same bug in fold to 3-bet:** that counter also keeps state per hand, not per street. Any later-street bet sets its "reraised" flag, so the opener's next action counts as facing a 3-bet.
- **Unused stat:** `f23` (fold to 3-bet) is computed in `_opp_rates` but never used.
- **Polluted prior:** `_live_prior` pools every `bot_id` it has seen, including ours. The adapter logs our actions as `"me"`, so heads-up our own play is half the pool.
- **Wrong cutoffs:** `_classify` uses 6-max cutoffs:
  - maniac: VPIP > 50% and aggression > 55%
  - station: VPIP > 50%, aggression < 25% and fold-to-bet < 35%
  - nit: VPIP < 25% and fold-to-bet > 55%

  VPIP above 50% is normal heads-up, and the fixed prior (VPIP 45%, `_FIXED_PRIOR`) is a 6-max number.
- **Fix:** rebuild it per spot, by street and position, with Beta priors. Use the showdown cards that `HandResult.opp_hole_cards` now gives you. Two rules carry most of the value:
  - Bluff when their fold rate beats bet/(pot + bet): 25% for a third-pot bet, 33% for half pot, 50% for pot.
  - Fold bluff-catchers to river bets from bots that have never shown a river bluff.

## 5. Stack depth and format

- **Unequal stacks:** `GameState` has a single `starting_stack`, and the adapter works out the opponent's stack from it in `to_quant_state` (`opp_stack = starting_stack - opp_committed`). The adapter's shove check (`raise_to >= starting_stack`) relies on it too.
  - If stacks carry over between hands (a freezeout), pass the effective stack (the smaller one) or add both stacks to the contract. That's a captain decision.
  - Otherwise the bot misreads stack depth, push/fold gating and SPR.
  - With the effective stack passed, the adapter still maps an all-in to `legal.max_raise_to`, so jams stay legal.
- **15 to 40bb:** v0 keeps 100bb sizing here. At 20bb:
  - SB opens to 2.5bb and BB 3-bets to 7.5bb (`_threebet_raise`, 3x).
  - SB's 4-bet goes to 17.25bb (`_fourbet_raise`, 2.3x), leaving 2.75bb behind.
  - SB also folds 90% of its opens to that 3-bet, which is over a third of its stack.

  If blinds rise, many hands get played at these depths, so it needs 3-bet-jam and 4-bet-jam ranges.
- **Push/fold (≤ 15bb):** its charts are tighter than Nash. From a quick approximate solve (A.7), v0 jams 25% where Nash jams about 45-52% at 12-15bb, and 40% where Nash jams about 58% at 10bb. That only costs 2-8 bb/100 against a Nash opponent, so do it after the above.
- **Environment:** v0 needs eval7, and without it it never bets postflop. It also ignores `time_left_ms` and always uses a fixed 1.2s budget (`TIME_BUDGET_S`). Check both against the tournament sandbox.

## Order of work

The harness is now merged on main (#18). It has `random`, `always_call`, `always_raise_pot` and `hackathon` opponents.

1. **Tonight, before the environment arrives:** add the likely opponents that are still missing to `harness/opponents.py` (#6):
   - an always-jam bot, and a top-10% jammer
   - a bot that min-raises any two
   - a bot that 3-bets any two, then folds to a 4-bet (`always_raise_pot` covers the 3-bet but never folds afterwards)
   - an equity-vs-random threshold bot (v0 itself, once #14 registers it in `make_bot`)

   Already covered: a calling station (`always_call`), a tiered "raise if strong" bot (`hackathon`), and `random`. Then run v0 against every one with `--duplicate`, and log the results in `docs/PRODUCT.md` under Results, so the numbers above become measured ones.
2. **Then items 1 and 2,** since neither needs the environment.
3. **When the rules arrive,** fill in the `docs/PRODUCT.md` table first. Stack depth, blinds, hands per match and scoring decide whether item 5 jumps to the top.
   - Short matches (a few hundred hands) favour good defaults over exploits, because postflop stats won't settle.
   - If the winner is the chip leader after N hands, the bot needs late-match risk control: protect a lead, gamble when behind.
4. **Submission:** keep v0 as the entry until `bots/main` beats it and loses to nothing in the gauntlet, each with a 95% CI that excludes 0.

## Appendix A: numbers and how they were computed

Common assumptions:
- Equities come from `core/equity.py`.
- Preflop equity against a random hand comes from `core/data/preflop_ranking.json` (200,000 samples per class).
- Chart frequencies come from expanding v0's own range strings (`_CHARTS`) and counting combos: 6 per pair, 4 per suited hand, 12 per offsuit hand, out of 1,326.
- Stacks are 100bb with no ante, and the SB is the button.

### A.1 v0's heads-up chart frequencies

| Spot (chart) | Combos | Share |
|---|---|---|
| SB open (`_HU_SB_OPEN`) | 610 | 46.0% of hands |
| BB 3-bet vs an open (`_HU_BB_3BET`) | 196 | 14.8% of hands |
| BB continue vs an open (3-bet range plus `_HU_BB_CALL`) | 550 | 41.5% of hands, so it folds 58.5% |
| SB vs a 3-bet: 4-bet (`_VS_3BET_4BET`) | 20 | 3.3% of opens |
| SB vs a 3-bet: call (`_VS_3BET_CALL`) | 42 | 6.9% of opens |
| SB vs a 3-bet: continue in total | 62 | 10.2% of opens, so it folds 89.8% |
| BB vs a 4-bet: continue (`_VS_4BET_CALL` within the 3-bet range) | 34 | 17.3% of 3-bets, so it folds 82.7% |
| BB raise vs a limp (`_ISO["BB"]`) | 182 | 13.7% of hands |
| HU jam at ≤ 10bb (`_HU_JAM["le10"]`) | 534 | 40.3% |
| HU jam at 10-15bb (`_HU_JAM["le15"]`) | 330 | 24.9% |
| HU call a jam at ≤ 10bb (`_HU_CALLJAM["le10"]`) | 430 | 32.4% |
| HU call a jam at 10-15bb (`_HU_CALLJAM["le15"]`) | 238 | 17.9% |

### A.2 Break-even fold frequencies for a pure bluff

A bluff that risks R more chips to win a pot of P breaks even when they fold R / (R + P) of the time.

| Bluff | Risk R | Pot P | Break-even folds |
|---|---|---|---|
| SB min-raise to 2bb | 1.5bb | 1.5bb | 50% |
| SB open to 2.5bb | 2bb | 1.5bb | 57.1% |
| BB 3-bet to 7.5bb over a 2.5bb open | 6.5bb | 3.5bb | 65% |
| Postflop bet of a third of the pot | B | 3B | 25% |
| Postflop bet of half the pot | B | 2B | 33% |
| Postflop bet of the pot | B | B | 50% |

### A.3 3-bet-any-two against v0's SB open

The exploiter (BB) 3-bets every hand to 7.5bb over v0's 2.5bb open, and folds to any 4-bet.

| v0's response | Frequency | Exploiter's result |
|---|---|---|
| Folds | 89.8% | +2.5bb |
| 4-bets | 3.3% | Folds: -7.5bb |
| Calls | 6.9% | 15bb pot, out of position: roughly -4bb (see below) |

- **Called pots:** sample junk hands (96o, Q4o, T8s, J2o, 55, A3o, K9o, 76s) average 30% equity against v0's calling range. Assuming about 25% of the pot is realised out of position gives roughly -4bb.
- **EV:** 0.898 × 2.5 - 0.033 × 7.5 - 0.069 × 4 ≈ +1.7bb per v0 open. Folding the BB instead would be -1bb.
- **Per 100 hands:** v0 opens 46% of its 50 SB hands, so about 23 times. That's ≈ +40 bb/100 for the exploiter.
- The postflop part is an assumption. The harness will give the real figure.

### A.4 Always-jam bot at 100bb

The jammer shoves any two cards: as SB first in, and as BB over any open or limp. All values are in bb, relative to the start of the hand.
- Calling a jam: EV = 200 × equity - 100.
- Folding: -1 in the BB, -0.5 for an SB fold, -2.5 for an SB open then fold.
- A call is +EV when equity is above 49.5%.

| Seat | v0's play | v0 EV per hand | Best response | Best EV per hand |
|---|---|---|---|---|
| BB | Calls with its 41.5% continue range | +6.86bb | Call iff equity ≥ 49.5% | +7.55bb |
| SB | Opens 46%, continues vs the jam with 62 of its 610 combos | +0.77bb | Enter every hand with equity ≥ 49.5% and call, fold the rest | +7.80bb |

- **Per 100 hands (50 in each seat):** v0 makes 382 bb/100, the best response 767 bb/100.
- **Bad calls:** 32 of v0's 550 BB calling combos (6%) are -EV even against any two cards.

### A.5 Jammer with only its top 10%

- **Jam range:** `top_percent_range(0.10)`, ranked by equity against a random hand.
- **Method:** for each class in v0's BB continue range, take the equity of one representative combo against that range (3,000 samples).
- **Result:** averaged over v0's calling combos, EV(call) - EV(fold) is -25.5bb per call.

### A.6 Postflop example

The board is K♥8♠3♣. The "value-raise range" is KK, 88, 33, K8, K3, 83, AK, KQ, KJ, KT and K9, with every suit combo of each. Each figure uses 20,000 samples.

| Hand | v0 class | vs a random hand | vs the value-raise range |
|---|---|---|---|
| K♣7♦ (top pair, weak kicker) | MARGINAL | 0.85 | 0.14 |
| 8♦3♦ (bottom two pair) | STRONG | 0.89 | 0.58 |

Two pair holds up fine here. The leak is in one-pair and overpair hands facing raises.

### A.7 Approximate heads-up push/fold Nash solve

**Method:**
- **Equity matrix:** a 169 × 169 class-vs-class matrix from `core/equity`. Each class is one representative combo, with 1,200 samples per pair, and E[j][i] = 1 - E[i][j].
- **Weights:** combos are weighted 6/4/12, ignoring card removal between classes.
- **Solver:** 3,000 rounds of fictitious play.
- **EVs:** with S as the effective stack in bb, an SB jam is worth P(fold) × 1 + P(call) × (2S × equity - S), and an SB fold -0.5. A BB call is worth 2S × equity - S, and a BB fold -1.

Treat the percentages as approximate, since card removal is ignored.

| Stack | Nash SB jam | v0 jam | Nash BB call | v0 call | v0 loses vs Nash |
|---|---|---|---|---|---|
| 8bb | 62.6% | 40.3% | 44.5% | 32.4% | 3.9 bb/100 |
| 10bb | 57.8% | 40.3% | 37.7% | 32.4% | 1.7 bb/100 |
| 12bb | 52.2% | 24.9% | 32.8% | 17.9% | 8.2 bb/100 |
| 15bb | 45.5% | 24.9% | 27.0% | 17.9% | 4.2 bb/100 |
| 20bb | 40.5% | (24.9%) | 20.8% | (17.9%) | (1.5 bb/100) |

- **Which chart applies:** v0 uses `le10` at 10bb or less and `le15` from 10 to 15bb.
- **The 20bb row:** v0 doesn't play push/fold at 20bb at all, so that row only shows where Nash sits.
- **Exploitability:** a best response to v0's fixed calling ranges gains at most about 0.27bb per SB hand over playing Nash (at 12bb). So these charts aren't a big exploit target either.

### A.8 Rough heads-up baselines

The "Rough HU baseline" column in item 1 is general solver knowledge, not computed here: at 100bb, SB opens ~80%, BB folds ~35-40% vs a 2.5x open, and SB continues ~50% vs a 3-bet. Use them as targets, not exact values.

## Appendix B: code references (v0 at `8c49ad9`)

`bots/v0/bot.py`:

| Line | Symbol | Note |
|---|---|---|
| 46 | `import eval7` | Guarded. Without it, no postflop equity and no postflop bets |
| 59 | `TIME_BUDGET_S = 1.2` | Fixed budget, ignores `time_left_ms` |
| 363 | `_ISO` | 6-max iso-raise charts, used for BB vs a limp |
| 389-392 | `_VS_3BET_4BET`, `_VS_3BET_CALL`, `_VS_4BET_CALL` | Generic 6-max charts, used heads-up |
| 395-398 | `_HU_SB_OPEN`, `_HU_BB_3BET`, `_HU_BB_CALL` | Heads-up deep charts |
| 424, 429 | `_HU_JAM`, `_HU_CALLJAM` | Heads-up push/fold, two tiers |
| 585, 590, 594 | `_open_raise`, `_threebet_raise`, `_fourbet_raise` | 2.5bb, 3x and 2.3x at every depth above 15bb |
| 600 | `_preflop_chart_action` | No opponent stats, no raise size, no all-in check above 15bb |
| 706-708 | `_VALUE_BET_EQ`, `_VALUE_RAISE_EQ`, `_CALL_CUSHION` | 0.58, 0.78, 0.03 |
| 717-719 | `_SPR_COMMIT`, `_STACKOFF_FRAC`, `_STACKOFF_EQ` | 1.5, 0.6, 0.85 |
| 744-746 | `_SHRINK_K`, `_POOL_K`, `_MIN_OBS` | 20, 200, 12 |
| 750 | `_FIXED_PRIOR` | 6-max prior (VPIP 0.45) |
| 835 | `_postflop_overcommit_guard` | MARGINAL hands only |
| 897, 929 | `_fold_entry` | The "faced" counter |
| 978, 983 | `_live_prior` | Pools every `bot_id`, including ours |
| 1000, 1017 | `_opp_rates` | `f23` computed, never used |
| 1022, 1029 | `_classify` | 6-max cutoffs |
| 1100 | `_all_opps_foldy` | The bluff gate |
| 1147 | `_hero_draw` | See Appendix C |

`bots/v0/adapter.py`:

| Line | What |
|---|---|
| 26, 81 | Our actions are logged as `bot_id "me"` |
| 66 | The shove check uses `starting_stack` |
| 94-95 | `my_stack` and `opp_stack` are both derived from `starting_stack` |

`core/interface.py`:

| Line | What |
|---|---|
| 36 | `starting_stack` |
| 41 | `time_left_ms` |
| 57 | `opp_hole_cards` |

## Appendix C: smaller notes from the code read

- `_MIN_OBS = 12` means an opponent gets a label after 12 actions, which is a handful of heads-up hands. Shrinkage (`_SHRINK_K = 20`) softens this, but early labels will flip.
- `_hero_draw` counts straight draws that come only from board cards as our draw, because it doesn't check that a hole card is part of the straight. It only matters when the bluff gate is open.
