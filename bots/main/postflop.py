"""Postflop strategy (#12). Contract: docs/API.md -> Strategy modules (postflop.py).

One decision on the flop, turn or river:
  1. Equity vs the opponent's range (core.equity), the range coming from OpponentModel.range_estimate or,
     when None, a default from who raised preflop.
  2. Facing a bet: raise strong equity, call when equity beats the pot odds plus a margin, else fold.
  3. Checked to: value-bet above a threshold with a size picked by equity and board texture; otherwise
     bet as a bluff / semi-bluff only when its expected value beats checking, given how often they fold.
  4. Exploit knobs from OpponentStats (prior defaults when None): vs a calling station bet thinner and
     bigger and stop bluffing; vs a folder bluff more; vs a maniac check-call and trap.

Ideas kept from v0 (bots/v0/bot.py): a call cushion over pot odds, a stack-off guard, 45%/70% pot base
sizes by texture. Thresholds are starting points, to be tuned in the harness.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from core.allin import call_price, effective_raise_to, opponent_start, terminal_call
from core.equity import RANKS, Range, equity, top_percent_range
from core.interface import Action, GameState, OpponentStats

DEFAULT_BUDGET_MS = 60.0
SAMPLES = 2000

# Defaults for unknown stats (None). Hackathon fields lean towards calling, so assume less folding.
DEFAULTS = {"fold_to_bet": 0.40, "fold_to_cbet": 0.45, "aggression": 1.0, "wtsd": 0.40}

VALUE_EQ = {2: 0.62, 3: 0.60, 4: 0.58}      # min equity to bet for value, by street
RAISE_EQ = 0.75                             # facing a bet: raise at or above this
CALL_MARGIN = {2: 0.01, 3: 0.03, 4: 0.03}   # extra equity over pot odds needed to call (reverse implied odds)
DRAW_BONUS = 0.03                           # implied odds for a real draw on flop/turn
STACKOFF_FRAC = 0.5                         # a call this big a share of my stack needs extra equity
STACKOFF_MARGIN = 0.05


@dataclass(frozen=True)
class Knobs:
    station: bool
    folder: bool
    maniac: bool
    fold_to_bet: float
    fold_to_cbet: float
    aggression: float


def knobs(opp: OpponentStats | None) -> Knobs:
    def g(name):
        v = getattr(opp, name, None) if opp is not None else None
        return DEFAULTS[name] if v is None else v

    fb, fcb, af, wtsd = g("fold_to_bet"), g("fold_to_cbet"), g("aggression"), g("wtsd")
    return Knobs(
        station=fb < 0.30 or wtsd > 0.55,
        folder=fb > 0.55,
        maniac=af > 2.5,
        fold_to_bet=fb, fold_to_cbet=fcb, aggression=af,
    )


# ------------------------------------------------------------------ board / hand features

def _ranks(cards) -> list[int]:
    return [RANKS.index(c[0]) for c in cards]


def is_wet(board: tuple[str, ...]) -> bool:
    """Flush or straight draws possible: 2+ of a suit on the flop (3+ later), or 3 ranks within 5."""
    suits = [c[1] for c in board]
    if max(suits.count(s) for s in set(suits)) >= (2 if len(board) == 3 else 3):
        return True
    rs = sorted(set(_ranks(board)) | ({-1} if "A" in [c[0] for c in board] else set()))
    return any(rs[i + 2] - rs[i] <= 4 for i in range(len(rs) - 2))


def has_draw(hole: tuple[str, str], board: tuple[str, ...]) -> bool:
    """Flush draw (4 to a suit using a hole card) or open-ended straight draw using a hole card."""
    if len(board) >= 5:
        return False
    cards = tuple(hole) + tuple(board)
    for s in {c[1] for c in hole}:
        if sum(c[1] == s for c in cards) == 4:
            return True
    rs = set(_ranks(cards))
    if 12 in rs:
        rs.add(-1)
    hole_rs = set(_ranks(hole)) | ({-1} if any(c[0] == "A" for c in hole) else set())
    for lo in range(-1, 9):
        run = set(range(lo, lo + 4))
        if run <= rs and run & hole_rs and lo + 4 not in rs and lo - 1 not in rs:
            if lo >= 0 and lo + 4 <= 12:          # open at both ends
                return True
    return False


def default_range(state: GameState) -> Range | None:
    """The opponent's range from preflop action alone, for when no estimate is supplied."""
    pre = [a for a in state.history if a.street == 1]
    opp_raised = any(a.actor == "opp" and a.kind == "raise" for a in pre)
    me_raised = any(a.actor == "me" and a.kind == "raise" for a in pre)
    if opp_raised:
        return top_percent_range(0.35)
    if me_raised:
        return top_percent_range(0.60)
    return None


# ------------------------------------------------------------------ sizing

def _raise_to(state: GameState, frac: float) -> int:
    """raise_to for betting/raising `frac` of the pot (after calling)."""
    call = state.legal.call_amount
    pot_after_call = state.my_committed + state.opp_committed + call
    return int(state.my_committed + call + round(frac * pot_after_call))


def _bet(state: GameState, frac: float) -> Action:
    lg = state.legal
    if lg.min_raise_to is None:
        return Action("check") if lg.can_check else Action("call")
    high = effective_raise_to(state)
    target = _raise_to(state, frac)
    if target - state.my_committed >= 0.8 * (high - state.my_committed):      # don't leave a sliver behind
        target = high
    return Action("raise", max(lg.min_raise_to, min(target, high)))


