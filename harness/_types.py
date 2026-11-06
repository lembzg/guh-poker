"""Game types from docs/API.md. Uses core.interface once #4 lands; until then, a local copy of the contract."""
from __future__ import annotations

try:  # pragma: no cover - depends on whether #4 has landed
    from core.interface import Action, ActionRecord, GameState, HandResult, LegalActions
except ImportError:  # pragma: no cover
    from dataclasses import dataclass
    from typing import Literal

    Street = Literal[1, 2, 3, 4]

    @dataclass(frozen=True)
    class LegalActions:
        can_fold: bool
        can_check: bool
        call_amount: int
        min_raise_to: int | None
        max_raise_to: int | None

    @dataclass(frozen=True)
    class ActionRecord:
        street: Street
        actor: Literal["me", "opp"]
        kind: Literal["fold", "check", "call", "raise"]
        raise_to: int | None

    @dataclass(frozen=True)
    class GameState:
        hand_id: int
        is_button: bool
        hole_cards: tuple[str, str]
        board: tuple[str, ...]
        street: Street
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

__all__ = ["Action", "ActionRecord", "GameState", "HandResult", "LegalActions"]
