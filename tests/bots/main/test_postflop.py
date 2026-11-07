import time

import pytest

from bots.main.postflop import has_draw, is_wet, knobs, postflop_action
from core.equity import range_from_classes, top_percent_range
from core.interface import Action, ActionRecord, GameState, LegalActions, OpponentStats

R = ActionRecord
STATION = OpponentStats(hands=200, vpip=0.9, pfr=0.05, fold_to_bet=0.05, fold_to_cbet=0.05, aggression=0.3,
                        wtsd=0.7)
FOLDER = OpponentStats(hands=200, vpip=0.5, pfr=0.2, fold_to_bet=0.8, fold_to_cbet=0.8, aggression=0.6,
                       wtsd=0.15)
MANIAC = OpponentStats(hands=200, vpip=0.95, pfr=0.9, fold_to_bet=0.1, aggression=6.0, wtsd=0.6)


def spot(hole, board, facing=0, pot=20, stack=200, button=True, history=None, hand_id=1):
    """A postflop spot: both put pot/2 in; `facing` = chips the opponent has bet on top."""
    half = pot // 2
    my, opp = half, half + facing
    street = {3: 2, 4: 3, 5: 4}[len(board.split())]
    if facing:
        legal = LegalActions(True, False, min(facing, stack - my),
                             opp + facing if stack - my > facing else None, stack if stack - my > facing else None)
    else:
        legal = LegalActions(False, True, 0, my + 2, stack)
    hist = history if history is not None else [R(1, "me", "raise", 6), R(1, "opp", "call", None)]
    if facing:
        hist = hist + [R(street, "opp", "raise", opp)]
    return GameState(hand_id=hand_id, is_button=button, hole_cards=tuple(hole.split()), board=tuple(board.split()),
                     street=street, small_blind=1, big_blind=2, starting_stack=stack, my_committed=my,
                     opp_committed=opp, history=tuple(hist), legal=legal)


def legal_ok(a: Action, s: GameState) -> bool:
    lg = s.legal
    if a.kind == "raise":
        return lg.min_raise_to is not None and isinstance(a.raise_to, int) and lg.min_raise_to <= a.raise_to <= lg.max_raise_to
    return {"fold": lg.can_fold, "check": lg.can_check, "call": lg.call_amount > 0}[a.kind]


def test_nuts_bets_when_checked_to():
    s = spot("Ah Kh", "Qh Jh Th")
    a = postflop_action(s, None, None)
    assert a.kind == "raise" and legal_ok(a, s)


def test_nuts_raises_facing_a_bet():
    s = spot("Ah Ad", "As Ac 7d 2h", facing=10, pot=40)
    a = postflop_action(s, None, None)
    assert a.kind == "raise" and legal_ok(a, s)


def test_air_folds_to_pot_bet_on_river():
    s = spot("4c 3d", "As Kd 9h 8s 2c", facing=40, pot=40)
    assert postflop_action(s, None, top_percent_range(0.4)).kind == "fold"


def test_flush_draw_calls_small_bet_folds_huge_one():
    small = spot("Ah 5h", "Kh 9h 2c", facing=5, pot=40)
    assert postflop_action(small, None, top_percent_range(0.5)).kind in ("call", "raise")
    huge = spot("Ah 5h", "Kh 9h 2c 3s", facing=190, pot=10, stack=200)
    assert postflop_action(huge, None, range_from_classes({"KK": 1, "99": 1, "K9s": 1, "AK": 1})).kind == "fold"


FOLD_COUNTS = {"fold_to_bet": (40, 50), "fold_to_bet_by_street": {2: (15, 18), 3: (12, 16), 4: (13, 16)},
               "bet_when_checked_to": (5, 30)}
STATION_COUNTS = {"fold_to_bet": (2, 50), "fold_to_bet_by_street": {}, "bet_when_checked_to": (3, 30)}
AUTO_BET_COUNTS = {"fold_to_bet": (10, 30), "fold_to_bet_by_street": {}, "bet_when_checked_to": (40, 45)}


def test_river_bluff_only_with_confident_fold_data():
    s = spot("7c 6d", "As Kd Qh 3s 2c")
    assert postflop_action(s, FOLDER, top_percent_range(0.5), opp_counts=FOLD_COUNTS).kind == "raise"
    assert postflop_action(s, STATION, top_percent_range(0.5), opp_counts=STATION_COUNTS).kind == "check"
    assert postflop_action(s, FOLDER, top_percent_range(0.5), opp_counts={}).kind == "check"      # no data


def test_pure_air_never_bluffs_without_data_but_draws_semi_bluff():
    assert postflop_action(spot("7c 6d", "As Kd 2h"), None, top_percent_range(0.5)).kind == "check"
    assert postflop_action(spot("Ah 5h", "Kh 9h 2c"), None, top_percent_range(0.5)).kind == "raise"


def test_turn_barrel_needs_same_street_evidence():
    hist = [R(1, "me", "raise", 6), R(1, "opp", "call", None), R(2, "me", "raise", 9), R(2, "opp", "call", None)]
    s = spot("7c 6d", "As Kd Qh 2c", pot=24, history=hist)
    thin = {"fold_to_bet": (40, 50), "fold_to_bet_by_street": {3: (5, 6)}}
    assert postflop_action(s, FOLDER, top_percent_range(0.5), opp_counts=thin).kind == "check"
    assert postflop_action(s, FOLDER, top_percent_range(0.5), opp_counts=FOLD_COUNTS).kind == "raise"


