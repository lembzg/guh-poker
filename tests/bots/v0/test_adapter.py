"""Hand-built GameStates -> legal actions, plus the conversions the adapter is responsible for."""
from __future__ import annotations

import pytest

from bots.v0.adapter import V0Bot, street_base, to_quant_state
from core.interface import Action, ActionRecord, GameState, HandResult, LegalActions

STACK = 200
BB = 2


def legal(call: int = 0, min_to: int | None = None, max_to: int | None = None) -> LegalActions:
    return LegalActions(can_fold=call > 0, can_check=call == 0, call_amount=call,
                        min_raise_to=min_to, max_raise_to=max_to)


def state(hole, *, button=True, board=(), street=1, mine=1, opp=2, history=(), lgl=None,
          stack=STACK, bb=BB) -> GameState:
    return GameState(hand_id=1, is_button=button, hole_cards=hole, board=board, street=street,
                     small_blind=bb // 2, big_blind=bb, starting_stack=stack, my_committed=mine,
                     opp_committed=opp, history=history, legal=lgl)


def rec(street, actor, kind, raise_to=None) -> ActionRecord:
    return ActionRecord(street=street, actor=actor, kind=kind, raise_to=raise_to)


def assert_legal(action: Action, lgl: LegalActions) -> None:
    if action.kind == "raise":
        assert lgl.min_raise_to is not None
        assert lgl.min_raise_to <= action.raise_to <= lgl.max_raise_to
    elif action.kind == "check":
        assert lgl.can_check
    elif action.kind == "call":
        assert lgl.call_amount > 0
    else:
        assert action.kind == "fold" and lgl.can_fold


OPEN_THEN_CALL = (rec(1, "me", "raise", 6), rec(1, "opp", "call"))

STATES = {
    "sb_unopened": state(("As", "Ah"), lgl=legal(call=1, min_to=4, max_to=STACK)),
    "bb_vs_open": state(("7c", "2d"), button=False, mine=2, opp=6,
                        history=(rec(1, "opp", "raise", 6),), lgl=legal(call=4, min_to=10, max_to=STACK)),
    "flop_checked_to": state(("Ah", "Kh"), button=False, board=("Qh", "7h", "2h"), street=2, mine=6, opp=6,
                             history=(rec(1, "opp", "raise", 6), rec(1, "me", "call")),
                             lgl=legal(min_to=8, max_to=STACK)),
    "turn_facing_bet": state(("Td", "9d"), board=("Qd", "7d", "2c", "3s"), street=3, mine=6, opp=16,
                             history=OPEN_THEN_CALL + (rec(3, "opp", "raise", 16),),
                             lgl=legal(call=10, min_to=26, max_to=STACK)),
    "river_trash_facing_pot": state(("7c", "2d"), board=("As", "Kd", "Qh", "Js", "9c"), street=4, mine=6, opp=18,
                                    history=OPEN_THEN_CALL + (rec(4, "opp", "raise", 18),),
                                    lgl=legal(call=12, min_to=30, max_to=STACK)),
    "facing_shove": state(("As", "Ah"), button=False, mine=2, opp=STACK,
                          history=(rec(1, "opp", "raise", STACK),), lgl=legal(call=STACK - 2)),
    "river_no_raise_allowed": state(("As", "Ad"), board=("Ah", "Ac", "Kd", "7s", "2c"), street=4, mine=6, opp=6,
                                    history=OPEN_THEN_CALL, lgl=legal()),
}


@pytest.mark.parametrize("name", STATES)
def test_returns_legal_action(name):
    s = STATES[name]
    assert_legal(V0Bot(seed=1).act(s), s.legal)


def test_opens_to_2_5_big_blinds_at_our_blind_size():
    # `_BB` must follow the state: with Quant's hardcoded 100, 100bb reads as 2bb and it jams.
    action = V0Bot(seed=1).act(STATES["sb_unopened"])
    assert action == Action("raise", 5)


def test_decisions_do_not_depend_on_chip_scale():
    small = V0Bot(seed=1).act(state(("Kd", "Qd"), lgl=legal(call=1, min_to=4, max_to=200)))
    big = V0Bot(seed=1).act(state(("Kd", "Qd"), mine=50, opp=100, bb=100, stack=10_000,
                                  lgl=legal(call=50, min_to=200, max_to=10_000)))
    assert (small.kind, small.raise_to * 50) == (big.kind, big.raise_to)


