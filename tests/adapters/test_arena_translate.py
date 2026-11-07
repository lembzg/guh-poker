"""Arena adapter tests with stand-ins for the organisers' player_sdk types (same field names)."""
from dataclasses import dataclass, field
from typing import Optional
from types import SimpleNamespace

from adapters.arena.translate import ArenaAdapter, card, from_response, to_game_state, to_response
from core.interface import Action, ActionRecord


@dataclass(frozen=True)
class Rec:
    player_id: str
    action: str
    amount: Optional[int] = None
    street: Optional[str] = None


@dataclass(frozen=True)
class GS:   # their GameState fields used by the adapter
    hole_cards: tuple
    community_cards: tuple
    pot_size: int
    stack_sizes: tuple
    current_bets: tuple
    call_amount: int
    action_history: tuple
    legal_actions: tuple
    my_index: int
    street: str
    player_ids: tuple = ("seat0", "seat1")
    min_raise_to: Optional[int] = None
    max_raise_to: Optional[int] = None
    dealer_index: int = 0
    small_blind: int = 10
    big_blind: int = 20


class Resp:
    @staticmethod
    def fold():
        return ("fold", None)

    @staticmethod
    def call():
        return ("call", None)

    @staticmethod
    def raise_to(n):
        return ("raise_to", n)


BLINDS = (Rec("seat0", "post_small_blind", 10, "preflop"), Rec("seat1", "post_big_blind", 20, "preflop"))


def preflop_button():
    return GS(("AS", "KD"), (), 30, (1990, 1980), (10, 20), 10, BLINDS, ("fold", "call", "raise_to"), 0,
              "preflop", min_raise_to=40, max_raise_to=2000)


def flop_bb_facing_bet():
    hist = BLINDS + (Rec("seat0", "raise_to", 60, "preflop"), Rec("seat1", "call", 40, "preflop"),
                     Rec("seat1", "check", 0, "flop"), Rec("seat0", "bet", 80, "flop"))
    return GS(("QH", "JH"), ("TH", "9C", "2D"), 200, (1860, 1940), (80, 0), 80, hist,
              ("fold", "call", "raise_to"), 1, "flop", min_raise_to=160, max_raise_to=1940, dealer_index=0)


def test_preflop_translation():
    s = to_game_state(preflop_button(), 0)
    assert s.hole_cards == ("As", "Kd") and s.board == () and s.street == 1 and s.is_button
    assert (s.my_committed, s.opp_committed, s.starting_stack) == (10, 20, 2000)
    assert s.history == ()
    lg = s.legal
    assert lg.can_fold and not lg.can_check and lg.call_amount == 10
    assert (lg.min_raise_to, lg.max_raise_to) == (40, 2000)


def test_flop_translation_hand_totals():
    s = to_game_state(flop_bb_facing_bet(), 3)
    assert s.street == 2 and not s.is_button and s.board == ("Th", "9c", "2d")
    assert (s.my_committed, s.opp_committed, s.starting_stack) == (60, 140, 2000)
    assert s.history == (ActionRecord(1, "opp", "raise", 60), ActionRecord(1, "me", "call", None),
                         ActionRecord(2, "me", "check", None), ActionRecord(2, "opp", "raise", 140))
    assert (s.legal.min_raise_to, s.legal.max_raise_to) == (220, 2000) and s.legal.call_amount == 80


def test_new_street_without_actions_moves_bets_to_prior():
    hist = BLINDS + (Rec("seat0", "call", 10, "preflop"), Rec("seat1", "check", 0, "preflop"))
    gs = GS(("2C", "7D"), ("AS", "KS", "QS"), 40, (1980, 1980), (0, 0), 0, hist, ("fold", "check", "bet"), 1,
            "flop", min_raise_to=20, max_raise_to=1980)
    s = to_game_state(gs, 0)
    assert (s.my_committed, s.opp_committed) == (20, 20) and s.legal.can_check
    assert (s.legal.min_raise_to, s.legal.max_raise_to) == (40, 2000)


def test_response_converts_hand_total_to_street_total_and_clamps():
    gs = flop_bb_facing_bet()
    s = to_game_state(gs, 0)
    assert to_response(Action("raise", 300), gs, s, Resp) == ("raise_to", 240)
    assert to_response(Action("raise", 10 ** 6), gs, s, Resp) == ("raise_to", 1940)
    assert to_response(Action("raise", 1), gs, s, Resp) == ("raise_to", 160)
    assert to_response(Action("call"), gs, s, Resp) == ("call", None)
    assert to_response(Action("fold"), gs, s, Resp) == ("fold", None)
    pre = preflop_button()
    assert to_response(Action("fold"), pre, to_game_state(pre, 0), Resp) == ("fold", None)


