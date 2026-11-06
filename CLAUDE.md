# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Situation

We are building a bot for a **heads-up no-limit hold'em bot-vs-bot tournament**. Goal: **win**. The base is a fork of [DyypHoldem](https://github.com/lucky72s/dyypholdem): a Python/PyTorch DeepStack port that uses continual re-solving and counterfactual value networks. The **tournament environment hasn't been released yet.** When it arrives, we reverse-engineer it and tune the bot to it.

**3 developers**, each driving an **independent** Claude Code agent on their own laptop, share this repo. Agents never talk to each other directly. All coordination goes through **GitHub Issues, PRs, and `docs/`**. Work is split into **independent tickets** so people rarely wait on each other.

| Role | Who (see `docs/PLAN.md`) | Does |
|---|---|---|
| **Integration captain** | lembzg (repo owner) | Owns shared files and the contracts (`docs/API.md`), reviews `shared`/`contract` PRs, keeps `main` green, decides what we submit |
| Everyone else | EulaBet + the third teammate | Takes independent tickets from the pool |

**Who am I?** Run `./scripts/me.sh`. It prints your GitHub login in lowercase. That login names your handoff (`.agent/handoffs/<login>.md`) and your branch prefix (`<login>/`). "Teammates" means everyone else.

## ⚠ Known state of the fork (read before running anything)

