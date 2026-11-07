from adapters.arena.build import build
from adapters.arena.gauntlet import format_table, label, parse_match

SAMPLE = """combo  vs  starter   (1000 deals = 2000 hands, 21.0s, status: complete)
  combo: +0.604 bb/hand (95% CI +0.124 .. +1.083)
  -> combo is ahead (CI excludes 0)
  faults: combo=0, starter=2    think time: combo=20.3s, starter=0.4s
"""


def test_parse_match():
    r = parse_match(SAMPLE)
    assert (r["bb_per_hand"], r["ci_low"], r["ci_high"]) == (0.604, 0.124, 1.083)
    assert (r["faults_a"], r["faults_b"], r["think_a_s"], r["status"]) == (0, 2, 20.3, "complete")
    assert parse_match("Traceback ... boom")["bb_per_hand"] is None


def test_format_table_marks_clear_results_and_errors():
    rows = [dict(parse_match(SAMPLE), opponent="bots/starter", deals=1000, seed=11),
            dict(parse_match("x"), opponent="/tmp/myteam", deals=1000, seed=11, error="boom")]
    t = format_table(rows)
    assert "starter" in t and "*" in t and "ERROR: boom" in t and "mean +0.604" in t
    assert label("/a/b/myteam") == "myteam" and label("call") == "call"


def test_build_wraps_harness_opponent(tmp_path):
    copied = build("jamtest", tmp_path / "jam", bot="jam_postflop")
    text = (tmp_path / "jam" / "bot.py").read_text()
    assert "OPPONENTS['jam_postflop']()" in text and text.count("(PokerBot)") == 1
    assert "harness/opponents.py" in copied and (tmp_path / "jam" / "harness" / "opponents.py").exists()
    main = (build("maintest", tmp_path / "main") and (tmp_path / "main" / "bot.py").read_text())
    assert "MainBot()" in main
