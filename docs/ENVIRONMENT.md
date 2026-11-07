# Tournament environment: reverse-engineering notes

_Whoever holds the `env` ticket owns this file. Everyone else adds findings by commenting on that ticket, or with a tiny direct commit if the finding is obviously right._

**Sources (read 2026-11-06 by EulaBet):** site https://poker-arena-site.vercel.app (guide = `data/submitting.md`, event = `data/event.json`; phase `registration`, 0 teams) and the public engine repo https://github.com/Manchester-AI-Society/poker_bot_infrastructure @ `8b89346` (`player_sdk/`, `game/`, `arena/`). Clone it to run `python -m arena validate|match|pack` locally.

Record **observed facts** with how you verified them: "sent a raise of 1 chip below the min-raise → server replied `ERR invalid`". Keep guesses in a separate section.

## Protocol
- Transport: in-process Python call. The arena loads our pickled `PokerBot` object in its own process and calls `act(game_state)` once per decision (`player_sdk/bot_interface.py`). **`act` is the only hook**: no new-match, no hand-over callback.
- `GameState` (`player_sdk/models.py`): `hole_cards`, `community_cards` (codes like `AS`, `TD`: **upper-case suits**), `pot_size` (incl. this round's bets), `stack_sizes`, `current_bets` (this round), `call_amount`, `minimum_raise`, `min_raise_to`, `max_raise_to` (all-in), `legal_actions` (`fold/check/call/bet/raise_to`), `my_index`, `dealer_index` (heads-up dealer = small blind), `street`, `small_blind`, `big_blind`, `folded`, `all_in`, `player_ids`, `action_history` (this hand only: `player_id`, `action`, `amount`, `street`). Helpers: `my_stack`, `my_bet`, `is_dealer`, `can(action)`, `can_raise`, `can_bet`.
- Actions: `Response.fold()`, `Response.call()` (= check when nothing is owed), `Response.raise_to(total)` where **total = our chips in this betting round** (street total), `Response.all_in()`.
- Hand result / opponent cards: **not reported to the bot.** We only see what `action_history` shows at our next turn. A fold by the opponent after our last bet, and every showdown, are invisible; they must be inferred when the next hand starts.

## Rules as enforced (vs rules as written)
- Min-raise / all-in edge cases: `game/action_engine.py` (`min_raise_to`, `runtime.min_raise_size`). Not yet tested against our harness engine.
- Time-out behaviour: 1 s per move is a fault; separate thinking bank 0.2 s × deals per half (`arena/duel.py: think_budget_per_deal`); overdraw → always-fold stub for the match.
- **Format (organisers, final, 2026-11-07 ~16:00): round 1 all-vs-all 400 hands (200 deals × 2 seats); top 5 play 1200 hands (600 deals).** Bank 40 s / 120 s per half. Bot startup (spawn + unpickle) is timed inside the first move. Broadcast shows the biggest-swing hands.
- Illegal-action behaviour: fault → check, else fold; 20 faults → always-fold stub for the match.
- Built-in opponents for `python -m arena match`: `call`, `fold`, `random`, `shove`.

## Mapping to our contract
How each environment field maps to `GameState` / `Action` in `docs/API.md`. Note any field the contract is missing.
- Cards: theirs `AS` → ours `As` (lower-case the suit).
- `raise_to`: theirs is a **street** total, ours a **hand** total → `their = ours - (my chips committed on earlier streets)`.
- `is_button` = `my_index == dealer_index`; `street` string → 1-4; `my_committed`/`opp_committed` = earlier streets (from `action_history`) + `current_bets`.
- `HandResult` / `new_match` have no source: the adapter must detect a new hand (fresh `action_history`/hole cards) and synthesise the previous hand's result from what it saw; `opp_hole_cards` is always None.

## Implications for our code (EulaBet, 2026-11-06)
1. **No numpy at play time.** `core/equity.py` (numpy evaluator), `bots/main/opponent.py`, `bots/main/ev.py` must get pure-Python paths. `rank7`/`_rank_ints` are already pure Python.
2. **No eval7** → v0's postflop equity is disabled in the tournament (it never bets postflop without it).
3. **Time:** 1 s per move hard; average budget 0.2 s per deal ≈ 50 ms per decision. Pure-Python Monte Carlo of ~1000 samples fits.
4. **Short matches:** 200 (round 1) / 600 (final) hands per opponent per half, model reset each half → solid defaults matter more than slow-converging exploits; `bluff_rate` never learns (no showdown cards).
5. **Packaging:** everything must import from helper `.py` files next to `bot.py`, and data (e.g. `core/data/preflop_ranking.json`) must be embedded or loaded in `__init__`.

## Verified locally (EulaBet, 2026-11-07, their repo @8b89346, Python 3.14, no numpy)
- `python -m adapters.arena.build --team <name>` builds a folder that `arena validate` accepts (40 hands vs @call, 0 faults) and `arena pack` turns into a 243 KB `.pkl`.
- History entries seen in practice: `post_small_blind`, `post_big_blind`, `fold`, `check`, `call` (amount = chips added), `bet` / `raise_to` (amount = street total). Player ids `seat0`/`seat1`; `dealer_index` = small blind.
- Their engine allows `fold` even when checking is free (our adapter turns such a fold into a check).
- `arena match` results for MainBot (current main, fallback preflop), 300 deals = 600 hands: vs @call +2.66 bb/hand, @random +6.76, @shove +2.93, @fold +0.38, starter +0.51 (n.s.). Vs starter, 1000 deals seed 5: +0.03 (CI -0.71..+0.77) without the opponent model; **+0.55 (CI +0.00..+1.10) with #19**. Think time ~10 ms per hand (bank allows 200 ms).

## Exploitable observations
Anything about the environment or the likely opponents we could use: deterministic deck seeds, fixed hand counts, time budget slack, opponent tendencies.

## Open questions
