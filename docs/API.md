# Contracts

The interfaces between tickets. Code to these, and mock the other side until the real one lands. Changes follow the contract process in `CLAUDE.md`. Status: **v1**. The env ticket (#8) may extend it once the tournament system is known.

All imports are from the repo root (`python -m ...`).

## Cards (`core/cards.py`, captain)
A card is a 2-char string: rank `23456789TJQKA` + suit `cdhs`, e.g. `"As"`, `"Td"`. Adapters convert to and from the environment's format.
```python
RANKS = "23456789TJQKA"; SUITS = "cdhs"
def full_deck() -> list[str]: ...                       # 52 cards, fixed order
def hand_class(hole: tuple[str, str]) -> str: ...       # "AKs", "T9o", "77"
```

## Game types (`core/interface.py`, captain)
```python
from dataclasses import dataclass
from typing import Literal, Protocol

Street = Literal[1, 2, 3, 4]                    # preflop, flop, turn, river

@dataclass(frozen=True)
class LegalActions:
    can_fold: bool
    can_check: bool
    call_amount: int                            # chips to add to call; 0 if checking is possible
    min_raise_to: int | None                    # None = raising not allowed
    max_raise_to: int | None                    # all-in, as a raise_to value

@dataclass(frozen=True)
class ActionRecord:
    street: Street
    actor: Literal["me", "opp"]
    kind: Literal["fold", "check", "call", "raise"]
    raise_to: int | None                        # same semantics as Action.raise_to

@dataclass(frozen=True)
class GameState:
    hand_id: int
    is_button: bool                             # heads-up: button = small blind, acts first preflop, last postflop
    hole_cards: tuple[str, str]
    board: tuple[str, ...]                      # 0, 3, 4 or 5 cards
    street: Street
    small_blind: int
    big_blind: int
    starting_stack: int                         # per player, at the start of this hand
    my_committed: int                           # total chips I've put in THIS HAND (all streets, incl. blind)
    opp_committed: int
    history: tuple[ActionRecord, ...]           # whole hand so far, blinds excluded
    legal: LegalActions
    time_left_ms: int | None = None             # if the environment exposes a clock

@dataclass(frozen=True)
class Action:
    kind: Literal["fold", "check", "call", "raise"]
    raise_to: int | None = None                 # for "raise": my TOTAL commitment for the hand after raising

@dataclass(frozen=True)
class HandResult:
    hand_id: int
    was_button: bool
    my_delta: int                               # chips won (+) or lost (-)
    history: tuple[ActionRecord, ...]           # the complete hand, including actions after my last decision
    board: tuple[str, ...]
    opp_hole_cards: tuple[str, str] | None      # if shown at showdown

@dataclass(frozen=True)
class OpponentStats:                            # None = not enough data yet; consumers must use defaults
    hands: int = 0
    vpip: float | None = None                   # share of hands they voluntarily put chips in preflop
    pfr: float | None = None                    # share of hands they raised preflop
    three_bet: float | None = None              # re-raise preflop when facing a raise
    fold_to_cbet: float | None = None           # fold when the preflop raiser bets the flop
    fold_to_bet: float | None = None            # fold when facing any postflop bet/raise
    aggression: float | None = None             # postflop (bets + raises) / calls
    wtsd: float | None = None                   # share of seen flops that reach showdown
    avg_bet_frac: float | None = None           # average postflop bet size / pot

class Bot(Protocol):
    name: str
    def new_match(self, match_id: str, opponent: str | None) -> None: ...
    def act(self, state: GameState) -> Action: ...       # must return a legal Action, never raise
    def hand_over(self, result: HandResult) -> None: ...

def clamp_to_legal(action: Action, legal: LegalActions) -> Action: ...   # nearest legal action; check > call > fold
```

## Bot registry (`bots/__init__.py`, captain)
`make_bot(name: str, **cfg) -> Bot`. Names: `main` (`bots/main/bot.py: MainBot`), `v0` (`bots/v0/adapter.py: V0Bot`, #14), plus the harness opponents `random`, `always_call`, `always_raise_pot`. Imports are lazy, so one broken bot doesn't break the others. An unknown name raises `ValueError`.

## Equity (`core/equity.py`, #10)
```python
Range = dict[tuple[str, str], float]   # opponent combo (higher card first) -> weight >= 0, not necessarily normalised

def equity(hole: tuple[str, str], board: tuple[str, ...], opp_range: Range | None = None,
           samples: int = 2000, time_budget_ms: float | None = None, seed: int | None = None) -> float: ...
    # P(win) + P(tie)/2 against one opponent hand drawn from opp_range (dead cards removed),
    # board completed at random. None = any two cards. Stops early at time_budget_ms.
def rank7(cards: tuple[str, ...]) -> int: ...      # 5–7 cards → strength; higher is better; equal = tie
def range_from_classes(classes: dict[str, float]) -> Range: ...   # {"AKs": 1.0, "22": 0.5} → combos
def top_percent_range(pct: float) -> Range: ...    # strongest pct (0–1) of starting hands by preflop equity
```
Performance target: `equity(..., samples=2000)` under 20 ms on a laptop.

## Strategy modules (`bots/main/`)
```python
# preflop.py (#11)
def preflop_action(state: GameState, opp: OpponentStats) -> Action: ...

# postflop.py (#12)
def postflop_action(state: GameState, opp: OpponentStats, opp_range: Range | None) -> Action: ...

# opponent.py (#13)
class OpponentModel:
    def __init__(self) -> None: ...
    def observe_hand(self, result: HandResult) -> None: ...      # call once per finished hand
    def stats(self) -> OpponentStats: ...
    def range_estimate(self, state: GameState) -> Range | None: ...   # opponent's likely holdings now; None = unknown
    def bluff_rate(self) -> float | None: ...                    # share of their big (>= 2/3 pot) postflop bets shown down as bluffs
def classify(stats: OpponentStats) -> str: ...                   # "station" | "maniac" | "nit" | "tag" | "unknown"

# fallback.py (#5)
def fallback_action(state: GameState) -> Action: ...             # no imports beyond core; < 1 ms; always legal

# bot.py (#5)
class MainBot:   # implements Bot; wires the above with a time guard, clamp_to_legal and fallback
    def __init__(self, time_budget_ms: int = 500, **cfg): ...
```
Strategy functions may return any Action. `MainBot` clamps it to legal. They should still aim to be legal and must not mutate their inputs.

## Harness result (`harness/`, #6)
CLI: `python -m harness.run --a <bot> --b <bot> --hands N --seed S [--duplicate] [--stack 200 --bb 2] [--a-cfg k=v ...]`
It appends one JSON object per match to `results/<date>.jsonl` (gitignored) and prints one summary line:
```json
{"bot_a": "main@abc123", "bot_b": "always_call@abc123", "hands": 10000, "duplicate": true,
 "seed": 42, "stack_bb": 100, "bb_per_100": 12.3, "ci95": 4.1, "a_ms_avg": 3.2, "a_ms_max": 41,
 "b_ms_avg": 0.1, "b_ms_max": 2, "illegal_a": 0, "illegal_b": 0, "errors_a": 0, "errors_b": 0}
```
The harness also exposes `play_match(bot_a, bot_b, hands, seed, duplicate, stack, bb) -> dict` (that same dict) for use in tests and tuning scripts.
