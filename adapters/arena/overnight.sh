#!/usr/bin/env bash
# Overnight confirmation runs for the combined entry in the organisers' engine.
#   ARENA_ROOT=/path/to/poker_bot_infrastructure adapters/arena/overnight.sh [seeds] [deals]
# Builds the candidate (lembzg #32 preflop + MainBot postflop) and arena versions of our test opponents,
# then runs `python -m adapters.arena.gauntlet` once per seed (fresh deals each time). Output: results/arena/
# overnight/summary.txt (tables) and results/arena_gauntlet/<date>.jsonl (every match). Keeps the Mac awake.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${ARENA_ROOT:?set ARENA_ROOT to a clone of Manchester-AI-Society/poker_bot_infrastructure with its venv}"
SEEDS="${1:-$(seq 101 120)}"
DEALS="${2:-2000}"
PY="${PYTHON:-.venv/bin/python}"
OUT=results/arena/overnight
mkdir -p "$OUT"
"$PY" -m adapters.arena.build --team cand --strategy combo --preflop-dir bots/myteam --out "$OUT/cand"
for o in hackathon equity_bot three_bet_any jam_postflop min_raiser; do
  "$PY" -m adapters.arena.build --team "o-${o//_/-}" --bot "$o" --out "$OUT/opp_$o" >/dev/null
done
AWAKE=()
command -v caffeinate >/dev/null && AWAKE=(caffeinate -i)
for s in $SEEDS; do
  echo "=== seed $s, $DEALS deals ($(date))" | tee -a "$OUT/summary.txt"
  "${AWAKE[@]}" "$PY" -m adapters.arena.gauntlet "$OUT/cand" --pool bots/myteam "$OUT"/opp_* \
    --deals "$DEALS" --seed "$s" | tee -a "$OUT/summary.txt"
done
"$PY" - <<'PY'
import json, glob, collections, math
rows = [json.loads(l) for f in glob.glob("results/arena_gauntlet/*.jsonl") for l in open(f)
        if '"overnight/cand"' in l or "/overnight/cand" in l]
by = collections.defaultdict(list)
for r in rows:
    if r.get("bb_per_hand") is not None:
        by[r["opponent"].rsplit("/", 1)[-1]].append(r["bb_per_hand"])
print("\nAcross all seeds (mean bb/hand, ~95% CI of the mean, runs):")
for k, v in sorted(by.items()):
    m = sum(v) / len(v)
    sd = (sum((x - m) ** 2 for x in v) / (len(v) - 1)) ** 0.5 if len(v) > 1 else float("nan")
    print(f"  {k:22s} {m:+.3f}  ± {1.96 * sd / math.sqrt(len(v)):.3f}  (n={len(v)})")
PY
