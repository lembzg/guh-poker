# Product: heads-up NLHE tournament bot

## Goal
Win a heads-up no-limit hold'em bot-vs-bot tournament with our own bot (D-005). It plays solid default poker, exploits whatever the opposing bots do wrong, and never acts illegally or times out.

## Tournament rules
_Paste the organisers' rules **verbatim** here as soon as we get them. Do the analysis in `docs/ENVIRONMENT.md`._

Fill in every row. Each one changes how we tune the bot:

| Question | Answer | Source |
|---|---|---|
| Format: number of hands per match, round-robin or knockout, stacks reset each hand? | One round, **round robin** of heads-up matches. Each pairing = N deals played twice with seats swapped (duplicate); default **200 deals** (`arena/duel.py PairingConfig`, `tournament_cli --deals 200`). Stacks **reset every hand**. Bot is restarted for each half. | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| Blinds, starting stack (in big blinds), antes | Blinds **10/20**, stacks **2000** (100bb), no antes | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| Bet sizing: any amount, or a fixed set? Minimum raise rule? | Any integer total in [`min_raise_to`, `max_raise_to`]; amounts are **totals for the current betting round** (street), not the hand. `max_raise_to` = all-in. Min-raise tracked in `game/action_engine.py` | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| Time limit per action / per hand / per match; what happens on time-out | **1 second per move**, plus a thinking bank of **0.2 s × deals per half** (e.g. 40 s for 200 deals); overdrawing the bank disables the bot for that match (always-fold stub). A timeout is a fault. (Supersedes the earlier "3 minutes per decision" relay.) | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| What happens on an illegal action or a crash | Fault: a safe default is played (check, otherwise fold). **After 20 faults the bot is replaced by an always-fold stub for that match.** | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| Interface: protocol, language, how the bot is submitted/hosted | **Python 3.14.** One `bot.py` with exactly one `PokerBot` subclass (no constructor args); `act(game_state) -> Response` (`fold()`, `call()`, `raise_to(total)`, `all_in()`). Packed with `python -m arena pack bots/<team> --team <team>` into one `.pkl` (≤ 25 MB, cloudpickle; helper `.py` files next to bot.py are included). Upload via the submission form by **18:00**; last working upload plays. | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| Hardware we run on (CPU/GPU, RAM), network access allowed? | One organiser machine, CPU only, several matches in parallel. **Only the standard library + `requirements.txt` (cloudpickle, ruff, pytest) — no numpy, no eval7.** No network, no files outside the bot (files on disk unavailable at play time). | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| How the winner is scored (total chips, bb/100, matches won) | **Mean big blinds won per hand** against every opponent, with a 95% CI; best score is champion. Prize £300. | Organisers' site https://poker-arena-site.vercel.app (data/submitting.md) + repo Manchester-AI-Society/poker_bot_infrastructure @8b89346, read 2026-11-06 |
| Is opponent identity visible? Can we persist state between matches? | | |

## Definition of done (for submission)
1. The bot connects to the tournament system and plays N hands with **zero illegal actions and zero time-outs**.
2. The fallback bot takes over automatically if the main bot errors out or is about to time out.
3. The bot beats our baselines in the local harness with a statistically meaningful margin (see Results).

## Results
_One line per measured run, newest at the bottom. Every row must come from the harness (`docs/API.md` → Harness result)._

| Date | Bot (commit) | Opponent | Hands | bb/100 ± 95% CI | ms/decision avg / max | Notes |
|---|---|---|---|---|---|---|

### All-in correction evidence (#39)

Research and policy assumptions: [ALL_IN.md](ALL_IN.md). Baseline is the unchanged
`d83bd2b` snapshot (same code as `9a9575a` plus the optional unused stack field);
candidate is the implementation committed as `b2fef33` on
`lembzg/39-allin-logic`, measured with the same source immediately before commit.
The baseline archive reports `nogit`; provenance is recorded here explicitly.
Both use the full development Python 3.12 environment (including v0's existing
eval7). Each run uses 400 hands = 200 duplicate deals, 100bb, seeds 101/202/303,
fresh bot instances and identical decks between variants.

The rows below are direct `harness.match.play_match` outputs; all have zero
illegal actions and errors for both seats. Baseline and final candidate each
played 7,200 hands. They are comparisons on a small fixed opponent suite, not
proof of universal improvement. Individual CIs describe each bot's win rate,
not a confidence interval for the before/after difference. The suite does not
validate the partial-observation arena learner's adaptation; that is separately
tested for bias handling and legality. Earlier candidate measurements from before
the known-fold learner correction were rejected and are not included.

