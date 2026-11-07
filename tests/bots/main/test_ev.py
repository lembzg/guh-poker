import time
from types import SimpleNamespace

import numpy as np
import pytest

from bots.main.ev import best_action, combo_equities, fold_share, score_actions
from core.equity import equity, range_from_classes, top_percent_range

STATION = SimpleNamespace(fold_to_bet=0.03, aggression=0.3)
FOLDER = SimpleNamespace(fold_to_bet=0.85, aggression=0.5)


def by_kind(evs):
    return {(a.kind, a.frac): a.ev for a in evs}


def test_combo_equities_exact_on_river_and_turn():
    board = ("Th", "9c", "2d", "3s", "Kd")
    ce = combo_equities(("Qh", "Jh"), board, [("As", "Ad"), ("Kh", "Kc"), ("Qs", "Jc"), ("Ac", "Qd")])
    assert ce == {("As", "Ad"): 1.0, ("Kh", "Kc"): 1.0, ("Qs", "Jc"): 0.5, ("Ac", "Qd"): 1.0}   # we hold the K-high straight
    turn = board[:4]
    ce = combo_equities(("Qh", "Jh"), turn, [("As", "Ad")])
    sampled = equity(("Qh", "Jh"), turn, {("As", "Ad"): 1.0}, samples=200_000, seed=1)
    assert ce[("As", "Ad")] == pytest.approx(sampled, abs=0.01)
    assert ce[("As", "Ad")] * 44 == pytest.approx(round(ce[("As", "Ad")] * 44))   # exact: k of 44 rivers


def test_combo_equities_match_monte_carlo_on_flop():
    r = top_percent_range(0.4)
    ce = combo_equities(("Qh", "Jh"), ("Th", "9c", "2d"), list(r))
    exact = np.average(list(ce.values()), weights=[r[k] for k in ce])
    assert exact == pytest.approx(equity(("Qh", "Jh"), ("Th", "9c", "2d"), r, samples=60_000, seed=3), abs=0.006)
    assert all(("Qh" not in k and "Th" not in k) for k in ce)      # dead cards dropped


def test_sampled_runouts_close_to_exact():
    r = top_percent_range(0.3)
    exact = combo_equities(("Ah", "Kd"), ("Kh", "7c", "2s"), list(r))
    sampled = combo_equities(("Ah", "Kd"), ("Kh", "7c", "2s"), list(r), runouts=300, seed=1)
    keys = list(exact)
    assert np.mean([abs(exact[k] - sampled[k]) for k in keys]) < 0.03


def test_call_ev_is_equity_times_pot_minus_call():
    r = range_from_classes({"AA": 1, "KK": 1, "QJs": 1})
    board = ("Th", "9c", "2d", "3s")
    evs = by_kind(score_actions(("Ad", "Kc"), board, pot=60, to_call=20, my_behind=100, opp_behind=80, opp_range=r))
    eq = np.average(list(combo_equities(("Ad", "Kc"), board, list(r)).values()))
    assert evs[("fold", None)] == 0.0
    assert evs[("call", None)] == pytest.approx(eq * 80 - 20)


def test_nuts_on_river_bets_biggest_vs_station():
    evs = score_actions(("Qh", "Jh"), ("Th", "9c", "2d", "3s", "Kd"), pot=40, to_call=0, my_behind=180,
                        opp_behind=180, opp_range=top_percent_range(0.6), opp_stats=STATION)
    best = best_action(evs)
    assert best.kind == "raise" and best.add == 180


def test_air_checks_vs_station_but_bluffs_folder():
    args = dict(hole=("7c", "6d"), board=("As", "Kd", "Qh", "3s", "2c"), pot=40, to_call=0, my_behind=180,
                opp_behind=180, opp_range=top_percent_range(0.5))
    assert best_action(score_actions(opp_stats=STATION, **args)).kind == "check"
    assert best_action(score_actions(opp_stats=FOLDER, **args)).kind == "raise"


