"""Exercise worker telemetry through a fake arena API; no engine, bots, or deals run."""
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from tools.tune.worker import pairing


@pytest.mark.parametrize("final,reported_decisions,complete", [(True, 1, True), (False, 1, False), (True, 0, False)])
def test_worker_collects_real_interface_fields_from_synthetic_pairing(tmp_path, monkeypatch, final, reported_decisions, complete):
    class Contestant:
        def __init__(self):
            self.decisions, self._stretch_think = 0, 0.0
        def new_stretch(self, budget):
            self._stretch_think = 0.0
        def decide(self, state, hero, history):
            self.decisions += 1
            self._stretch_think += 0.01
            return SimpleNamespace(action="call")
    contestants = []
    def contestant_from_spec(*args, **kwargs):
        value = Contestant()
        contestants.append(value)
        return value
    def play_pairing(a, b, config, hand_sink):
        assert config.stack == 2000 and config.big_blind == 20
        assert config.think_budget_per_deal == 0.2
        for orientation in (0, 1):
            a.new_stretch(40)
            a.decide({"street": "flop"}, orientation, [])
            hand_sink(dict(orientation=orientation, dealer_seat=0, deal=0,
                           net=[20, -20], ended_by="showdown"))
        with (tmp_path / "candidate.log").open("w") as log:
            for seat in (0, 1):
                log.write("OVERNIGHT_METRICS " + json.dumps(dict(seat=seat, final=final, decisions=reported_decisions, fallbacks={"bank": 2})) + "\n")
        return SimpleNamespace(to_dict=lambda: dict(status="complete", mean_bb=0.0, faults_a=0, faults_b=0))
    arena = ModuleType("arena")
    arena.__path__ = []
    duel, specs = ModuleType("arena.duel"), ModuleType("arena.specs")
    duel.PairingConfig, duel.play_pairing = lambda **kw: SimpleNamespace(**kw), play_pairing
    specs.contestant_from_spec = contestant_from_spec
    for name, module in (("arena", arena), ("arena.duel", duel), ("arena.specs", specs)):
        monkeypatch.setitem(sys.modules, name, module)
    result = pairing(dict(job_dir=str(tmp_path), a="a", b="b", deals=200, seed=7, timeout=100))
    assert result["telemetry_complete"] is complete
    assert result["latency"]["count"] == 2
    assert result["actions"] == {"flop:call": 2}
    assert result["positions"]["button"] == {"hands": 1, "net_bb": 1.0}
    assert result["positions"]["big_blind"] == {"hands": 1, "net_bb": -1.0}
    assert result["bank_fraction_max"] == 0.01/40
    assert len(result["bot_metrics"]) == 2
    assert (tmp_path / "hands.jsonl.gz").exists()
