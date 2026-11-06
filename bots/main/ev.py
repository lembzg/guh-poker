"""Postflop EV engine (#24): score each action by simulating the opponent's response across their range.

    combo_equities(...)  our equity against each specific opponent combo (exact over runouts, or sampled)
    score_actions(...)   expected chips, counted from now, of fold / check / call / each bet or raise size

The opponent responds by strength within their range (the rank of their made hand on this board):
the weakest share folds (from `fold_to_bet`, scaled by bet size), the strongest share raises (from
`aggression`), the rest calls. When they raise, we call or fold by our equity against their raising
hands. After the current action the hand is assumed to check down, so later betting is not modelled.

Pure functions on primitives; stats are duck-typed (any object with fold_to_bet / aggression attributes,
or None). Built for the tournament's large time budget: a flop decision is exact over all 1,081 runouts
in under a second; pass `runouts` (or `time_budget_ms`) to sample fewer for fast harness runs.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass

import numpy as np

from core.equity import _CARD_TO_IDX, _IDX_TO_CARD, _rank_ints, _rank_matrix, Range

DEFAULT_SIZES = (0.33, 0.5, 0.75, 1.0)
DEFAULT_FOLD_TO_BET = 0.40
DEFAULT_AGGRESSION = 1.0
ROWS_PER_MS = 800          # conservative evaluator throughput, used to fit `time_budget_ms`
_CHUNK_ROWS = 100_000      # opponent hands evaluated per numpy batch (bounds memory)
_ALL_COMBOS = np.array([(a, b) for a in range(52) for b in range(a)], dtype=np.int64)


@dataclass(frozen=True)
class ActionEV:
    kind: str          # "fold", "check", "call" or "raise"
    add: int           # chips we put in now (0 for fold/check; to_call for call; to_call + bet for raise)
    frac: float | None  # for raises: bet size as a share of the pot after calling; "all-in" = None
    ev: float          # expected chips won from now on (folding = 0)


# ------------------------------------------------------------------ equity per combo

def _combos_and_weights(opp_range: Range | None, dead: set[int]) -> tuple[np.ndarray, np.ndarray]:
    if opp_range is None:
        live = ~np.isin(_ALL_COMBOS, list(dead)).any(axis=1)
        combos = _ALL_COMBOS[live]
        return combos, np.ones(len(combos))
    acc: dict[tuple[int, int], float] = {}
    for (a, b), w in opp_range.items():
        if not w or w <= 0:
            continue
        ia, ib = _CARD_TO_IDX[a], _CARD_TO_IDX[b]
        if ia == ib or ia in dead or ib in dead:
            continue
        key = (ia, ib) if ia > ib else (ib, ia)
        acc[key] = acc.get(key, 0.0) + float(w)
    if not acc:
        return _combos_and_weights(None, dead)
    return np.array(list(acc), dtype=np.int64), np.array(list(acc.values()))


def _runout_matrix(deck: list[int], need: int, runouts: int | None, rng: np.random.Generator) -> np.ndarray:
    all_runs = np.array(list(itertools.combinations(deck, need)), dtype=np.int64).reshape(-1, need)
    if runouts is not None and runouts < len(all_runs):
        all_runs = all_runs[rng.choice(len(all_runs), size=max(1, runouts), replace=False)]
    return all_runs


def _equities(hero: list[int], board: list[int], combos: np.ndarray, runouts: int | None,
              seed: int | None) -> np.ndarray:
    need = 5 - len(board)
    if need == 0:
        h = _rank_ints(hero + board)
        o = _rank_matrix(np.concatenate([combos, np.broadcast_to(np.array(board), (len(combos), 5))], axis=1))
        return (h > o) + 0.5 * (h == o)
    deck = [c for c in range(52) if c not in set(hero + board)]
    runs = _runout_matrix(deck, need, runouts, np.random.default_rng(seed))
    k = len(runs)
    brd = np.broadcast_to(np.array(board, dtype=np.int64), (k, len(board)))
    full_boards = np.concatenate([brd, runs], axis=1)                                        # (K, 5)
    hv = _rank_matrix(np.concatenate([np.broadcast_to(np.array(hero), (k, 2)), full_boards], axis=1))
    score = np.zeros(len(combos))
    count = np.zeros(len(combos))
    per = max(1, _CHUNK_ROWS // k)
    for s in range(0, len(combos), per):
        cc = combos[s:s + per]                                                               # (m, 2)
        m = len(cc)
        clash = (runs[None, :, :, None] == cc[:, None, None, :]).any(axis=(2, 3))            # (m, K)
        opp_cards = np.repeat(cc, k, axis=0)
        opp_cards[clash.reshape(-1)] = hero      # runout reuses their card: evaluate a dummy, masked below
        ov = _rank_matrix(np.concatenate([opp_cards, np.tile(full_boards, (m, 1))], axis=1)).reshape(m, k)
        valid = ~clash
        score[s:s + m] = (((hv > ov) + 0.5 * (hv == ov)) * valid).sum(axis=1)
        count[s:s + m] = valid.sum(axis=1)
    return score / np.maximum(count, 1)


def combo_equities(hole: tuple[str, str], board: tuple[str, ...], combos, runouts: int | None = None,
                   seed: int | None = None) -> dict[tuple[str, str], float]:
    """Our equity (win + tie/2) against each opponent combo. combos: iterable of card pairs or a Range.
    Exact over every runout when runouts is None; otherwise over `runouts` sampled runouts (shared)."""
    hero = [_CARD_TO_IDX[c] for c in hole]
    brd = [_CARD_TO_IDX[c] for c in board]
    if len(brd) not in (3, 4, 5):
        raise ValueError("combo_equities is for postflop boards (3-5 cards)")
    arr, _ = _combos_and_weights({tuple(c): 1.0 for c in combos}, set(hero + brd))
    eq = _equities(hero, brd, arr, runouts, seed)
    return {(_IDX_TO_CARD[a], _IDX_TO_CARD[b]): float(e) for (a, b), e in zip(arr, eq)}


# ------------------------------------------------------------------ opponent response model

def _weighted_pct(vals: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted strength percentile in [0, 1]; equal values share their group's midpoint."""
    order = np.argsort(vals, kind="stable")
    sv, sw = vals[order], w[order]
    total = sw.sum()
    uniq, first = np.unique(sv, return_index=True)
    group = np.searchsorted(uniq, sv)
    gw = np.bincount(group, weights=sw)
    below = np.cumsum(gw) - gw
    mid = (below + gw / 2) / max(total, 1e-12)
    out = np.empty(len(vals))
    out[order] = mid[group]
    return out


