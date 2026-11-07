import time

import pytest

from bots.main.opponent import OpponentModel, classify
from core.equity import equity
from core.interface import Action, ActionRecord, GameState, HandResult, LegalActions
from harness.match import play_match
from harness.opponents import AlwaysCall, AlwaysRaisePot, HackathonBot, RandomBot

R = ActionRecord
LEGAL = LegalActions(True, False, 2, 4, 200)


def hand(history, was_button=True, board=(), shown=None, delta=0):
    return HandResult(hand_id=0, was_button=was_button, my_delta=delta, history=tuple(history),
                      board=tuple(board), opp_hole_cards=shown)


def state(history, board=(), hole=("2c", "3d"), button=True, street=None):
    street = street or {0: 1, 3: 2, 4: 3, 5: 4}[len(board)]
    return GameState(hand_id=0, is_button=button, hole_cards=hole, board=tuple(board), street=street,
                     small_blind=1, big_blind=2, starting_stack=200, my_committed=2, opp_committed=2,
                     history=tuple(history), legal=LEGAL)


class Watcher:
    """Plays like `inner`, and feeds every finished hand to an OpponentModel."""

    def __init__(self, inner):
        self.inner, self.model, self.name = inner, OpponentModel(), "watcher"

    def new_match(self, match_id, opponent):
        self.inner.new_match(match_id, opponent)

    def act(self, state):
        self.model.range_estimate(state)   # also exercises range_estimate on real states
        return self.inner.act(state)

    def hand_over(self, result):
        self.model.observe_hand(result)


# ------------------------------------------------------------------ stats from synthetic hands

def test_none_until_enough_samples_then_smoothed():
    m = OpponentModel()
    assert m.stats().vpip is None and m.stats().hands == 0
    for _ in range(11):   # we open, they 3-bet, we fold
        m.observe_hand(hand([R(1, "me", "raise", 6), R(1, "opp", "raise", 18), R(1, "me", "fold", None)]))
    assert m.stats().three_bet is None
    m.observe_hand(hand([R(1, "me", "raise", 6), R(1, "opp", "raise", 18), R(1, "me", "fold", None)]))
    s = m.stats()
    assert s.hands == 12
    assert s.three_bet == pytest.approx((12 + 20 * 0.12) / 32)     # shrunk toward the prior
    assert s.vpip == pytest.approx((12 + 20 * 0.60) / 32) and s.pfr == pytest.approx((12 + 20 * 0.35) / 32)


def test_raw_counts_with_no_shrinkage():
    m = OpponentModel(min_samples=1, shrink_k=0)
    # we open, they call; flop: they check, we c-bet, they fold
    m.observe_hand(hand([R(1, "me", "raise", 6), R(1, "opp", "call", None),
                         R(2, "opp", "check", None), R(2, "me", "raise", 9), R(2, "opp", "fold", None)],
                        board=("As", "7d", "2c")))
    # they open as button, we call; flop: we check, they bet, we call; turn: we check, they bet 2/3, we fold
    m.observe_hand(hand([R(1, "opp", "raise", 6), R(1, "me", "call", None),
                         R(2, "me", "check", None), R(2, "opp", "raise", 12), R(2, "me", "call", None),
                         R(3, "me", "check", None), R(3, "opp", "raise", 28), R(3, "me", "fold", None)],
                        was_button=False, board=("As", "7d", "2c", "9h")))
    s = m.stats()
    assert s.hands == 2 and s.vpip == 1.0 and s.pfr == 0.5
    assert s.three_bet == 0.0            # faced our open once, flat-called
    assert s.fold_to_cbet == 1.0 and s.fold_to_bet == 1.0
    assert s.wtsd == 0.0
    # flop: bet 6 into 12; turn: bet 16 into 24
    assert s.avg_bet_frac == pytest.approx((6 / 12 + 16 / 24) / 2)
    assert s.aggression == 10.0         # two bets, no calls: capped


def test_walks_are_not_vpip_opportunities():
    m = OpponentModel(min_samples=1, shrink_k=0)
    m.observe_hand(hand([R(1, "me", "fold", None)]))
    m.observe_hand(hand([R(1, "me", "call", None), R(1, "opp", "check", None)] +
                        [R(s, p, "check", None) for s in (2, 3, 4) for p in ("opp", "me")],
                        board=("As", "7d", "2c", "9h", "3s"), shown=("Kd", "Qd")))
    s = m.stats()
    assert s.hands == 2 and s.vpip == 0.0 and s.wtsd == 1.0


