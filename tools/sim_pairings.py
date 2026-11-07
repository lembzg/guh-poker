"""Tournament-length evaluation: many separate short matches, pooled.

A long `arena match` overstates the exploit layer, because a bot's memory lasts
one half and in the tournament a half is about 100 hands. This plays many
independent matches at the real length and pools them. Run it from a checkout
of poker_bot_infrastructure, with this file's path:

    python /path/to/tools/sim_pairings.py bots/myteam call fold random shove \
        bots/starter --matches 100 --deals 100

Scoring uses the same play_pairing as the arena, so per-match results are
duplicate-deal means. The CI comes from the spread between matches.
"""

from __future__ import annotations

import argparse
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from arena.duel import PairingConfig, play_pairing  # noqa: E402
from arena.specs import contestant_from_spec  # noqa: E402


def one_match(job: tuple[str, str, int, int]) -> tuple[float, int, int, float]:
    bot, opponent, deals, seed = job
    first = contestant_from_spec(bot, name="a")
    second = contestant_from_spec(opponent, name="b")
    result = play_pairing(first, second, PairingConfig(deals=deals, seed=seed))
    return result.mean_bb, result.faults_a, result.faults_b, result.think_a


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bot")
    parser.add_argument("opponents", nargs="+")
    parser.add_argument("--matches", type=int, default=100)
    parser.add_argument("--deals", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    with ProcessPoolExecutor(args.workers) as pool:
        for opponent in args.opponents:
            jobs = [
                (args.bot, opponent, args.deals, args.seed + index)
                for index in range(args.matches)
            ]
            rows = list(pool.map(one_match, jobs))
            means = [row[0] for row in rows]
            mean = sum(means) / len(means)
            variance = sum((m - mean) ** 2 for m in means) / (len(means) - 1)
            ci = 1.96 * math.sqrt(variance / len(means))
            wins = sum(1 for m in means if m > 0)
            faults = sum(row[1] for row in rows)
            think = max(row[3] for row in rows)
            print(
                f"{opponent:28} {mean:+7.3f} bb/hand  CI95 "
                f"{mean - ci:+7.3f} .. {mean + ci:+7.3f}  "
                f"match wins {wins:3d}/{len(means)}  faults {faults}  "
                f"max think {think:.2f}s"
            )


if __name__ == "__main__":
    main()
