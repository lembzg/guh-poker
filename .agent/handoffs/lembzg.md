# Handoff — lembzg

Updated: 2026-11-07T00:30:00+00:00
Status: in-review
Task: #11
Branch: lembzg/11-preflop-arena
Commit: pending first push of this branch

## Done
- #4 merged (#17). #14 merged (#16). #27 opened for the v0 reuse decision, still undecided (its handoff is on lembzg/27-v0-reuse).
- Tournament environment found: public repo Manchester-AI-Society/poker_bot_infrastructure, checked at 8b89346. It isn't vendored here.
- Built bots/myteam (preflop tables, opponent model, postflop placeholder), its generators in tools/, tests/test_preflop.py and docs/preflop_crosscheck.md.

## In progress
- Draft PR for #11, waiting on the human's decisions below. Not merged.

## Files touched
- bots/myteam/, tools/gen_equity_table.py, tools/gen_ranges.py, tools/gen_crosscheck.py, tools/sim_pairings.py, tests/test_preflop.py, docs/preflop_crosscheck.md

## Tests
- tests/test_preflop.py, Python 3.14, needs ARENA_ROOT pointing at an infra checkout: 59 passed. It's skipped without ARENA_ROOT, and CI doesn't run pytest until #3 lands.
- 200 separate 100-deal matches per opponent, exploits on: call +0.165, fold +0.711, random +2.644, shove +5.301, starter +0.118, all with CIs above 0. No-exploit copy +0.021. 0 faults.
- Single 300-deal runs vs starter sometimes span 0, because the edge is smaller than that CI. See docs/preflop_crosscheck.md.
- arena validate OK. arena pack OK on Python 3.14 (241 KB).

## Bugs / blockers
- The infra clone and venvs are in this session's scratchpad, so they need recreating in a new session. See the header of tests/test_preflop.py and tools/sim_pairings.py.
- python3.14 is at /opt/homebrew/bin/python3.14. There's no plain python command on this laptop.

## Decisions & dependencies
- Rules differ from the brief: the current README and event.json describe one round-robin, not groups plus a final.
- bots/myteam targets the real arena API. bots/main and its open PRs (#19, #20, #21) target our own docs/API.md, so the team has two bots. Needs a captain decision.
- Hand composition in the charts is heuristic. Only frequencies come from the reference.
- #11's acceptance criteria name bots/main/preflop.py, so the PR says Refs #11, not Closes.

## Next steps
1. Get the human's answer on which bot we enter, and on the team name for arena pack.
2. Build real postflop play. The placeholder never bets, and it's the largest known gap.
3. Tell teammates the environment is available, and update #8 and docs/ENVIRONMENT.md.
4. Review PR #19, requested from lembzg, and get the decision on #27.
