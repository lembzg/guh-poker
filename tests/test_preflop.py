"""Tests for bots/myteam. They drive the real engine, not a mock of it.

They need a checkout of poker_bot_infrastructure, which is a separate repo:

    ARENA_ROOT=/path/to/poker_bot_infrastructure python -m pytest tests/test_preflop.py

Without ARENA_ROOT this file is skipped.
"""

from __future__ import annotations

import ast
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import pytest

ARENA_ROOT = os.environ.get("ARENA_ROOT")
if not ARENA_ROOT:
    pytest.skip("ARENA_ROOT is not set", allow_module_level=True)
sys.path.insert(0, ARENA_ROOT)

BOT_DIR = Path(__file__).resolve().parents[1] / "bots" / "myteam"
sys.path.insert(0, str(BOT_DIR))

import bot as bot_module  # noqa: E402
import cloudpickle  # noqa: E402
import opponent as opponent_module  # noqa: E402
import preflop  # noqa: E402
import ranges  # noqa: E402
from arena.agents import LocalAgent  # noqa: E402
from arena.contestant import Contestant  # noqa: E402
from arena.pickling import MAX_BYTES, pickle_bot  # noqa: E402
from arena.table import play_hand  # noqa: E402
from equity_table import COMBOS, EQ, HANDS, INDEX, W  # noqa: E402
from game.action_engine import apply_action  # noqa: E402
from game.match_runtime import MatchRuntime  # noqa: E402
from game.player import Player  # noqa: E402
from game.poker_game import PokerGame  # noqa: E402
from game.runtime_flow import (  # noqa: E402
    current_actor_index,
    finish_action,
    prepare_turn_event,
)
from player_sdk.models import ActionRecord, GameState, Response  # noqa: E402
from player_sdk.parser import GameStateParser  # noqa: E402
from player_sdk.response import validate_response  # noqa: E402
from player_sdk.translate import translate_action  # noqa: E402

PARSER = GameStateParser()
BOUNDARY_STACKS = (
    11, 19, 20, 21, 30, 39, 40, 41, 49, 50, 51, 69, 70, 71, 79, 80, 81,
    199, 200, 201, 439, 440, 441, 600, 800, 1000, 1999, 2000, 2001, 5000,
)
NO_LOG = lambda *_: None  # noqa: E731


class Table:
    """A real engine hand that can be advanced by scripted actions."""

    def __init__(self, stacks, seed):
        self.players = [
            Player(stacks[0], "seat0"), Player(stacks[1], "seat1"),
        ]
        self.engine = PokerGame(
            self.players, big_blind_amount=20, small_blind_amount=10,
            rng=random.Random(seed),
        )
        self.runtime = MatchRuntime(
            match_id="t", engine=self.engine, turn_timeout_seconds=0,
            event_log_limit=1, status="running",
        )
        self.engine.start_hand()
        self.history = [
            {
                "player_id": move[0], "action": name, "amount": move[2],
                "street": "preflop",
            }
            for move, name in zip(
                self.engine.preflop_moves[:2],
                ("post_small_blind", "post_big_blind"),
            )
        ]
        self.over = False

    def state(self):
        actor = current_actor_index(self.runtime)
        if actor is None or self.over:
            return None, None
        _, event = prepare_turn_event(self.runtime, NO_LOG)
        payload = dict(event["state"])
        payload["action_history"] = list(self.history)
        return (
            PARSER.parse({"state": payload}, hero_index=actor),
            actor,
        )

    def apply(self, actor, action, amount=None):
        street = self.engine.curr_street
        name, emitted = apply_action(self.runtime, actor, action, amount)
        self.history.append(
            {
                "player_id": f"seat{actor}", "action": name,
                "amount": emitted, "street": street,
            }
        )
        if finish_action(self.runtime, actor, street, NO_LOG) is not None:
            self.over = True


def scripted_raise(state, rng):
    low, high = state.min_raise_to, state.max_raise_to
    if rng.random() < 0.7:
        return min(high, low + rng.randint(0, 60))
    return rng.randint(low, high)


