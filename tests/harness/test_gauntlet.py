import random

from harness._types import Action, ActionRecord
from harness.engine import Seat, _validate, play_hand
from harness.gauntlet import format_table, main as gauntlet_main, run_gauntlet
from harness.match import deal
from harness.opponents import (OPPONENTS, AlwaysJam, EquityBot, JamTop, MinRaiser, ThreeBetAny)
from tests.harness.test_harness import Scripted, run

R = ActionRecord


def test_always_jam_shoves():
    b = Scripted()
    run(AlwaysJam(), b)
    assert b.states[0].opp_committed == 200 and b.states[0].legal.min_raise_to is None


def test_jam_top_jams_premiums_and_folds_trash():
    aa = ["As", "Ah", "2c", "7d", "3h", "8s", "Td", "Jc", "4d"]
    trash = ["7s", "2h", "Ac", "Ad", "3h", "8s", "Td", "Jc", "4d"]
    b = Scripted()
    out, _ = run(JamTop(), b, deck=aa)
    assert b.states[0].opp_committed == 200
    out, _ = run(JamTop(), Scripted(), deck=trash)
    assert out.deltas == (-1, 1)
    assert len(JamTop(0.5)._range) > len(JamTop(0.1)._range)


def test_min_raiser_min_raises():
    b = Scripted(Action("call"))
    run(MinRaiser(), b)
    assert b.states[0].opp_committed == 4                  # opened to the 2bb minimum
    assert b.states[2].history[-1] == R(2, "opp", "raise", 6)   # flop (BB checks first): min bet of one bb


def test_three_bet_any_opens_three_bets_and_folds_to_four_bet():
    b = Scripted(Action("call"))
    run(ThreeBetAny(), b)
    assert b.states[0].opp_committed == 5                  # 2.5bb open
    assert b.states[2].street == 2 and b.states[2].history[-1] == R(2, "opp", "raise", 10)   # half-pot c-bet
    a = Scripted(Action("raise", 6), Action("raise", 40))
    out, _ = run(a, ThreeBetAny())
    assert a.states[1].opp_committed == 18                 # 3-bet to 3x
    assert out.deltas == (18, -18)                         # folded to the 4-bet


def test_equity_bot_value_and_folds():
    strong = ["Ks", "Kh", "As", "Ah", "2c", "7d", "9h", "3s", "4c"]   # BB holds AA
    a = Scripted(Action("call"))
    run(a, EquityBot(), deck=strong)
    assert a.states[1].opp_committed > 2                   # AA raised the limp
    weak = ["Ks", "Kh", "7s", "2h", "Kd", "Kc", "9h", "3s", "4c"]
    out, _ = run(Scripted(Action("raise", 6), Action("raise", 100)), EquityBot(), deck=weak)
    assert out.deltas[0] > 0                               # 72o folds to aggression


def test_all_opponents_legal_against_each_other():
    rng = random.Random(5)
    names = list(OPPONENTS)
    for i in range(1500):
        a, b = OPPONENTS[rng.choice(names)](), OPPONENTS[rng.choice(names)]()
        for bot in (a, b):
            bot.new_match("m", None)
        seats = (Seat(a), Seat(b))
        out = play_hand(seats, deal(9, i), (rng.randint(3, 300), rng.randint(3, 300)), 1, 2, i)
        assert out.deltas[0] + out.deltas[1] == 0
        assert seats[0].illegal == seats[1].illegal == seats[0].errors == seats[1].errors == 0


def test_run_gauntlet_and_table():
    res = run_gauntlet("always_call", hands=50, seed=1, opponents=["random", "jam_top"])
    assert [r["bot_b"].split("@")[0] for r in res] == ["random", "jam_top"]
    assert all(r["duplicate"] and r["hands"] == 50 for r in res)
    table = format_table(res)
    assert "jam_top" in table and "mean" in table
    res = run_gauntlet(lambda: MinRaiser(), hands=20, seed=1, opponents=["always_jam"])
    assert res[0]["illegal_a"] == 0


def test_cli(capsys):
    gauntlet_main(["--a", "random", "--hands", "20", "--only", "always_call", "min_raiser", "--no-save"])
    out = capsys.readouterr().out
    assert "always_call" in out and "min_raiser" in out and "always_jam" not in out


def test_postflop_jammer_shoves_made_hands_and_folds_air():
    from harness.opponents import PostflopJammer
    from tests.bots.main.test_fallback import make_state
    j = PostflopJammer()
    pair = make_state(("Ah", "7c"), ("7d", "Kc", "2s"))
    assert j.act(pair) == Action("raise", pair.legal.max_raise_to)
    air = make_state(("4h", "3c"), ("Kd", "Qc", "9s"), facing=10, pot=20)
    assert j.act(air) == Action("fold")
    assert j.act(make_state(("4h", "3c"), ("Kd", "Qc", "9s"))) == Action("check")
    draw = make_state(("Ah", "5h"), ("Kh", "9h", "2c"), facing=10, pot=20)
    assert j.act(draw).kind == "raise"


def test_research_archetypes_behave_as_described():
    from harness.opponents import MCPotOdds, Maniac70, PassiveStation, SolverLite, StarterClone, TagValue
    from tests.bots.main.test_fallback import make_state
    nuts = make_state(("Ah", "Kh"), ("Qh", "Jh", "Th"))
    air_facing = make_state(("4c", "3d"), ("Ah", "Kd", "9s", "8c", "2h"), facing=40, pot=40)
    for bot in (StarterClone(), MCPotOdds(), PassiveStation()):
        assert bot.act(nuts).kind == "raise", bot.name
        assert bot.act(air_facing) == Action("fold"), bot.name
    # Station calls a cheap bet with modest equity; starter clone wants +10% over pot odds.
    middling = make_state(("9s", "7d"), ("Kc", "9h", "4s"), facing=4, pot=40)
    assert PassiveStation().act(middling) == Action("call")
    # TAG folds trash preflop, raises premiums.
    assert TagValue().act(make_state(("7d", "2c"), facing=10, pot=30)) == Action("fold")
    assert TagValue().act(make_state(("As", "Ah"), facing=10, pot=30)).kind == "raise"
    # Maniac raises about 70% of the time.
    m = Maniac70()
    m.new_match("m", None)
    raises = sum(m.act(make_state(("7d", "2c"), ("Kd", "9s", "3h"))).kind == "raise" for _ in range(400))
    assert 230 < raises < 330
    # Solver-lite opens about 70% from the button and always acts legally.
    s = SolverLite()
    s.new_match("m", None)
    st = make_state(("Ah", "Kd"), facing=10, pot=30)
    assert s.act(st).kind == "raise"
