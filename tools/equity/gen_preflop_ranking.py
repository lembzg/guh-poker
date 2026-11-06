"""Generate core/data/preflop_ranking.json: the 169 hand classes ranked by equity vs a random hand.

Usage (from the repo root):  python -m tools.equity.gen_preflop_ranking [--samples 200000] [--seed 1]
"""
from __future__ import annotations

import argparse
import json

from core.equity import _PREFLOP_RANKING, RANKS, equity


def classes() -> list[str]:
    out = []
    for i, hi in enumerate(reversed(RANKS)):
        for lo in reversed(RANKS[: len(RANKS) - i]):
            if hi == lo:
                out.append(hi + lo)
            else:
                out += [hi + lo + "s", hi + lo + "o"]
    return out


def representative(cls: str) -> tuple[str, str]:
    return (cls[0] + "s", cls[1] + ("s" if cls.endswith("s") else "h"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=200_000)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rows = [[c, round(equity(representative(c), (), samples=args.samples, seed=args.seed), 4)] for c in classes()]
    assert len(rows) == 169
    rows.sort(key=lambda r: -r[1])
    _PREFLOP_RANKING.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_by": "python -m tools.equity.gen_preflop_ranking", "samples": args.samples,
               "seed": args.seed, "metric": "equity vs a uniformly random hand", "ranking": rows}
    _PREFLOP_RANKING.write_text(json.dumps(payload, indent=0) + "\n")
    print(f"wrote {_PREFLOP_RANKING} ({len(rows)} classes); top 5: {rows[:5]}")


if __name__ == "__main__":
    main()
