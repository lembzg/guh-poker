# Plan

Tasks live in GitHub Issues (`./scripts/status.sh`). This file holds the team mapping, file ownership, and the cut list.

## Team
Add yourself when you join (a direct commit to `main` is fine). Your handoff is `.agent/handoffs/<login-lowercase>.md`.

| GitHub login | Role (CLAUDE.md) | Suggested first tickets |
|---|---|---|
| lembzg | **Integration captain**: shared files, contracts, reviews, submission | #14 import existing bot, #4 interface, #3 env/CI, then #8 tournament adapter |
| EulaBet | Tickets | #10 equity, #6 harness, then #13 opponent model |
| _(third teammate)_ | Tickets | #11 preflop, #12 postflop, then #5 bot wiring |

## File ownership
A ticket's **Owns:** must fit this table. Every ticket also owns its mirror folder under `tests/`.

| Path | Owner | Notes |
|---|---|---|
| `CLAUDE.md`, `scripts/`, `.github/`, `.claude/`, root config, `requirements*.txt` | captain (#3) | shared |
| `docs/API.md`, `core/interface.py`, `core/cards.py`, `bots/__init__.py` | captain (#4) | contract |
| `core/equity.py` | #10 | |
| `bots/v0/` (our existing bot, imported as-is + adapter) | #14 | |
| `bots/main/bot.py`, `bots/main/fallback.py` | #5 | |
| `bots/main/preflop.py` (+ data files under `bots/main/data/preflop*`) | #11 | |
| `bots/main/postflop.py` | #12 | |
| `bots/main/opponent.py` | #13 | |
| `harness/` | #6 | |
| `adapters/`, `docs/ENVIRONMENT.md` | #8 | |
| `docs/PRODUCT.md`, `docs/PLAN.md`, `docs/DECISIONS.md` | anyone | tiny direct commits OK |

## Milestones
| Milestone | Done? |
|---|---|
| `MainBot` plays legal hands in the harness (fallback only is fine) | |
| Preflop + postflop + equity merged; MainBot beats `always_call` and `random` with CI > 0 | |
| Opponent model merged; MainBot beats its own previous version | |
| Tournament system received; ENVIRONMENT.md filled; adapter plays 1000 legal hands | |
| Tuned for the environment (time budget, stack depth, bet sizes) | |
| Submitted | |

## Cut list
_Features we dropped, and why. Move things here early._
- DyypHoldem (DeepStack port): its models and tables are gone, it needs a GPU, and it's slow. See D-005.