- **Upstream's Git LFS data is gone.** All 17 LFS objects return 410 on upstream and on every fork (upstream issue #7). In this repo they exist only as **pointer files**: `data/models/*/final_*.tar`, `src/nn/bucketing/*.{sqlite,pkl,pt}`, `src/game/evaluation/hand_ranks.pt`, `src/terminal_equity/*.pt`. **The bot cannot run until they're recovered.** Ticket: see `./scripts/status.sh`. `.lfsconfig` stops git-lfs from trying to download them.
- The original DeepHoldem torch7 models are still on Google Drive (links: happypepper/DeepHoldem issue #28, comment 689021950). `src/torch7/torch7_model_converter.py` converts them to the format this repo uses.
- `src/settings/arguments.py` has `use_gpu = True` by default. On Macs and other machines without CUDA, set it to `False`.
- Upstream reports: there are bugs in bet-size parsing against Slumbot (upstream issue #5), and the shipped models lose to Slumbot (issue #4). Don't assume upstream behaviour is correct. Measure it.
- **Never commit large binaries** (models, tables, training data). `check.sh` rejects files over 5 MB. Large artifacts go in **GitHub Release assets** on this repo, with a fetch script (see `docs/DECISIONS.md`).

## Commands

```bash
./scripts/status.sh      # Board snapshot: what's waiting on you, issues by person, open PRs + CI/review. Run often.
./scripts/check.sh       # The single quality gate. CI runs exactly this. Must pass before any PR is marked ready.
./scripts/resume.sh      # Recovery brief after /compact, /clear, or a new session (read-only).
./scripts/checkpoint.sh  # Pre-checkpoint check: git state, sensitive files, handoff freshness. Never commits.
./scripts/me.sh          # Prints your GitHub login (lowercase).
./scripts/setup-labels.sh  # One-time: create workflow labels on GitHub (idempotent).
```

The bot itself runs from `src/`, because its paths are relative to that folder:
```bash
cd src && python player/dyypholdem_acpc_player.py <host> <port>     # vs an ACPC dealer (acpc_server/dyypholdem_match.sh)
cd src && python player/dyypholdem_slumbot_player.py <hands>        # vs Slumbot's public API
cd src && python torch7/torch7_model_converter.py <file> <street> <mode>   # DeepHoldem → DyypHoldem model
```
When the Python environment ticket lands, its install and test commands go here and into `check.sh`, including how to run a single test.

## Where things live

| Need | Location |
|---|---|
| Goal, tournament rules (verbatim once known), what "winning" means | `docs/PRODUCT.md` |
| Reverse-engineering notes on the tournament system | `docs/ENVIRONMENT.md` |
| Code map, data flow, run instructions | `docs/ARCHITECTURE.md` |
| Interfaces between tickets (Bot interface, game-state shape, harness output) | `docs/API.md` (the contract) |
| Team, folder ownership, cut list | `docs/PLAN.md` |
| Why we chose X | `docs/DECISIONS.md` (append-only) |
| Individual tasks, owner, questions | **GitHub Issues** (never duplicate tasks in docs) |
| My current working state | `.agent/handoffs/<login>.md` (your own file only) |
| Upstream code | `src/`, `acpc_server/`, `data/` (snapshot of lucky72s/dyypholdem @ `0e2dda5`) |

## Context persistence and recovery

Conversation memory is disposable; the repo is not. The full protocol is in `.agent/RECOVERY.md`.

- **At session start, and after `/compact` or `/clear`:** a SessionStart hook injects the `./scripts/resume.sh` brief. If you don't see a "RECOVERY BRIEF" in context, run the script yourself. Read your handoff in full, resolve every ⚠ (trust Git/GitHub over the handoff), then continue its Next steps. Never redo work that Git or a closed issue shows as done.
- **Checkpoint** at a task stage change, when blocked or unblocked, before `/compact`/`/clear`/ending the session, or after ~45 min. Steps: update your handoff with verified facts → run `./scripts/checkpoint.sh` → commit safe files and the handoff on your branch and push → report `💾 Checkpoint: …` to your human. Never commit secrets, `.env*`, or large artifacts.
- Only pushed commits and GitHub updates exist for teammates.

## Task lifecycle

Every unit of work is a GitHub Issue. **Owner = assignee. Progress = the PR's state.** There are no owner or status labels.

| Stage | Visible as | What you do |
|---|---|---|
| Unclaimed | issue with no assignee | Uses the task template: goal, acceptance criteria, **Owns:** folder |
| Claimed | you are the assignee | Re-check it's still unassigned, then `gh issue edit <n> --add-assignee @me` |
| In progress | **draft PR** | Branch `<login>/<n>-<slug>` from fresh `origin/main`. First push (a handoff update is enough), then `gh pr create --draft --title "<title> (#<n>)" --body "Closes #<n> …"` |
| Ready | PR marked ready | Rebased on `origin/main`, `./scripts/check.sh` passes, acceptance criteria verified → `gh pr ready <n>` |
| Done | issue closed | Squash-merged once CI is green (and approved, if review is required). The merge auto-closes the issue |

**Independent tickets.** Every ticket names the folder or files it **owns**. Only edit what your ticket owns. If two tickets need the same files, they aren't independent: merge them or sequence them (`Depends on: #n`). Take P0 tickets first. Never take a ticket assigned to someone else. Ask them instead (see below). **Prefer adding new modules over editing upstream files.** Upstream edits are where conflicts happen, so each ticket that touches `src/` names the exact upstream files it changes.

Labels: `P0` (needed to field a bot: do first), `blocked`, `question`, `shared`, `contract`, `decision`, `env` (needs the tournament system).

## Communication protocol (agent ↔ agent)

- **Asking a teammate something:** comment on the relevant issue or PR, starting with their `@login` (a real login from `docs/PLAN.md`; this also notifies their human). Add the `question` label. `status.sh` shows it to them under "Waiting on you". They answer in a comment that starts with your `@login`, then remove `question`.
- **Asking for a review:** `gh pr edit <n> --add-reviewer <login>`. The reviewer answers with `gh pr review <n> --approve` or `--request-changes -b "<what>"`.
- **When to sync** (run `./scripts/status.sh`): at session start, before starting each task, before marking a PR ready, after each merge, and whenever idle. Answer anything under "Waiting on you" **before** starting new work.
- **Share findings, not just code.** Put anything another ticket could use in a file: tournament behaviour in `docs/ENVIRONMENT.md`, measured results (bb/100, latency) in the PR body and `docs/PRODUCT.md` → Results. Never leave it only in your own chat.
- Keep comments short and factual: what changed, what's needed, by when.

## Git, branching, PRs

- `main` is always runnable. Nobody pushes broken code to `main`, and nobody force-pushes it.
- Branches: `<login>/<issue#>-<slug>` from fresh `origin/main`. Only push to your own branches. After rebasing your own branch, use `git push --force-with-lease`.
- **Small PRs, merged often.** Rebase right before you merge.
- **Squash merge only** (`gh pr merge --squash --delete-branch`). The author merges their own PR once CI is green. The exception is PRs labeled `shared` or `contract`, which need an approving review first.
- You may commit tiny docs-only edits straight to `main`. This covers everything in `docs/` except `docs/API.md`. Run `git pull --rebase` first and push immediately.
- Commit messages are imperative and reference the issue (`Add equity baseline bot (#12)`).
- Our history is unrelated to upstream's (D-002), so never `git merge upstream/main`. Upstream has been inactive since 2022. If it ever ships a fix, the captain ports it by hand in a `shared` PR.

## Shared files and contracts

- **Shared files** are root config, `requirements*.txt`, CI, `scripts/`, `CLAUDE.md`, `docs/API.md`, `src/settings/`, and the bot interface module once it exists. **The integration captain owns them.** If you need a change, ask the captain (add `question` to your issue), or make it in a small dedicated PR labeled `shared` with the captain as reviewer. Never bundle it with feature work. The captain's own `shared` PRs get reviewed by any teammate.
- **Contract-first:** anything that crosses ticket boundaries (the Bot interface, the game-state shape, the harness result format, artifact paths) goes into `docs/API.md` **before** either side implements it. Code to the contract, and mock the other side until the real one lands.
- **Additive** contract changes go in your PR with the `contract` label and a review request to the consumers. **Breaking** changes get a PR that changes *only* `docs/API.md`, reviewed by every consumer before anyone implements them.

## Measuring "better" (bot quality rules)

- No strategy change merges on vibes. Any PR that claims to improve play reports a harness result: opponent, hands played, **bb/100 ± 95% CI**, and seeds. Use duplicate or mirrored deals when the harness supports them, because variance in heads-up is huge.
- Track **latency per decision** alongside win rate. A time-out or an illegal action in the tournament can cost more than a weak strategy.
- Keep a fast, simple fallback bot working at all times. If the DeepStack path fails (missing models, too slow, crash), the bot must still act legally.

## Blockers and architectural changes

- **Blocked:** add `blocked` (and a `question` to whoever can unblock), comment exactly what you need, then **switch to another ticket**, or stub or mock the dependency from the contract and continue. Never sit idle.
- **Architectural change** (new dependency of note, swapping the solver, changing the model format, restructuring directories): open an issue labeled `decision` with a 3–5 line proposal and get your human's approval. If it touches shared files, it also needs the captain's review. Record the outcome in `docs/DECISIONS.md`.

## Token efficiency

- **Read narrowly.** Search first, then read only the relevant line ranges. Never read LFS pointers, model or tensor files, training data, logs, or `acpc_server/` binaries.
- **Keep command output short.** Pipe through `| tail -40`. Put one-line summaries in issues and PRs, never full logs.
- **Use the scripts** instead of many separate `gh` and `git` calls.
- **Use one context per task.** Checkpoint, then `/compact` at task boundaries. If you've tried the same fix twice and it failed, stop and rethink, or ask your human.
- **Don't spawn subagents or parallel explorations unless your human asks.**

## Updates to your human

- Keep updates to 5 lines or fewer. No code blocks, diffs, or long logs unless asked. Reference `#issue` and `#PR` numbers.
- Lead with what needs the human, if anything. Questions must be answerable in one word: yes/no or numbered options, with your recommendation marked.
  ```
  ✅ Done: <what> (#PR)
  🔨 Now: <what> (#issue), ETA <time>
  ⛔ Blocked: <what> — need <who/what>
  ❓ Decide: <question>? 1) … (recommended) 2) …
  ```
- Before an action that is hard to undo (merging a `contract` PR, deleting things, changing CI or shared config, publishing a release), state it in one line and wait for approval.