# Each script gives the actions before the node under test. "r" raises and "c"
# calls; the actor alternates automatically.
NODE_SCRIPTS = {
    preflop.SB_FIRST_IN: "",
    preflop.BB_VS_LIMP: "c",
    preflop.BB_VS_OPEN: "r",
    preflop.SB_VS_3BET: "rr",
    preflop.SB_VS_ISO: "cr",
    preflop.BB_VS_4BET: "rrr",
    preflop.BB_VS_LIMP_RERAISE: "crr",
    "DEEP_5BET": "rrrr",
}


def table_at(script, stacks, seed, rng):
    table = Table(stacks, seed)
    for step in script:
        state, actor = table.state()
        if state is None:
            return None
        if step == "c":
            if state.call_amount == 0:
                table.apply(actor, "check")
            else:
                table.apply(actor, "call")
        else:
            if not (state.can_raise or state.can_bet):
                return None
            table.apply(actor, "raise_to", scripted_raise(state, rng))
    return table


def make_bot(seed=1):
    bot_module.SEED = seed
    return bot_module.MyTeamBot()


# ---- legality ------------------------------------------------------------


@pytest.mark.parametrize("name,script", NODE_SCRIPTS.items())
def test_each_node_is_legal_across_10k_random_states(name, script):
    rng = random.Random(hash(name) & 0xffff)
    played = 0
    attempts = 0
    while played < 10_000:
        attempts += 1
        assert attempts < 200_000, f"could not reach {name}"
        if rng.random() < 0.5:
            stacks = (2000, 2000)
        else:
            stacks = (
                rng.choice(BOUNDARY_STACKS), rng.choice(BOUNDARY_STACKS),
            )
        table = table_at(script, stacks, rng.randrange(10**9), rng)
        if table is None:
            continue
        state, actor = table.state()
        if state is None or state.street != "preflop":
            continue
        bot = make_bot(played)
        response = bot.act(state)
        assert isinstance(response, Response)
        validate_response(response, state)
        action, amount = translate_action(response, state)
        table.apply(actor, action, amount)  # the engine raises if illegal
        played += 1


def test_postflop_placeholder_is_legal_on_every_street():
    rng = random.Random(5)
    for hand in range(3000):
        stacks = (rng.choice(BOUNDARY_STACKS), rng.choice(BOUNDARY_STACKS))
        table = Table(stacks, hand)
        bot = make_bot(hand)
        for _ in range(60):
            state, actor = table.state()
            if state is None:
                break
            if rng.random() < 0.5 and state.street != "preflop":
                if state.can_raise or state.can_bet:
                    table.apply(actor, "raise_to", scripted_raise(state, rng))
                    continue
            response = bot.act(state)
            validate_response(response, state)
            table.apply(actor, *translate_action(response, state))


def test_no_faults_in_real_hands_at_boundary_stacks():
    rng = random.Random(9)
    from arena.baselines import RandomBot

    for hand in range(1500):
        ours = Contestant(
            name="ours", factory=lambda: LocalAgent(bot_module.MyTeamBot)
        )
        theirs = Contestant(
            name="theirs", factory=lambda: LocalAgent(RandomBot)
        )
        stacks = [rng.choice(BOUNDARY_STACKS), rng.choice(BOUNDARY_STACKS)]
        seats = [ours, theirs] if hand % 2 else [theirs, ours]
        play_hand(seats, deal_seed=hand, stacks=stacks)
        assert ours.faults == 0, ours.fault_log


# ---- engine facts the design relies on -----------------------------------


def test_sb_limp_is_call_at_call_amount_10():
    table = Table((2000, 2000), 1)
    state, actor = table.state()
    assert actor == 0
    assert state.call_amount == 10
    assert state.current_bets == (10, 20)
    action, amount = translate_action(Response.call(), state)
    assert (action, amount) == ("call", None)
    table.apply(actor, action, amount)
    assert table.history[-1]["amount"] == 10
    state, actor = table.state()
    assert actor == 1
    assert state.current_bets == (20, 20)
    assert state.call_amount == 0
    assert preflop.detect_node(state) == preflop.BB_VS_LIMP


