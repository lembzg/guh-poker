"""Heads-up no-limit hold'em dealer (#6).

One call to `play_hand` plays one hand between two `Seat`s. Seat 0 is the button (small blind): it acts
first preflop and last postflop. Amounts are chips; every commitment is a total for the hand, matching
docs/API.md (`my_committed`, `raise_to`).

Rules:
- Blinds: a stack smaller than its blind posts all-in.
- Min raise: the raise increment must be at least the previous bet/raise increment on this street (the big
  blind at the start of each street). An all-in for less is always allowed but, being incomplete, does not
  reopen raising for a player who has already acted on this street.
- Raises above what the opponent can match are allowed; the uncalled part is returned.
- Folding is legal only when facing a bet. "call" with nothing to call counts as a check.
- An illegal action (or an exception, or a non-Action return) becomes check-if-possible-else-fold and is
  counted on the seat.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.equity import rank7
from harness._types import Action, ActionRecord, GameState, HandResult, LegalActions

STREET_CARDS = {1: 0, 2: 3, 3: 4, 4: 5}   # board cards visible on each street


@dataclass
class Seat:
    """A bot plus the counters the harness reports for it."""
    bot: object
    decisions: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    illegal: int = 0
    errors: int = 0
    latencies: list[float] = field(default_factory=list)

    def timed_act(self, state: GameState):
        t = time.perf_counter()
        try:
            action = self.bot.act(state)
            failed = False
        except Exception:
            action, failed = None, True
        ms = (time.perf_counter() - t) * 1000.0
        self.decisions += 1
        self.total_ms += ms
        self.max_ms = max(self.max_ms, ms)
        if failed:
            self.errors += 1
        return action, failed

    def notify(self, result: HandResult) -> None:
        try:
            self.bot.hand_over(result)
        except Exception:
            self.errors += 1


@dataclass
class HandOutcome:
    deltas: tuple[int, int]               # chips won by seat 0 (button), seat 1 (big blind)
    board: tuple[str, ...]
    showdown: bool
    history: list[tuple[int, int, str, int | None]]   # (street, seat, kind, raise_to)


def _legal(p: int, committed: list[int], behind: list[int], level: int, last_inc: int,
           can_raise: list[bool]) -> LegalActions:
    to_call = level - committed[p]
    max_to = committed[p] + behind[p]
    raise_ok = can_raise[p] and behind[1 - p] > 0 and behind[p] > to_call
    return LegalActions(
        can_fold=to_call > 0,
        can_check=to_call <= 0,
        call_amount=min(to_call, behind[p]) if to_call > 0 else 0,
        min_raise_to=min(level + last_inc, max_to) if raise_ok else None,
        max_raise_to=max_to if raise_ok else None,
    )


def _validate(action, legal: LegalActions) -> tuple[str, int | None] | None:
    """(kind, raise_to) if the action is legal, else None."""
    kind = getattr(action, "kind", None)
    if kind == "fold":
        return ("fold", None) if legal.can_fold else None
    if kind == "check":
        return ("check", None) if legal.can_check else None
    if kind == "call":
        return ("check", None) if legal.can_check else ("call", None)
    if kind == "raise":
        r = getattr(action, "raise_to", None)
        if isinstance(r, float) and r.is_integer():
            r = int(r)
        if legal.min_raise_to is None or isinstance(r, bool) or not isinstance(r, int):
            return None
        if legal.min_raise_to <= r <= legal.max_raise_to:
            return ("raise", r)
    return None


def play_hand(seats: tuple[Seat, Seat], deck: list[str], stacks: tuple[int, int], small_blind: int,
              big_blind: int, hand_id: int) -> HandOutcome:
    """Play one hand. seats[0] is the button. deck: button hole = deck[0:2], BB hole = deck[2:4],
    board = deck[4:9]. stacks: chips each seat starts the hand with."""
    holes = (tuple(deck[0:2]), tuple(deck[2:4]))
    full_board = tuple(deck[4:9])
    committed = [0, 0]
    behind = list(stacks)
    folded = -1
    history: list[tuple[int, int, str, int | None]] = []

    for p, blind in ((0, small_blind), (1, big_blind)):
        amt = min(blind, behind[p])
        committed[p] += amt
        behind[p] -= amt

    def view(p: int, street: int, legal: LegalActions) -> GameState:
        return GameState(
            hand_id=hand_id, is_button=(p == 0), hole_cards=holes[p],
            board=full_board[:STREET_CARDS[street]], street=street,
            small_blind=small_blind, big_blind=big_blind, starting_stack=stacks[p],
            opp_starting_stack=stacks[1 - p],
            my_committed=committed[p], opp_committed=committed[1 - p],
            history=tuple(ActionRecord(s, "me" if a == p else "opp", k, r) for s, a, k, r in history),
            legal=legal,
        )

    for street in (1, 2, 3, 4):
        if behind[0] == 0 or behind[1] == 0:
            if street > 1:
                continue          # someone is all-in: run the board out
        level = max(committed)
        last_inc = big_blind
        acted = [False, False]
        can_raise = [True, True]
        p = 0 if street == 1 else 1
        while True:
            live = [i for i in (0, 1) if behind[i] > 0]
            if not live:
                break
            if len(live) == 1 and committed[live[0]] >= level:
                break             # opponent all-in and I've matched: nothing to decide
            if all(acted[i] or behind[i] == 0 for i in (0, 1)) and all(
                    committed[i] >= level or behind[i] == 0 for i in (0, 1)):
                break
            if behind[p] == 0:
                p = 1 - p
                continue
            legal = _legal(p, committed, behind, level, last_inc, can_raise)
            seat = seats[p]
            action, failed = seat.timed_act(view(p, street, legal))
            choice = _validate(action, legal)
            if choice is None:
                if not failed:
                    seat.illegal += 1
                choice = ("check", None) if legal.can_check else ("fold", None)
            kind, raise_to = choice
            acted[p] = True
            if kind == "fold":
                history.append((street, p, "fold", None))
                folded = p
                break
            if kind == "call":
                amt = legal.call_amount
                committed[p] += amt
                behind[p] -= amt
            elif kind == "raise":
                inc = raise_to - level
                if inc >= last_inc:
                    last_inc = inc
                    can_raise[1 - p] = True
                else:     # incomplete all-in raise: doesn't reopen for a player who already acted
                    can_raise[1 - p] = not acted[1 - p]
                behind[p] -= raise_to - committed[p]
                committed[p] = raise_to
                level = raise_to
            history.append((street, p, kind, raise_to))
            p = 1 - p
        # Return any uncalled chips.
        hi = 0 if committed[0] > committed[1] else 1
        excess = committed[hi] - committed[1 - hi]
        if excess and (folded == -1 and behind[1 - hi] == 0 or folded == 1 - hi):
            committed[hi] -= excess
            behind[hi] += excess
        if folded != -1:
            break

    pot = committed[0] + committed[1]
    if folded != -1:
        winner = 1 - folded
        deltas = [-committed[0], -committed[1]]
        deltas[winner] += pot
        last_street = history[-1][0]
        return HandOutcome((deltas[0], deltas[1]), full_board[:STREET_CARDS[last_street]], False, history)

    v0 = rank7(holes[0] + full_board)
    v1 = rank7(holes[1] + full_board)
    deltas = [-committed[0], -committed[1]]
    if v0 > v1:
        deltas[0] += pot
    elif v1 > v0:
        deltas[1] += pot
    else:
        deltas[0] += pot // 2
        deltas[1] += pot - pot // 2
    return HandOutcome((deltas[0], deltas[1]), full_board, True, history)


def results_for(outcome: HandOutcome, holes: tuple[tuple[str, str], tuple[str, str]], hand_id: int
                ) -> tuple[HandResult, HandResult]:
    """Each seat's HandResult. Opponent hole cards are shown only at showdown."""
    out = []
    for p in (0, 1):
        out.append(HandResult(
            hand_id=hand_id, was_button=(p == 0), my_delta=outcome.deltas[p],
            history=tuple(ActionRecord(s, "me" if a == p else "opp", k, r) for s, a, k, r in outcome.history),
            board=outcome.board,
            opp_hole_cards=holes[1 - p] if outcome.showdown else None,
        ))
    return out[0], out[1]
