# Architecture

## Stack
Python 3.11+ (CI uses 3.12), numpy, and pytest. No GPU, no trained models. Anything else needs a `decision` issue.

## Shape
```
 tournament system ──(ENVIRONMENT.md)──> adapters/<env>/ ──GameState──> MainBot.act() ──Action──> back to the system
                                                                          │  (time guard + clamp_to_legal + fallback)
                         ┌───────────────────────┬────────────────────────┼────────────────────────┐
                         ▼                       ▼                        ▼                        ▼
                bots/main/preflop.py    bots/main/postflop.py    bots/main/opponent.py    bots/main/fallback.py
                charts by stack depth   equity vs range,         stats + range estimate   always legal, < 1 ms
                + exploit adjustments   pot odds, bet sizing     from finished hands
                                                 │
                                                 ▼
                                          core/equity.py ── core/cards.py, core/interface.py (types)

 harness/ ── local dealer: plays Bot vs Bot with duplicate deals → bb/100 ± CI, latency, illegal-action count
```

## Folders
| Path | What |
|---|---|
| `core/` | Shared types (`interface.py`), card helpers (`cards.py`), the equity engine (`equity.py`) |
| `bots/main/` | The bot we enter, one file per concern (see above) |
| `bots/__init__.py` | `make_bot` registry |
| `harness/` | NLHE dealer, match runner, stats, and trivial opponents |
| `adapters/` | Bridges to the tournament system (and anything else we play against) |
| `tests/` | Mirrors the folders above: `tests/core/`, `tests/bots/main/`, `tests/harness/`, … |
| `tools/` | One-off scripts (generating charts or tables, tuning sweeps) |

Ownership per file is in `docs/PLAN.md`. Run everything from the repo root (`python -m …`).

## Strategy notes
- The opponents are other teams' bots, which are likely simple and exploitable: calling stations, maniacs, fixed bet sizes, no adaptation. **Exploitation is the main edge.** Start from sensible default play, then shift with `OpponentStats` as data comes in.
- Variance in heads-up is huge. Only trust harness results with duplicate deals and a CI that excludes 0.
- Latency and legality come before strength. A crash or a time-out can forfeit hands or the match.
