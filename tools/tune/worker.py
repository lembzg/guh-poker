"""One isolated pack/check or pairing job. Only invoked by an explicitly started run."""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

from .common import RULES, atomic_json, canonical, read_json

LATENCY_BINS_MS = (0.25, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 400, 700, 1000, 2000, 10000)


def pairing(job):
    # Arena is imported only inside a started worker, never at preparation/import time.
    from arena.duel import PairingConfig, play_pairing
    from arena.specs import contestant_from_spec
    directory = Path(job["job_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    a = contestant_from_spec(job["a"], name="candidate", log_dir=directory,
                            move_timeout=RULES["move_timeout"], max_faults=RULES["max_faults"])
    b = contestant_from_spec(job["b"], name="opponent", log_dir=directory,
                            move_timeout=RULES["move_timeout"], max_faults=RULES["max_faults"])
    latency = {"count": 0, "sum_ms": 0.0, "max_ms": 0.0, "hist": [0]*(len(LATENCY_BINS_MS)+1)}
    actions = collections.Counter()
    halves = []
    decide, new_stretch = a.decide, a.new_stretch
    def measured(state, hero_index, action_history):
        started = time.perf_counter()
        response = decide(state, hero_index, action_history)
        elapsed = (time.perf_counter()-started)*1000
        latency["count"] += 1
        latency["sum_ms"] += elapsed
        latency["max_ms"] = max(latency["max_ms"], elapsed)
        index = next((i for i, limit in enumerate(LATENCY_BINS_MS) if elapsed <= limit), len(LATENCY_BINS_MS))
        latency["hist"][index] += 1
        actions[f"{state.get('street', 'unknown')}:{response.action}"] += 1
        return response
    def stretch(budget):
        if a.decisions:
            halves.append(a._stretch_think)
        return new_stretch(budget)
    a.decide, a.new_stretch = measured, stretch
    counts = collections.Counter()
    positions = {name: {"hands": 0, "net_bb": 0.0} for name in ("button", "big_blind")}
    worst = []
    with gzip.open(directory / "hands.jsonl.gz", "wt", encoding="utf-8") as hands:
        def sink(record):
            # Evaluator-only audit data. Never forwarded to any bot or used to select actions.
            hands.write(canonical(record)+"\n")
            net = record["net"][record["orientation"]] / RULES["big_blind"]
            position = "button" if record["orientation"] == record["dealer_seat"] else "big_blind"
            positions[position]["hands"] += 1
            positions[position]["net_bb"] += net
            counts["won" if net>0 else "lost" if net<0 else "tied"] += 1
            counts[record["ended_by"]] += 1
            worst.append({"bb": net, "deal": record["deal"], "orientation": record["orientation"]})
            worst.sort(key=lambda r: r["bb"])
            del worst[10:]
        result = play_pairing(a, b, PairingConfig(
            deals=job["deals"], seed=job["seed"], stack=RULES["stack"],
            small_blind=RULES["small_blind"], big_blind=RULES["big_blind"],
            think_budget_per_deal=RULES["think_budget_per_deal"],
            time_cap_seconds=job["timeout"]-5), hand_sink=sink)
    halves.append(a._stretch_think)
    summaries = {}
    entry_errors = 0
    if (directory / "candidate.log").exists():
        with (directory / "candidate.log").open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                entry_errors += "act() failed, playing safe:" in line or "record_own() failed:" in line
                if "OVERNIGHT_METRICS " in line:
                    try:
                        packet = json.loads(line.split("OVERNIGHT_METRICS ", 1)[1])
                        summaries[str(packet["seat"])] = packet
                    except (ValueError, KeyError):
                        continue
    return {"ok": True, "result": result.to_dict(), "latency": latency,
            "actions": dict(actions), "hand_counts": dict(counts), "worst_hands": worst,
            "positions": positions, "bot_metrics": summaries,
            "entry_errors": entry_errors,
            "telemetry_complete": (set(summaries) == {"0", "1"}
                and all(p.get("final") is True for p in summaries.values())
                and sum(p.get("decisions", -1) for p in summaries.values()) == latency["count"]),
            "bank_fraction_max": max(halves, default=0)/(job["deals"]*RULES["think_budget_per_deal"])}


def pack(job):
    from arena.package import pack as arena_pack, unpack
    from arena.pickling import read_submission
    folder, target = Path(job["source"]), Path(job["target"])
    result = arena_pack(folder, job["label"], target.parent,
                        validate=job.get("validate", False))
    if result.bytes > RULES["max_pickle_bytes"]:
        raise RuntimeError("Packed candidate exceeds the official size limit")
    read_submission(result.path)
    payload = target / "bot.pkl"
    unpack(result.path, target)
    return {"ok": True, "payload": str(payload), "bytes": result.bytes, "digest": result.digest}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    args = parser.parse_args(argv)
    job = read_json(args.job)
    if hasattr(os, "sched_getaffinity"):
        available = sorted(os.sched_getaffinity(0))
        if len(available) > 1:
            # Inherited by arena bot children; leave one logical CPU outside the worker pool.
            os.sched_setaffinity(0, available[:-1])
    # The worker's frozen runner and arena have explicit paths; no user checkout imports.
    runner_root = str(Path(__file__).resolve().parents[2])
    sys.path[:] = [p for p in sys.path if p and str(Path(p).resolve()) != runner_root]
    sys.path.insert(0, job["arena"])
    try:
        response = pack(job) if job["kind"] == "pack" else pairing(job)
    except Exception:
        response = {"ok": False, "error": traceback.format_exc(limit=12)}
    # No NaN/Infinity in the journal or CSV JSON cells.
    def clean(value):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    atomic_json(args.result, clean({**job, **response}))
    return 0 if response["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
