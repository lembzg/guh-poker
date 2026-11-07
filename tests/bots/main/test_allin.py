from dataclasses import replace
import random

import pytest

from bots.main.allin import JamModel, all_in_call_action
from bots.main.bot import MainBot
from bots.main.fallback import fallback_action
from bots.main.postflop import _bet, _facing_bet, knobs
from bots.v0.adapter import V0Bot, to_quant_state
from core.interface import Action, ActionRecord, LegalActions
from tests.core.test_stack_accounting import spot


def test_terminal_call_uses_price_without_survival_cushion(monkeypatch):
    import bots.main.allin as module
    s = spot()
    monkeypatch.setattr(module, 'equity', lambda *a, **kw: .50)
    assert all_in_call_action(s, None) == Action('call')
    monkeypatch.setattr(module, 'equity', lambda *a, **kw: .49)
    assert all_in_call_action(s, None) == Action('fold')


def test_postflop_terminal_call_has_no_draw_bonus_or_stackoff_penalty():
    s = spot(street=2, my_committed=20, opp_committed=60, opp_starting_stack=60,
             board=('2h','3h','7d'), legal=LegalActions(True, False, 40, None, None))
    args = (knobs(None), 2, 0, True, True, random.Random(1))
    assert _facing_bet(s, .34, *args) == Action('call')
    assert _facing_bet(s, .32, *args) == Action('fold')


def test_allin_sampling_is_given_budget(monkeypatch):
    import bots.main.allin as module
    seen = {}
    def sample(*args, **kw):
        seen.update(kw)
        return .8
    monkeypatch.setattr(module, 'equity', sample)
    assert all_in_call_action(spot(), None, 17).kind == 'call'
    assert seen['time_budget_ms'] == 17


@pytest.mark.parametrize('bot_type', [MainBot, V0Bot])
def test_deep_jam_does_not_use_ordinary_defence_chart(bot_type):
    for hole in [('5s','4s'), ('9s','6s')]:
        assert bot_type().act(spot(hole_cards=hole)) == Action('fold')
    assert bot_type().act(spot()) == Action('call')


def test_short_opponent_stack_reaches_v0_and_is_marked_allin():
    s = spot(opp_starting_stack=60, opp_committed=60,
             history=(ActionRecord(1,'opp','raise',60),),
             legal=LegalActions(True,False,58,None,None))
    q = to_quant_state(s, [])
    assert q['players'][1]['stack'] == 0
    assert q['action_log'][-1]['action'] == 'all_in'


def test_jam_learning_deduplicates_snapshots_and_resets_hand_not_match():
    m = JamModel()
    s = spot()
    m.observe(s)
    share = m.share(s)
    m.observe(s)
    assert m.share(s) == share
    for _ in range(50):
        m.finish_hand()
        m.observe(s)  # duplicate deals may reuse hand IDs
    assert m.share(s) > .85
    assert JamModel().share(s) == .10
    # Same opponent in another role/context has its own prior.
    assert m.share(replace(s, is_button=True)) == .10
    raised = replace(s, history=(ActionRecord(1,'me','raise',6),) + s.history)
    assert m.share(raised) == .06


def test_nonjam_decisions_count_but_unseen_opponent_actions_do_not():
    m = JamModel()
    s = spot(history=())
    for i in range(20):
        m.observe(replace(s, hand_id=i))
    assert not m.counts
    for i in range(20, 40):
        m.observe(replace(s, hand_id=i, history=(ActionRecord(1,'opp','raise',6),)))
    assert m.share(s) < .04


def test_remaining_stack_threshold_does_not_count_sunk_chips():
    s = spot(street=4, starting_stack=1000, my_committed=900, opp_committed=900,
             board=('2c','3d','7h','8s','Jc'),
             legal=LegalActions(False,True,0,902,1000), history=())
    assert _bet(s, .04) == Action('raise', 972)
    assert _bet(s, .05) == Action('raise', 1000)
    # A covering bet risks only the amount the opponent can match.
    s = replace(s, starting_stack=2000, opp_starting_stack=950,
                legal=LegalActions(False,True,0,902,2000))
    assert _bet(s, .04) == Action('raise', 950)