def _value_size(eq: float, wet: bool, k: Knobs, spr: float) -> float:
    base = 0.70 if wet else 0.45
    if eq >= 0.85:
        base += 0.25
    elif eq >= 0.72:
        base += 0.10
    if k.station:
        base += 0.25
    if spr <= 1.5 and eq >= 0.70:
        base = 10.0                           # shallow: get it all in
    return base


# ------------------------------------------------------------------ main entry

def postflop_action(state: GameState, opp: OpponentStats | None, opp_range: Range | None,
                    time_budget_ms: float = DEFAULT_BUDGET_MS) -> Action:
    lg = state.legal
    street = state.street if state.street in (2, 3, 4) else 2
    k = knobs(opp)
    rng_mix = random.Random(f"{state.hand_id}:{street}:{len(state.history)}:{state.hole_cards}")

    if opp_range is None:
        opp_range = default_range(state)
    try:
        eq = equity(state.hole_cards, state.board, opp_range, samples=SAMPLES,
                    time_budget_ms=time_budget_ms, seed=state.hand_id)
    except Exception:
        return Action("check") if lg.can_check else Action("fold")

    pot = state.my_committed + state.opp_committed
    my_behind = state.starting_stack - state.my_committed
    opp_behind = opponent_start(state) - state.opp_committed
    spr = min(my_behind, opp_behind) / max(1, pot)
    wet = is_wet(state.board)
    draw = has_draw(state.hole_cards, state.board)

    if not lg.can_check:
        return _facing_bet(state, eq, k, street, spr, wet, draw, rng_mix)
    return _checked_to(state, eq, k, street, spr, wet, draw, rng_mix)


def _facing_bet(state, eq, k, street, spr, wet, draw, rng_mix) -> Action:
    lg = state.legal
    call = lg.call_amount
    pot = state.my_committed + state.opp_committed
    if terminal_call(state):
        cost, final_pot = call_price(state)
        return Action("call" if eq * final_pot >= cost else "fold")
    pot_odds = call / (pot + call)
    need = pot_odds + CALL_MARGIN[street]
    if draw and street < 4:
        need -= DRAW_BONUS
    if k.maniac:
        need -= 0.03                          # their bets are often air
    elif k.fold_to_bet > 0.55 and k.aggression < 0.8:
        need += 0.04                          # a passive folder that bets has it
    my_behind = state.starting_stack - state.my_committed
    if call >= STACKOFF_FRAC * my_behind and eq < 0.80:
        need += STACKOFF_MARGIN               # v0's stack-off guard, softened

    raise_eq = RAISE_EQ - (0.05 if k.station else 0.0)
    if eq >= raise_eq and lg.min_raise_to is not None:
        if k.maniac and street < 4 and eq < 0.9 and rng_mix.random() < 0.5:
            return Action("call")             # let the maniac keep firing
        return _bet(state, 0.75 if not k.station else 1.0)
    # Semi-bluff raise with a draw against someone who folds a lot.
    if (draw and street == 2 and k.folder and not k.maniac and lg.min_raise_to is not None
            and eq >= pot_odds - 0.05 and rng_mix.random() < 0.5):
        return _bet(state, 0.75)
    if eq >= need:
        return Action("call")
    return Action("fold")


def _checked_to(state, eq, k, street, spr, wet, draw, rng_mix) -> Action:
    lg = state.legal
    if lg.min_raise_to is None:
        return Action("check")
    value_eq = VALUE_EQ[street] - (0.05 if k.station else 0.0) + (0.03 if k.folder and not k.station else 0.0)
    oop = not state.is_button

    if eq >= value_eq:
        # Trap a maniac: check strong (not nutted) hands out of position and let them bet.
        if k.maniac and oop and street < 4 and eq < 0.92 and rng_mix.random() < 0.7:
            return Action("check")
        return _bet(state, _value_size(eq, wet, k, spr))

    # Bluff / semi-bluff only when it beats checking in expected value.
    i_raised_pre = any(a.actor == "me" and a.kind == "raise" for a in state.history if a.street == 1)
    cbet_spot = street == 2 and i_raised_pre and not any(a.street == 2 and a.kind == "raise"
                                                         for a in state.history)
    fold_p = k.fold_to_cbet if cbet_spot else k.fold_to_bet
    if k.maniac:
        fold_p *= 0.7                         # they raise instead of folding
    pot = state.my_committed + state.opp_committed
    ev_check = eq * pot
    best, best_ev = None, ev_check
    for frac in (0.33, 0.5, 0.75):
        action = _bet(state, frac)
        b = min(action.raise_to, opponent_start(state)) - state.my_committed
        actual_frac = b / max(1, pot)
        f = min(0.95, fold_p * (0.85 + 0.3 * actual_frac))   # bigger bets fold out a little more
        eq_called = eq * 0.85                 # they call with their better hands
        ev = f * pot + (1 - f) * (eq_called * (pot + 2 * b) - b)
        if ev > best_ev * 1.05 + 0.01 * pot:
            best, best_ev = frac, ev
    if best is not None and (eq >= 0.2 or draw or k.folder or street == 4):
        return _bet(state, best)
    return Action("check")
