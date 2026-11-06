"""Match runner (#6): plays many hands between two bots and reports bb/100 with a 95% CI, latency and
illegal-action counts. Output format: docs/API.md -> Harness result."""
from __future__ import annotations

import math
import random
import subprocess
from pathlib import Path

from core.equity import RANKS, SUITS
from harness.engine import Seat, play_hand, results_for
from harness.opponents import OPPONENTS

_DECK = [r + s for r in RANKS for s in SUITS]
_REPO = Path(__file__).resolve().parent.parent


def make_bot(name: str, **cfg):
    """Harness opponents by name; anything else goes through the bot registry (bots.make_bot, #4)."""
    if name in OPPONENTS:
        return OPPONENTS[name](**cfg)
    try:
        from bots import make_bot as registry
    except ImportError as e:
        raise ValueError(f"unknown bot {name!r}: not a harness opponent and bots.make_bot is unavailable ({e})")
    return registry(name, **cfg)


def code_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_REPO, capture_output=True,
                             text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=_REPO,
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return (sha or "nogit") + ("-dirty" if dirty else "")
    except Exception:
        return "nogit"


def deal(seed: int, n: int) -> list[str]:
    deck = list(_DECK)
    random.Random(seed * 1_000_003 + n).shuffle(deck)
    return deck


def _ci95(units: list[float]) -> float | None:
    if len(units) < 2:
        return None
    mean = sum(units) / len(units)
    var = sum((u - mean) ** 2 for u in units) / (len(units) - 1)
    return 1.96 * math.sqrt(var / len(units))


def play_match(bot_a, bot_b, hands: int, seed: int, duplicate: bool = False, stack: int = 200, bb: int = 2,
               reset_stacks: bool = True) -> dict:
    """Play `hands` hands of bot_a vs bot_b (names or Bot instances); return the Harness result dict.

    Non-duplicate: a fresh deal every hand, button alternating. Duplicate: every deal is played twice
    with seats swapped (same cards to the same position), so `hands` is rounded up to an even number and
    the CI is computed over deal pairs. reset_stacks=False carries stacks between hands (both reset when
    one busts) and can't be combined with duplicate.
    """
    if duplicate and not reset_stacks:
        raise ValueError("duplicate mode needs reset_stacks=True")
    if hands < 1 or bb < 2 or stack < bb:
        raise ValueError("need hands >= 1, bb >= 2 and stack >= bb")
    a = make_bot(bot_a) if isinstance(bot_a, str) else bot_a
    b = make_bot(bot_b) if isinstance(bot_b, str) else bot_b
    name_a = bot_a if isinstance(bot_a, str) else getattr(a, "name", type(a).__name__)
    name_b = bot_b if isinstance(bot_b, str) else getattr(b, "name", type(b).__name__)
    sa, sb_ = Seat(a), Seat(b)
    for seat, opp in ((sa, name_b), (sb_, name_a)):
        try:
            seat.bot.new_match(f"seed{seed}", opp)
        except Exception:
            seat.errors += 1

    small_blind = bb // 2
    n_hands = hands + (hands % 2 if duplicate else 0)
    a_deltas: list[int] = []
    stacks = {id(sa): stack, id(sb_): stack}
    for i in range(n_hands):
        a_button = i % 2 == 0
        deck = deal(seed, i // 2 if duplicate else i)
        seats = (sa, sb_) if a_button else (sb_, sa)
        st = (stacks[id(seats[0])], stacks[id(seats[1])]) if not reset_stacks else (stack, stack)
        out = play_hand(seats, deck, st, small_blind, bb, hand_id=i)
        res = results_for(out, (tuple(deck[0:2]), tuple(deck[2:4])), hand_id=i)
        seats[0].notify(res[0])
        seats[1].notify(res[1])
        a_deltas.append(out.deltas[0] if a_button else out.deltas[1])
        if not reset_stacks:
            stacks[id(seats[0])] += out.deltas[0]
            stacks[id(seats[1])] += out.deltas[1]
            if min(stacks.values()) < bb:
                stacks = {id(sa): stack, id(sb_): stack}

    if duplicate:
        units = [(a_deltas[k] + a_deltas[k + 1]) / 2 for k in range(0, n_hands, 2)]
    else:
        units = [float(d) for d in a_deltas]
    scale = 100.0 / bb
    ci = _ci95(units)
    ver = code_version()

    def ms(seat: Seat) -> tuple[float, float]:
        return (round(seat.total_ms / seat.decisions, 3) if seat.decisions else 0.0, round(seat.max_ms, 2))

    a_avg, a_max = ms(sa)
    b_avg, b_max = ms(sb_)
    return {
        "bot_a": f"{name_a}@{ver}", "bot_b": f"{name_b}@{ver}", "hands": n_hands, "duplicate": duplicate,
        "seed": seed, "stack_bb": stack / bb if stack % bb else stack // bb,
        "bb_per_100": round(sum(a_deltas) / n_hands * scale, 2),
        "ci95": round(ci * scale, 2) if ci is not None else None,
        "a_ms_avg": a_avg, "a_ms_max": a_max, "b_ms_avg": b_avg, "b_ms_max": b_max,
        "illegal_a": sa.illegal, "illegal_b": sb_.illegal, "errors_a": sa.errors, "errors_b": sb_.errors,
    }
