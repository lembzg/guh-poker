import time

import numpy as np
import pytest

from core import equity as E
from core.equity import equity, range_from_classes, rank7, top_percent_range


def h(s):
    return tuple(s.split())


# ------------------------------------------------------------------ rank7

ORDERED = [  # strictly decreasing strength
    "As Ks Qs Js Ts",       # royal flush
    "9h 8h 7h 6h 5h",       # straight flush
    "5d 4d 3d 2d Ad",       # steel wheel (lowest straight flush)
    "Ac Ad Ah As Kc",       # quads, K kicker
    "Ac Ad Ah As 2c",       # quads, 2 kicker
    "Kc Kd Kh As Ac",       # kings full of aces
    "Kc Kd Kh Qs Qc",       # kings full of queens
    "Qc Qd Qh As Ac",       # queens full
    "Ah Jh 9h 5h 3h",       # flush
    "Ah Jh 9h 5h 2h",       # lower flush kicker
    "As Kd Qc Jh Tc",       # broadway
    "6s 5d 4c 3h 2c",       # six-high straight
    "5s 4d 3c 2h Ac",       # wheel
    "7c 7d 7h Ac Kd",       # trips
    "7c 7d 7h Ac Qd",
    "Ac Ad Kh Kc 2d",       # two pair
    "Ac Ad Qh Qc Kd",
    "Ac Ad Qh Qc Jd",
    "Ac Ad Kh Qc Jd",       # one pair
    "Ac Ad Kh Qc Td",
    "Kc Kd Ah Qc Jd",
    "Ac Kd Qh Jc 9d",       # high card
    "Ac Kd Qh Jc 8d",
    "7c 5d 4h 3c 2d",       # worst hand
]


def test_rank_ordering():
    vals = [rank7(h(x)) for x in ORDERED]
    assert all(a > b for a, b in zip(vals, vals[1:])), list(zip(ORDERED, vals))


def test_suits_irrelevant_and_order_irrelevant():
    assert rank7(h("Ac Kd Qh Jc 9d")) == rank7(h("9s Js Qd Kc Ah"))


def test_seven_card_best_five():
    # board plays: both players have the board's straight
    board = "5c 6d 7h 8s 9c"
    assert rank7(h(board + " 2c 2d")) == rank7(h(board + " Ah Kd"))
    # higher straight wins
    assert rank7(h(board + " Ts 2d")) > rank7(h(board + " Ah Kd"))
    # three pairs: best two pairs + best kicker (third pair's rank counts as a kicker)
    assert rank7(h("Ac Ad Kc Kd Qc Qd 2s")) == rank7(h("Ac Ad Kc Kd Qh 3s 2s"))
    # two trips -> full house
    assert rank7(h("Ac Ad Ah Kc Kd Kh 2s")) == rank7(h("Ac Ad Ah Kc Kd 3s 2s"))
    # flush beats straight in the same 7 cards; 6-card flush takes the top 5
    assert rank7(h("2h 4h 6h 8h Th Qh 9c")) == rank7(h("4h 6h 8h Th Qh"))
    # wheel with extra cards, and a 6 making it a 6-high straight
    assert rank7(h("Ac 2d 3h 4s 5c Kd Qh")) == rank7(h("5s 4d 3c 2h Ac"))
    assert rank7(h("Ac 2d 3h 4s 5c 6d Qh")) == rank7(h("6s 5d 4c 3h 2c"))
    # kicker counts when the board pairs
    assert rank7(h("Ks Kd 7c 4h 2s Ah 3d")) > rank7(h("Ks Kd 7c 4h 2s Qh 3d"))


def test_rank7_accepts_5_6_7_and_rejects_bad_input():
    rank7(h("Ac Kd Qh Jc 9d"))
    rank7(h("Ac Kd Qh Jc 9d 2c"))
    for bad in ["Ac Kd Qh Jc", "Ac Kd Qh Jc 9d 2c 3c 4c", "Ac Ac Qh Jc 9d", "Ax Kd Qh Jc 9d"]:
        with pytest.raises(ValueError):
            rank7(h(bad))


def test_vectorised_matches_scalar():
    rng = np.random.default_rng(7)
    for k in (5, 6, 7):
        hands = np.array([rng.permutation(52)[:k] for _ in range(5000)])
        vec = E._rank_matrix(hands)
        assert all(int(v) == E._rank_ints(list(r)) for v, r in zip(vec, hands))


def test_category_frequencies_7_cards():
    rng = np.random.default_rng(3)
    hands = np.argsort(rng.random((100_000, 52)), axis=1)[:, :7]
    freq = np.bincount(E._rank_matrix(hands) >> 25, minlength=9) / len(hands)
    known = [0.1741, 0.4383, 0.2350, 0.0483, 0.0462, 0.0303, 0.0260, 0.00168, 0.00031]
    assert np.allclose(freq, known, atol=0.005)


