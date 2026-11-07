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
4. **Short matches:** ≤ 200 hands per opponent per half, model reset each half → solid defaults matter more than slow-converging exploits; `bluff_rate` never learns (no showdown cards).
5. **Packaging:** everything must import from helper `.py` files next to `bot.py`, and data (e.g. `core/data/preflop_ranking.json`) must be embedded or loaded in `__init__`.

## Verified locally (EulaBet, 2026-11-07, their repo @8b89346, Python 3.14, no numpy)
- `python -m adapters.arena.build --team <name>` builds a folder that `arena validate` accepts (40 hands vs @call, 0 faults) and `arena pack` turns into a 243 KB `.pkl`.
- History entries seen in practice: `post_small_blind`, `post_big_blind`, `fold`, `check`, `call` (amount = chips added), `bet` / `raise_to` (amount = street total). Player ids `seat0`/`seat1`; `dealer_index` = small blind.
- Their engine allows `fold` even when checking is free (our adapter turns such a fold into a check).
- `arena match` results for MainBot (current main, fallback preflop), 300 deals = 600 hands: vs @call +2.66 bb/hand, @random +6.76, @shove +2.93, @fold +0.38, starter +0.51 (n.s.). Vs starter, 1000 deals seed 5: +0.03 (CI -0.71..+0.77) without the opponent model; **+0.55 (CI +0.00..+1.10) with #19**. Think time ~10 ms per hand (bank allows 200 ms).

## Exploitable observations
Anything about the environment or the likely opponents we could use: deterministic deck seeds, fixed hand counts, time budget slack, opponent tendencies.

## Building the combined candidate (#34)

The default `python -m adapters.arena.build --team NAME` still builds MainBot.
The gauntlet's `--bot <harness opponent>` and positional `build(team, out, bot)` API are preserved;
the combined strategy requires the default `--bot main`.
For #32's table-driven preflop plus MainBot's postflop and opponent model, use:

```bash
python -m adapters.arena.build --team NAME --strategy combo --preflop-dir /path/to/preflop-checkout/bots/myteam
# From the infrastructure checkout, using its Python 3.14 environment:
python -m arena validate /absolute/path/to/guh-poker/results/arena/NAME
python -m arena pack /absolute/path/to/guh-poker/results/arena/NAME --team NAME --out /path/to/submissions
python -c 'from pathlib import Path; from arena.package import unpack; unpack(Path("/path/to/submissions/NAME.pkl"), Path("/path/to/packed-check"))'
python -m arena match /path/to/packed-check call --deals 200 --seed 101
```

Until #32 merges, `--preflop-dir` points to its checkout; once `bots/myteam` is present locally,
the flag can be omitted. The builder copies `opponent.py`, `preflop.py`, `ranges.py`, and
`equity_table.py` into the output alongside the MainBot modules. Missing combined dependencies
fail before replacing an existing build. No offline generator, numpy or eval7 is required to play.
`arena match` consumes source or the inner `bot.pkl`; the uploaded `NAME.pkl` is an envelope.
The unpack step above extracts that payload for a source-independent match. `arena pack` also
automatically validates the packed payload in a fresh process.

`ArenaAdapter.observe(gs, response)` records a decision made by the external preflop strategy
without invoking MainBot's preflop strategy. `from_response` converts street raise totals back
to hand totals; subsequent postflop decisions and completed-hand observations use the same adapter.
The combined wrapper records safe fallback actions too, and bookkeeping failures do not replace
an action that has already been recorded. Opponent cards remain unavailable, and hand-end folds
are inferred with the limitations described above. The final hand has no subsequent callback.

This is an integration candidate with unchanged strategy thresholds. The prototype's single-seed,
long-match results do not establish a tournament-length improvement. Compare variants on identical
duplicate deals across independent short matches, and confirm selected parameters on fresh seeds.

## Open questions
