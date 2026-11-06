import pytest

from core.cards import RANKS, SUITS, full_deck, hand_class


def test_full_deck_has_52_unique_cards_in_a_fixed_order():
    deck = full_deck()
    assert len(set(deck)) == 52
    assert deck == full_deck()
    assert deck[0] == "2c" and deck[-1] == "As"
    assert {card[0] for card in deck} == set(RANKS)
    assert {card[1] for card in deck} == set(SUITS)


@pytest.mark.parametrize("hole, expected", [
    (("As", "Ks"), "AKs"),
    (("Ks", "As"), "AKs"),
    (("9d", "Tc"), "T9o"),
    (("7h", "7c"), "77"),
    (("2c", "3c"), "32s"),
])
def test_hand_class(hole, expected):
    assert hand_class(hole) == expected
