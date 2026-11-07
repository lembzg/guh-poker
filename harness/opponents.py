"""Baseline opponents for the harness (#6). Each implements the Bot protocol from docs/API.md."""
from __future__ import annotations

import random

from core.equity import RANKS, SUITS, equity, rank7, top_percent_range
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


# ---------------------------------------------------------------- research archetypes (#49)
# The deep-research report's forecast field (section 6 pseudo-code): starter clones ~35%, MC/pot-odds ~20%,
# TAG/value ~15%, passive stations ~10%, maniacs ~10%, solver-lite ~10%. Equity is vs a random hand, as these
# bots compute it; samples are kept small so they also run fast in the organisers' engine.

def _eq_random(state: GameState, samples: int = 200) -> float:
    return equity(state.hole_cards, state.board, None, samples=samples,
                  seed=state.hand_id * 31 + len(state.history))


def _pot_odds(state: GameState) -> float:
    call = state.legal.call_amount
    return call / (state.my_committed + state.opp_committed + call) if call else 0.0


def _raise_mult_of_bet(state: GameState, mult: float) -> int:
    """raise_to for 'raise to mult x the current bet' (their street bet ~= our call amount)."""
    return state.my_committed + int(round(mult * max(state.legal.call_amount, state.big_blind)))


def _passive(state: GameState, call_ok: bool) -> Action:
    lg = state.legal
    if lg.can_check:
        return Action("check")
    return Action("call") if call_ok else Action("fold")


class StarterClone(_Base):
    """Starter-clone threshold bot: raise 2.5x at >= 0.78, call at >= pot odds + 0.10, bet 2/3 pot at >= 0.75."""
    name = "starter_clone"

    def act(self, state: GameState) -> Action:
        eq = _eq_random(state)
        if not state.legal.can_check:
            if eq >= 0.78:
                return _raise_or_call(state, _raise_mult_of_bet(state, 2.5))
            return _passive(state, eq >= _pot_odds(state) + 0.10)
        if eq >= 0.75:
            return _raise_or_call(state, _pot_raise_to(state, 0.67))
        return Action("check")


class MCPotOdds(_Base):
    """Monte-Carlo / pot-odds bot: raise 2/3 pot at > 0.72, call at > pot odds + 0.03, bet 2/3 pot at > 0.65."""
    name = "mc_potodds"

    def act(self, state: GameState) -> Action:
        eq = _eq_random(state)
        if not state.legal.can_check:
            if eq > 0.72:
                return _raise_or_call(state, _pot_raise_to(state, 0.67))
            return _passive(state, eq > _pot_odds(state) + 0.03)
        if eq > 0.65:
            return _raise_or_call(state, _pot_raise_to(state, 0.67))
        return Action("check")


class TagValue(_Base):
    """TAG/value bot: preflop raises its top 15% to 3bb and folds the rest; postflop bets 3/4 pot with two pair+,
    check-calls a pair or a good draw at a reasonable price, otherwise check/folds."""
    name = "tag_value"

    def __init__(self):
        self._premium = set(top_percent_range(0.15))

    def act(self, state: GameState) -> Action:
        lg = state.legal
        if state.street == 1:
            a, b = state.hole_cards
            combo = (a, b) if (RANKS.index(a[0]), SUITS.index(a[1])) > (RANKS.index(b[0]), SUITS.index(b[1])) else (b, a)
            if combo in self._premium:
                return _raise_or_call(state, max(3 * state.big_blind, _raise_mult_of_bet(state, 3)))
            return _passive(state, False)
        v = rank7(tuple(state.hole_cards) + tuple(state.board))
        cat = v >> 25
        hole_ranks = {c[0] for c in state.hole_cards}
        pair_uses_hole = cat == 1 and RANKS[(v >> 21) & 0xF] in hole_ranks
        if cat >= 2:
            return _raise_or_call(state, _pot_raise_to(state, 0.75)) if lg.can_check else _passive(state, True)
        if pair_uses_hole or PostflopJammer._wants_it(state):
            return _passive(state, _pot_odds(state) <= 0.35)
        return _passive(state, False)


class PassiveStation(_Base):
    """Calling station: raise 3/4 pot at > 0.82, call whenever equity >= pot odds, bet 2/3 pot only at > 0.80."""
    name = "passive_station"

    def act(self, state: GameState) -> Action:
        eq = _eq_random(state)
        if not state.legal.can_check:
            if eq > 0.82:
                return _raise_or_call(state, _pot_raise_to(state, 0.75))
            return _passive(state, eq >= _pot_odds(state))
        if eq > 0.80:
            return _raise_or_call(state, _pot_raise_to(state, 0.67))
        return Action("check")