def test_seat_zero_is_always_the_button():
    ours = Contestant(name="a", factory=lambda: LocalAgent(bot_module.MyTeamBot))
    theirs = Contestant(name="b", factory=lambda: LocalAgent(bot_module.MyTeamBot))
    for deal in range(50):
        record = play_hand(
            [ours, theirs], deal_seed=deal, hand_index=deal,
            stacks=[2000, 2000],
        )
        assert record.dealer_seat == 0
        assert record.actions[0]["seat"] == 0
        assert record.actions[0]["action"] == "post_small_blind"


def test_raise_total_counts_chips_in_this_round():
    table = Table((2000, 2000), 1)
    state, actor = table.state()
    assert state.min_raise_to == 40
    assert state.max_raise_to == 2000
    table.apply(actor, "raise_to", 50)
    assert table.players[0].curr_balance == 1950  # the blind counts toward 50


def test_opponent_hand_number_and_cards_are_not_visible():
    table = Table((2000, 2000), 1)
    state, _ = table.state()
    assert not hasattr(state, "hand_number")
    assert not hasattr(state, "opponent_cards")


# ---- node detection ------------------------------------------------------


def crafted(sequence, is_sb, call=20, stack=1900, bets=(50, 100)):
    records = [
        ActionRecord("seat0", "post_small_blind", 10, "preflop"),
        ActionRecord("seat1", "post_big_blind", 20, "preflop"),
    ]
    seat = 0
    for step in sequence:
        action = {"r": "raise_to", "c": "call"}[step]
        records.append(ActionRecord(f"seat{seat}", action, 50, "preflop"))
        seat = 1 - seat
    me = 0 if is_sb else 1
    return GameState(
        hole_cards=("AS", "KS"), community_cards=(), pot_size=150,
        stack_sizes=(stack, stack), current_bets=bets,
        current_player_index=me, call_amount=call, minimum_raise=20,
        action_history=tuple(records), legal_actions=("fold", "call", "raise_to"),
        my_index=me, street="preflop", player_ids=("seat0", "seat1"),
        min_raise_to=100, max_raise_to=2000, dealer_index=0,
    )


@pytest.mark.parametrize(
    "sequence,is_sb,expected",
    [
        ("", True, preflop.SB_FIRST_IN),
        ("c", False, preflop.BB_VS_LIMP),
        ("r", False, preflop.BB_VS_OPEN),
        ("rr", True, preflop.SB_VS_3BET),
        ("cr", True, preflop.SB_VS_ISO),
        ("rrr", False, preflop.BB_VS_4BET),
        ("crr", False, preflop.BB_VS_LIMP_RERAISE),
        ("rrrr", True, preflop.FACING_BIG),
    ],
)
def test_node_detection_from_crafted_history(sequence, is_sb, expected):
    assert preflop.detect_node(crafted(sequence, is_sb)) == expected


@pytest.mark.parametrize("sequence,is_sb", [("r", False), ("rr", True)])
def test_a_jam_is_detected_at_any_stage(sequence, is_sb):
    state = crafted(sequence, is_sb, call=1950, stack=50, bets=(2000, 50))
    assert preflop.detect_node(state) == preflop.FACING_BIG


@pytest.mark.parametrize(
    "cards,key",
    [
        (("AS", "AH"), "AA"), (("AS", "KS"), "AKs"), (("KS", "AS"), "AKs"),
        (("AS", "KH"), "AKo"), (("2C", "7D"), "72o"), (("TD", "9D"), "T9s"),
    ],
)
def test_hand_key(cards, key):
    assert preflop.hand_key(cards) == key


# ---- tables and equity ---------------------------------------------------


def frequency(table, column, reach=None):
    reach = reach or {hand: 1.0 for hand in HANDS}
    total = sum(COMBOS[INDEX[h]] * reach[h] for h in HANDS)
    return sum(
        COMBOS[INDEX[h]] * reach[h] * table[h][column] for h in HANDS
    ) / total