def _stat(stats, name: str, default: float) -> float:
    v = getattr(stats, name, None) if stats is not None else None
    return default if v is None else float(v)


def fold_share(stats, frac: float) -> float:
    """Share of their range that folds to a bet of `frac` x pot (calibrated so frac 2/3 = fold_to_bet)."""
    fb = _stat(stats, "fold_to_bet", DEFAULT_FOLD_TO_BET)
    return float(np.clip(fb * (0.8 + 0.3 * min(frac, 1.5)), 0.0, 0.95))   # many bots barely react to size


def raise_share(stats) -> float:
    return float(np.clip(0.04 * _stat(stats, "aggression", DEFAULT_AGGRESSION), 0.0, 0.35))


# ------------------------------------------------------------------ scoring

def score_actions(hole: tuple[str, str], board: tuple[str, ...], pot: int, to_call: int, my_behind: int,
                  opp_behind: int, opp_range: Range | None = None, opp_stats=None,
                  sizes: tuple[float, ...] = DEFAULT_SIZES, min_bet: int = 1, runouts: int | None = None,
                  seed: int | None = None, time_budget_ms: float | None = None) -> list[ActionEV]:
    """EV (chips from now; folding = 0) of each legal-looking action.

    pot: chips in the pot now, including any bet we face. to_call: chips we must add to call.
    my_behind / opp_behind: chips each player has behind now. min_bet: smallest extra over the call that
    counts as a legal bet/raise. If time_budget_ms is set and an exact flop count wouldn't fit, runouts
    are sampled to fit.
    """
    t0 = time.perf_counter()
    hero = [_CARD_TO_IDX[c] for c in hole]
    brd = [_CARD_TO_IDX[c] for c in board]
    if len(brd) not in (3, 4, 5):
        raise ValueError("score_actions is for postflop boards (3-5 cards)")
    combos, w = _combos_and_weights(opp_range, set(hero + brd))
    if time_budget_ms is not None and len(brd) < 5:
        n_runs = 47 * 46 // 2 if len(brd) == 3 else 46
        fit = int(time_budget_ms * 0.7 * ROWS_PER_MS / max(1, len(combos)))
        if fit < n_runs:
            runouts = max(8, min(runouts or n_runs, fit))
    e = _equities(hero, brd, combos, runouts, seed)
    strength = _rank_matrix(np.concatenate([combos, np.broadcast_to(np.array(brd), (len(combos), len(brd)))],
                                           axis=1))
    pct = _weighted_pct(strength, w)
    W = w.sum()

    def mean(x, mask=None):
        ww = w if mask is None else w * mask
        s = ww.sum()
        return float((ww * x).sum() / s) if s > 0 else 0.0

    out: list[ActionEV] = []
    eq_all = mean(e)
    if to_call > 0:
        out.append(ActionEV("fold", 0, None, 0.0))
        call = min(to_call, my_behind)
        out.append(ActionEV("call", call, None, eq_all * (pot + call) - call))
    else:
        out.append(ActionEV("check", 0, None, eq_all * pot))

    eff = min(my_behind - to_call, opp_behind)      # the most a bet can put at risk
    if eff <= 0 or my_behind <= to_call:
        return out
    p_after_call = pot + to_call
    candidates = {}
    for f in sizes:
        b = int(round(f * p_after_call))
        if b >= eff:
            continue
        if b >= max(1, min_bet):
            candidates[b] = f
    candidates[eff] = None                           # all-in (for the effective stack)
    r_share = raise_share(opp_stats) if opp_behind > 0 else 0.0
    for b, f in sorted(candidates.items()):
        frac = b / p_after_call
        fold = pct < fold_share(opp_stats, frac)
        rz = (pct >= 1 - r_share) & ~fold if b < opp_behind else np.zeros(len(pct), dtype=bool)
        add = to_call + b
        ev_call = e * (pot + to_call + 2 * b) - add
        ev = np.where(fold, float(pot), ev_call)
        if rz.any():
            x = min(opp_behind - b, pot + to_call + 2 * b, my_behind - add)   # their pot-size re-raise
            if x > 0:
                final = pot + to_call + 2 * b + 2 * x
                ev_vs_raise_call = e * final - (add + x)
                we_call = mean(ev_vs_raise_call, rz) > -add
                ev = np.where(rz, ev_vs_raise_call if we_call else -float(add), ev)
            else:
                ev = np.where(rz, ev_call, ev)
        out.append(ActionEV("raise", add, f, float((w * ev).sum() / W)))
        if time_budget_ms is not None and (time.perf_counter() - t0) * 1000 > time_budget_ms:
            break
    return out


def best_action(evs: list[ActionEV]) -> ActionEV:
    return max(evs, key=lambda a: a.ev)