@pytest.mark.parametrize('board', [('Qh','Jh','Th'), ('Qh','Jh','Th','2c'), ('Qh','Jh','Th','2c','3d')])
def test_fallback_never_folds_royal_flush(board):
    s = spot(hole_cards=('Ah','Kh'), board=board, street={3:2,4:3,5:4}[len(board)])
    assert fallback_action(s) == Action('call')


def test_river_shared_royal_is_a_profitable_split_call():
    s = spot(hole_cards=('2c','3d'), board=('Ah','Kh','Qh','Jh','Th'), street=4)
    assert all_in_call_action(s, None) == Action('call')


def test_covering_raise_counts_as_effective_jam_when_hero_is_short():
    m = JamModel()
    s = spot(starting_stack=20, opp_starting_stack=200, opp_committed=20,
             history=(ActionRecord(1,'opp','raise',20),),
             legal=LegalActions(True,False,18,None,None))
    initial = m.share(s)
    for _ in range(50):
        m.finish_hand()
        m.observe(s)
    assert m.share(s) > initial and m.share(s) > .9


def test_known_terminal_folds_are_learning_opportunities():
    from core.interface import HandResult
    m = JamModel()
    s = spot(is_button=True, history=(ActionRecord(1,'me','raise',6),))
    for i in range(100):
        # Nine folds after our open for every effective jam.
        m.observe(replace(s, hand_id=i))
        action = ActionRecord(1,'opp','raise',200) if i % 10 == 0 else ActionRecord(1,'opp','fold',None)
        history = s.history + (action,)
        if i % 10 == 0:
            m.observe(replace(s, hand_id=i, history=history))
        m.finish_hand(HandResult(i, True, 0, history, (), None))
    jams, total = m.counts[m._key(s, 1)]
    assert (jams, total) == (10, 100)
    assert m.share(replace(s, history=s.history+(ActionRecord(1,'opp','raise',200),))) < .12


def test_partial_arena_data_scales_sb_jam_frequency_instead_of_ignoring_it():
    """Invisible SB folds make the exact open-jam frequency unknowable, but ignoring visible jams kept the 10%
    prior all half vs an always-shover: -3.7 bb/hand vs @shove in the organisers' engine (#45 review). Visible
    jams now count, scaled by an assumed SB entry rate (HIDDEN_SB_ENTRY)."""
    m = JamModel()
    m.complete_hands = False
    s = spot()  # villain is SB, opens
    for _ in range(100):
        m.observe(s)
        m.finish_hand()
    assert .6 < m.share(s) < .85


def test_v0_learns_blinds_before_nonterminal_observations():
    from core.interface import HandResult
    bot = V0Bot(seed=1)
    s = spot(starting_stack=2000, small_blind=10, big_blind=20, my_committed=20,
             opp_committed=20, history=(ActionRecord(1,'opp','call',None),),
             legal=LegalActions(False,True,0,40,2000))
    bot.act(s)
    bot.hand_over(HandResult(1,False,0,s.history,(),None))
    assert (bot._terminal_model.small_blind, bot._terminal_model.big_blind) == (10,20)


@pytest.mark.parametrize('hole,board', [
    (('9h','Th'),('Jh','Qh','Kh','2c','3d')),
    (('As','Ks'),('Ah','Ad','Kc','Kd','2h')),
    (('As','Ah'),('Ac','Ad','Ks','2h','3d')),
    (('9h','Th'),('Jh','Qh','Kh')),
])
def test_fallback_calls_other_provably_unbeatable_hands(hole, board):
    s = spot(hole_cards=hole, board=board, street={3:2,5:4}[len(board)])
    assert fallback_action(s) == Action('call')


def test_hidden_sb_folds_scale_but_keep_open_jam_evidence():
    """#45 review: in the arena BB half (complete_hands=False) visible open jams still count, scaled by an
    assumed SB entry rate, so an always-shover is not stuck at the 10% prior."""
    from bots.main.allin import HIDDEN_SB_ENTRY
    m = JamModel()
    m.complete_hands = False
    s = spot()
    assert m.share(s) == .10                     # no evidence yet: prior
    for _ in range(50):
        m.finish_hand()
        m.observe(s)
    expected = (50 * HIDDEN_SB_ENTRY + 8 * .10) / (50 + 8)
    assert m.share(s) == pytest.approx(expected) and m.share(s) > .6
    full = JamModel()
    for _ in range(50):
        full.finish_hand()
        full.observe(s)
    assert full.share(s) > m.share(s)             # complete view still trusts the raw ratio more