def test_tables_are_complete_probabilities():
    tables = [
        ranges.SB_FIRST_IN, ranges.SB_FIRST_IN_TIGHT, ranges.SB_FIRST_IN_WIDE,
        ranges.BB_VS_LIMP, ranges.BB_VS_LIMP_WIDE, ranges.SB_VS_3BET,
        ranges.SB_VS_3BET_WIDE, ranges.BB_VS_4BET, ranges.SB_VS_ISO,
        *ranges.BB_VS_OPEN.values(),
    ]
    for table in tables:
        assert set(table) == set(HANDS)
        for row in table.values():
            assert all(-1e-9 <= x <= 1 + 1e-9 for x in row)
            assert sum(row) == pytest.approx(1.0, abs=0.005)


def test_baseline_frequencies_hit_their_bands():
    assert 0.86 <= frequency(ranges.SB_FIRST_IN, 0) <= 0.95
    bb = ranges.BB_VS_OPEN[50]
    three_bet = frequency(bb, 0) + frequency(bb, 1)
    assert 0.20 <= three_bet <= 0.25
    assert 1 - frequency(bb, 3) > 0.429
    assert 0.35 <= frequency(ranges.BB_VS_LIMP, 0) + frequency(
        ranges.BB_VS_LIMP, 1) <= 0.42
    assert 1 - frequency(ranges.BB_VS_OPEN[40], 3) > 0.50


def test_folds_are_only_offsuit_trash():
    for hand, row in ranges.SB_FIRST_IN.items():
        if row[2] > 0.5:
            assert hand.endswith("o")


def test_equity_matrix_is_antisymmetric_and_card_removal_is_right():
    for i in range(169):
        for j in range(169):
            assert EQ[i][j] + EQ[j][i] == 10000
            assert W[i][j] == W[j][i]
    assert sum(W[INDEX["AA"]]) == 6 * 1225
    assert W[INDEX["AA"]][INDEX["AA"]] == 1 * 6
    assert W[INDEX["AKs"]][INDEX["AKo"]] == 24
    assert EQ[INDEX["AA"]][INDEX["KK"]] == pytest.approx(8195, abs=60)


def jam_state(hole, bets=(2000, 20), stacks=(0, 1980), me=1):
    pot = sum(bets)
    return GameState(
        hole_cards=hole, community_cards=(), pot_size=pot,
        stack_sizes=stacks, current_bets=bets, current_player_index=me,
        call_amount=max(bets) - bets[me], minimum_raise=20,
        action_history=(
            ActionRecord("seat0", "post_small_blind", 10, "preflop"),
            ActionRecord("seat1", "post_big_blind", 20, "preflop"),
            ActionRecord("seat0", "raise_to", 2000, "preflop"),
        ),
        legal_actions=("fold", "call"), my_index=me, street="preflop",
        player_ids=("seat0", "seat1"), min_raise_to=2000, max_raise_to=1980,
        dealer_index=0,
    )


def test_jam_price_uses_exact_chips():
    state = jam_state(("AS", "AH"))
    assert preflop.required_equity(state) == pytest.approx(1980 / 4000)


def test_shove_bot_is_called_at_the_right_threshold_after_evidence():
    model = opponent_module.OpponentModel()
    rng = random.Random(1)
    # Before evidence, the jam range is tight, so a marginal hand folds.
    assert preflop.preflop_action(jam_state(("AS", "7H")), model, rng).action_type == "fold"
    model.c["sb_seen"] = 100
    model.c["sb_jam"] = 100
    calls = {}
    for hand in HANDS:
        first = hand[0] + "S"
        second = hand[1] + ("S" if hand.endswith("s") else "H")
        calls[hand] = preflop.preflop_action(
            jam_state((first, second)), model, rng
        ).action_type
    # Against a range near any-two, the price is 49.5%.
    from equity_table import equity_vs_weights

    weights = preflop.top_range(model.jam_range("open"))
    for hand in HANDS:
        equity = equity_vs_weights(hand, weights)
        if equity >= 0.495 + 1e-9:
            assert calls[hand] == "call", hand
        elif equity < 0.495 - 1e-9:
            assert calls[hand] == "fold", hand


# ---- opponent model ------------------------------------------------------


