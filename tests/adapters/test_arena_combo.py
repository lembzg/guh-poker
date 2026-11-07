"""Routing/failure tests; real SDK and packed execution are checked separately in the arena."""
import runpy
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def combo(monkeypatch):
    class Response:
        @staticmethod
        def call():
            return SimpleNamespace(action_type="call", amount=None)

        @staticmethod
        def fold():
            return SimpleNamespace(action_type="fold", amount=None)

        @staticmethod
        def raise_to(amount):
            return SimpleNamespace(action_type="raise", amount=amount)

    def module(name, **attrs):
        value = ModuleType(name)
        value.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, value)

    module("opponent", OpponentModel=lambda: None)
    module("preflop", preflop_action=lambda *args: Response.raise_to(60))
    module("player_sdk")
    module("player_sdk.bot_interface", PokerBot=type("PokerBot", (), {}))
    module("player_sdk.models", Response=Response)
    path = Path(__file__).resolve().parents[2] / "adapters/arena/combo_bot_example.py"
    namespace = runpy.run_path(str(path))
    bot = namespace["ComboBot"]()
    tracked = []
    bot._post = SimpleNamespace(observe=lambda gs, resp: tracked.append(resp),
                                act=lambda gs: Response.raise_to(100))
    bot.model = SimpleNamespace(observe=lambda gs: None, record_own=lambda *args: None)
    state = SimpleNamespace(is_preflop=True, call_amount=10, max_raise_to=2000,
                            min_raise_to=40, can_raise=True, can_bet=False)
    return bot, state, tracked


def test_preflop_routes_external_decision_to_tracker(combo):
    bot, state, tracked = combo
    response = bot.act(state)
    assert response.action_type == "raise" and response.amount == 60
    assert tracked == [response]


def test_preflop_failure_tracks_the_safe_action(combo):
    bot, state, tracked = combo
    def fail(gs):
        raise RuntimeError("strategy failed")
    bot.model.observe = fail
    response = bot.act(state)
    assert response.action_type == "fold"
    assert tracked == [response]


def test_bookkeeping_failure_does_not_change_returned_action(combo):
    bot, state, tracked = combo
    def fail(*args):
        raise RuntimeError("bookkeeping failed")
    bot.model.record_own = fail
    response = bot.act(state)
    assert response.action_type == "raise"
    assert tracked == [response]


def test_postflop_uses_mainbot_response(combo):
    bot, state, tracked = combo
    state.is_preflop = False
    response = bot.act(state)
    assert response.action_type == "raise" and response.amount == 100
    assert tracked == []
