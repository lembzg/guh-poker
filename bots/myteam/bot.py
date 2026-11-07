"""Our tournament bot: table-driven preflop, placeholder postflop.

Routing lives here so the strategy modules stay independent. ``act`` can never
raise: any failure returns a legal safe move (check, otherwise fold), and the
response is checked against the legal menu before it is returned.
"""

from __future__ import annotations

import os
import random

from opponent import OpponentModel
from player_sdk.bot_interface import PokerBot
from player_sdk.models import GameState, Response
from postflop import postflop_action
from preflop import preflop_action

# Set to an integer for a reproducible RNG in tests. None plays for real.
SEED = None


class MyTeamBot(PokerBot):
    def __init__(self) -> None:
        self.rng = random.Random(SEED)
        self.model = OpponentModel()
        # ``arena pack`` pickles this object once, so without a reseed every
        # half would restore the same RNG state. See _start_process.
        self._started = False

    def _start_process(self) -> None:
        if SEED is None:
            self.rng.seed(os.urandom(16))
        self._started = True

    def act(self, game_state: GameState) -> Response:
        try:
            if not self._started:
                self._start_process()
            self.model.observe(game_state)
            if game_state.is_preflop:
                response = preflop_action(game_state, self.model, self.rng)
            else:
                response = postflop_action(
                    game_state, self.model.postflop_loosen()
                )
            response = self._legal(response, game_state)
            self.model.record_own(
                self._kind(response),
                response.action_type == "all_in"
                or response.amount == game_state.max_raise_to,
                bool(game_state.is_preflop),
            )
            return response
        except Exception as exc:  # noqa: BLE001 - never fault the arena
            print(f"act() failed, playing safe: {exc!r}")
            return self._safe(game_state)

    @staticmethod
    def _kind(response: Response) -> str:
        return "raise" if response.action_type in ("raise", "all_in") else (
            response.action_type
        )

    @staticmethod
    def _safe(state: GameState) -> Response:
        return Response.call() if state.call_amount == 0 else Response.fold()

    def _legal(self, response: Response, state: GameState) -> Response:
        kind = response.action_type
        if kind in ("raise", "all_in"):
            if not (state.can_raise or state.can_bet):
                return Response.call()
            if kind == "raise":
                low, high = state.min_raise_to, state.max_raise_to
                if low is None or high is None or high <= 0:
                    return self._safe(state)
                amount = max(low, min(int(response.amount), high))
                return Response.raise_to(amount)
            return response
        if kind == "fold" and state.call_amount == 0:
            return Response.call()
        return response
