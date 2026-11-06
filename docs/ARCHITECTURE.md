# Architecture

## Stack
Python 3 + PyTorch, from upstream DyypHoldem. The exact versions get pinned in `requirements.txt` by the environment ticket. CPU is the default for us. CUDA is optional.

## Shape
```
 tournament system ──(ENVIRONMENT.md)──> src/adapters/<env>/  ──GameState──>  Bot.act()  ──Action──> back to system
                                                                                │
                                   ┌────────────────────────────────────────────┼──────────────────────┐
                                   ▼                                            ▼                      ▼
                         src/bots/deepstack/                         src/bots/baseline/        (future bots)
                         wraps upstream continual re-solving         fast equity/rule bot,
                         (src/lookahead, src/nn, data/models)        also the fallback

 src/harness/  ── plays Bot vs Bot locally, duplicate deals ──> bb/100 ± CI, latency  (docs/API.md → Harness result)
```
Everything new goes in new folders under `src/`. Upstream scripts put `src/` on `sys.path` and use paths relative to it (`../data/models/`), so we always run from `src/`.

## Upstream code map (only what you need to find your way)
| Path | What |
|---|---|
| `src/player/` | Entry points: `dyypholdem_acpc_player.py` (ACPC dealer), `dyypholdem_slumbot_player.py` (Slumbot API), `manual_acpc_player.py` (human) |
| `src/server/` | Protocol parsing: `acpc_game.py`, `slumbot_game.py`, `protocol_to_node.py` (message → `ProcessedState` + `TreeNode`) |
| `src/lookahead/` | `continual_resolving.py`: the per-action solver (`start_new_hand`, `compute_action`). `resolving.py`, `lookahead.py`: depth-limited CFR |
| `src/nn/` | Value networks, the bucketer, and the next-round value. `bucketing/` holds the large lookup tables (currently missing) |
| `src/tree/` | Game tree building and bet sizing (which raise sizes the solver considers) |
| `src/terminal_equity/`, `src/game/` | Showdown equity, card tools, the hand evaluator (`hand_ranks.pt`, currently missing) |
| `src/settings/` | `arguments.py` (GPU flag, CFR iterations, paths), `game_settings.py`, `constants.py` |
| `src/data_generation/`, `src/training/` | Generating training data and retraining value nets |
| `src/torch7/` | Converter for DeepHoldem torch7 models |
| `acpc_server/` | Pre-built ACPC dealer and match scripts (Linux + Windows binaries) |
| `data/models/<street>/final_{cpu,gpu}.tar` | Value-net weights (currently LFS pointers only) |

Main tuning knobs, before any retraining: `cfr_iters` and `cfr_skip_iters` in `arguments.py` (strength vs latency), and the bet sizes in `src/settings/` and `src/tree/` (which actions we consider).

## Directory ownership
The live table is in `docs/PLAN.md`.

## Run locally
```bash
# Filled in by the environment ticket: install, fetch artifacts, smoke test.
cd src && python player/dyypholdem_acpc_player.py 127.0.0.1 18902
```

## Large artifacts
Models and tables are **not** stored in git. They live as GitHub Release assets on this repo, and a fetch script downloads them into place. See `docs/DECISIONS.md` D-004.
