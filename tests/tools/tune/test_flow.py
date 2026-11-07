"""Accelerated, entirely synthetic coordinator test: zero arena imports and zero games."""
import types
from pathlib import Path

from tools.tune.common import tree_hash
from tools.tune.overnight import Runner
from tools.tune.space import fields, initial_candidates
from tools.tune.store import Store


def test_full_phase_flow_locks_before_test_and_never_changes_source(tmp_path, monkeypatch):
    import tools.tune.overnight as module
    clock = {"now": 0.0}
    monkeypatch.setattr(module.time, "monotonic", lambda: clock["now"])
    source = tmp_path / "source"
    source.mkdir()
    sentinel = source / "production_bot.py"
    sentinel.write_text("# immutable fixture, never executed\n")
    candidates = initial_candidates(8, 42)
    plan = dict(hours=8, plan_hash="p", repo_sha="repo", arena_sha="arena", seed=42, deals=200,
                candidates=candidates, fields=fields(), min_validation_blocks=3, min_test_blocks=3,
                practical_delta=0.005, max_family_regression=0.10,
                source_hash=tree_hash(source), artifact_hashes={})
    for identity in [c["id"] for c in candidates]:
        (tmp_path / "candidates" / identity).mkdir(parents=True)
    for phase in plan["fields"].values():
        for profiles in phase.values():
            for profile in profiles:
                (tmp_path / "opponents" / profile["id"]).mkdir(parents=True)
    runner = Runner(tmp_path, plan, workers=1)
    runner.phase_end = lambda phase: dict(preflight=100, search=200, validation=400, test=600)[phase]
    winner = candidates[1]["id"]
    test_locks = []
    def synthetic_batch(self, jobs, boundary):
        for job in jobs:
            if self.store.get(job["id"]):
                continue
            if job["kind"] == "pack":
                target = Path(job["target"])
                target.mkdir(parents=True, exist_ok=True)
                payload = target / "bot.pkl"
                payload.write_bytes(b"synthetic fixture, not a pickle")
                result = {**job, "ok": True, "payload": str(payload), "bytes": 1}
            else:
                if job["phase"] == "test":
                    assert self.state.get("selection_hash")
                    assert self.state.get("selection_pack_validated")
                    test_locks.append(self.state["selection_hash"])
                score = (0 if job["candidate"] == "baseline" else
                         0.2 if job["candidate"] == winner else -0.1)
                result = {**job, "ok": True, "result": dict(status="complete", deals_completed=200,
                    mean_bb=score, hands_played=400, faults_a=0, faults_b=0, disabled_a=None, disabled_b=None)}
            self.store.add(result)
        clock["now"] += 30
        return True
    runner.batch = types.MethodType(synthetic_batch, runner)
    runner.run_all()
    assert runner.state["phase"] == "complete" and runner.state["selected"] == winner
    assert len(set(test_locks)) == 1
    assert tree_hash(source) == plan["source_hash"]
    assert sentinel.read_text() == "# immutable fixture, never executed\n"
    assert (tmp_path / "reports/MORNING_REPORT.md").exists()
    recovered = Store(tmp_path)
    assert any(r["phase"] == "test" for r in recovered.rows())
    recovered.close()
