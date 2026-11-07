"""Prepare now. Explicitly start later. Eight-hour, report-only, resumable arena tuning."""
from __future__ import annotations

import argparse
import contextlib
import concurrent.futures as cf
import datetime as dt
import os
import platform
import signal
import sys
import threading
import time
from pathlib import Path

from .build import build_candidate, prepare
from .common import (atomic_json, cpu_budget, digest, ensure_disk, python_guard,
                     read_json, reap_orphans, run_process, seed_for, tree_hash)
from .report import export
from .space import offspring
from .stats import summarize
from .store import Store


@contextlib.contextmanager
def run_lock(run):
    stream = (run / "run.lock").open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            stream.write(b"0")
            stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        stream.close()


def load_plan(run, *, verify=True):
    plan = read_json(run / "plan.json")
    value = dict(plan)
    expected = value.pop("plan_hash")
    if digest(value) != expected:
        raise RuntimeError("Plan changed after preparation; create a new run instead")
    if verify:
        if tree_hash(run / "source") != plan["source_hash"]:
            raise RuntimeError("Frozen source changed; refusing to mix experiment versions")
        for path, fingerprint in plan["artifact_hashes"].items():
            if tree_hash(run / path) != fingerprint:
                raise RuntimeError(f"Prepared bot changed: {path}")
    return plan