def test_fold_when_check_is_free_becomes_check():
    hist = BLINDS + (Rec("seat0", "call", 10, "preflop"),)
    gs = GS(("2C", "7D"), (), 40, (1980, 1980), (20, 20), 0, hist, ("fold", "check", "raise_to"), 1, "preflop",
            min_raise_to=40, max_raise_to=2000)
    assert to_response(Action("fold"), gs, to_game_state(gs, 0), Resp) == ("call", None)


class Recorder:
    def __init__(self, actions):
        self.actions, self.states, self.results, self.matches = list(actions), [], [], 0

    def new_match(self, match_id, opponent):
        self.matches += 1

    def act(self, state):
        self.states.append(state)
        return self.actions.pop(0)

    def hand_over(self, result):
        self.results.append(result)


def test_adapter_tracks_hands_and_infers_folds():
    bot = Recorder([Action("raise", 60), Action("call")])
    ad = ArenaAdapter(bot, Resp)
    assert bot.matches == 1
    assert ad.act(preflop_button()) == ("raise_to", 60)
    # Next hand (new cards): our preflop raise got no further turn, so they folded.
    nxt = GS(("7C", "7D"), (), 30, (1990, 1980), (10, 20), 0, BLINDS, ("fold", "check", "raise_to"), 1,
             "preflop", min_raise_to=40, max_raise_to=2000, dealer_index=0)
    ad.act(nxt)
    assert [s.hand_id for s in bot.states] == [0, 1]
    r = bot.results[0]
    assert r.hand_id == 0 and r.was_button and r.opp_hole_cards is None
    assert r.history == (ActionRecord(1, "me", "raise", 60), ActionRecord(1, "opp", "fold", None))


def test_adapter_never_raises():
    class Boom(Recorder):
        def act(self, state):
            raise RuntimeError("bug")
    ad = ArenaAdapter(Boom([]), Resp)
    assert ad.act(preflop_button()) == ("fold", None) and ad.errors == 1
    assert ad.act(object()) in (("fold", None), ("call", None))


def test_card():
    assert card("TD") == "Td" and card("as") == "As"


def test_external_response_uses_hand_totals_and_legal_bounds():
    gs = flop_bb_facing_bet()
    state = to_game_state(gs, 3)
    def response(kind, amount=None):
        return SimpleNamespace(action_type=kind, amount=amount)
    assert from_response(response("raise", 240), gs, state) == Action("raise", 300)
    assert from_response(response("raise", 1), gs, state) == Action("raise", 220)
    assert from_response(response("raise", 9999), gs, state) == Action("raise", 2000)
    assert from_response(response("all_in"), gs, state) == Action("raise", 2000)
    assert from_response(response("fold"), gs, state) == Action("fold")
    assert from_response(response("call"), gs, state) == Action("call")


def test_observe_preflop_then_act_postflop_reports_complete_hand_once():
    from dataclasses import replace
    bot = Recorder([Action("call")])
    ad = ArenaAdapter(bot, Resp)
    pre = replace(preflop_button(), hole_cards=("QH", "JH"), my_index=1)
    ad.observe(pre, SimpleNamespace(action_type="call", amount=None))
    assert bot.states == []  # external preflop never invokes MainBot's preflop strategy
    ad.act(flop_bb_facing_bet())
    ad.observe(preflop_button(), SimpleNamespace(action_type="fold", amount=None))
    assert ad.hand_id == 1 and ad.errors == 0
    assert len(bot.results) == 1
    result = bot.results[0]
    assert [r.kind for r in result.history] == ["raise", "call", "check", "raise", "call"]
    assert result.history[-1] == ActionRecord(2, "me", "call", None)


def test_observed_preflop_raise_followed_by_new_hand_infers_fold():
    from dataclasses import replace
    bot = Recorder([])
    ad = ArenaAdapter(bot, Resp)
    ad.observe(preflop_button(), SimpleNamespace(action_type="raise", amount=60))
    ad.observe(replace(preflop_button(), hole_cards=("7C", "7D")),
               SimpleNamespace(action_type="fold", amount=None))
    assert bot.results[0].history == (
        ActionRecord(1, "me", "raise", 60), ActionRecord(1, "opp", "fold", None),
    )
    assert ad.errors == 0


def test_actual_opponent_stack_and_covering_bet_do_not_invent_fold():
    from dataclasses import replace
    gs = replace(preflop_button(), stack_sizes=(1990, 40))
    bot = Recorder([Action('raise', 60)])
    ad = ArenaAdapter(bot, Resp)
    ad.act(gs)
    assert bot.states[0].opp_starting_stack == 60
    ad._finish_hand()
    assert bot.results[0].history == (ActionRecord(1, 'me', 'raise', 60),)


def test_external_decisions_update_optional_state_observer():
    bot = Recorder([])
    seen = []
    bot.observe_state = seen.append
    ad = ArenaAdapter(bot, Resp)
    ad.observe(preflop_button(), SimpleNamespace(action_type='call', amount=None))
    assert len(seen) == 1 and seen[0].opp_starting_stack == 2000