def test_value_vs_station_is_thin_and_never_overbet():
    s = spot("Ah 9c", "As 8d 4h 2s 7c", pot=40)
    a = postflop_action(s, STATION, top_percent_range(0.9), opp_counts=STATION_COUNTS)
    assert a.kind == "raise" and a.raise_to - s.my_committed <= 0.86 * 40
    nuts = spot("Qh Jh", "Th 9c 8d 2s Kd", pot=40)
    a = postflop_action(nuts, STATION, top_percent_range(0.9), opp_counts=STATION_COUNTS)
    assert a.kind == "raise" and a.raise_to - nuts.my_committed <= 0.86 * 40


def test_auto_bettor_called_at_pot_odds():
    s = spot("Qd 7c", "Qs 8d 4h 2s", facing=30, pot=30)
    assert postflop_action(s, None, top_percent_range(0.6), opp_counts=AUTO_BET_COUNTS).kind in ("call", "raise")


def test_traps_maniac_out_of_position():
    checks = sum(postflop_action(spot("Ad Qc", "As Kd 7h", button=False, hand_id=i), MANIAC,
                                 top_percent_range(0.9)).kind == "check" for i in range(20))
    bets = sum(postflop_action(spot("Ad Qc", "As Kd 7h", button=False, hand_id=i), None,
                               top_percent_range(0.9)).kind == "raise" for i in range(20))
    assert checks >= 8 and bets == 20


def test_calls_maniac_wider():
    s = spot("Qd Jc", "Qs 8d 4h 2s", facing=30, pot=30)
    assert postflop_action(s, MANIAC, None).kind in ("call", "raise")


def test_short_stack_value_goes_all_in():
    s = spot("Ah Ad", "As 8d 4h", pot=60, stack=80)
    a = postflop_action(s, None, None)
    assert a == Action("raise", 80)


@pytest.mark.parametrize("facing", [0, 6, 50])
@pytest.mark.parametrize("hole,board", [("2c 7d", "As Kd 9h"), ("Qh Jh", "Th 9h 2c 5d"), ("Kc Kd", "Ac 7s 7d 2h 3c")])
def test_always_legal_and_fast(hole, board, facing):
    s = spot(hole, board, facing=facing, pot=40)
    t = time.perf_counter()
    a = postflop_action(s, None, top_percent_range(0.5))
    assert (time.perf_counter() - t) * 1000 < 100
    assert legal_ok(a, s), a


def test_does_not_mutate_range_and_handles_unknown():
    rng = top_percent_range(0.3)
    copy = dict(rng)
    postflop_action(spot("Qh Jh", "Th 9h 2c"), None, rng)
    assert rng == copy
    assert legal_ok(postflop_action(spot("Qh Jh", "Th 9h 2c", history=[]), None, None), spot("Qh Jh", "Th 9h 2c"))


def test_features():
    assert is_wet(("Kh", "9h", "2c")) and is_wet(("9c", "8d", "6s")) and not is_wet(("Kh", "7d", "2c"))
    assert has_draw(("Ah", "5h"), ("Kh", "9h", "2c")) and has_draw(("9c", "8d"), ("7h", "6s", "2c"))
    assert not has_draw(("Ac", "5d"), ("Kh", "9h", "2c")) and not has_draw(("Ah", "5h"), ("Kh", "9h", "2c", "3d", "7s"))
    k = knobs(None)
    assert not (k.station or k.folder or k.maniac)
    assert knobs(STATION).station and knobs(FOLDER).folder and knobs(MANIAC).maniac


def test_sticky_caller_gets_big_value_bets():
    sticky = {"fold_to_bet": (0, 80), "fold_to_bet_by_street": {}, "bet_when_checked_to": (0, 40)}
    nuts = spot("Qh Jh", "Th 9c 8d 2s Kd", pot=40)
    a = postflop_action(nuts, STATION, top_percent_range(0.9), opp_counts=sticky)
    assert a.kind == "raise" and a.raise_to - nuts.my_committed >= 1.4 * 40


def test_mdf_floor_vs_frequent_bettor(monkeypatch):
    import bots.main.postflop as P
    from bots.main.postflop import made_hand_percentile
    monkeypatch.setattr(P, "MDF_SHARE", 0.9)       # off by default (#50); test the dial
    assert made_hand_percentile(("Qh", "Jh"), ("Th", "9c", "8d", "2s", "Kd")) > 0.99    # the nuts
    assert made_hand_percentile(("4c", "3d"), ("Ah", "Kd", "9s", "8c", "2h")) < 0.15     # air
    # Middle pair facing a pot-size bet: folds normally vs a tight range, defends vs a confident auto-bettor.
    s = spot("9d 7c", "Kc 9h 4s 2d", facing=80, pot=40)     # 2x-pot bet: MDF = 1/3, defend top 30%
    tight = top_percent_range(0.05)
    assert postflop_action(s, None, tight, opp_counts=STATION_COUNTS).kind == "fold"
    hf = {"fold_to_bet": (10, 30), "fold_to_bet_by_street": {}, "bet_when_checked_to": (22, 26)}
    assert postflop_action(s, None, tight, opp_counts=hf).kind == "call"


def test_mdf_floor_off_by_default():
    import bots.main.postflop as P
    assert P.MDF_SHARE == 0.0
    s = spot("9d 7c", "Kc 9h 4s 2d", facing=80, pot=40)
    hf = {"fold_to_bet": (10, 30), "fold_to_bet_by_street": {}, "bet_when_checked_to": (22, 26)}
    assert postflop_action(s, None, top_percent_range(0.05), opp_counts=hf).kind == "fold"