def test_folds_trash_to_an_open_and_calls_a_shove_with_aces():
    assert V0Bot(seed=1).act(STATES["bb_vs_open"]) == Action("fold")
    assert V0Bot(seed=1).act(STATES["facing_shove"]) == Action("call")


def test_short_stack_jam_is_a_raise_to_max():
    s = state(("As", "Ah"), stack=16, lgl=legal(call=1, min_to=4, max_to=16))
    assert V0Bot(seed=1).act(s) == Action("raise", 16)


def test_raise_to_is_total_for_the_hand_not_for_the_street():
    # Quant bets the nut flush into 12 chips: a bet this street must sit on top of the 6 already in.
    action = V0Bot(seed=1).act(STATES["flop_checked_to"])
    assert action.kind == "raise" and action.raise_to > 6 + 2


def test_street_conversion_matches_fullhouse_fields():
    s = STATES["turn_facing_bet"]
    assert street_base(s) == 6
    q = to_quant_state(s, [])
    assert q["street"] == "turn"
    assert q["pot"] == 22
    assert q["current_bet"] == 10
    assert q["your_bet_this_street"] == 0
    assert q["amount_owed"] == 10
    assert q["min_raise_to"] == 20
    assert q["your_stack"] == STACK - 6


def test_action_log_starts_with_blinds_and_marks_a_shove():
    q = to_quant_state(STATES["facing_shove"], [])
    opp_seat = q["players"][1]["seat"]
    assert q["action_log"][0] == {"seat": opp_seat, "action": "small_blind"}  # we're not the button
    assert q["action_log"][1] == {"seat": q["seat_to_act"], "action": "big_blind"}
    assert q["action_log"][2]["action"] == "all_in"


def test_broken_state_still_acts_legally():
    s = state(("??", "!!"), lgl=legal(call=1, min_to=4, max_to=STACK))
    assert_legal(V0Bot(seed=1).act(s), s.legal)


def test_decide_crash_falls_back_to_legal_action(monkeypatch):
    bot = V0Bot(seed=1)
    monkeypatch.setattr(bot._quant, "decide", lambda _: 1 / 0)
    assert bot.act(STATES["facing_shove"]) == Action("fold")
    assert bot.act(STATES["river_no_raise_allowed"]) == Action("check")


def _finish_hand(bot, hand_id, history):
    bot.hand_over(HandResult(hand_id=hand_id, was_button=True, my_delta=0, history=history,
                             board=(), opp_hole_cards=None))


def test_opponent_model_counts_each_action_once():
    bot = V0Bot(seed=1)
    history = (rec(1, "me", "raise", 6), rec(1, "opp", "fold"))
    bot.act(state(("As", "Ah"), mine=6, opp=2, history=history[:1],
                  lgl=legal(call=0, min_to=10, max_to=STACK)))
    _finish_hand(bot, 1, history)
    # Repeated hand_id, as duplicate deals may produce: it must still count as a new hand.
    _finish_hand(bot, 1, history)
    bot.act(STATES["sb_unopened"])
    assert bot._quant._OPP["opp"]["hands"] == 2
    assert bot._quant._OPP["opp"]["n"] == 2
    assert bot._quant._OPP["opp"]["fold"] == 2


def test_instances_do_not_share_an_opponent_model():
    a, b = V0Bot(seed=1), V0Bot(seed=1)
    _finish_hand(a, 1, (rec(1, "opp", "raise", 6),))
    a.act(STATES["sb_unopened"])
    b.act(STATES["sb_unopened"])
    assert "opp" in a._quant._OPP
    assert "opp" not in b._quant._OPP


def test_new_match_resets_the_opponent_model():
    bot = V0Bot(seed=1)
    _finish_hand(bot, 1, (rec(1, "opp", "raise", 6),))
    bot.act(STATES["sb_unopened"])
    bot.new_match("m2", None)
    bot.act(STATES["sb_unopened"])
    assert "opp" not in bot._quant._OPP


def test_registered_in_make_bot():
    bots = pytest.importorskip("bots")
    if not hasattr(bots, "make_bot"):
        pytest.skip("make_bot arrives with #4; add the v0 line then")
    assert isinstance(bots.make_bot("v0"), V0Bot)
