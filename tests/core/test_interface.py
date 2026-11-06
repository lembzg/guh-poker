import dataclasses

import pytest

from core.interface import Action, LegalActions, clamp_to_legal

FACING_BET = LegalActions(can_fold=True, can_check=False, call_amount=10, min_raise_to=30, max_raise_to=200)
CHECKED_TO = LegalActions(can_fold=False, can_check=True, call_amount=0, min_raise_to=2, max_raise_to=200)
SHOVED_ON = LegalActions(can_fold=True, can_check=False, call_amount=50, min_raise_to=None, max_raise_to=None)
NO_RAISE_CHECK = LegalActions(can_fold=False, can_check=True, call_amount=0, min_raise_to=None, max_raise_to=None)


@pytest.mark.parametrize("action, legal, expected", [
    (Action("raise", 5), FACING_BET, Action("raise", 30)),  # below the minimum
    (Action("raise", 999), FACING_BET, Action("raise", 200)),  # above the maximum
    (Action("raise", 50), FACING_BET, Action("raise", 50)),  # in range
    (Action("raise"), FACING_BET, Action("raise", 30)),  # no size given
    (Action("raise", 50), SHOVED_ON, Action("call")),  # raising not allowed, call owed
    (Action("raise", 50), NO_RAISE_CHECK, Action("check")),  # raising not allowed, check free
    (Action("check"), FACING_BET, Action("call")),  # check when a call is owed
    (Action("fold"), CHECKED_TO, Action("check")),  # fold when checking is possible
    (Action("call"), CHECKED_TO, Action("check")),  # nothing to call
    (Action("call"), FACING_BET, Action("call")),
    (Action("fold"), FACING_BET, Action("fold")),
    (Action("check"), CHECKED_TO, Action("check")),
])
def test_clamp_to_legal(action, legal, expected):
    assert clamp_to_legal(action, legal) == expected


def test_fold_becomes_call_when_folding_is_not_allowed():
    legal = LegalActions(can_fold=False, can_check=False, call_amount=10, min_raise_to=None, max_raise_to=None)
    assert clamp_to_legal(Action("fold"), legal) == Action("call")


def test_short_all_in_range_where_min_equals_max():
    legal = LegalActions(can_fold=True, can_check=False, call_amount=10, min_raise_to=40, max_raise_to=40)
    assert clamp_to_legal(Action("raise", 5), legal) == Action("raise", 40)


def test_game_types_are_immutable():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Action("fold").kind = "call"