# ------------------------------------------------------------------ equity

@pytest.mark.parametrize("hole, opp, expected", [
    ("Ah Ac", None, 0.852),
    ("Ah Kh", {"QQ": 1.0}, 0.46),
    ("7h 2c", None, 0.346),
])
def test_known_equities(hole, opp, expected):
    rng = range_from_classes(opp) if opp else None
    assert equity(h(hole), (), rng, samples=20_000, seed=1) == pytest.approx(expected, abs=0.015)


def test_seed_reproducible():
    a = equity(h("Ah Kd"), h("2c 7d Ks"), samples=2000, seed=5)
    assert a == equity(h("Ah Kd"), h("2c 7d Ks"), samples=2000, seed=5)


def test_dead_cards_excluded():
    # Opponent range is AA; with As Ah in our hand only Ad Ac is live, so on a dry board it's a near tie.
    rng = range_from_classes({"AA": 1.0})
    eq = equity(h("As Ah"), h("2c 7d 9s"), rng, samples=5000, seed=1)
    assert 0.45 < eq < 0.55
    # All of their combos dead -> treated as any two cards, still returns a probability.
    assert 0.0 <= equity(h("As Ah"), h("Ad 7d 9s"), {("Ac", "Ad"): 1.0}, samples=500, seed=1) <= 1.0


def test_river_exact():
    board = h("2c 7d 9s Jh 3c")
    assert equity(h("Ah Ad"), board, range_from_classes({"KK": 1.0})) == 1.0
    assert equity(h("Kh Kd"), board, range_from_classes({"AA": 1.0})) == 0.0
    assert equity(h("Ah Kd"), board, {("As", "Kc"): 1.0}) == 0.5
    # weights matter: 3 to 1 in favour of a hand we beat
    eq = equity(h("Qh Qd"), board, {("Ah", "Ac"): 1.0, ("Th", "Tc"): 3.0})
    assert eq == pytest.approx(0.75)


def test_nuts_on_turn_and_drawing_dead():
    assert equity(h("Ah Kh"), h("Qh Jh Th 2c"), samples=500, seed=1) == 1.0
    assert equity(h("2c 3d"), h("Ah Kh Qh Jh"), {("Th", "9c"): 1.0}, samples=500, seed=1) == 0.0


def test_time_budget_stops_early():
    t = time.perf_counter()
    equity(h("Ah Kd"), (), samples=10_000_000, time_budget_ms=30, seed=1)
    assert (time.perf_counter() - t) < 0.5


def test_bad_input():
    for hole, board in [(("Ah",), ()), (h("Ah Kd"), h("2c 3c")), (h("Ah Ah"), ()), (h("Ah Kd"), h("Ah 2c 3c"))]:
        with pytest.raises(ValueError):
            equity(hole, board, samples=10)


def test_speed_2000_samples():
    equity(h("Ah Kd"), h("2c 7d Ks"), samples=2000, seed=0)  # warm-up
    t = time.perf_counter()
    for i in range(10):
        equity(h("Ah Kd"), (), top_percent_range(0.3), samples=2000, seed=i)
    per_call_ms = (time.perf_counter() - t) * 100
    assert per_call_ms < 20, per_call_ms


# ------------------------------------------------------------------ ranges

def test_range_from_classes_counts_and_keys():
    r = range_from_classes({"AKs": 1.0, "AKo": 0.5, "77": 0.25})
    assert len(r) == 4 + 12 + 6
    assert r[("As", "Ks")] == 1.0 and r[("Ah", "Kc")] == 0.5 and r[("7s", "7c")] == 0.25
    assert len(range_from_classes({"T9": 1.0})) == 16
    for bad in ["AKx", "77s", "A", "1Ks"]:
        with pytest.raises(ValueError):
            range_from_classes({bad: 1.0})


def test_top_percent_range():
    assert top_percent_range(0) == {}
    assert len(top_percent_range(1.0)) == 1326
    r = top_percent_range(0.1)
    assert sum(r.values()) == pytest.approx(132.6)
    assert r[("As", "Ah")] == 1.0 and ("7h", "2c") not in r
    tight = equity(h("Ah Kd"), (), top_percent_range(0.05), samples=5000, seed=1)
    loose = equity(h("Ah Kd"), (), top_percent_range(0.8), samples=5000, seed=1)
    assert tight < loose


def test_ranking_table_is_complete():
    ranking = E._preflop_ranking()
    assert len(ranking) == 169 == len(set(ranking))
    assert ranking[0] == "AA" and ranking[-1] == "32o"
