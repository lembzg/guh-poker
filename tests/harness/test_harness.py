import random

import pytest

from harness._types import Action, ActionRecord
from harness.engine import Seat, play_hand, results_for
from harness.match import deal, play_match
from harness.opponents import AlwaysCall, AlwaysRaisePot, HackathonBot, RandomBot
from harness.run import main as cli_main

ROYAL_BOARD = ["As", "Ks", "Qs", "Js", "Ts"]


class Scripted:
    """Plays the given actions in order (callables get the state), then checks/calls. Records states."""
    name = "scripted"

    def __init__(self, *script):
        self.script = list(script)
        self.states = []
        self.results = []

    def new_match(self, match_id, opponent):
        pass

    def act(self, state):
        self.states.append(state)
        if self.script:
            a = self.script.pop(0)
            return a(state) if callable(a) else a
        return Action("check") if state.legal.can_check else Action("call")

    def hand_over(self, result):
        self.results.append(result)


def run(btn, bb, deck=None, stacks=(200, 200), blinds=(1, 2)):
    deck = deck or deal(0, 0)
    seats = (Seat(btn), Seat(bb))
    out = play_hand(seats, deck, stacks, blinds[0], blinds[1], hand_id=7)
    res = results_for(out, (tuple(deck[0:2]), tuple(deck[2:4])), 7)
    btn.hand_over(res[0]) if hasattr(btn, "results") else None
    bb.hand_over(res[1]) if hasattr(bb, "results") else None
    return out, seats


def test_blinds_order_and_legal_preflop():
    btn, bb = Scripted(), Scripted()
    run(btn, bb)
    s = btn.states[0]
    assert s.is_button and s.street == 1 and s.board == ()
    assert (s.my_committed, s.opp_committed, s.small_blind, s.big_blind, s.starting_stack) == (1, 2, 1, 2, 200)
    assert s.legal.can_fold and not s.legal.can_check and s.legal.call_amount == 1
    assert (s.legal.min_raise_to, s.legal.max_raise_to) == (4, 200)
    s = bb.states[0]                      # BB gets the option after the limp
    assert not s.is_button and s.legal.can_check and not s.legal.can_fold and s.legal.call_amount == 0
    assert s.legal.min_raise_to == 4
    # Postflop the big blind acts first, and the minimum bet is one big blind.
    assert bb.states[1].street == 2 and len(bb.states[1].board) == 3
    assert btn.states[1].street == 2 and len(btn.states) == len(bb.states) == 4
    assert bb.states[1].legal.min_raise_to == 4 and bb.states[1].legal.max_raise_to == 200


def test_min_raise_and_reraise():
    btn = Scripted(Action("raise", 6))
    bb = Scripted(Action("raise", 14))
    run(btn, bb)
    lg = bb.states[0].legal
    assert lg.call_amount == 4 and lg.min_raise_to == 10
    lg = btn.states[1].legal               # faced a full raise: may re-raise by at least 8
    assert lg.call_amount == 8 and lg.min_raise_to == 22 and lg.max_raise_to == 200


def test_short_all_in_does_not_reopen():
    btn = Scripted(Action("raise", 10))
    bb = Scripted(Action("raise", 13))     # all-in, raising by 3 < 8
    out, _ = run(btn, bb, stacks=(100, 13))
    lg = btn.states[1].legal
    assert lg.call_amount == 3 and lg.min_raise_to is None and lg.max_raise_to is None
    assert abs(out.deltas[0]) == 13 and out.showdown


def test_short_stack_min_raise_is_all_in():
    btn = Scripted(Action("raise", 6))
    bb = Scripted()
    run(btn, bb, stacks=(200, 8))
    lg = bb.states[0].legal
    assert (lg.min_raise_to, lg.max_raise_to) == (8, 8)


def test_uncalled_chips_are_returned():
    btn = Scripted(Action("raise", 300))
    bb = Scripted()
    out, _ = run(btn, bb, stacks=(300, 100))
    assert bb.states[0].legal.call_amount == 98
    assert abs(out.deltas[0]) == 100 and out.deltas[0] + out.deltas[1] == 0
    assert len(bb.states) == 1 and len(btn.states) == 1     # board runs out with nobody to act
    assert out.board == tuple(deal(0, 0)[4:9])


def test_split_pot_when_board_plays():
    deck = ["2c", "3d", "4c", "5d"] + ROYAL_BOARD
    btn, bb = Scripted(Action("raise", 20)), Scripted()
    out, _ = run(btn, bb, deck=deck)
    assert out.deltas == (0, 0) and out.showdown
    assert btn.results[0].opp_hole_cards == ("4c", "5d") and bb.results[0].opp_hole_cards == ("2c", "3d")


def test_fold_and_hand_result():
    btn, bb = Scripted(Action("fold")), Scripted()
    out, _ = run(btn, bb)
    assert out.deltas == (-1, 1) and not out.showdown and out.board == ()
    r = bb.results[0]
    assert r.my_delta == 1 and not r.was_button and r.opp_hole_cards is None and r.hand_id == 7
    assert r.history == (ActionRecord(1, "opp", "fold", None),)
    assert btn.results[0].history == (ActionRecord(1, "me", "fold", None),)


