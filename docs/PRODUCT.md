# Product: heads-up NLHE tournament bot

## Goal
Win a heads-up no-limit hold'em bot-vs-bot tournament. Our bot is a fork of DyypHoldem (DeepStack-style continual re-solving), plus whatever we learn by reverse-engineering the tournament system.

## Tournament rules
_Paste the organisers' rules **verbatim** here as soon as we get them. Do the analysis in `docs/ENVIRONMENT.md`._

Fill in every row. Each one changes how we tune the bot:

| Question | Answer | Source |
|---|---|---|
| Format: number of hands per match, round-robin or knockout, stacks reset each hand? | | |
| Blinds, starting stack (in big blinds), antes | | |
| Bet sizing: any amount, or a fixed set? Minimum raise rule? | | |
| Time limit per action / per hand / per match; what happens on time-out | | |
| What happens on an illegal action or a crash | | |
| Interface: protocol, language, how the bot is submitted/hosted | | |
| Hardware we run on (CPU/GPU, RAM), network access allowed? | | |
| How the winner is scored (total chips, bb/100, matches won) | | |
| Is opponent identity visible? Can we persist state between matches? | | |

## Definition of done (for submission)
1. The bot connects to the tournament system and plays N hands with **zero illegal actions and zero time-outs**.
2. The fallback bot takes over automatically if the main bot errors out or is about to time out.
3. The bot beats our baselines in the local harness with a statistically meaningful margin (see Results).

## Results
_One line per measured run, newest at the bottom. Every row must come from the harness (`docs/API.md` → Harness result)._

| Date | Bot (commit) | Opponent | Hands | bb/100 ± 95% CI | ms/decision avg / max | Notes |
|---|---|---|---|---|---|---|
