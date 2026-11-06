"""CLI (#6): python -m harness.run --a <bot> --b <bot> --hands N --seed S [--duplicate] [--stack 200 --bb 2]
[--a-cfg k=v ...] [--b-cfg k=v ...] [--carry-stacks]

Prints one JSON summary line and appends it to results/<date>.jsonl (gitignored)."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from harness.match import _REPO, make_bot, play_match


def _cfg(pairs: list[str]) -> dict:
    out = {}
    for pair in pairs or []:
        k, sep, v = pair.partition("=")
        if not sep:
            raise SystemExit(f"bad cfg {pair!r}; expected k=v")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(prog="python -m harness.run", description=__doc__.splitlines()[0])
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--hands", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--duplicate", action="store_true")
    ap.add_argument("--stack", type=int, default=200, help="starting stack in chips")
    ap.add_argument("--bb", type=int, default=2, help="big blind in chips (small blind = bb // 2)")
    ap.add_argument("--a-cfg", nargs="*", default=[], metavar="K=V")
    ap.add_argument("--b-cfg", nargs="*", default=[], metavar="K=V")
    ap.add_argument("--carry-stacks", action="store_true", help="don't reset stacks each hand")
    ap.add_argument("--no-save", action="store_true", help="don't append to results/")
    args = ap.parse_args(argv)

    bot_a = make_bot(args.a, **_cfg(args.a_cfg))
    bot_b = make_bot(args.b, **_cfg(args.b_cfg))
    for bot, name in ((bot_a, args.a), (bot_b, args.b)):
        try:
            bot.name = name
        except Exception:
            pass
    res = play_match(bot_a, bot_b, args.hands, args.seed, args.duplicate, args.stack, args.bb,
                     reset_stacks=not args.carry_stacks)
    line = json.dumps(res)
    if not args.no_save:
        out = _REPO / "results" / f"{dt.date.today().isoformat()}.jsonl"
        out.parent.mkdir(exist_ok=True)
        with out.open("a") as f:
            f.write(line + "\n")
    print(line)
    return res


if __name__ == "__main__":
    main()