def test_history_is_from_each_players_perspective():
    btn, bb = Scripted(Action("raise", 6)), Scripted(Action("call"))
    run(btn, bb)
    flop = bb.states[1]
    assert flop.history == (ActionRecord(1, "opp", "raise", 6), ActionRecord(1, "me", "call", None))
    assert flop.my_committed == flop.opp_committed == 6
    assert btn.states[1].history == (ActionRecord(1, "me", "raise", 6), ActionRecord(1, "opp", "call", None),
                                     ActionRecord(2, "opp", "check", None))


@pytest.mark.parametrize("bad", [Action("raise", 3), Action("raise", 201), Action("check"), None,
                                 Action("raise", None), Action("bet", 10)])
def test_illegal_action_becomes_fold_when_facing_a_bet(bad):
    btn = Scripted(bad)
    out, seats = run(btn, Scripted())
    assert out.deltas == (-1, 1) and seats[0].illegal == 1 and seats[0].errors == 0


def test_fold_when_check_is_possible_becomes_check():
    btn, bb = Scripted(), Scripted(Action("fold"))
    out, seats = run(btn, bb)
    assert seats[1].illegal == 1 and out.showdown
    assert bb.states[1].history[1] == ActionRecord(1, "me", "check", None)


def test_exception_is_counted_not_raised():
    def boom(state):
        raise RuntimeError("bug")
    out, seats = run(Scripted(boom), Scripted())
    assert out.deltas == (-1, 1) and seats[0].errors == 1 and seats[0].illegal == 0


def test_float_raise_to_accepted():
    btn = Scripted(Action("raise", 6.0))
    out, seats = run(btn, Scripted(Action("fold")))
    assert seats[0].illegal == 0 and out.deltas == (2, -2)


def test_tiny_stacks_post_blinds_all_in():
    out, _ = run(Scripted(), Scripted(), stacks=(1, 1))
    assert abs(out.deltas[0]) in (0, 1) and out.showdown
    out, _ = run(Scripted(), Scripted(), stacks=(200, 1))
    assert abs(out.deltas[0]) in (0, 1) and out.showdown


def test_random_fuzz_conserves_chips_and_stays_legal():
    rng = random.Random(3)
    a, b = RandomBot(1), RandomBot(2)
    for i in range(3000):
        stacks = (rng.randint(1, 300), rng.randint(1, 300))
        seats = (Seat(a), Seat(b))
        out = play_hand(seats, deal(5, i), stacks, 1, 2, hand_id=i)
        assert out.deltas[0] + out.deltas[1] == 0
        assert abs(out.deltas[0]) <= min(stacks)
        assert seats[0].illegal == seats[1].illegal == seats[0].errors == seats[1].errors == 0


def test_duplicate_mirror_is_exactly_zero():
    res = play_match(AlwaysCall(), AlwaysCall(), hands=401, seed=4, duplicate=True)
    assert res["hands"] == 402 and res["bb_per_100"] == 0 and res["ci95"] == 0
    res = play_match(HackathonBot(), HackathonBot(), hands=400, seed=4, duplicate=True)
    assert res["bb_per_100"] == 0


def test_duplicate_reuses_deals_with_seats_swapped():
    a, b = Scripted(), Scripted()
    play_match(a, b, hands=4, seed=9, duplicate=True)
    # hand 0: a is button with deal(9,0)[0:2]; hand 1: a is BB with deal(9,0)[2:4]
    r = a.results
    assert r[0].was_button and not r[1].was_button and r[0].board == r[1].board
    first = [s for s in a.states if s.hand_id == 0][0].hole_cards
    second = [s for s in a.states if s.hand_id == 1][0].hole_cards
    assert first == tuple(deal(9, 0)[0:2]) and second == tuple(deal(9, 0)[2:4])


def test_result_format_matches_contract():
    res = play_match("hackathon", "always_raise_pot", hands=200, seed=1, duplicate=False, stack=200, bb=2)
    assert set(res) == {"bot_a", "bot_b", "hands", "duplicate", "seed", "stack_bb", "bb_per_100", "ci95",
                        "a_ms_avg", "a_ms_max", "b_ms_avg", "b_ms_max", "illegal_a", "illegal_b",
                        "errors_a", "errors_b"}
    assert res["bot_a"].startswith("hackathon@") and res["stack_bb"] == 100 and res["hands"] == 200
    assert res["illegal_a"] == res["illegal_b"] == 0


def test_carry_stacks():
    res = play_match(AlwaysRaisePot(), RandomBot(), hands=300, seed=2, reset_stacks=False)
    assert res["illegal_a"] == res["illegal_b"] == 0
    with pytest.raises(ValueError):
        play_match(AlwaysCall(), AlwaysCall(), hands=10, seed=1, duplicate=True, reset_stacks=False)


def test_cli():
    res = cli_main(["--a", "hackathon", "--b", "random", "--hands", "100", "--seed", "3", "--duplicate",
                    "--b-cfg", "seed=5", "--no-save"])
    assert res["hands"] == 100 and res["duplicate"] and res["bot_b"].startswith("random@")
