"""Runs the imported Quant bot (bots/v0/bot.py, kept unchanged) behind the Bot interface.

Quant was written for the Fullhouse engine, so this converts GameState into that
engine's state dict and Quant's reply into an Action. Three things in bot.py need
handling here rather than there:

- It keeps its opponent model in module globals, so each V0Bot loads a private copy of
  the module. Otherwise v0 vs v0 in one process would share a model.
- It hardcodes a 100-chip big blind in `_BB`, so we set that from the state.
- It learns about opponents only from `match_action_log`, which we rebuild from history.
"""
from __future__ import annotations

import importlib.util
import itertools
import random
from pathlib import Path
from types import ModuleType
from typing import Any

from core.interface import Action, GameState, HandResult, clamp_to_legal

_BOT_FILE = Path(__file__).with_name("bot.py")
_STREET_NAMES = {1: "preflop", 2: "flop", 3: "turn", 4: "river"}
_MATCH_LOG_MAX_ENTRIES = 200  # the Fullhouse engine's rolling window
_ME = "me"
_OPP = "opp"
_module_ids = itertools.count()


def _load_quant(seed: int | None) -> ModuleType:
    """Execute bot.py as a new module object that shares no state with other copies."""
    spec = importlib.util.spec_from_file_location(f"_quant_v0_{next(_module_ids)}", _BOT_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if seed is not None:
        module._RNG = random.Random(seed)
    return module


def _seats(is_button: bool) -> tuple[int, int]:
    """(my seat, opponent's seat). Seat numbers only need to be consistent within a state."""
    return (0, 1) if is_button else (1, 0)


def street_base(state: GameState) -> int:
    """Chips each player had in before this street. Quant counts bets per street, GameState per hand."""
    if state.street == 1:
        return 0  # the blinds count as this street's bets
    base = state.big_blind
    for record in state.history:
        if record.street < state.street and record.kind == "raise" and record.raise_to:
            base = max(base, record.raise_to)
    return min(base, state.my_committed, state.opp_committed)


def _action_log(state: GameState, my_seat: int, opp_seat: int) -> list[dict[str, Any]]:
    """This hand's actions in Fullhouse form. Quant reads only `seat` and `action` here."""
    sb_seat, bb_seat = (my_seat, opp_seat) if state.is_button else (opp_seat, my_seat)
    log: list[dict[str, Any]] = [
        {"seat": sb_seat, "action": "small_blind"},
        {"seat": bb_seat, "action": "big_blind"},
    ]
    for record in state.history:
        # Quant's short-stack charts need to know whether the raise it faces is a shove.
        is_shove = record.kind == "raise" and (record.raise_to or 0) >= state.starting_stack
        log.append({
            "seat": my_seat if record.actor == "me" else opp_seat,
            "action": "all_in" if is_shove else record.kind,
        })
    return log


def _match_log_entries(history: tuple, hand_num: int, is_button: bool) -> list[dict[str, Any]]:
    """One hand's voluntary actions in `match_action_log` form."""
    my_seat, opp_seat = _seats(is_button)
    return [
        {
            "hand_num": hand_num,
            "seat": my_seat if record.actor == "me" else opp_seat,
            "bot_id": _ME if record.actor == "me" else _OPP,
            "action": record.kind,
        }
        for record in history
    ]


def to_quant_state(state: GameState, match_log: list[dict[str, Any]]) -> dict[str, Any]:
    """GameState -> the dict that Fullhouse's engine passes to `decide`."""
    base = street_base(state)
    my_seat, opp_seat = _seats(state.is_button)
    my_bet = state.my_committed - base
    opp_bet = state.opp_committed - base
    my_stack = state.starting_stack - state.my_committed
    opp_stack = state.starting_stack - state.opp_committed
    current_bet = max(my_bet, opp_bet)
    # With no raise available, Quant's raise comes back through clamp_to_legal as a check or call.
    min_raise_to = state.legal.min_raise_to
    return {
        "type": "action_request",
        "hand_id": state.hand_id,
        "street": _STREET_NAMES[state.street],
        "seat_to_act": my_seat,
        "pot": state.my_committed + state.opp_committed,
        "community_cards": list(state.board),
        "current_bet": current_bet,
        "min_raise_to": current_bet if min_raise_to is None else min_raise_to - base,
        "amount_owed": state.legal.call_amount,
        "can_check": state.legal.can_check,
        "your_cards": list(state.hole_cards),
        "your_stack": my_stack,
        "your_bet_this_street": my_bet,
        "players": [
            {"seat": my_seat, "bot_id": _ME, "stack": my_stack,
             "is_folded": False, "is_all_in": my_stack <= 0, "bet_this_street": my_bet},
            {"seat": opp_seat, "bot_id": _OPP, "stack": opp_stack,
             "is_folded": False, "is_all_in": opp_stack <= 0, "bet_this_street": opp_bet},
        ],
        "action_log": _action_log(state, my_seat, opp_seat),
        "match_action_log": match_log[-_MATCH_LOG_MAX_ENTRIES:],
    }


def from_quant_action(reply: dict[str, Any], state: GameState) -> Action:
    """Quant's reply -> Action. Not necessarily legal yet; the caller clamps it."""
    kind = reply.get("action")
    if kind == "raise":
        return Action("raise", int(reply["amount"]) + street_base(state))
    if kind == "all_in":
        if state.legal.max_raise_to is not None:
            return Action("raise", state.legal.max_raise_to)
        return Action("call" if state.legal.call_amount > 0 else "check")
    return Action(kind)


class V0Bot:
    """Implements Bot from docs/API.md. Pass `seed` for reproducible Monte-Carlo sampling."""

    name = "v0"

    def __init__(self, seed: int | None = None, **cfg: Any) -> None:
        self._seed = seed
        self._reset()

    def _reset(self) -> None:
        self._quant = _load_quant(self._seed)
        self._match_log: list[dict[str, Any]] = []
        self._hand_num = 0  # our own count, because hand_id may repeat in duplicate deals

    def new_match(self, match_id: str, opponent: str | None) -> None:
        self._reset()

    def act(self, state: GameState) -> Action:
        try:
            self._quant._BB = state.big_blind
            current = _match_log_entries(state.history, self._hand_num, state.is_button)
            reply = self._quant.decide(to_quant_state(state, self._match_log + current))
            action = from_quant_action(reply, state)
        except Exception:
            action = Action("check" if state.legal.can_check else "fold")
        return clamp_to_legal(action, state.legal)

    def hand_over(self, result: HandResult) -> None:
        try:
            entries = _match_log_entries(result.history, self._hand_num, result.was_button)
            self._match_log = (self._match_log + entries)[-_MATCH_LOG_MAX_ENTRIES:]
        finally:
            self._hand_num += 1
