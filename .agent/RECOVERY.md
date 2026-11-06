# Context persistence & recovery

How each agent survives `/compact`, `/clear`, a crashed or new session, or a different laptop without losing progress. It uses plain Markdown and Git. Don't rely on Claude's conversation summary or auto-memory: **if it's not in the repo, assume it's lost.**

## What persists where

| Information | Lives in | Visible to teammates? |
|---|---|---|
| My current task state | `.agent/handoffs/<login>.md` on **my current branch** | Only after I push |
| Code | My branch | Only after I push |
| Tasks, status, questions | GitHub Issues / PRs | Immediately |
| Product, architecture, contracts, decisions | `docs/` | Once merged to `main` (or pushed, if they read my branch) |

- Each agent edits **only its own** handoff file (named after its GitHub login; `./scripts/me.sh`). Never touch a teammate's file. New people copy `_template.md`.
- The handoff is a **snapshot, not a log**. Overwrite it at each checkpoint; git history keeps the old versions.
- It travels with your branch. Commit it in your checkpoint commits, and it reaches `main` when your PR is squash-merged.
- Never assume the other laptop matches yours. Only pushed commits and GitHub updates exist for teammates. `resume.sh` shows one line per teammate, read from their newest pushed branch (`<login>/…`), falling back to `origin/main`.

## Handoff format

Header fields are machine-checked, so keep the exact keys:

```
Updated: <date -Iseconds>
Status:  idle | in progress | ready | blocked
Task:    #<issue> <title>          (or "none")
Branch:  <branch you're on>
Commit:  <short sha> <subject>     (latest commit containing real work; "none" if none)
```

Sections, in this order. Write 1–5 terse bullets each, and only verified facts:
- **Done**: finished and committed (cite commit/PR).
- **In progress**: partially done, including what's uncommitted and why.
- **Files touched**: paths on this branch.
- **Tests**: exact command → result (`./scripts/check.sh → OK`).
- **Bugs / blockers**: with `#issue` links and who can unblock.
- **Decisions & dependencies**: `D-NNN`, `docs/API.md` entries, and teammates' work you're waiting on.
- **Next steps**: numbered, concrete, and executable by a fresh session with no memory ("Add POST /items handler in server/items.ts per API.md#items", not "continue").

## When to checkpoint

At meaningful milestones only, never after every tool call:
- at a task stage change (claimed → draft PR → ready → merged)
- when you get blocked or unblocked
- after a decision that affects your work
- before `/compact`, `/clear`, or ending the session
- after about 45 minutes of work with no checkpoint

## Checkpoint procedure (before you intentionally compact or reset)

1. **Verify** what's actually true: run the tests or checks you're about to cite.
2. **Update the handoff** from verified facts. Set `Updated:` with `date -Iseconds`, and set `Branch:` and `Commit:` to the real values.
3. **Run `./scripts/checkpoint.sh`.** It splits your changes into committed-but-unpushed, staged, unstaged and untracked, flags sensitive-looking files, and checks the handoff is fresh and matches git. Fix every ⚠.
4. **Preserve the work safely:**
   - On your feature branch, commit the work that's safe to share plus the handoff: `wip(#N): checkpoint — <what>`, then push. Work-in-progress commits are fine there, because squash merge hides them.
   - **Never commit** secrets, `.env*`, credentials, or large generated files. Leave half-written experiments you don't want shared uncommitted, list them under **In progress**, or `git stash push -m "#N <what>"` and note the stash.
   - On `main` with no code changes, commit only your handoff file directly (the docs exemption).
5. **Report** to your human in mobile format: `💾 Checkpoint: #N <stage>, pushed <sha>. Next: <step 1>.`
6. Then `/compact` or `/clear`, or end the session.

## Recovery procedure (after a reset or in a new session)

1. Read `CLAUDE.md` (loaded automatically). The brief's title shows who you are (your GitHub login).
2. Read the **`./scripts/resume.sh`** brief. A SessionStart hook in `.claude/settings.json` injects it automatically on startup, `/clear` and `/compact`. If you can't see "RECOVERY BRIEF" in context, run it yourself. It shows your handoff header and next steps, discrepancies between the handoff and real git/GitHub state, a full git-state report, each teammate's latest pushed handoff status, and the board from `status.sh`.
3. Read your handoff file in full, plus whatever docs it or your issue references (`docs/PRODUCT.md`, `ARCHITECTURE.md`, `API.md`, `DECISIONS.md`).
4. **Resolve every ⚠ before writing code.** Trust git and GitHub over the handoff:
   - Code changed after the recorded commit: read `git log`/`git diff` from that commit and update **Done**.
   - Task closed, or PR merged: don't redo it. Mark it done and take the next task.
   - Uncommitted changes not mentioned in the handoff: inspect them with `git diff` before deciding to keep, commit or stash them.
   - Docs disagree with the code: the code is the truth for *what is*, and docs/issues are the truth for *what was agreed*. Raise contract mismatches through the contract process in CLAUDE.md.
5. Answer anything under "Waiting on you", then continue from **Next steps**.
6. Send one mobile-format line: `♻️ Recovered: #N <stage>. Resuming: <next step>.`

## `/compact` or a fresh session?

- **`/compact`**: the default. Use it when the conversation is long but still about the current task. Checkpoint first, so a bad summary costs nothing.
- **Fresh session** (`/clear`, or quit and start `claude` again): use it when the context is polluted (a long debugging detour, an unrelated exploration), the agent behaves inconsistently or repeats mistakes, or you're switching to an unrelated task. Checkpoint first. The new session recovers with `resume.sh`.
- **Remote Control users:** after quitting, start again with `claude remote-control --name guh-poker-<login>`. `claude remote-control -c` reattaches to the *same* conversation, which is not a fresh context.