def test_no_shift_before_min_observations():
    model = opponent_module.OpponentModel()
    model.c["open_seen"] = opponent_module.MIN_OBS - 1
    model.c["open_fold"] = opponent_module.MIN_OBS - 1
    assert model.fold_to_open() == opponent_module.BASE_FOLD_TO_OPEN
    assert model.sb_knobs().open_shift == 0.0
    model.c["open_seen"] += 1
    model.c["open_fold"] += 1
    assert model.fold_to_open() > opponent_module.BASE_FOLD_TO_OPEN


def test_shift_grows_with_sample():
    small = opponent_module.shrunk(20, 20, 0.33)
    large = opponent_module.shrunk(100, 100, 0.33)
    assert 0.33 < small < large < 1.0


@pytest.mark.parametrize(
    "fields",
    [
        {"open_seen": 1000, "open_fold": 1000},
        {"open_seen": 1000, "open_call": 1000},
        {"open_seen": 1000, "open_3bet": 1000},
        {"open_seen": 1000, "open_jam": 1000},
        {"sb_seen": 1000, "sb_limp": 1000},
        {"sb_seen": 1000, "sb_jam": 1000},
        {"tb_seen": 1000, "tb_fold": 1000},
        {"tb_seen": 1000, "tb_call": 1000},
        {"tb_seen": 1000, "tb_4bet": 1000},
        {"iso_seen": 1000, "iso_fold": 1000},
        {"iso_seen": 1000, "iso_call": 1000},
    ],
)
def test_exploits_stay_bounded_at_extreme_reads(fields):
    model = opponent_module.OpponentModel()
    model.c.update(fields)
    sb, bb = model.sb_knobs(), model.bb_knobs()
    assert -1 <= sb.open_shift <= 1
    assert 40 <= sb.open_size <= 50
    assert 50 <= sb.value_size <= 100
    assert 0 <= sb.bluff_mult <= 1.6
    assert 0 <= bb.bluff_mult <= 1.6
    assert 3.7 <= bb.three_bet_mult <= 5.0
    assert 60 <= bb.iso_size <= 100
    for context in ("open", "vs_open", "deep"):
        assert 0.03 <= model.jam_range(context) <= 1.0


def play_scripted(bot, script_opponent, hands, seats_sb):
    """Plays real hands, handing the opponent's turn to a function."""
    for hand in range(hands):
        table = Table((2000, 2000), hand)
        for _ in range(40):
            state, actor = table.state()
            if state is None:
                break
            ours = actor == (0 if seats_sb else 1)
            if ours:
                response = bot.act(state)
                table.apply(actor, *translate_action(response, state))
            else:
                table.apply(actor, *script_opponent(state))


def fold_or_check(state):
    return ("check", None) if state.call_amount == 0 else ("fold", None)


def test_fold_to_open_is_inferred_though_never_shown():
    bot = make_bot(1)
    play_scripted(bot, fold_or_check, 200, seats_sb=True)
    counts = bot.model.c
    assert counts["open_seen"] > 100
    # Our non-all-in opens all got a fold. The newest hand isn't finished yet.
    assert counts["open_fold"] == counts["open_seen"]


def test_overfolder_gets_wider_smaller_opens():
    bot = make_bot(1)
    play_scripted(bot, fold_or_check, 200, seats_sb=True)
    knobs = bot.model.sb_knobs()
    assert knobs.open_shift > 0.5
    assert knobs.open_size < 50


def call_all(state):
    return ("check", None) if state.call_amount == 0 else ("call", None)


def test_calling_station_gets_no_bluffs_and_bigger_value():
    bot = make_bot(1)
    play_scripted(bot, call_all, 300, seats_sb=True)
    knobs = bot.model.sb_knobs()
    assert knobs.value_size > 50
    assert knobs.bluff_mult < 0.5
    assert knobs.limp_junk
    bb = make_bot(2)
    play_scripted(bb, call_all, 300, seats_sb=False)
    assert bb.model.bb_knobs().bluff_mult < 0.5 or bb.model.bb_knobs().iso_bluff_mult < 0.5


