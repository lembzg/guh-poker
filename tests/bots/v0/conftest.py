"""Stands in for core/interface.py (#4) until it lands, copied from docs/API.md.

Once the real module exists it is imported instead and this stub goes unused. Delete the
stub then.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from typing import Literal


def _make_stub() -> types.ModuleType:
    @dataclass(frozen=True)
    class LegalActions:
        can_fold: bool
        can_check: bool
        call_amount: int
        min_raise_to: int | None
        max_raise_to: int | None

    @dataclass(frozen=True)
    class ActionRecord:
        street: int
        actor: Literal["me", "opp"]
        kind: Literal["fold", "check", "call", "raise"]
        raise_to: int | None

    @dataclass(frozen=True)
    class GameState:
        hand_id: int
        is_button: bool
        hole_cards: tuple[str, str]
        board: tuple[str, ...]
        street: int
        small_blind: int
        big_blind: int
        starting_stack: int
        my_committed: int
        opp_committed: int
        history: tuple[ActionRecord, ...]
        legal: LegalActions
        time_left_ms: int | None = None

    @dataclass(frozen=True)
    class Action:
        kind: Literal["fold", "check", "call", "raise"]
        raise_to: int | None = None

    @dataclass(frozen=True)
    class HandResult:
        hand_id: int
        was_button: bool
        my_delta: int
        history: tuple[ActionRecord, ...]
        board: tuple[str, ...]
        opp_hole_cards: tuple[str, str] | None

    def clamp_to_legal(action: Action, legal: LegalActions) -> Action:
        if action.kind == "raise" and action.raise_to is not None and legal.min_raise_to is not None:
            return Action("raise", max(legal.min_raise_to, min(action.raise_to, legal.max_raise_to)))
        if action.kind == "fold" and legal.can_fold and not legal.can_check:
            return action
        if legal.can_check:
            return Action("check")
        if legal.call_amount > 0 and action.kind != "fold":
            return Action("call")
        return Action("fold")

    module = types.ModuleType("core.interface")
    for obj in (LegalActions, ActionRecord, GameState, Action, HandResult, clamp_to_legal):
        setattr(module, obj.__name__, obj)
    return module


if importlib.util.find_spec("core.interface") is None:
    sys.modules["core.interface"] = _make_stub()