| Date | Bot / variant | Opponent | Hands | bb/100 ± 95% CI | ms/decision avg / max | Notes |
|---|---|---|---|---|---|---|
| 2026-11-07 | main / baseline | always_jam | 400 | 351.25 ± 332.52 | 0.002 / 0.04 | duplicate; seed 101 |
| 2026-11-07 | main / baseline | always_jam | 400 | 726.62 ± 337.64 | 0.002 / 0.02 | duplicate; seed 202 |
| 2026-11-07 | main / baseline | always_jam | 400 | 27.38 ± 332.95 | 0.002 / 0.02 | duplicate; seed 303 |
| 2026-11-07 | main / baseline | jam_top | 400 | 27.00 ± 5.21 | 2.617 / 29.51 | duplicate; seed 101 |
| 2026-11-07 | main / baseline | jam_top | 400 | 27.50 ± 69.83 | 2.530 / 12.47 | duplicate; seed 202 |
| 2026-11-07 | main / baseline | jam_top | 400 | -0.38 ± 49.01 | 2.284 / 11.80 | duplicate; seed 303 |
| 2026-11-07 | main / baseline | random | 400 | 231.12 ± 204.18 | 4.030 / 17.00 | duplicate; seed 101 |
| 2026-11-07 | main / baseline | random | 400 | 635.75 ± 276.75 | 3.848 / 39.13 | duplicate; seed 202 |
| 2026-11-07 | main / baseline | random | 400 | 279.62 ± 204.53 | 3.356 / 13.43 | duplicate; seed 303 |
| 2026-11-07 | main / baseline | always_call | 400 | 516.88 ± 136.60 | 6.492 / 24.30 | duplicate; seed 101 |
| 2026-11-07 | main / baseline | always_call | 400 | 653.75 ± 163.43 | 6.542 / 38.65 | duplicate; seed 202 |
| 2026-11-07 | main / baseline | always_call | 400 | 480.75 ± 137.62 | 6.362 / 55.76 | duplicate; seed 303 |
| 2026-11-07 | v0 / baseline | always_jam | 400 | 423.12 ± 414.90 | 0.026 / 0.06 | duplicate; seed 101 |
| 2026-11-07 | v0 / baseline | always_jam | 400 | 428.50 ± 453.96 | 0.025 / 0.05 | duplicate; seed 202 |
| 2026-11-07 | v0 / baseline | always_jam | 400 | 431.12 ± 396.16 | 0.025 / 0.18 | duplicate; seed 303 |
| 2026-11-07 | v0 / baseline | jam_top | 400 | -75.88 ± 119.26 | 0.025 / 0.03 | duplicate; seed 101 |
| 2026-11-07 | v0 / baseline | jam_top | 400 | -75.12 ± 119.96 | 0.027 / 0.19 | duplicate; seed 202 |
| 2026-11-07 | v0 / baseline | jam_top | 400 | -30.25 ± 137.46 | 0.026 / 0.18 | duplicate; seed 303 |
| 2026-11-07 | main / candidate | always_jam | 400 | 477.25 ± 483.69 | 16.229 / 127.32 | duplicate; seed 101 |
| 2026-11-07 | main / candidate | always_jam | 400 | 928.63 ± 464.56 | 14.401 / 114.24 | duplicate; seed 202 |
| 2026-11-07 | main / candidate | always_jam | 400 | 499.88 ± 454.72 | 13.826 / 71.32 | duplicate; seed 303 |
| 2026-11-07 | main / candidate | jam_top | 400 | 27.00 ± 5.21 | 4.842 / 41.87 | duplicate; seed 101 |
| 2026-11-07 | main / candidate | jam_top | 400 | 1.25 ± 50.51 | 4.791 / 65.00 | duplicate; seed 202 |
| 2026-11-07 | main / candidate | jam_top | 400 | 98.12 ± 82.77 | 4.347 / 26.53 | duplicate; seed 303 |
| 2026-11-07 | main / candidate | random | 400 | 268.62 ± 213.51 | 8.381 / 154.30 | duplicate; seed 101 |
| 2026-11-07 | main / candidate | random | 400 | 635.75 ± 276.75 | 3.946 / 35.13 | duplicate; seed 202 |
| 2026-11-07 | main / candidate | random | 400 | 279.62 ± 204.53 | 3.401 / 20.16 | duplicate; seed 303 |
| 2026-11-07 | main / candidate | always_call | 400 | 516.88 ± 136.60 | 6.869 / 108.30 | duplicate; seed 101 |
| 2026-11-07 | main / candidate | always_call | 400 | 639.88 ± 157.06 | 6.944 / 93.31 | duplicate; seed 202 |
| 2026-11-07 | main / candidate | always_call | 400 | 476.13 ± 136.85 | 9.097 / 133.57 | duplicate; seed 303 |
| 2026-11-07 | v0 / candidate | always_jam | 400 | 346.25 ± 488.32 | 13.910 / 51.39 | duplicate; seed 101 |
| 2026-11-07 | v0 / candidate | always_jam | 400 | 872.00 ± 482.14 | 12.820 / 32.42 | duplicate; seed 202 |
| 2026-11-07 | v0 / candidate | always_jam | 400 | 418.75 ± 453.71 | 13.244 / 63.77 | duplicate; seed 303 |
| 2026-11-07 | v0 / candidate | jam_top | 400 | 24.38 ± 5.83 | 2.728 / 25.87 | duplicate; seed 101 |
| 2026-11-07 | v0 / candidate | jam_top | 400 | -1.38 ± 50.76 | 2.751 / 23.75 | duplicate; seed 202 |
| 2026-11-07 | v0 / candidate | jam_top | 400 | 93.00 ± 82.61 | 2.771 / 53.83 | duplicate; seed 303 |
