"""Baseline opponents for the harness (#6). Each implements the Bot protocol from docs/API.md."""
from __future__ import annotations

import random

from core.equity import RANKS, SUITS, equity, top_percent_range
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


class AlwaysJam(_Base):
    """All-in at every decision; calls when it can't raise."""
    name = "always_jam"

    def act(self, state: GameState) -> Action:
        lg = state.legal
        if lg.max_raise_to is not None:
            return Action("raise", lg.max_raise_to)
        return Action("check") if lg.can_check else Action("call")


class JamTop(_Base):
    """Jams its top `pct` of hands preflop (by equity vs random) and folds/checks everything else;
    calls any bet with those hands postflop."""
    name = "jam_top"

    def __init__(self, pct: float = 0.10):
        self.pct = pct
        self._range = set(top_percent_range(pct))

    def act(self, state: GameState) -> Action:
        lg = state.legal
        a, b = state.hole_cards
        combo = (a, b) if (RANKS.index(a[0]), SUITS.index(a[1])) > (RANKS.index(b[0]), SUITS.index(b[1])) else (b, a)
        if combo not in self._range:
            return Action("check") if lg.can_check else Action("fold")
        if state.street == 1 and lg.max_raise_to is not None:
            return Action("raise", lg.max_raise_to)
        return Action("check") if lg.can_check else Action("call")


class MinRaiser(_Base):
    """Min-raises any two cards whenever it can, otherwise checks/calls."""
    name = "min_raiser"

    def act(self, state: GameState) -> Action:
        lg = state.legal
        if lg.min_raise_to is not None:
            return Action("raise", lg.min_raise_to)
        return Action("check") if lg.can_check else Action("call")


class ThreeBetAny(_Base):
    """Preflop: opens to 2.5bb and 3-bets to 3x with any two cards, folds to a 4-bet.
    Postflop: c-bets half pot on the flop as the preflop aggressor; continues only with a pair or better."""
    name = "three_bet_any"

    def act(self, state: GameState) -> Action:
        lg = state.legal
        pre = [a for a in state.history if a.street == 1]
        my_raises = sum(a.actor == "me" and a.kind == "raise" for a in pre)
        if state.street == 1:
            if my_raises:
                return Action("check") if lg.can_check else Action("fold")      # facing a 4-bet
            if not pre and state.is_button:
                return _raise_or_call(state, int(2.5 * state.big_blind))       # open
            if any(a.actor == "opp" and a.kind == "raise" for a in pre):
                return _raise_or_call(state, 3 * state.opp_committed)          # 3-bet
            return _raise_or_call(state, 3 * state.big_blind)                  # raise the limp
        h1, h2 = (RANKS.index(c[0]) for c in state.hole_cards)
        made = h1 == h2 or bool({h1, h2} & {RANKS.index(c[0]) for c in state.board})
        if lg.can_check:
            last_pre_raiser = next((a.actor for a in reversed(pre) if a.kind == "raise"), None)
            flop_bets = any(a.street == 2 and a.kind == "raise" for a in state.history)
            if state.street == 2 and last_pre_raiser == "me" and not flop_bets:
                return _raise_or_call(state, _pot_raise_to(state, 0.5))
            return Action("check")
        return Action("call") if made else Action("fold")


class EquityBot(_Base):
    """The typical LLM-written bot: equity vs a random hand against pot odds.
    Raises 2/3 pot at >= 65% equity, bets half pot when checked to at >= 55%, calls when equity beats
    the pot odds by 5 points, else checks/folds."""
    name = "equity_bot"

    def __init__(self, samples: int = 300):
        self.samples = samples

    def act(self, state: GameState) -> Action:
        lg = state.legal
        eq = equity(state.hole_cards, state.board, None, samples=self.samples, seed=state.hand_id)
        if eq >= 0.65 and lg.min_raise_to is not None:
            return _raise_or_call(state, _pot_raise_to(state, 2 / 3))
        if lg.can_check:
            if eq >= 0.55 and lg.min_raise_to is not None:
                return _raise_or_call(state, _pot_raise_to(state, 0.5))
            return Action("check")
        pot = state.my_committed + state.opp_committed
        return Action("call") if eq >= lg.call_amount / (pot + lg.call_amount) + 0.05 else Action("fold")


class PostflopJammer(_Base):
    """Loose-passive preflop (calls anything, raises the top 20% to 3x), then shoves postflop with any pair
    that uses a hole card, two overcards to the board, or a flush / open-ended straight draw; otherwise
    check/fold. Tests how we defend against frequent postflop all-ins we can't see the cards of."""
    name = "jam_postflop"

    def __init__(self):
        self._top = set(top_percent_range(0.20))

    def act(self, state: GameState) -> Action:
        lg = state.legal
        a, b = state.hole_cards
        if state.street == 1:
            combo = (a, b) if (RANKS.index(a[0]), SUITS.index(a[1])) > (RANKS.index(b[0]), SUITS.index(b[1])) else (b, a)
            if combo in self._top and lg.min_raise_to is not None and state.opp_committed <= 3 * state.big_blind:
                return _raise_or_call(state, 3 * max(state.opp_committed, state.big_blind))
            return Action("check") if lg.can_check else Action("call")
        if self._wants_it(state):
            if lg.max_raise_to is not None:
                return Action("raise", lg.max_raise_to)
            return Action("check") if lg.can_check else Action("call")
        return Action("check") if lg.can_check else Action("fold")

    @staticmethod
    def _wants_it(state: GameState) -> bool:
        hole = [RANKS.index(c[0]) for c in state.hole_cards]
        board = [RANKS.index(c[0]) for c in state.board]
        if hole[0] == hole[1] or set(hole) & set(board):
            return True
        if len(board) < 5 and min(hole) > max(board):
            return True                                          # two overcards
        if len(board) < 5:
            suits = [c[1] for c in state.hole_cards + state.board]
            if any(suits.count(s) >= 4 for s in {c[1] for c in state.hole_cards}):
                return True                                      # flush draw
            ranks = set(hole + board)
            if any(all(r in ranks for r in range(lo, lo + 4)) and set(range(lo, lo + 4)) & set(hole)
                   for lo in range(0, 10)):
                return True                                      # four to a straight
        return False


OPPONENTS = {
    "random": RandomBot,
    "always_call": AlwaysCall,
    "always_raise_pot": AlwaysRaisePot,
    "hackathon": HackathonBot,
    "always_jam": AlwaysJam,
    "jam_top": JamTop,
    "min_raiser": MinRaiser,
    "three_bet_any": ThreeBetAny,
    "equity_bot": EquityBot,
    "jam_postflop": PostflopJammer,
}
