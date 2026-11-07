from types import ModuleType, SimpleNamespace
import sys

import pytest

from tools.tune.build import validate_contract
from tools.tune.runtime import configure
from tools.tune.space import DEFAULT
from tools.tune.stats import healthy, reliability_failure


def test_baseline_contract_refuses_silent_default_drift(tmp_path):
    root, helpers = tmp_path / "repo", tmp_path / "helpers"
    (root / "bots/main").mkdir(parents=True)
    helpers.mkdir()
    (root / "bots/main/opponent.py").write_text("MIN_SAMPLES = 12\n")
    (helpers / "opponent.py").write_text("MIN_OBS = 15\n")
    path = root / "bots/main/postflop.py"
    code = "RAISE_EQ = 0.75\ndef _checked_to(a,b,c,d,e,f,g,h): pass\ndef _facing_bet(a,b,c,d,e,f,g,h): pass\ndef _bet(a,b): pass\n"
    path.write_text(code)
    validate_contract(root, helpers)
    path.write_text(code.replace("0.75", "0.80"))
    with pytest.raises(RuntimeError, match="Unsupported default"):
        validate_contract(root, helpers)
    path.write_text(code.replace("_bet(a,b)", "_bet(a,b,c)"))
    with pytest.raises(RuntimeError, match="interface"):
        validate_contract(root, helpers)


def test_optional_raw_counts_are_forwarded_to_newer_research_policy(monkeypatch):
    opponent = ModuleType("opponent")
    pf = ModuleType("bots.main.postflop")
    pf.VALUE_EQ, pf.CALL_MARGIN, pf.RAISE_EQ = {2: 0.62}, {2: 0.01}, 0.75
    pf._checked_to = lambda *args: None
    pf._facing_bet = lambda *args: None
    received = []
    def knobs(opp, counts=None):
        received.append(counts)
        return SimpleNamespace(station=False, folder=False, maniac=False,
                               fold_to_bet=0.4, fold_to_cbet=0.4, aggression=1.0, counts=counts)
    pf.knobs = knobs
    bots, main = ModuleType("bots"), ModuleType("bots.main")
    bots.__path__, main.__path__, main.postflop = [], [], pf
    for name, module in (("opponent", opponent), ("bots", bots), ("bots.main", main), ("bots.main.postflop", pf)):
        monkeypatch.setitem(sys.modules, name, module)
    configure({**DEFAULT, "bluff_mode": "measured"})
    counts = {"fold_to_bet": (10, 20)}
    value = pf.knobs(SimpleNamespace(fold_to_bet=0.6, fold_to_cbet=0.5), counts)
    assert received == [counts] and value.counts == counts


def test_internal_strategy_errors_cannot_hide_behind_safe_arena_actions_or_censoring():
    row = dict(ok=True, deals=200, censored=True, result=dict(status="complete", deals_completed=200,
                mean_bb=10, faults_a=0, faults_b=0, disabled_a=None, disabled_b=None),
               bot_metrics={"0": {"fallbacks": {"error": 1}}})
    assert not healthy(row) and reliability_failure(row)
    row["bot_metrics"]["0"]["fallbacks"] = {"bank": 1}
    assert healthy(row)  # intentional clock protection is reported, not falsely called an engine fault
