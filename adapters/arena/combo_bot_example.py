"""Combined prototype: lembzg's table-driven preflop (#32) + EulaBet's MainBot postflop and opponent model.
To build: copy lembzg's bots/myteam/{opponent,preflop,ranges,equity_table}.py next to this file (renamed bot.py)
in a folder from `python -m adapters.arena.build`, then `arena validate` / `arena pack`."""
from __future__ import annotations

import os
import random

from opponent import OpponentModel
from player_sdk.bot_interface import PokerBot
from player_sdk.models import Response
from preflop import preflop_action

from adapters.arena.translate import ArenaAdapter
from bots.main.bot import MainBot


class ComboBot(PokerBot):
    def __init__(self) -> None:
        self.rng = random.Random(None)
        self.model = OpponentModel()            # lembzg's preflop model
        self._post = ArenaAdapter(MainBot(), Response)   # our postflop + opponent model
        self._started = False

    def act(self, gs):
        try:
            if not self._started:
                self.rng.seed(os.urandom(16))
                self._started = True
            self.model.observe(gs)
            if gs.is_preflop:
                resp = self._legal(preflop_action(gs, self.model, self.rng), gs)
                self._post.observe(gs, resp)
            else:
                resp = self._post.act(gs)
            kind = "raise" if resp.action_type in ("raise", "all_in") else resp.action_type
            self.model.record_own(kind, resp.action_type == "all_in" or resp.amount == gs.max_raise_to,
                                  bool(gs.is_preflop))
            return resp
        except Exception as exc:  # noqa: BLE001
            print(f"act() failed, playing safe: {exc!r}")
            return Response.call() if gs.call_amount == 0 else Response.fold()

    @staticmethod
    def _legal(resp, gs):
        kind = resp.action_type
        if kind in ("raise", "all_in"):
            if not (gs.can_raise or gs.can_bet):
                return Response.call()
            if kind == "raise":
                low, high = gs.min_raise_to, gs.max_raise_to
                if low is None or high is None or high <= 0:
                    return Response.call() if gs.call_amount == 0 else Response.fold()
                return Response.raise_to(max(low, min(int(resp.amount), high)))
            return resp
        if kind == "fold" and gs.call_amount == 0:
            return Response.call()
        return resp