def test_bluff_rate_from_showdowns():
    m = OpponentModel()
    board = ("As", "7d", "2c", "9h", "3s")
    big_river_bet = [R(1, "me", "call", None), R(1, "opp", "check", None),
                     R(2, "opp", "check", None), R(2, "me", "check", None),
                     R(3, "opp", "check", None), R(3, "me", "check", None),
                     R(4, "opp", "raise", 6), R(4, "me", "call", None)]   # pot 4, bet 4 = pot-size
    assert m.bluff_rate() is None
    for shown in [("Kd", "Qd"), ("Jh", "Tc"), ("Ah", "5c"), ("8c", "6c")]:   # 3 air, 1 top pair
        m.observe_hand(hand(big_river_bet, board=board, shown=shown))
    assert m.bluff_rate() == pytest.approx((3 + 5 * 0.30) / (4 + 5))
    # A pair that's only on the board counts as a bluff.
    m2 = OpponentModel()
    for _ in range(3):
        m2.observe_hand(hand(big_river_bet, board=("As", "As"[0] + "d", "2c", "9h", "3s"), shown=("Kd", "Qd")))
    assert m2.bluff_rate() > 0.5


def test_observe_never_raises():
    m = OpponentModel()
    m.observe_hand(None)
    m.observe_hand(hand([R(9, "opp", "raise", None)]))
    assert m.range_estimate(None) is None


# ------------------------------------------------------------------ convergence against real bots

def test_converges_against_always_call():
    w = Watcher(AlwaysRaisePot())
    play_match(w, AlwaysCall(), hands=600, seed=1)
    s = w.model.stats()
    assert s.vpip > 0.95 and s.pfr < 0.05 and s.three_bet < 0.05
    assert s.fold_to_bet < 0.05 and s.fold_to_cbet < 0.05 and s.wtsd > 0.95
    assert classify(s) == "station"


def test_converges_against_always_raise_pot():
    w = Watcher(AlwaysCall())
    play_match(w, AlwaysRaisePot(), hands=600, seed=1)
    s = w.model.stats()
    assert s.vpip > 0.95 and s.pfr > 0.95
    assert s.fold_to_bet is None       # always_call never bets, so they never face one
    assert s.aggression > 5 and 0.8 < s.avg_bet_frac < 1.2
    assert classify(s) == "maniac"


def test_hackathon_bot_profile():
    w = Watcher(RandomBot(3))
    play_match(w, HackathonBot(), hands=2000, seed=2)
    s = w.model.stats()
    assert 0.55 < s.vpip < 0.8 and s.pfr == pytest.approx(s.vpip, abs=0.05)   # raise-or-fold preflop
    assert s.fold_to_bet > 0.3


def test_unknown_with_no_data():
    assert classify(OpponentModel().stats()) == "unknown"


# ------------------------------------------------------------------ range estimate

def test_no_opponent_action_is_unknown():
    assert OpponentModel().range_estimate(state([])) is None


def test_preflop_3bet_range_is_tight():
    m = OpponentModel()
    r = m.range_estimate(state([R(1, "me", "raise", 6), R(1, "opp", "raise", 18)]))
    total = sum(r.values())
    assert 0.08 * 1326 < total < 0.16 * 1326           # prior 3-bet frequency 12%, minus dead cards
    assert r[("As", "Ah")] == 1.0 and ("7h", "2s") not in r
    assert ("2c", "2d") not in r and all("3d" not in k for k in r)   # dead cards removed


def test_limp_range_downweights_strong_hands():
    m = OpponentModel()
    r = m.range_estimate(state([R(1, "opp", "call", None)], button=False))
    assert r[("As", "Ah")] < r[("9s", "8s")] == 1.0
    assert ("7h", "2s") in r


def test_postflop_bet_narrows_toward_strong_hands():
    m = OpponentModel()
    board = ("As", "Kd", "7c")
    hist = [R(1, "me", "raise", 6), R(1, "opp", "call", None), R(2, "opp", "raise", 10)]
    r = m.range_estimate(state(hist, board=board, hole=("Qh", "Jh")))
    assert r[("Ah", "Kh")] > 0 and r[("Ah", "Kh")] > 3 * r.get(("6h", "5h"), 0.0)
    unknown = equity(("Qh", "Jh"), board, None, samples=4000, seed=1)
    vs_bet = equity(("Qh", "Jh"), board, r, samples=4000, seed=1)
    assert vs_bet < unknown - 0.05


