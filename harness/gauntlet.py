"""Gauntlet (#22): one bot against every harness opponent, duplicate deals.

CLI:  python -m harness.gauntlet --a <bot> [--hands 4000] [--seed 1] [--stack 200 --bb 2]
                                 [--a-cfg k=v ...] [--only name ...] [--no-save]
Prints a table (bb/100 ± 95% CI, latency, illegal/errors) and appends each match to results/<date>.jsonl.
Use `run_gauntlet(...)` from scripts and tests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from typing import Callable

from harness.match import _REPO, make_bot, play_match
from harness.opponents import OPPONENTS
from harness.run import _cfg


def run_gauntlet(bot: str | Callable[[], object], hands: int = 4000, seed: int = 1,
                 opponents: list[str] | None = None, stack: int = 200, bb: int = 2, **cfg) -> list[dict]:
    """Play a fresh instance of `bot` (a registry name, or a zero-argument factory) against each opponent."""
    names = opponents or list(OPPONENTS)
    results = []
    for opp in names:
        a = make_bot(bot, **cfg) if isinstance(bot, str) else bot()
        if isinstance(bot, str):
            try:
                a.name = bot
            except Exception:
                pass
        res = play_match(a, opp, hands, seed, duplicate=True, stack=stack, bb=bb)
        res["bot_b"] = f"{opp}@{res['bot_b'].split('@', 1)[1]}"
        results.append(res)
    return results


def format_table(results: list[dict]) -> str:
    lines = [f"{'opponent':18s} {'bb/100':>9s} {'± ci95':>8s} {'ms avg':>7s} {'ms max':>7s} {'illegal':>7s} {'errors':>6s}"]
    for r in results:
        ci = r["ci95"] if r["ci95"] is not None else float("nan")
        sig = "*" if r["ci95"] is not None and abs(r["bb_per_100"]) > r["ci95"] else " "
        lines.append(f"{r['bot_b'].split('@')[0]:18s} {r['bb_per_100']:9.1f} {ci:8.1f}{sig}{r['a_ms_avg']:6.2f} "
                     f"{r['a_ms_max']:7.0f} {r['illegal_a']:7d} {r['errors_a']:6d}")
    worst = min(results, key=lambda r: r["bb_per_100"])
    mean = sum(r["bb_per_100"] for r in results) / len(results)
    lines.append(f"mean {mean:.1f} bb/100; worst {worst['bot_b'].split('@')[0]} {worst['bb_per_100']:.1f}  "
                 f"(* = CI excludes 0; {results[0]['hands']} hands each, seed {results[0]['seed']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(prog="python -m harness.gauntlet", description=__doc__.splitlines()[0])
    ap.add_argument("--a", required=True)
    ap.add_argument("--hands", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--stack", type=int, default=200)
    ap.add_argument("--bb", type=int, default=2)
    ap.add_argument("--a-cfg", nargs="*", default=[], metavar="K=V")
    ap.add_argument("--only", nargs="*", default=None, metavar="NAME", help=f"subset of {sorted(OPPONENTS)}")
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args(argv)
    unknown = set(args.only or []) - set(OPPONENTS)
    if unknown:
        raise SystemExit(f"unknown opponents {sorted(unknown)}; choose from {sorted(OPPONENTS)}")
    results = run_gauntlet(args.a, args.hands, args.seed, args.only, args.stack, args.bb, **_cfg(args.a_cfg))
    if not args.no_save:
        out = _REPO / "results" / f"{dt.date.today().isoformat()}.jsonl"
        out.parent.mkdir(exist_ok=True)
        with out.open("a") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")
    print(format_table(results))
    return results


if __name__ == "__main__":
    main()