class Maniac70(_Base):
    """Aggressor: 70% of decisions raise 2.5x the bet (or bet 2/3 pot), otherwise check/call. Any cards."""
    name = "maniac70"

    def __init__(self, seed: int | str | None = 0):
        self._seed = seed
        self._rng = random.Random(seed)

    def new_match(self, match_id: str, opponent: str | None) -> None:
        self._rng = random.Random(f"{self._seed}:{match_id}")

    def act(self, state: GameState) -> Action:
        lg = state.legal
        if self._rng.random() < 0.70 and lg.min_raise_to is not None:
            if lg.can_check:
                return _raise_or_call(state, _pot_raise_to(state, 0.67))
            return _raise_or_call(state, _raise_mult_of_bet(state, 2.5))
        return Action("check") if lg.can_check else Action("call")


class SolverLite(_Base):
    """Solver-lite: a preflop chart (open 70%, defend 55% / 3-bet 12%, 4-bet 4%) and mixed postflop sizes by
    equity: > 0.75 bet 67% / check / pot; > 0.50 check / bet 33% / call; draws bet 67% at 25%; else mostly check."""
    name = "solver_lite"

    def __init__(self, seed: int | str | None = 0):
        self._seed = seed
        self._rng = random.Random(seed)
        self._tops = {p: set(top_percent_range(p)) for p in (0.04, 0.12, 0.15, 0.30, 0.55, 0.70)}

    def new_match(self, match_id: str, opponent: str | None) -> None:
        self._rng = random.Random(f"{self._seed}:{match_id}")

    def _in(self, state: GameState, pct: float) -> bool:
        a, b = state.hole_cards
        combo = (a, b) if (RANKS.index(a[0]), SUITS.index(a[1])) > (RANKS.index(b[0]), SUITS.index(b[1])) else (b, a)
        return combo in self._tops[pct]

    def _mix(self, options: dict) -> str:
        x, acc = self._rng.random(), 0.0
        for k, p in options.items():
            acc += p
            if x < acc:
                return k
        return k

    def act(self, state: GameState) -> Action:
        lg = state.legal
        if state.street == 1:
            opp_raises = sum(a.actor == "opp" and a.kind == "raise" for a in state.history)
            my_raises = sum(a.actor == "me" and a.kind == "raise" for a in state.history)
            if not state.history and state.is_button:                       # open
                return _raise_or_call(state, int(2.5 * state.big_blind)) if self._in(state, 0.70) else _passive(state, False)
            if my_raises == 0 and opp_raises == 0:                          # BB vs limp
                return _raise_or_call(state, 3 * state.big_blind) if self._in(state, 0.30) else Action("check")
            if my_raises == 0:                                              # facing an open
                if self._in(state, 0.12):
                    return _raise_or_call(state, 3 * state.opp_committed)
                return _passive(state, self._in(state, 0.55))
            if self._in(state, 0.04):                                       # facing a 3-bet+
                return Action("raise", lg.max_raise_to) if lg.max_raise_to is not None else _passive(state, True)
            return _passive(state, self._in(state, 0.15))
        eq = _eq_random(state)
        if not lg.can_check:
            if eq > 0.80 and self._rng.random() < 0.5:
                return _raise_or_call(state, _pot_raise_to(state, 0.67))
            return _passive(state, eq >= _pot_odds(state))
        if eq > 0.75:
            pick = self._mix({"bet67": 0.65, "check": 0.20, "bet100": 0.15})
        elif eq > 0.50:
            pick = self._mix({"check": 0.55, "bet33": 0.30, "call": 0.15})
        elif PostflopJammer._wants_it(state) and eq > 0.30:
            pick = self._mix({"bet67": 0.25, "check": 0.75})
        else:
            pick = self._mix({"check": 0.85, "bet33": 0.15})
        if pick.startswith("bet"):
            return _raise_or_call(state, _pot_raise_to(state, int(pick[3:]) / 100))
        return Action("check")


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
    "starter_clone": StarterClone,
    "mc_potodds": MCPotOdds,
    "tag_value": TagValue,
    "passive_station": PassiveStation,
    "maniac70": Maniac70,
    "solver_lite": SolverLite,
}
