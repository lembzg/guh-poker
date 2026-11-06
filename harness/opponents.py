"""Baseline opponents for the harness (#6). Each implements the Bot protocol from docs/API.md."""
from __future__ import annotations

import random

from core.equity import RANKS
from harness._types import Action, GameState, HandResult


def _raise_or_call(state: GameState, raise_to: int) -> Action:
    lg = state.legal
    if lg.min_raise_to is not None:
        return Action("raise", max(lg.min_raise_to, min(int(raise_to), lg.max_raise_to)))
    return Action("check") if lg.can_check else Action("call")


def _pot_raise_to(state: GameState, frac: float = 1.0) -> int:
    """raise_to for a raise of `frac` x the pot after calling."""
    call = max(0, state.opp_committed - state.my_committed)
    pot_after_call = state.my_committed + state.opp_committed + call
    return state.opp_committed + int(round(frac * pot_after_call))


class _Base:
    name = "base"

    def new_match(self, match_id: str, opponent: str | None) -> None:
        pass

    def hand_over(self, result: HandResult) -> None:
        pass


class RandomBot(_Base):
    """Uniform over the legal action kinds; raise sizes uniform in [min, max]."""
    name = "random"

    def __init__(self, seed: int | str | None = 0):
        self._seed = seed
        self._rng = random.Random(seed)

    def new_match(self, match_id: str, opponent: str | None) -> None:
        self._rng = random.Random(f"{self._seed}:{match_id}")

    def act(self, state: GameState) -> Action:
        lg = state.legal
        kinds = ["check"] if lg.can_check else ["fold", "call"]
        if lg.min_raise_to is not None:
            kinds.append("raise")
        kind = self._rng.choice(kinds)
        if kind == "raise":
            return Action("raise", self._rng.randint(lg.min_raise_to, lg.max_raise_to))
        return Action(kind)


class AlwaysCall(_Base):
    """Checks when it can, otherwise calls. Never folds or raises."""
    name = "always_call"

    def act(self, state: GameState) -> Action:
        return Action("check") if state.legal.can_check else Action("call")


class AlwaysRaisePot(_Base):
    """Raises the size of the pot every time it can, otherwise calls."""
    name = "always_raise_pot"

    def act(self, state: GameState) -> Action:
        return _raise_or_call(state, _pot_raise_to(state))


class HackathonBot(_Base):
    """A typical simple hackathon bot. Preflop: raises 3x with a pocket pair or a T+ card, folds the rest.
    Postflop: bets 2/3 pot with a pair or better that uses a hole card, otherwise check/fold."""
    name = "hackathon"

    def act(self, state: GameState) -> Action:
        lg = state.legal
        h1, h2 = (RANKS.index(c[0]) for c in state.hole_cards)
        if state.street == 1:
            strong = h1 == h2 or max(h1, h2) >= RANKS.index("T")
            size = 3 * max(state.opp_committed, state.big_blind)
        else:
            board_ranks = {RANKS.index(c[0]) for c in state.board}
            strong = h1 == h2 or h1 in board_ranks or h2 in board_ranks
            size = _pot_raise_to(state, 2 / 3)
        if strong:
            return _raise_or_call(state, size)
        return Action("check") if lg.can_check else Action("fold")


OPPONENTS = {
    "random": RandomBot,
    "always_call": AlwaysCall,
    "always_raise_pot": AlwaysRaisePot,
    "hackathon": HackathonBot,
}
