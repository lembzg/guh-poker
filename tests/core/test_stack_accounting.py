from dataclasses import replace

from core.allin import call_price, effective_raise_to, opponent_start, terminal_call
from core.interface import ActionRecord, GameState, LegalActions


def spot(**kw):
    base = GameState(1, False, ('As', 'Ah'), (), 1, 1, 2, 200, 2, 200,
                     (ActionRecord(1, 'opp', 'raise', 200),),
                     LegalActions(True, False, 198, None, None))
    return replace(base, **kw)


def test_short_call_excludes_unmatched_chips():
    s = spot(starting_stack=20, my_committed=10, opp_committed=100,
             opp_starting_stack=200, legal=LegalActions(True, False, 10, None, None))
    assert terminal_call(s)
    assert call_price(s) == (10, 40)


def test_opponent_allin_while_we_cover_and_legacy_equal_stacks():
    s = spot(opp_starting_stack=60, opp_committed=60,
             legal=LegalActions(True, False, 58, 118, 200))
    assert opponent_start(s) == 60 and terminal_call(s)
    assert call_price(s) == (58, 120)
    assert terminal_call(spot())
    assert not terminal_call(replace(s, opp_starting_stack=200))


def test_no_raise_rights_does_not_imply_terminal_call():
    s = spot(opp_committed=20, legal=LegalActions(True, False, 18, None, None))
    assert not terminal_call(s)


def test_effective_raise_obeys_minimum_even_when_it_exceeds_short_stack():
    s = spot(opp_starting_stack=60, legal=LegalActions(True, False, 18, 40, 200))
    assert effective_raise_to(s) == 60
    assert effective_raise_to(replace(s, legal=LegalActions(True, False, 18, 80, 200))) == 80


def test_unbeatable_bound_agrees_with_exhaustive_opponent_river_hands():
    import itertools
    import random
    from core.allin import unbeatable
    from core.cards import full_deck
    from core.equity import rank7
    deck = full_deck()
    rng = random.Random(9)
    checked = 0
    for _ in range(1000):
        cards = rng.sample(deck, 7)
        hole, board = tuple(cards[:2]), tuple(cards[2:])
        value = rank7(hole + board)
        if value >> 25 < 4:
            continue
        live = [c for c in deck if c not in cards]
        exact = all(rank7(tuple(opp) + board) <= value for opp in itertools.combinations(live, 2))
        assert unbeatable(hole, board, value) == exact, (hole, board)
        checked += 1
    assert checked > 50
