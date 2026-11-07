"""Synthetic opponent families. Own/public cards only; standard library at play time."""
from __future__ import annotations

import hashlib
import random

from player_sdk.bot_interface import PokerBot
from player_sdk.models import Response
from official_starter import preflop_strength, postflop_strength
from core.equity import equity, rank7


class SparringBot(PokerBot):
    def __init__(self):
        from profile_data import PROFILE
        self.kind = PROFILE["kind"]
        self.p = PROFILE["params"]
        self.rng = random.Random(0)
        self.started = False

    def act(self, gs):
        if not self.started:
            self.rng.seed(int.from_bytes(hashlib.sha256(
                repr((gs.hole_cards, gs.my_index, self.kind)).encode()).digest()[:8], "big"))
            self.started = True
        q = preflop_strength(gs.hole_cards) if gs.is_preflop else postflop_strength(
            gs.hole_cards, gs.community_cards)
        kind, p = self.kind, self.p
        if not gs.is_preflop and kind in ("trap", "delayed", "postjam", "switch"):
            # Unseen families also use an independent, exact made-hand evaluator (includes straights).
            cards = tuple(c[0] + c[1].lower() for c in (*gs.hole_cards, *gs.community_cards))
            category = rank7(cards) >> 25
            q = (0.22, 0.53, 0.74, 0.83, 0.89, 0.93, 0.97, 0.99, 1.0)[min(category, 8)]
        size = p.get("size", 2/3)
        aggression = p.get("aggression", 0.65)
        price = gs.call_amount / max(1, gs.pot_size + gs.call_amount)
        roll = self.rng.random()
        if kind == "switch":
            # Changes style with public history; the switch schedule never uses an opponent's cards.
            kind = "maniac" if len(gs.action_history) % 4 < 2 else "nit"
        if kind == "equity":
            def cards(cs):
                return tuple(c[0] + c[1].lower() for c in cs)
            key = int.from_bytes(hashlib.sha256(repr((gs.hole_cards, gs.community_cards)).encode()).digest()[:8], "big")
            q = equity(cards(gs.hole_cards), cards(gs.community_cards), samples=160,
                       time_budget_ms=25, seed=key)
        if kind == "shove":
            if q >= p.get("threshold", 0):
                return self.raise_to(gs, gs.max_raise_to)
            return self.check_fold(gs)
        if kind == "station":
            if not gs.is_preflop and q > 0.85:
                return self.bet(gs, size)
            return Response.call() if roll < p.get("looseness", 0.85) or gs.call_amount == 0 else Response.fold()
        if kind == "maniac":
            if roll < aggression:
                return self.raise_to(gs, gs.max_raise_to) if roll < 0.12 else self.bet(gs, size*1.5)
            return Response.call() if q > price or gs.call_amount == 0 else Response.fold()
        if kind == "minraise":
            return self.raise_to(gs, gs.min_raise_to) if roll < aggression else Response.call()
        if kind == "nit":
            threshold = p.get("threshold", 0.71)
            if q >= threshold:
                return self.bet(gs, size)
            return self.check_fold(gs)
        if kind == "threebet" and gs.is_preflop:
            raises = sum(a.action in ("raise_to", "bet") for a in gs.action_history)
            if raises >= 2 and q < 0.85:
                return self.check_fold(gs)
            if roll < aggression or q > 0.75:
                return self.raise_to(gs, max(50, (gs.my_bet + gs.call_amount)*3))
            return Response.call() if q > 0.45 else self.check_fold(gs)
        if kind == "postjam" and not gs.is_preflop:
            return self.raise_to(gs, gs.max_raise_to) if q >= p.get("threshold", 0.48) else self.check_fold(gs)
        if kind == "trap" and not gs.is_preflop:
            if q > 0.75 and gs.street != "river":
                return Response.call()
            if q > 0.62 or (roll < 0.10 and gs.call_amount == 0):
                return self.bet(gs, 1.1)
        if kind == "delayed" and not gs.is_preflop:
            if gs.street == "flop":
                return Response.call() if q > price + 0.08 or not gs.call_amount else Response.fold()
            if q > 0.65 or roll < aggression:
                return self.bet(gs, 0.8)
        margin = p.get("margin", 0.10)
        threshold = 0.65 if kind == "equity" else 0.75
        if q >= threshold:
            return self.bet(gs, size)
        return Response.call() if gs.call_amount == 0 or q >= price + margin else Response.fold()

    @staticmethod
    def check_fold(gs):
        return Response.call() if gs.call_amount == 0 else Response.fold()

    @staticmethod
    def raise_to(gs, target):
        if not (gs.can_raise or gs.can_bet) or gs.min_raise_to is None or gs.max_raise_to is None:
            return Response.call()
        return Response.raise_to(max(gs.min_raise_to, min(int(target or gs.min_raise_to), gs.max_raise_to)))

    def bet(self, gs, fraction):
        # Street total after calling plus a fraction of the pot after calling.
        return self.raise_to(gs, gs.my_bet + gs.call_amount + round(fraction*(gs.pot_size+gs.call_amount)))
