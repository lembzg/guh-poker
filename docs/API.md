# Contracts

The interfaces between tickets. Code to these. Mock the other side until the real one lands. Changes follow the contract process in `CLAUDE.md`. Status: **draft v0**. The captain confirms it in the interface ticket, and the env ticket may extend it once the tournament system is known.

## Cards
A card is a 2-char string: rank `23456789TJQKA` + suit `cdhs`, e.g. `"As"`, `"Td"`. This matches ACPC. Adapters convert to and from any other format.

## Bot interface (`src/bots/interface.py`, owned by the captain)
```python
from dataclasses import dataclass, field
from typing import Literal, Protocol

Street = Literal[1, 2, 3, 4]                    # preflop, flop, turn, river (upstream numbering)

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
    is_button: bool                             # heads-up: button = small blind, acts first preflop
    hole_cards: tuple[str, str]
    board: tuple[str, ...]                      # 0, 3, 4 or 5 cards
    street: Street
    small_blind: int
    big_blind: int
    starting_stack: int                         # per player, at the start of this hand
    my_committed: int                           # total chips I've put in THIS HAND (all streets)
    opp_committed: int
    history: tuple[ActionRecord, ...]           # whole hand, blinds excluded
    legal: LegalActions
    time_left_ms: int | None = None             # if the environment exposes a clock

@dataclass(frozen=True)
class Action:
    kind: Literal["fold", "check", "call", "raise"]
    raise_to: int | None = None                 # for "raise": my TOTAL commitment for the hand after raising (ACPC semantics)

@dataclass(frozen=True)
class HandResult:
    hand_id: int
    my_delta: int                               # chips won (+) or lost (-)
    opp_hole_cards: tuple[str, str] | None      # if shown
    board: tuple[str, ...]

class Bot(Protocol):
    name: str
    def new_match(self, match_id: str, opponent: str | None) -> None: ...
    def act(self, state: GameState) -> Action: ...       # must return a legal Action
    def hand_over(self, result: HandResult) -> None: ... # for opponent modelling; may be a no-op
```
Rules:
- `act` must **never raise an exception or return an illegal action**. Adapters still clamp and fall back to check/call (or fold) if a bot misbehaves, and they log it.
- Bots are created with no arguments, or from a dict config via `make_bot(name: str, **cfg) -> Bot` in `src/bots/__init__.py`.

## Harness result (`src/harness/`)
One JSON object per match, appended to `results/*.jsonl` (gitignored), and printed as one summary line:
```json
{"bot_a": "deepstack@abc123", "bot_b": "baseline@abc123", "hands": 10000, "duplicate": true,
 "seed": 42, "bb_per_100": 12.3, "ci95": 4.1, "a_ms_avg": 850, "a_ms_max": 4100,
 "b_ms_avg": 2, "b_ms_max": 9, "illegal_a": 0, "illegal_b": 0, "errors_a": 0, "errors_b": 0}
```
CLI: `cd src && python -m harness.run --a <bot> --b <bot> --hands N --seed S [--duplicate] [--stack 200 --bb 2]`.

## Large artifacts
`tools/fetch_artifacts.sh` (owned by the captain once the first artifact exists) downloads release assets into the upstream paths (`data/models/<street>/final_cpu.tar`, `src/nn/bucketing/...`, etc.). Each artifact ticket adds its own entries to the manifest `tools/artifacts.txt`, one per line: `<release-tag> <asset-name> <dest-path> <sha256>`.
