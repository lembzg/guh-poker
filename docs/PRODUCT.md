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