def test_maniac_bets_are_weaker_than_nit_bets():
    board = ("As", "Kd", "7c")
    hist = [R(1, "me", "raise", 6), R(1, "opp", "call", None), R(2, "opp", "raise", 10)]
    maniac = Watcher(AlwaysCall())
    play_match(maniac, AlwaysRaisePot(), hands=300, seed=1)
    eq_maniac = equity(("Ah", "Qh"), board, maniac.model.range_estimate(state(hist, board, ("Ah", "Qh"))),
                       samples=4000, seed=1)
    eq_default = equity(("Ah", "Qh"), board, OpponentModel().range_estimate(state(hist, board, ("Ah", "Qh"))),
                        samples=4000, seed=1)
    assert eq_maniac > eq_default


def test_range_estimate_speed():
    m = OpponentModel()
    hist = [R(1, "me", "raise", 6), R(1, "opp", "call", None), R(2, "opp", "raise", 10),
            R(2, "me", "call", None), R(3, "opp", "check", None), R(3, "me", "raise", 20),
            R(3, "opp", "call", None), R(4, "opp", "raise", 60)]
    st = state(hist, board=("As", "Kd", "7c", "2h", "9s"), hole=("Qh", "Jh"))
    m.range_estimate(st)
    t = time.perf_counter()
    for _ in range(20):
        m.range_estimate(st)
    assert (time.perf_counter() - t) / 20 * 1000 < 25


def test_hidden_sb_folds_are_corrected():
    """#35: as the arena's big blind we only see SB hands the opponent entered. A nit (fold 80, raise 15,
    limp 5) then looks like it plays every hand; the model must not read it as a maniac."""
    m = OpponentModel()
    for i in range(100):
        if i % 4 == 3:   # 25% of the visible hands are limps, 75% raises (15 / 20 of the entered hands)
            hist = [R(1, "opp", "call", None), R(1, "me", "check", None)]
        else:
            hist = [R(1, "opp", "raise", 60), R(1, "me", "fold", None)]
        m.observe_hand(hand(hist, was_button=False))
    assert m.sb_folds_hidden()
    s = m.stats()
    assert s.vpip == pytest.approx(0.45) and s.pfr < 0.45 and classify(s) != "maniac"
    # A visible SB fold, or any hand with them in the BB, means nothing is censored.
    m.observe_hand(hand([R(1, "opp", "fold", None)], was_button=False))
    assert not m.sb_folds_hidden()


def test_counts_and_bet_frequency():
    m = OpponentModel()
    for _ in range(12):   # we check the flop, they bet; we call; turn they check
        m.observe_hand(hand([R(1, "me", "call", None), R(1, "opp", "check", None),
                             R(2, "opp", "raise", 4), R(2, "me", "call", None),
                             R(3, "opp", "check", None), R(3, "me", "raise", 8), R(3, "opp", "fold", None)],
                            board=("As", "7d", "2c", "9h")))
    c = m.counts()
    assert c["bet_when_checked_to"] == (12, 24) and c["fold_to_bet"] == (12, 12)
    assert c["fold_to_bet_by_street"][3] == (12, 12) and c["fold_to_bet_by_street"][2] == (0, 0)
    assert m.bet_frequency() == pytest.approx(17 / 34)


def test_per_street_bet_frequency_bounds_bluffs():
    """#53: an opponent who bets the flop a lot but the river rarely is assumed value-heavy on the river."""
    from bots.main.opponent import _Act, _postflop_multiplier

    def mult(street_freq):
        a = _Act(street=4, actor="opp", kind="raise", raise_to=100, pot_before=100, facing=False,
                 bet_frac=0.66, raises_before=0)
        pct = [i / 100 for i in range(100)]
        get = lambda name: 4.0 if name == "aggression" else 0.45
        m = _postflop_multiplier(a, pct, get, None, 0.6, street_freq)
        return m[10]   # weight on a weak hand

    rarely, often = mult(0.33), mult(0.75)
    assert rarely < often                    # rare river bettor: weak hands get far less weight
    assert mult(None) >= rarely              # without street data: falls back to aggression

    m = OpponentModel()
    for _ in range(12):   # flop: they bet when checked to; river: they check when checked to
        m.observe_hand(hand([R(1, "me", "call", None), R(1, "opp", "check", None),
                             R(2, "opp", "raise", 4), R(2, "me", "call", None),
                             R(3, "opp", "check", None), R(3, "me", "check", None),
                             R(4, "opp", "check", None), R(4, "me", "check", None)],
                            board=("As", "7d", "2c", "9h", "3s")))
    assert m.street_bet_frequency(2) == pytest.approx(17 / 22)
    assert m.street_bet_frequency(4) == pytest.approx(5 / 22)
    assert m.counts()["bet_when_checked_to_by_street"][4] == (0, 12)
