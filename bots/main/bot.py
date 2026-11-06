"""MainBot (#5): the bot we enter. Contract: docs/API.md -> Strategy modules (bot.py), Bot.

Routes preflop to `preflop_action`, postflop to `postflop_action(state, model.stats(),
model.range_estimate(state))`, and feeds finished hands to the OpponentModel. Every decision goes through:
  * a time guard: the strategy runs on a worker thread; if it raises or overruns the budget
    (time_budget_ms, also capped by state.time_left_ms), we answer with fallback_action instead;
  * clamp_to_legal on whatever comes back.
Strategy imports are guarded, so a missing or broken module just means the fallback (or neutral stats).
"""
from __future__ import annotations

import inspect
import logging
import threading
import time
from collections import Counter

from bots.main.fallback import fallback_action
from core.interface import Action, GameState, HandResult, OpponentStats, clamp_to_legal

log = logging.getLogger("bots.main")

try:
    from bots.main.preflop import preflop_action as _preflop
except Exception as e:  # missing (#11 not landed) or broken
    _preflop = None
    log.warning("preflop strategy unavailable, using fallback: %r", e)
try:
    from bots.main.postflop import postflop_action as _postflop
except Exception as e:
    _postflop = None
    log.warning("postflop strategy unavailable, using fallback: %r", e)
try:
    from bots.main.opponent import OpponentModel as _OpponentModel
except Exception as e:
    _OpponentModel = None
    log.warning("opponent model unavailable, using neutral stats: %r", e)

TIME_LEFT_SHARE = 0.25   # never spend more than this share of a reported clock on one decision
SAFETY_MS = 15.0         # headroom for thread hand-off, the fallback and clamping
POSTFLOP_SHARE = 0.6     # share of the budget handed to postflop's equity sampling


class _Timeout(Exception):
    pass


def _accepts_budget(fn) -> bool:
    """postflop_action's time_budget_ms is an optional extra beyond the contract."""
    try:
        return "time_budget_ms" in inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False


def _run_with_timeout(fn, timeout_s: float):
    """Run fn() on a daemon thread; return its result, re-raise its exception, or raise _Timeout.
    A thread that overruns is abandoned (Python can't kill it); it finishes in the background."""
    box: dict = {}

    def target():
        try:
            box["result"] = fn()
        except BaseException as e:  # noqa: BLE001 - reported to the caller
            box["error"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise _Timeout()
    if "error" in box:
        raise box["error"]
    return box["result"]


class MainBot:
    name = "main"

    def __init__(self, time_budget_ms: int = 500, **cfg):
        self.time_budget_ms = float(time_budget_ms)
        self.cfg = cfg
        self.fallbacks: Counter = Counter()   # reason -> count; read by tests and tuning scripts
        self.model = None
        self._new_model()

    def _new_model(self) -> None:
        self.model = None
        if _OpponentModel is not None:
            try:
                self.model = _OpponentModel()
            except Exception as e:
                log.warning("OpponentModel() failed: %r", e)

    # ------------------------------------------------------------- Bot protocol

    def new_match(self, match_id: str, opponent: str | None) -> None:
        self.fallbacks.clear()
        self._new_model()

    def hand_over(self, result: HandResult) -> None:
        if self.model is not None:
            try:
                self.model.observe_hand(result)
            except Exception as e:
                self.fallbacks["observe_error"] += 1
                log.debug("observe_hand failed: %r", e)

    def act(self, state: GameState) -> Action:
        start = time.perf_counter()
        try:
            budget_ms = self._budget_ms(state)
            strategy = self._strategy_for(state, budget_ms)
            if strategy is None:
                self.fallbacks["unavailable"] += 1
                return self._fallback(state)
            remaining_s = max(0.0, budget_ms - (time.perf_counter() - start) * 1000.0) / 1000.0
            action = _run_with_timeout(strategy, remaining_s)
            if not isinstance(getattr(action, "kind", None), str):
                raise TypeError(f"strategy returned {action!r}")
            return clamp_to_legal(action, state.legal)
        except _Timeout:
            self.fallbacks["timeout"] += 1
            log.warning("hand %s street %s: strategy over budget, using fallback", state.hand_id, state.street)
        except Exception as e:
            self.fallbacks["error"] += 1
            log.warning("hand %s street %s: strategy failed (%r), using fallback",
                        getattr(state, "hand_id", "?"), getattr(state, "street", "?"), e)
        return self._fallback(state)

    # ------------------------------------------------------------- internals

    def _budget_ms(self, state: GameState) -> float:
        budget = self.time_budget_ms
        if state.time_left_ms is not None:
            budget = min(budget, state.time_left_ms * TIME_LEFT_SHARE)
        return max(1.0, budget - SAFETY_MS)

    def _strategy_for(self, state: GameState, budget_ms: float):
        if state.street == 1:
            if _preflop is None:
                return None
            stats = self._stats()
            return lambda: _preflop(state, stats)
        if _postflop is None:
            return None
        model = self.model
        kwargs = {"time_budget_ms": budget_ms * POSTFLOP_SHARE} if _accepts_budget(_postflop) else {}

        def run():   # range_estimate runs inside the time guard too
            rng = None
            if model is not None:
                try:
                    rng = model.range_estimate(state)
                except Exception:
                    rng = None
            return _postflop(state, self._stats(), rng, **kwargs)
        return run

    def _stats(self) -> OpponentStats:
        if self.model is None:
            return OpponentStats()
        try:
            return self.model.stats()
        except Exception:
            return OpponentStats()

    def _fallback(self, state: GameState) -> Action:
        try:
            return fallback_action(state)
        except Exception:
            lg = state.legal
            return Action("check") if lg.can_check else Action("fold")
