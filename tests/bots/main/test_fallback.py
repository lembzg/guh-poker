import random
import time

from bots.main.fallback import fallback_action
from core.cards import full_deck
from core.interface import Action, GameState, LegalActions
from harness.engine import _validate


def make_state(hole, board=(), facing=0, pot=4, stack=200, street=None):
    half = pot // 2
    my, opp = half, half + facing
    behind = stack - my
    raise_ok = behind > facing
    legal = LegalActions(can_fold=facing > 0, can_check=facing == 0, call_amount=min(facing, behind),
                         min_raise_to=min(opp + max(2, facing), stack) if raise_ok else None,
                         max_raise_to=stack if raise_ok else None)
    street = street or {0: 1, 3: 2, 4: 3, 5: 4}[len(board)]
    return GameState(hand_id=1, is_button=True, hole_cards=tuple(hole), board=tuple(board), street=street,
                     small_blind=1, big_blind=2, starting_stack=stack, my_committed=my, opp_committed=opp,
                     history=(), legal=legal)


def test_preflop_rules():
    assert fallback_action(make_state(("As", "Ah"), facing=1, pot=3)).kind == "raise"
    assert fallback_action(make_state(("Ts", "9s"), facing=1, pot=3)).kind == "call"
    assert fallback_action(make_state(("7d", "2c"), facing=1, pot=3)).kind == "fold"
    assert fallback_action(make_state(("7d", "2c"), pot=4)).kind == "check"
    assert fallback_action(make_state(("Ts", "9s"), facing=40, pot=10)).kind == "fold"


def test_postflop_rules():
    assert fallback_action(make_state(("As", "Kd"), ("Ah", "7c", "2d"))).kind == "raise"       # top pair, checked to
    assert fallback_action(make_state(("As", "Kd"), ("Ah", "7c", "2d"), facing=8, pot=10)).kind == "call"
    assert fallback_action(make_state(("As", "Kd"), ("Ah", "7c", "2d"), facing=50, pot=10)).kind == "fold"
    assert fallback_action(make_state(("As", "7d"), ("Ah", "7c", "2d"), facing=8, pot=10)).kind == "raise"  # two pair
    assert fallback_action(make_state(("Qs", "Jd"), ("9h", "9c", "2d"), facing=4, pot=10)).kind == "fold"   # board pair
    assert fallback_action(make_state(("Qs", "Jd"), ("9h", "8c", "2d"))).kind == "check"


def test_always_legal_and_fast():
    rng = random.Random(1)
    deck = full_deck()
    worst = 0.0
    for _ in range(3000):
        cards = rng.sample(deck, 7)
        n_board = rng.choice([0, 3, 4, 5])
        stack = rng.randint(4, 400)
        pot = rng.randint(2, max(2, stack // 2)) // 2 * 2
        facing = rng.choice([0, 0, rng.randint(1, max(1, stack - pot // 2))])
        s = make_state(cards[:2], cards[2:2 + n_board], facing=facing, pot=pot, stack=stack)
        t = time.perf_counter()
        a = fallback_action(s)
        worst = max(worst, time.perf_counter() - t)
        assert _validate(a, s.legal) is not None, (s, a)
    assert worst * 1000 < 1.0


def test_never_raises_on_garbage():
    s = make_state(("As", "Kd"), ("Ah", "7c", "2d"))
    bad = GameState(**{**s.__dict__, "hole_cards": ("??", "Kd")})
    assert fallback_action(bad) == Action("check")