def three_bet_all(state):
    if state.street == "preflop" and state.can_raise:
        return "raise_to", min(state.max_raise_to, state.min_raise_to + 100)
    return ("check", None) if state.call_amount == 0 else ("call", None)


def test_maniac_tightens_opens_and_widens_four_bet_value():
    bot = make_bot(1)
    play_scripted(bot, three_bet_all, 300, seats_sb=True)
    knobs = bot.model.sb_knobs()
    assert knobs.open_shift < 0
    assert knobs.wide_value > 0
    assert knobs.call_wider > 0


def limper(state):
    return ("call", None) if state.call_amount else ("check", None)


def test_limp_heavy_sb_is_isolated_more():
    bot = make_bot(1)
    play_scripted(bot, limper, 200, seats_sb=False)
    assert bot.model.limp_share() > 0.6
    assert bot.model.bb_knobs().iso_shift > 0.5


# ---- robustness, speed, packaging ----------------------------------------


def test_act_returns_a_safe_move_when_strategy_raises(monkeypatch):
    def boom(*_):
        raise RuntimeError("boom")

    monkeypatch.setattr(bot_module, "preflop_action", boom)
    bot = make_bot(1)
    table = Table((2000, 2000), 1)
    state, _ = table.state()
    assert bot.act(state).action_type == "fold"
    table.apply(0, "call")
    state, _ = table.state()
    assert bot.act(state).action_type == "call"  # free, so it checks


def test_act_p99_latency_is_far_below_50ms():
    rng = random.Random(3)
    timings = []
    scripts = list(NODE_SCRIPTS.values())
    bot = make_bot(1)
    while len(timings) < 20_000:
        table = table_at(rng.choice(scripts), (2000, 2000), rng.randrange(10**9), rng)
        if table is None:
            continue
        state, _ = table.state()
        if state is None:
            continue
        started = time.perf_counter()
        bot.act(state)
        timings.append(time.perf_counter() - started)
    timings.sort()
    assert timings[int(len(timings) * 0.99)] < 0.005


def test_pickle_round_trips_in_a_fresh_process_and_fits(tmp_path):
    payload = pickle_bot(BOT_DIR)
    assert len(payload) < MAX_BYTES
    path = tmp_path / "bot.pkl"
    path.write_bytes(payload)
    # The fresh process has no bot folder on its path, as in the arena.
    code = (
        "import sys, cloudpickle, random\n"
        f"sys.path.insert(0, {ARENA_ROOT!r})\n"
        f"bot = cloudpickle.loads(open({str(path)!r}, 'rb').read())\n"
        "from player_sdk.models import GameState\n"
        "state = GameState(hole_cards=('AS','KS'), community_cards=(),\n"
        "    pot_size=30, stack_sizes=(1990,1980), current_bets=(10,20),\n"
        "    current_player_index=0, call_amount=10, minimum_raise=20,\n"
        "    action_history=(), legal_actions=('fold','call','raise_to'),\n"
        "    my_index=0, street='preflop', player_ids=('seat0','seat1'),\n"
        "    min_raise_to=40, max_raise_to=2000, dealer_index=0)\n"
        "print(bot.act(state).action_type)\n"
        "print(bot.rng.random())\n"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-I", "-c", code], cwd=tmp_path,
            capture_output=True, text=True, check=True,
        ).stdout.split()
        for _ in range(2)
    ]
    assert runs[0][0] == "raise"
    # The pickle stores one RNG state, and the first act reseeds it per process.
    assert runs[0][1] != runs[1][1]
    assert cloudpickle.loads(payload).model.c["sb_seen"] == 0


def test_runtime_imports_only_stdlib_and_sdk():
    allowed = set(sys.stdlib_module_names) | {
        "player_sdk", "ranges", "equity_table", "opponent", "preflop",
        "postflop", "__future__",
    }
    for path in BOT_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                assert name.split(".")[0] in allowed, (path.name, name)


def test_exactly_one_pokerbot_subclass():
    tree = ast.parse((BOT_DIR / "bot.py").read_text())
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert len(classes) == 1
    assert classes[0].bases[0].id == "PokerBot"
