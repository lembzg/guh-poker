"""Arena gauntlet (#37): play one bot folder against a pool, in the organisers' real engine, in parallel.

    python -m adapters.arena.gauntlet <bot-folder> [--pool FOLDER ...] [--no-builtins]
                                      [--deals 1000] [--seed 11] [--workers 6] [--arena-root PATH]

The pool is the organisers' built-ins (call, random, shove, fold) and their bots/starter, plus any extra bot
folders (ours from `python -m adapters.arena.build`, e.g. `--bot jam_postflop`, or lembzg's bots/myteam).
Every match uses the same --seed, so candidates are compared on identical deals.
The organisers' repo (Manchester-AI-Society/poker_bot_infrastructure) comes from --arena-root or $ARENA_ROOT;
its venv python (<root>/venv/bin/python) is used when present. Results are appended to
results/arena_gauntlet/<date>.jsonl.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILTINS = ["call", "random", "shove", "fold"]

_SCORE = re.compile(r"([+-]?\d+(?:\.\d+)?) bb/hand \(95% CI ([+-]?\d+(?:\.\d+)?) \.\. ([+-]?\d+(?:\.\d+)?)\)")
_FAULTS = re.compile(r"faults: [^=]+=(\d+), [^=]+=(\d+)")
_THINK = re.compile(r"think time: [^=]+=([\d.]+)s")
_STATUS = re.compile(r"status: (\w+)")


def parse_match(output: str) -> dict:
    """Pull the headline numbers out of `python -m arena match` output (A's point of view)."""
    out: dict = {"bb_per_hand": None, "ci_low": None, "ci_high": None, "faults_a": None, "faults_b": None,
                 "think_a_s": None, "status": None}
    m = _SCORE.search(output)
    if m:
        out["bb_per_hand"], out["ci_low"], out["ci_high"] = (float(x) for x in m.groups())
    m = _FAULTS.search(output)
    if m:
        out["faults_a"], out["faults_b"] = int(m.group(1)), int(m.group(2))
    m = _THINK.search(output)
    if m:
        out["think_a_s"] = float(m.group(1))
    m = _STATUS.search(output)
    if m:
        out["status"] = m.group(1)
    return out


def _arena_python(root: Path) -> str:
    venv = root / "venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def run_match(root: Path, bot: Path, opponent: str, deals: int, seed: int, timeout_s: float) -> dict:
    cmd = [_arena_python(root), "-m", "arena", "match", str(bot), opponent, "--deals", str(deals),
           "--seed", str(seed)]
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=timeout_s)
        text = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        text = "status: timeout"
    res = parse_match(text)
    res.update({"bot": str(bot), "opponent": opponent, "deals": deals, "seed": seed})
    if res["bb_per_hand"] is None:
        res["error"] = text.strip().splitlines()[-1][:300] if text.strip() else "no output"
    return res


def label(opponent: str) -> str:
    return Path(opponent).name if ("/" in opponent or os.sep in opponent) else opponent


def format_table(results: list[dict]) -> str:
    lines = [f"{'opponent':22s} {'bb/hand':>8s}  {'95% CI':>17s}  {'faults':>6s} {'think s':>7s}"]
    for r in results:
        if r["bb_per_hand"] is None:
            lines.append(f"{label(r['opponent']):22s}  ERROR: {r.get('error', '?')}")
            continue
        clear = "*" if r["ci_low"] > 0 or r["ci_high"] < 0 else " "
        lines.append(f"{label(r['opponent']):22s} {r['bb_per_hand']:+8.3f}  "
                     f"[{r['ci_low']:+7.3f} {r['ci_high']:+7.3f}]{clear} {r['faults_a'] or 0:6d} "
                     f"{(r['think_a_s'] or 0):7.1f}")
    ok = [r for r in results if r["bb_per_hand"] is not None]
    if ok:
        worst = min(ok, key=lambda r: r["bb_per_hand"])
        lines.append(f"mean {sum(r['bb_per_hand'] for r in ok) / len(ok):+.3f} bb/hand; worst "
                     f"{label(worst['opponent'])} {worst['bb_per_hand']:+.3f}  (* = CI excludes 0; "
                     f"{ok[0]['deals']} deals x2 each, seed {ok[0]['seed']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(prog="python -m adapters.arena.gauntlet", description=__doc__.splitlines()[0])
    ap.add_argument("bot", type=Path, help="bot folder (contains bot.py)")
    ap.add_argument("--pool", nargs="*", default=[], type=Path, help="extra opponent bot folders")
    ap.add_argument("--no-builtins", action="store_true", help="skip call/random/shove/fold/starter")
    ap.add_argument("--deals", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--timeout", type=float, default=1800.0, help="seconds per match")
    ap.add_argument("--arena-root", type=Path, default=os.environ.get("ARENA_ROOT"))
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    if not args.arena_root or not (Path(args.arena_root) / "arena").is_dir():
        raise SystemExit("set --arena-root or ARENA_ROOT to a clone of Manchester-AI-Society/poker_bot_infrastructure")
    root = Path(args.arena_root).resolve()
    bot = args.bot.resolve()
    if not (bot / "bot.py").is_file():
        raise SystemExit(f"{bot} has no bot.py (build one with python -m adapters.arena.build)")
    opponents = [] if args.no_builtins else BUILTINS + ["bots/starter"]
    opponents += [str(p.resolve()) for p in args.pool]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(lambda o: run_match(root, bot, o, args.deals, args.seed, args.timeout), opponents))
    if not args.no_save:
        out = REPO / "results" / "arena_gauntlet" / f"{dt.date.today().isoformat()}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
    print(f"{bot.name} vs {len(opponents)} opponents (organisers' engine)")
    print(format_table(results))
    return results


if __name__ == "__main__":
    main()
