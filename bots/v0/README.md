# v0: "Quant", our existing bot

Our entry from the Fullhouse hackathon, a 6-max no-limit hold'em event that shrank to heads-up as bots busted. `bot.py`, `BOT_README.md` and `data/preflop.json` are byte-for-byte copies of `bots/mybot/` from that project. **Don't edit them.** They exist so we can measure v0 and reuse parts of it. `adapter.py` runs it behind our `Bot` interface.

## Strategy

**Preflop** is an O(1) chart lookup by position, what it's facing, and stack depth. Spots the charts don't cover fall through to the equity logic. The rows below show what it uses heads-up.

| Spot | Action |
|---|---|
| Effective stack ≤ 15bb | Jam or fold from `HU_JAM`; call a shove from `HU_CALLJAM`. Tiers: ≤ 10bb and 10–15bb |
| Button, unopened | Raise 46% of hands to 2.5bb, fold the rest. It never limps |
| Big blind, facing a limp | Raise the `ISO` chart to 2.5bb + 1bb per limper, otherwise check |
| Big blind, facing a raise | 3-bet 15% of hands to 3x, call 27%, fold the rest |
| Facing a 3-bet | 4-bet `KK+, AKs, A5s` to 2.3x, call `QQ-TT, AQs, AJs, KQs, AKo`, fold the rest |
| Facing a 4-bet | Call `QQ+, AKs, AKo`, fold the rest |

**Postflop** starts from Monte-Carlo equity against one random hand, using `eval7`: 1,500 samples on the flop, 2,000 on the turn, 2,500 on the river.

1. It classifies the hand as STRONG (two pair or better), MEDIUM (overpair, or top pair with a J+ kicker), MARGINAL (weaker pairs) or WEAK (high card).
2. A guard stops a MARGINAL hand stacking off when deep. If a call would cost ≥ 60% of the stack with SPR > 1.5 and equity < 85%, it folds.
3. Checked to: bet STRONG and MEDIUM at equity ≥ 58%. Bet MARGINAL likewise, but only on dry boards.
4. Facing a bet: raise STRONG and MEDIUM at equity ≥ 78%, and call when equity ≥ pot odds + 3%. MARGINAL's call bar also moves with board texture and SPR.

**Bet sizes** are 45% of the pot on dry boards and 70% on wet ones, added on top of the current bet. Opponent adjustments can move that within 25–125%.

**Opponent modelling** tracks VPIP, PFR, aggression and fold-to-bet from the action log, shrunk toward a prior. After 12 observed actions it labels the opponent:

| Label | Adjustment |
|---|---|
| Station | Thinner, bigger value bets; fold more to their raises |
| Maniac | Call down wider |
| Nit | Smaller value bets, fold more to their bets |
| TAG or unknown | No change |

Bluffs are **off by default**. It semi-bluffs and c-bets only once the opponent looks like a folder, and it never bluffs all-in.

**Safety:** it works out a legal pot-odds fallback before any Monte Carlo, stops sampling at a 1.2 s budget, and catches all exceptions.

## Running it