class Runner:
    def __init__(self, run, plan, workers=None):
        self.run, self.plan = run, plan
        reap_orphans(run)
        self.store = Store(run)
        self.store.recover(plan["plan_hash"])
        self.stop = threading.Event()
        self.budget = cpu_budget(workers)
        self.last_report = 0.0
        self.state_path = run / "state.json"
        self.state = read_json(self.state_path) if self.state_path.exists() else dict(
            phase="preflight", started_epoch=time.time(),
            deadline_epoch=time.time()+plan["hours"]*3600,
            plan_hash=plan["plan_hash"], candidates={c["id"]: c for c in plan["candidates"]},
            active=[c["id"] for c in plan["candidates"]], search_block=0,
            protected=[c["id"] for c in plan["candidates"][:5]],
            validation_block=0, test_block=0, generation=0, phase_round=0,
            source_integrity=True, machine=dict(system=platform.platform(), python=sys.version,
                                               logical_cpus=os.cpu_count(), cpu_tokens=self.budget))
        if self.state["plan_hash"] != plan["plan_hash"]:
            raise RuntimeError("State belongs to another plan")
        if self.state.get("machine", {}).get("system") != platform.platform():
            raise RuntimeError("Resume on the same machine/OS; prepare a new run after moving computers")
        if "last_error" in self.state:
            self.state.setdefault("previous_errors", []).append(self.state.pop("last_error"))
        total = plan["hours"]*3600
        elapsed = max(self.state.get("elapsed_seconds", 0), time.time()-self.state["started_epoch"], 0)
        remaining = min(max(0, total-elapsed), max(0, self.state["deadline_epoch"]-time.time()))
        self.clock_start = time.monotonic()
        self.elapsed_before = total-remaining
        self.end = self.clock_start + remaining
        self.start = self.end - plan["hours"]*3600
        self.save()

    def save(self):
        self.state["updated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        self.state["remaining_seconds"] = max(0, self.end-time.monotonic())
        self.state["elapsed_seconds"] = self.elapsed_before + max(0, time.monotonic()-self.clock_start)
        atomic_json(self.state_path, self.state)

    def phase_end(self, name):
        order = ("preflight", "search", "validation", "test", "finalize")
        fraction = sum(self.plan["phase_fractions"][p] for p in order[:order.index(name)+1])
        return self.start + self.plan["hours"]*3600*fraction

    def report(self, final=False):
        self.save()
        result = export(self.run, self.plan, self.state, self.store.rows(), final=final)
        self.last_report = time.monotonic()
        print(f"{self.state['updated_utc']} phase={self.state['phase']} "
              f"jobs={len(self.store.rows())} remaining={self.state['remaining_seconds']/3600:.2f}h", flush=True)
        return result

    def pack_job(self, label, source, validate=False):
        identity = digest([self.plan["plan_hash"], "pack", label, tree_hash(source), validate])[:24]
        target = self.run / "packed" / (label + ("-checked" if validate else ""))
        return dict(id=identity, kind="pack", plan_hash=self.plan["plan_hash"],
                    source=str(source), label=label, target=str(target), validate=validate,
                    arena=str(self.run / "source/arena"), timeout=180.0, cost=1)

    def payload(self, label, source):
        for checked in (True, False):
            result = self.store.get(self.pack_job(label, source, checked)["id"])
            if result and result.get("ok") and Path(result["payload"]).is_file():
                return str(Path(result["payload"]).parent)
        raise RuntimeError(f"No usable packed payload for {label}")

    def execute(self, job, boundary):
        job = dict(job)
        directory = self.run / "jobs" / job["id"]
        attempt = directory / f"attempt-{time.time_ns()}"
        attempt.mkdir(parents=True, exist_ok=True)
        job["job_dir"] = str(attempt)
        timeout = max(0, min(job["timeout"], boundary-time.monotonic()))
        administrative_timeout = timeout < job["timeout"]
        job["timeout"] = timeout
        atomic_json(directory / "job.json", job)
        result_file = directory / "result.json"
        process = run_process([sys.executable, "-m", "tools.tune.worker", "--job", str(directory / "job.json"),
                               "--result", str(result_file)], cwd=self.run / "source/repo",
                              timeout=timeout, log=attempt / "worker.log", stop_event=self.stop)
        if result_file.exists():
            result = read_json(result_file)
            if result.get("id") != job["id"] or result.get("plan_hash") != self.plan["plan_hash"]:
                raise RuntimeError("Worker returned a mismatched job identity")
            result["censored"] = administrative_timeout and result.get("result", {}).get("status") == "incomplete"
            atomic_json(result_file, result)
            return result
        result = {**job, "ok": False, "error": "timeout/cancel" if process["timeout"] else
                  f"worker exited {process['returncode']} without an atomic result", "process": process,
                  "censored": (administrative_timeout or self.stop.is_set()) and process["timeout"]}
        atomic_json(result_file, result)
        return result

    def batch(self, jobs, boundary):
        pending = [j for j in jobs if not self.store.get(j["id"])]
        # Start expensive pairings early; short shove/fold matches fill spare tokens and reduce idle tails.
        priority = {"equity": 4, "main_reference": 4, "combined_reference": 4,
                    "station": 3, "minraise": 3, "starter": 2}
        pending.sort(key=lambda j: (j["cost"], priority.get(j.get("family"), 1)), reverse=True)
        with cf.ThreadPoolExecutor(max_workers=self.budget) as pool:
            active, used = {}, 0
            try:
                while pending or active:
                    ensure_disk(self.run)
                    while pending and not self.stop.is_set() and boundary-time.monotonic() > 20:
                        index = next((i for i, j in enumerate(pending)
                                      if min(j["cost"], self.budget)+used <= self.budget), None)
                        if index is None:
                            break
                        job = pending.pop(index)
                        cost = min(job["cost"], self.budget)
                        future = pool.submit(self.execute, job, boundary)
                        active[future] = cost
                        used += cost
                    if not active:
                        break
                    done, _ = cf.wait(active, timeout=1, return_when=cf.FIRST_COMPLETED)
                    for future in done:
                        used -= active.pop(future)
                        self.store.add(future.result())
                    if time.monotonic()-self.last_report > 300:
                        self.report()
            except BaseException:
                self.stop.set()
                raise
        self.save()
        return all(self.store.get(j["id"]) is not None for j in jobs)

    def match_jobs(self, identities, phase, block, *, deals=None):
        field = self.plan["fields"]["test" if phase.startswith("stress") else phase]
        jobs = []
        for family, profiles in field.items():
            profile = profiles[block % len(profiles)]
            opponent = self.payload(profile["id"], self.run / "opponents" / profile["id"])
            for identity in dict.fromkeys(["baseline", *identities]):
                source = self.run / "candidates" / identity
                pair_seed = seed_for(self.plan["seed"], phase, block)
                count = deals or self.plan["deals"]
                job_id = digest([self.plan["plan_hash"], phase, block, family, profile["id"], identity, count])[:24]
                jobs.append(dict(id=job_id, kind="match", plan_hash=self.plan["plan_hash"], phase=phase,
                                 block=block, family=family, opponent=profile["id"], candidate=identity,
                                 a=self.payload(identity, source), b=opponent, seed=pair_seed, deals=count,
                                 arena=str(self.run / "source/arena"), timeout=300.0, cost=profile["cpu_cost"]))
        return jobs

    def preflight(self):
        jobs = [self.pack_job(identity, self.run / "candidates" / identity, True)
                for identity in self.state["candidates"]]
        for phase in self.plan["fields"].values():
            for profiles in phase.values():
                jobs += [self.pack_job(p["id"], self.run / "opponents" / p["id"], True) for p in profiles]
        if not self.batch(jobs, self.phase_end("preflight")):
            raise RuntimeError("Packing did not finish in preflight budget; no valid experiment started")
        failed = [j["label"] for j in jobs if not self.store.get(j["id"]).get("ok")]
        if failed:
            raise RuntimeError("Packing/preflight failed: " + ", ".join(failed))
        self.state["phase"] = "search"
        self.save()

    def rankings(self, phase, identities, *, adjusted=False):
        rows = self.store.rows()
        families = list(self.plan["fields"][phase])
        alpha = 0.05 / max(1, len(identities)) if adjusted else 0.10
        values = [summarize(rows, i, phase, families, alpha=alpha) for i in identities if i != "baseline"]
        def key(value):
            ci = value["paired"]
            if value["failures"] or value["reference_failures"] or ci["n"] < 2:
                return -1e9
            worst = value["worst_family_delta"] or 0
            # Regularize specialization: prefer lower bound and penalize a deeply losing family.
            return ci["low"] - max(0, -0.10-worst)
        return sorted(values, key=key, reverse=True)

    def search(self):
        boundary = self.phase_end("search")
        while time.monotonic() < boundary-20 and not self.stop.is_set():
            block = self.state["search_block"]
            if not self.batch(self.match_jobs(self.state["active"], "search", block), boundary):
                break
            self.state["search_block"] += 1
            self.state["phase_round"] += 1
            ranked = self.rankings("search", self.state["active"])
            if self.state["phase_round"] % 2 == 0 and len(self.state["active"]) > 9:
                self.state["active"] = list(dict.fromkeys(self.state["protected"] + [
                    s["candidate"] for s in ranked[:max(4, len(ranked)//2)]]))
            # Propose new settings only from search data, with smoothed cross-entropy marginals.
            if self.state["phase_round"] % 8 == 0 and len(self.state["candidates"]) < 96 and boundary-time.monotonic() > 600:
                all_ranked = self.rankings("search", list(self.state["candidates"]))
                elites = [self.state["candidates"][s["candidate"]]["config"] for s in all_ranked[:4]
                          if s["paired"]["n"] >= 2 and not s["failures"]]
                proposals = offspring(elites, 8, seed_for(self.plan["seed"], "proposal", self.state["generation"]),
                                      set(self.state["candidates"]))
                for item in proposals:
                    folder = build_candidate(self.run, item)
                    item["artifact_hash"] = tree_hash(folder)
                    self.state["candidates"][item["id"]] = item
                jobs = [self.pack_job(item["id"], self.run / "candidates" / item["id"], True) for item in proposals]
                self.batch(jobs, boundary)
                usable = [p["id"] for p, j in zip(proposals, jobs) if self.store.get(j["id"]) and self.store.get(j["id"])["ok"]]
                self.state["active"] = list(dict.fromkeys(self.state["protected"] + [
                    s["candidate"] for s in all_ranked[:6]] + usable))
                self.state["generation"] += 1
            self.save()
        if self.stop.is_set():
            self.save()
            return
        ranked = self.rankings("search", list(self.state["candidates"]))
        self.state["validation_candidates"] = [s["candidate"] for s in ranked
                                               if s["paired"]["n"] >= 2 and not s["failures"]
                                               and not s["reference_failures"]][:3]
        self.state["phase"] = "validation"
        self.report()

    def validation(self):
        boundary = self.phase_end("validation")
        identities = self.state["validation_candidates"]
        while time.monotonic() < boundary-20 and not self.stop.is_set():
            block = self.state["validation_block"]
            if not self.batch(self.match_jobs(identities, "validation", block), boundary):
                break
            self.state["validation_block"] += 1
            self.save()
        if self.stop.is_set():
            self.save()
            return
        ranked = self.rankings("validation", identities, adjusted=True)
        self.state["validation_adjusted_intervals"] = ranked
        eligible = [s for s in ranked if s["paired"]["n"] >= self.plan["min_validation_blocks"]
                    and not s["failures"] and not s["reference_failures"]
                    and s["paired"]["mean"] >= self.plan["practical_delta"]
                    and not any(v["high"] is not None and v["high"] < -self.plan["max_family_regression"]
                                for v in s["family"].values())]
        self.state["selected"] = eligible[0]["candidate"] if eligible else "baseline"
        self.state["selection_locked_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        self.state["selection_hash"] = digest([self.plan["plan_hash"], self.state["selected"],
                                                self.state["validation_adjusted_intervals"]])
        # Lock persists BEFORE any test game. The test cannot change candidate or parameters.
        self.state["phase"] = "test"
        self.state["selection_pack_validated"] = False
        self.save()
        self.report()

    def test(self):
        expected = digest([self.plan["plan_hash"], self.state["selected"], self.state["validation_adjusted_intervals"]])
        if expected != self.state["selection_hash"]:
            raise RuntimeError("Finalist lock changed; test must not be used for reselection")
        boundary = self.phase_end("test")
        if not self.state.get("selection_pack_validated"):
            checked = self.pack_job(self.state["selected"], self.run / "candidates" / self.state["selected"], True)
            self.batch([checked], min(boundary, time.monotonic()+180))
            if not self.store.get(checked["id"]) or not self.store.get(checked["id"])["ok"]:
                raise RuntimeError("Locked finalist failed fresh-process packed validation")
            self.state["selection_pack_validated"] = True
            self.save()
        while time.monotonic() < boundary-20 and not self.stop.is_set():
            block = self.state["test_block"]
            if not self.batch(self.match_jobs([self.state["selected"]], "test", block), boundary):
                break
            self.state["test_block"] += 1
            self.save()
        if not self.stop.is_set():
            self.state["phase"] = "complete"

    def run_all(self):
        try:
            if self.state["phase"] == "preflight":
                self.preflight()
            if self.state["phase"] == "search" and not self.stop.is_set():
                self.search()
            if self.state["phase"] == "validation" and not self.stop.is_set():
                self.validation()
            if self.state["phase"] == "test" and not self.stop.is_set():
                self.test()
        except BaseException as exc:
            self.state["last_error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.state["source_integrity"] = tree_hash(self.run / "source") == self.plan["source_hash"]
            for path, fingerprint in self.plan["artifact_hashes"].items():
                self.state["source_integrity"] &= tree_hash(self.run / path) == fingerprint
            for identity, item in self.state["candidates"].items():
                if "artifact_hash" in item:
                    self.state["source_integrity"] &= tree_hash(self.run / "candidates" / identity) == item["artifact_hash"]
            self.state["interrupted"] = self.stop.is_set()
            try:
                self.report(final=self.state["phase"] == "complete")
            finally:
                self.store.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="freeze code, rules, variants; NEVER plays any games")
    prep.add_argument("--arena-root", type=Path, required=True)
    prep.add_argument("--run-dir", type=Path, required=True)
    prep.add_argument("--preflop-dir", type=Path)
    prep.add_argument("--preflop-ref", default="origin/lembzg/11-preflop-arena")
    prep.add_argument("--candidates", type=int, default=32)
    prep.add_argument("--seed", type=int, default=20261107)
    prep.add_argument("--hours", type=float, default=8)
    prep.add_argument("--rules-file", type=Path)
    for name in ("plan", "run", "report"):
        command = sub.add_parser(name)
        command.add_argument("--run-dir", type=Path, required=True)
        if name == "run":
            command.add_argument("--start", action="store_true", help="explicitly authorize starting/resuming games")
            command.add_argument("--workers", type=int, help="CPU-token ceiling; default all logical cores minus one")
            command.add_argument("--frozen", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    run = args.run_dir.resolve()
    if args.command == "prepare":
        python_guard()
        value = prepare(Path(__file__).resolve().parents[2], args.arena_root, run,
                        preflop_dir=args.preflop_dir, preflop_ref=args.preflop_ref,
                        count=args.candidates, seed=args.seed, hours=args.hours, rules_file=args.rules_file)
        print(value["message"])
        print(f"Frozen {len(value['candidates'])} candidates; plan {value['plan_hash']}; run directory {run}")
        return 0
    plan = load_plan(run, verify=args.command != "report")
    if args.command == "plan":
        print(f"PREPARED, not started: {plan['hours']}h, {len(plan['candidates'])} initial candidates, "
              f"{plan['deals']} duplicate deals/match; CPU tokens {cpu_budget()}.")
        print("Search 8 families; shifted validation profiles; final test 14 families including six unseen styles/controls.")
        return 0
    if args.command == "report":
        with run_lock(run):
            store = Store(run)
            store.recover(plan["plan_hash"])
            state = read_json(run / "state.json") if (run / "state.json").exists() else {
                "phase": "not_started", "candidates": {c["id"]: c for c in plan["candidates"]}}
            export(run, plan, state, store.rows(), final=state["phase"] == "complete")
            store.close()
        print(run / "reports/MORNING_REPORT.md")
        return 0
    if not args.start:
        parser.error("No games started. run requires --start; preparation/plan are safe before bedtime.")
    python_guard()
    if not args.frozen:
        command = [sys.executable, "-m", "tools.tune.overnight", "run", "--run-dir", str(run), "--start", "--frozen"]
        if args.workers:
            command += ["--workers", str(args.workers)]
        # Replace this process, keeping the lock owner unambiguous on resume.
        os.chdir(run / "source/repo")
        os.execvpe(sys.executable, command, {**os.environ, "PYTHONPATH": ""})
    with run_lock(run):
        runner = Runner(run, plan, args.workers)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: runner.stop.set())
        runner.run_all()
    print(f"Finished. No parameters applied. Read {run / 'reports/MORNING_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
