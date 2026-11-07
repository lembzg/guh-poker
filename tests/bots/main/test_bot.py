import time

import pytest

import bots.main.bot as B
from bots.main.bot import MainBot
from core.interface import Action, OpponentStats
from harness.match import play_match
from tests.bots.main.test_fallback import make_state


@pytest.fixture
def patch(monkeypatch):
    def apply(preflop="keep", postflop="keep", model="keep"):
        if preflop != "keep":
            monkeypatch.setattr(B, "_preflop", preflop)
        if postflop != "keep":
            monkeypatch.setattr(B, "_postflop", postflop)
        if model != "keep":
            monkeypatch.setattr(B, "_OpponentModel", model)
    return apply


def postflop_state(**kw):
    return make_state(("As", "Kd"), ("Ah", "7c", "2d"), **kw)


def test_routes_streets_and_passes_stats_and_range(patch):
    seen = {}

    class Model:
        def stats(self):
            return OpponentStats(hands=7)

        def range_estimate(self, state):
            return {("Ks", "Kh"): 1.0}

        def observe_hand(self, r):
            seen["observed"] = r

    def pre(state, opp):
        seen["pre"] = opp.hands
        return Action("call")

    def post(state, opp, opp_range, time_budget_ms=None):
        seen["post"] = (opp.hands, opp_range, time_budget_ms)
        return Action("check")

    patch(preflop=pre, postflop=post, model=Model)
    bot = MainBot(time_budget_ms=200)
    bot.new_match("m", None)
    assert bot.act(make_state(("7d", "2c"), facing=1, pot=3)) == Action("call")
    assert bot.act(postflop_state()) == Action("check")
    bot.hand_over("result")
    assert seen["pre"] == 7 and seen["post"][:2] == (7, {("Ks", "Kh"): 1.0}) and seen["observed"] == "result"
    assert 0 < seen["post"][2] < 200
    assert sum(bot.fallbacks.values()) == 0


def test_postflop_without_budget_kwarg_still_works(patch):
    patch(postflop=lambda state, opp, opp_range: Action("check"))
    assert MainBot().act(postflop_state()) == Action("check")


def test_exception_uses_fallback(patch):
    def boom(*a, **k):
        raise RuntimeError("bug")
    patch(preflop=boom, postflop=boom)
    bot = MainBot()
    assert bot.act(make_state(("As", "Ah"), facing=1, pot=3)).kind == "raise"    # fallback raises AA
    assert bot.act(postflop_state(facing=50, pot=10)) == Action("fold")
    assert bot.fallbacks["error"] == 2


def test_slow_strategy_times_out_within_budget(patch):
    def slow(*a, **k):
        time.sleep(1.0)
        return Action("raise", 10)
    patch(postflop=slow)
    bot = MainBot(time_budget_ms=80)
    t = time.perf_counter()
    a = bot.act(postflop_state())
    assert (time.perf_counter() - t) * 1000 < 150
    assert a.kind == "raise" and bot.fallbacks["timeout"] == 1      # fallback bets top pair


def test_time_left_caps_budget(patch):
    def slow(*a, **k):
        time.sleep(0.5)
        return Action("check")
    patch(postflop=slow)
    bot = MainBot(time_budget_ms=5000)
    s = postflop_state()
    s = type(s)(**{**s.__dict__, "time_left_ms": 200})
    t = time.perf_counter()
    bot.act(s)
    assert (time.perf_counter() - t) * 1000 < 120 and bot.fallbacks["timeout"] == 1


def test_illegal_output_is_clamped(patch):
    patch(postflop=lambda s, o, r, time_budget_ms=None: Action("raise", 10 ** 9),
          preflop=lambda s, o: "not an action")
    bot = MainBot()
    s = postflop_state()
    assert bot.act(s) == Action("raise", s.legal.max_raise_to)
    assert bot.act(make_state(("As", "Ah"), facing=1, pot=3)).kind == "raise"   # garbage -> fallback
    assert bot.fallbacks["error"] == 1


def test_missing_modules_use_fallback_and_neutral_stats(patch):
    patch(preflop=None, postflop=None, model=None)
    bot = MainBot()
    bot.new_match("m", None)
    bot.hand_over(None)
    assert bot.act(postflop_state()).kind == "raise"
    assert bot.fallbacks["unavailable"] == 1


def test_broken_model_does_not_break_the_bot(patch):
    class Broken:
        def stats(self):
            raise RuntimeError

        def range_estimate(self, state):
            raise RuntimeError

        def observe_hand(self, r):
            raise RuntimeError

    patch(model=Broken, postflop=lambda s, o, r, time_budget_ms=None: Action("check"))
    bot = MainBot()
    bot.hand_over(None)
    assert bot.act(postflop_state()) == Action("check") and bot.fallbacks["observe_error"] == 1


def test_harness_1000_hands_vs_random_no_illegal():
    res = play_match(MainBot(), "random", hands=1000, seed=3, duplicate=True)
    assert res["illegal_a"] == 0 and res["errors_a"] == 0
    assert res["a_ms_max"] < 500


def test_bank_guard_falls_back_when_running_hot(patch):
    patch(postflop=lambda s, o, r, time_budget_ms=None: Action("check"))
    bot = MainBot()
    bot.think_s = 100.0                      # pretend we've already overspent
    a = bot.act(postflop_state())
    assert a.kind == "raise" and bot.fallbacks["bank"] == 1   # fallback bets top pair
    bot.new_match("m2", None)
    assert bot.think_s == 0.0 and bot.act(postflop_state()) == Action("check")


def test_runs_without_numpy():
    import subprocess
    import sys
    from pathlib import Path
    code = r'''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name == "numpy" or name.startswith("numpy."):
            raise ImportError("numpy blocked (tournament sandbox)")
sys.meta_path.insert(0, Block())
import bots.main.bot as B
from pathlib import Path
assert B._postflop is not None, "postflop failed to import without numpy"
if Path("bots/main/opponent.py").exists():
    assert B._OpponentModel is not None, "opponent model failed to import without numpy"
from tests.bots.main.test_fallback import make_state
bot = B.MainBot()
for s in [make_state(("As", "Ah"), facing=10, pot=30), make_state(("As", "Kd"), ("Ah", "7c", "2d"))]:
    a = bot.act(s)
    assert a.kind in ("fold", "check", "call", "raise"), a
assert sum(bot.fallbacks.values()) <= 1, bot.fallbacks   # preflop may be unavailable (#11)
print("ok")
'''
    root = Path(__file__).resolve().parents[3]
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "ok" in out.stdout, out.stderr[-2000:]