Through the adapter, from the repo root (needs `core/interface.py`, #4):
```python
from bots.v0.adapter import V0Bot
bot = V0Bot(seed=1)       # seed is optional and makes Monte Carlo reproducible
bot.new_match("m1", None)
action = bot.act(state)   # GameState -> Action, see docs/API.md
```

Standalone, without our interface:
```python
from bots.v0.bot import decide
decide({"street": "preflop", "your_cards": ["As", "Ah"], "community_cards": [], "pot": 150,
        "your_stack": 9950, "amount_owed": 50, "can_check": False, "current_bet": 100,
        "your_bet_this_street": 50, "min_raise_to": 200, "seat_to_act": 0,
        "players": [{"seat": 0, "bot_id": "me", "stack": 9950, "bet_this_street": 50, "is_folded": False},
                    {"seat": 1, "bot_id": "opp", "stack": 9900, "bet_this_street": 100, "is_folded": False}],
        "action_log": [{"seat": 0, "action": "small_blind"}, {"seat": 1, "action": "big_blind"}],
        "match_action_log": []})
# -> {"action": "raise", "amount": 250}
```

## Input and output

`decide(state: dict) -> dict`. Amounts are chips, and `*_bet*`, `min_raise_to` and `amount` count **this street only**. `GameState` counts the whole hand, which is the main thing the adapter converts.

| Field | Meaning |
|---|---|
| `street` | `"preflop"`, `"flop"`, `"turn"` or `"river"` |
| `your_cards`, `community_cards` | Card strings such as `"As"`, the same format as ours |
| `pot` | All chips in the pot, including this street's bets |
| `your_stack` | Chips behind |
| `amount_owed`, `can_check` | Chips to call, and whether checking is possible |
| `current_bet`, `your_bet_this_street` | Highest bet this street, and my bet this street |
| `min_raise_to` | Smallest legal raise, as a total for this street |
| `seat_to_act` | My seat |
| `players` | Each player's `seat`, `bot_id`, `stack`, `bet_this_street`, `is_folded` |
| `action_log` | This hand, including blinds: `{"seat", "action"}` |
| `match_action_log` | Last 200 voluntary actions of the match: `{"hand_num", "bot_id", "seat", "action"}` |

The reply is `{"action": "fold" | "check" | "call" | "all_in"}` or `{"action": "raise", "amount": <total this street>}`.

## Dependencies

`eval7`, plus the standard library. It builds and imports on Python 3.12. If it's missing, `bot.py` still plays legally, but it never bets postflop, because it loses both equity and hand classes.

`eval7` is outside our default of pure Python plus numpy, so using it in `bots/main` needs a `decision` issue.

## What the adapter does

- **Private module copy per `V0Bot`.** `bot.py` keeps its opponent model in module globals, so v0 vs v0 would otherwise share one. `new_match` loads a fresh copy.
- **Big blind.** `bot.py` hardcodes `_BB = 100`, and the adapter sets it from the state. Without this, a 2-chip-blind game would read a 100bb stack as 2bb, and the bot would play jam-or-fold every hand.
- **`match_action_log`** is rebuilt from `history` and `HandResult`.
- **All-in calls are logged as calls.** Fullhouse logged them as `all_in`, which `bot.py` counts as aggression, so opponents here read slightly less aggressive than they did there.

Measured on the real Fullhouse engine, v0 vs v0, 3,000 heads-up hands at 9–100bb: all 5,918 decisions matched the same bot fed directly by the engine, and none was illegal. Adapter plus bot took 1.0 ms on average, 4.3 ms at p99 and 36 ms at most. That was a one-off check, not a test in this repo, and those decisions used the stub `clamp_to_legal`.

## Known weaknesses

From reading the code. None of these has been measured heads-up yet.

- **Overfolds to 3-bets.** It opens 46% of hands on the button but continues with only 10% of those against a 3-bet, because that spot uses the 6-max chart rather than a heads-up one. An opponent who 3-bets often wins a lot of pots uncontested. It also continues with only 17% of its own 3-bets against a 4-bet.
- **Equity ignores the opponent's range.** It computes equity against a random hand, even after they've shown strength, with only a 3% cushion on calls. Two pair or better can overcall, and the guard only covers one-pair hands.
- **Readable and passive by default.** With no bluffs until an opponent is labelled a folder, its bets are almost always value. No preflop mixing either: a given spot and hand always gets the same action.
- **Tuned for a different field.** Its thresholds and the prior behind the opponent labels came from a 6-max hackathon field described as loose-passive and over-folding.
- **Limited opponent reads.** It has no street information or showdown cards, so it can't use `HandResult.opp_hole_cards` or tell a flop bet from a river bet.
- **Ignores `time_left_ms`.** It always uses its fixed 1.2 s ceiling. Real decisions take far less, but a shorter tournament clock would need a change.
