import json
import os
import platform
import sys
import threading
import time

import pytest

from tools.tune.common import atomic_json, digest, run_process, seed_for, tree_hash
from tools.tune.overnight import Runner, load_plan, main, run_lock
from tools.tune.space import DEFAULT, candidate, initial_candidates, offspring
from tools.tune.store import Store


def minimal_plan(run):
    (run / "source").mkdir()
    (run / "source/frozen.py").write_text("VALUE = 1\n")
    plan = dict(schema=1, source_hash=tree_hash(run / "source"), artifact_hashes={})
    plan["plan_hash"] = digest(plan)
    atomic_json(run / "plan.json", plan)
    return plan


def test_phase_seeds_reproducible_and_disjoint():
    keys = [seed_for(123, p, b) for p in ("search", "validation", "test") for b in range(100)]
    assert len(keys) == len(set(keys))
    assert seed_for(123, "test", 10) == seed_for(123, "test", 10)


def test_proposals_are_unique_bounded_and_reproducible():
    first = initial_candidates(32, 1)
    assert first[0]["id"] == "baseline" and len(first) == 32
    assert first == initial_candidates(32, 1)
    assert len({r["id"] for r in first}) == 32
    proposal = offspring([DEFAULT], 8, 2, {r["id"] for r in first})
    assert not {r["id"] for r in proposal} & {r["id"] for r in first}
    assert all(r["id"] == candidate(r["config"])["id"] for r in proposal)


def test_changed_plan_or_frozen_source_refuses_resume(tmp_path):
    minimal_plan(tmp_path)
    assert load_plan(tmp_path)["schema"] == 1
    (tmp_path / "source/frozen.py").write_text("VALUE = 2\n")
    with pytest.raises(RuntimeError, match="source changed"):
        load_plan(tmp_path)
    plan = json.loads((tmp_path / "plan.json").read_text())
    plan["schema"] = 2
    atomic_json(tmp_path / "plan.json", plan)
    with pytest.raises(RuntimeError, match="Plan changed"):
        load_plan(tmp_path)


def test_atomic_worker_results_recovered_once_and_checked(tmp_path):
    directory = tmp_path / "jobs/one"
    directory.mkdir(parents=True)
    job = dict(id="one", kind="match", phase="search", candidate="baseline", plan_hash="p")
    atomic_json(directory / "job.json", job)
    atomic_json(directory / "result.json", {**job, "ok": True})
    store = Store(tmp_path)
    assert store.recover("p") == 1
    assert store.recover("p") == 0
    assert len(store.rows()) == 1
    with pytest.raises(RuntimeError, match="another plan"):
        store.recover("other")
    store.close()


@pytest.mark.skipif(os.name == "nt", reason="POSIX advisory-lock semantics")
def test_second_coordinator_cannot_take_lock(tmp_path):
    with run_lock(tmp_path):
        with pytest.raises(BlockingIOError):
            with run_lock(tmp_path):
                pytest.fail("double-start must be blocked")


def test_process_timeout_terminates_synthetic_job(tmp_path):
    started = time.monotonic()
    outcome = run_process([sys.executable, "-c", "import time; time.sleep(30)"],
                          cwd=tmp_path, timeout=0.3, log=tmp_path / "process.log")
    assert outcome["timeout"] and time.monotonic()-started < 5


def test_scheduler_obeys_weighted_cpu_tokens_and_deduplicates(tmp_path, monkeypatch):
    runner = Runner.__new__(Runner)
    runner.run, runner.store = tmp_path, Store(tmp_path)
    runner.stop, runner.budget, runner.last_report = threading.Event(), 3, time.monotonic()
    runner.save = lambda: None
    lock, counter = threading.Lock(), {"active": 0, "max": 0, "calls": 0}
    def execute(job, boundary):
        with lock:
            counter["active"] += job["cost"]
            counter["max"] = max(counter["max"], counter["active"])
            counter["calls"] += 1
        time.sleep(0.02)
        with lock:
            counter["active"] -= job["cost"]
        return {**job, "ok": True}
    runner.execute = execute
    jobs = [dict(id=str(i), cost=2 if i%2 else 1, kind="match", phase="search", candidate="v") for i in range(8)]
    assert runner.batch(jobs, time.monotonic()+30)
    assert counter["max"] <= 3 and counter["calls"] == 8
    assert runner.batch(jobs, time.monotonic()+30)
    assert counter["calls"] == 8
    runner.store.close()


def test_run_requires_explicit_start_and_never_launches_worker(tmp_path, monkeypatch):
    minimal_plan(tmp_path)
    monkeypatch.setattr(Runner, "run_all", lambda self: pytest.fail("a run was started"))
    with pytest.raises(SystemExit):
        main(["run", "--run-dir", str(tmp_path)])


def test_expired_run_deadline_is_not_reset_by_resume(tmp_path):
    plan = dict(hours=8, plan_hash="p", candidates=[dict(id="baseline", config=DEFAULT)])
    state = dict(phase="complete", started_epoch=time.time()-30000, deadline_epoch=time.time()-100,
                 plan_hash="p", candidates={"baseline": plan["candidates"][0]}, machine={"system": platform.platform()})
    atomic_json(tmp_path / "state.json", state)
    runner = Runner(tmp_path, plan)
    assert runner.end <= time.monotonic()+0.1
    assert runner.state["deadline_epoch"] == state["deadline_epoch"]
    runner.store.close()


def test_match_jobs_share_deals_and_reset_match_scope(tmp_path):
    from tools.tune.space import fields
    runner = Runner.__new__(Runner)
    runner.run, runner.plan = tmp_path, dict(fields=fields(), seed=42, deals=200, plan_hash="p")
    runner.payload = lambda label, source: str(tmp_path / label)
    jobs = runner.match_jobs(["v1", "v2"], "search", 7)
    assert len(jobs) == 8*3
    assert len({j["seed"] for j in jobs}) == 1
    assert {j["deals"] for j in jobs} == {200}
    assert len({j["id"] for j in jobs}) == len(jobs)
    assert not {j["seed"] for j in jobs} & {j["seed"] for j in runner.match_jobs(["v1"], "test", 7)}