def test_air_folds_to_a_big_bet():
    evs = score_actions(("7c", "6d"), ("As", "Kd", "Qh", "3s", "2c"), pot=80, to_call=40, my_behind=160,
                        opp_behind=120, opp_range=top_percent_range(0.3), opp_stats=STATION)
    assert best_action(evs).kind == "fold"


def test_bet_sizes_respect_stacks_and_min_bet():
    evs = score_actions(("Ah", "Ad"), ("As", "7c", "2d"), pot=100, to_call=0, my_behind=60, opp_behind=500,
                        min_bet=40)
    raises = [a for a in evs if a.kind == "raise"]
    assert all(40 <= a.add <= 60 for a in raises) and max(a.add for a in raises) == 60
    assert score_actions(("Ah", "Ad"), ("As", "7c", "2d"), 100, 10, 10, 50)[-1].kind == "call"   # all-in call only


def test_fold_share_scales_with_size():
    assert fold_share(None, 0.33) < fold_share(None, 0.66) < fold_share(None, 1.5)
    assert fold_share(SimpleNamespace(fold_to_bet=0.5, aggression=None), 2 / 3) == pytest.approx(0.5)


def test_time_budget_samples_runouts():
    t = time.perf_counter()
    score_actions(("Qh", "Jh"), ("Th", "9c", "2d"), 40, 0, 180, 180, None, time_budget_ms=40)
    assert (time.perf_counter() - t) * 1000 < 150


def test_rejects_preflop():
    with pytest.raises(ValueError):
        score_actions(("Qh", "Jh"), (), 3, 1, 199, 198)


MANIAC = SimpleNamespace(fold_to_bet=0.1, aggression=6.0, avg_bet_frac=1.0)
PASSIVE = SimpleNamespace(fold_to_bet=0.4, aggression=0.4, avg_bet_frac=0.5)


def check_ev(stats, in_position, hole=("Ah", "Kd"), board=("As", "8c", "3d")):
    evs = score_actions(hole, board, 20, 0, 190, 190, top_percent_range(0.6), stats, runouts=100, seed=1,
                        in_position=in_position)
    return by_kind(evs)[("check", None)]


def test_out_of_position_check_values_their_bets():
    # Strong hand OOP: checking to a maniac is worth much more than checking it down.
    assert check_ev(MANIAC, False) > check_ev(MANIAC, True) + 10
    # Against a passive bot, checking OOP adds little.
    assert check_ev(PASSIVE, False) - check_ev(PASSIVE, True) < check_ev(MANIAC, False) - check_ev(MANIAC, True)


def test_weak_hand_check_oop_costs_equity_vs_aggression():
    weak = dict(hole=("7c", "6d"), board=("As", "Kd", "Qh"))
    assert check_ev(MANIAC, False, **weak) <= check_ev(MANIAC, True, **weak) + 0.5   # they bet us off it


def test_draws_count_as_strength():
    from bots.main.ev import _strength_vs_random
    import numpy as np
    from core.equity import _CARD_TO_IDX as I
    board = [I[c] for c in ("Kh", "9h", "2c")]
    combos = np.array([[I["Ah"], I["5h"]], [I["4d"], I["3s"]], [I["Kd"], I["Qc"]]])
    s = _strength_vs_random(combos, board, 400, np.random.default_rng(1))
    assert s[2] > s[0] > s[1] and s[0] > 0.5        # nut flush draw beats air, below top pair


def test_short_allin_call_excludes_opponent_uncallable_excess():
    # Hero has 10 in and 10 behind; villain has 100 in. 80 must be returned.
    args = dict(hole=('As','Ah'), board=('2c','3d','7h','8s','Jc'), pot=110,
                to_call=90, my_behind=10, opp_behind=100, opp_range={('Ks','Kh'):1})
    call = next(a for a in score_actions(**args) if a.kind == 'call')
    assert call.add == 10 and call.ev == 30
