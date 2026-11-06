# Plan

Tasks live in GitHub Issues (`./scripts/status.sh`). This file holds the team mapping, folder ownership, and the cut list.

## Team
Add yourself when you join (a direct commit to `main` is fine). Your handoff is `.agent/handoffs/<login-lowercase>.md`.

| GitHub login | Role (CLAUDE.md) | Notes |
|---|---|---|
| lembzg | **Integration captain**: shared files, contracts, reviews, submission | Repo owner |
| EulaBet | Tickets | |
| _(third teammate)_ | Tickets | |

## Folder ownership
A ticket's **Owns:** must fit this table. Upstream folders are listed only where a ticket is expected to edit them.

| Path | Owner | Notes |
|---|---|---|
| `CLAUDE.md`, `scripts/`, `.github/`, `.claude/`, root config, `requirements*.txt`, `src/settings/` | captain | shared |
| `docs/API.md`, `src/bots/interface.py`, `src/bots/__init__.py` | captain | contract |
| `docs/PRODUCT.md`, `docs/PLAN.md`, `docs/DECISIONS.md` | anyone | tiny direct commits OK |
| `docs/ENVIRONMENT.md`, `src/adapters/` | env ticket | |
| `src/bots/baseline/` | fallback-bot ticket | |
| `src/bots/deepstack/` | DeepStack adapter ticket | |
| `src/harness/` | harness ticket | |
| `tools/models/`, `data/models/` | model-recovery ticket | |
| `tools/tables/` + the table pointer files in `src/nn/bucketing/`, `src/game/evaluation/`, `src/terminal_equity/` | table-recovery ticket | |
| `src/server/` | protocol-bugfix ticket | upstream file |

## Milestones
| Milestone | Done? |
|---|---|
| Bot runs end-to-end locally (models + tables recovered, CPU) | |
| Harness reports DeepStack vs baseline bb/100 | |
| Tournament system received; ENVIRONMENT.md filled; adapter plays legal hands | |
| Tuned for the environment (time budget, bet sizes) | |
| Submitted | |

## Cut list
_Features we dropped, and why. Move things here early._
