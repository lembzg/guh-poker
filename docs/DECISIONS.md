# Decisions

Append-only. One entry per decision that would surprise someone reading the code later. Newest at the bottom.

```
## D-NNN Title — YYYY-MM-DD — decided by
Context: why this came up (1 line)
Decision: what we chose (1 line)
Consequences: what this commits us to / what we gave up (1–2 lines)
```

## D-001 Coordinate agents through GitHub, not direct messaging — 2026-11-06 — EulaBet (bootstrap)
Context: Three independent Claude Code agents on separate laptops; the workflow is reused from our hackathon-2026 repo.
Decision: GitHub Issues (assignee = owner), PRs (draft → ready → merged = progress) and `docs/` are the only coordination channels. `scripts/status.sh` is the shared view; questions use the `question` label plus an @mention.
Consequences: Agents poll `status.sh` at the sync points in CLAUDE.md, and all durable info is written to the repo.

## D-002 Base the bot on a DyypHoldem snapshot, squashed into our own history — 2026-11-06 — EulaBet
Context: We need a strong heads-up NLHE bot fast; DyypHoldem is an open-source Python DeepStack port. Importing its history listed its authors as contributors on our repo.
Decision: Copy lucky72s/dyypholdem at commit `0e2dda5` (2022-01-03) as a single commit of ours, with no upstream history, and put our code in new folders under `src/` where we can.
Consequences: Upstream fixes can't be merged; they have to be ported by hand (upstream is inactive). Upstream has **no licence file**, so the README keeps the credit, and we check that the organisers allow it.

## D-003 Upstream LFS data is unavailable; keep pointers, recover separately — 2026-11-06 — EulaBet
Context: All 17 LFS objects (≈2.1 GB of value nets and bucketing/equity tables) return HTTP 410 on upstream and on all 13 forks (upstream issue #7).
Decision: Keep the pointer files, add `.lfsconfig` with `fetchexclude = *` so clones don't fail, and recover the data through dedicated tickets (DeepHoldem torch7 models from Google Drive + the converter; tables regenerated).
Consequences: The DeepStack bot can't run until both recovery tickets land. A fallback bot and the harness are developed in parallel.

## D-004 Large artifacts go in GitHub Release assets, not git or LFS — 2026-11-06 — EulaBet (proposal; captain to confirm)
Context: Models and tables are 100–400 MB each. LFS has storage and bandwidth quotas (which is how upstream lost its data), and `check.sh` rejects files over 5 MB.
Decision: Upload them as release assets on this repo (up to 2 GB each). `tools/artifacts.txt` lists tag, asset, destination and sha256, and `tools/fetch_artifacts.sh` downloads them.
Consequences: One extra setup step per clone. Artifacts are versioned by release tag, not by commit.
