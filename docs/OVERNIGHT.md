# Overnight sparring and tuning — prepare now, start explicitly later

This is an offline parameter experiment, not neural-network training. It uses the organisers' real
engine and produces evidence and suggested parameters. **It never applies a configuration, edits the
production bot/tables, merges a PR, uploads a submission, or runs a job merely by importing/preparing.**

The i7-12700F machine is the target. The RTX 3060 is not used: the arena and these Python policies
run on CPUs, and the official playing environment is CPU-only. Creating a GPU dependency would not
accelerate this engine or produce a deployable policy. The runner uses the available logical CPUs
minus one as a token budget, caps concurrency using available memory, and charges two tokens when
both bots do heavy calculations. On an unrestricted 20-thread system this is up to 19 tokens,
not 19 simultaneous pairs of two CPU-heavy bots. The OS schedules the P/E cores.

## 1. Exact setup on CachyOS (does not start games)

Run these commands in a terminal on the PC. Keep the clone on a local SSD and allow at least 20GB
free space. Install packages only if needed. [uv is in Arch extra](https://archlinux.org/packages/extra/x86_64/uv/);
[uv supports managed Python 3.14](https://docs.astral.sh/uv/guides/install-python/).

```bash
sudo pacman -S --needed git uv
git clone --branch lembzg/33-overnight-runner https://github.com/lembzg/guh-poker.git
cd guh-poker
git clone https://github.com/Manchester-AI-Society/poker_bot_infrastructure.git ../poker_bot_infrastructure
git -C ../poker_bot_infrastructure checkout --detach 8b893461c0d020ae8ed9c78aed298cd698e025a0
uv python install 3.14
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r ../poker_bot_infrastructure/requirements.txt
.venv/bin/python --version
```

Use this clean environment for playing. Do not install the project's older numpy/eval7 dependencies
in it. The runner deliberately refuses them to exercise the same pure-Python path used at the event.
No CUDA, torch, paid API or additional Python library is needed.

If tournament fixes have landed since this branch was prepared, incorporate and review them **before**
preparation. The experiment freezes the current committed bot exactly; it does not pull updates while
running. Commit/stash tracked work first. The branch includes the #34 combined entry and gauntlet
builder compatibility. Until #32 merges, the default helper source is the fetched
`origin/lembzg/11-preflop-arena` commit. To evaluate newer preflop work, explicitly provide
`--preflop-ref origin/YOUR-REVIEWED-BRANCH`, or `--preflop-dir /absolute/path/to/bots/myteam`.
The report records precisely which source and table fingerprints were used.

Alternatively pass `--bot-ref origin/REVIEWED-BOT-BRANCH` to preparation. This freezes that revision's
`core/`, `bots/` and `adapters/` into the experiment while retaining the runner from this branch.
It does not checkout, merge or change either revision. A revision containing `bots/myteam` supplies
its own preflop helpers unless explicitly overridden. The default is the runner branch's current bot.
Default thresholds and adapter/strategy signatures are checked; incompatible baselines fail loudly.
The report records the runner SHA, bot SHA and helper fingerprints separately. Do not select an
unreviewed branch merely because it has a newer timestamp.

## 2. Prepare only (safe before bedtime)

```bash
.venv/bin/python -m tools.tune.overnight prepare --arena-root ../poker_bot_infrastructure --run-dir results/overnight/night1
.venv/bin/python -m tools.tune.overnight plan --run-dir results/overnight/night1
```

These commands snapshot committed source, the audited arena, official rules, the parameter space,
opponents, and copied variant folders. **They do not play, validate, tune or pack a bot.**
There is no timer until the explicit start command. A reused run directory is rejected rather than
overwritten. Preparation downloads the official submitting guide once; if that is unavailable,
download it yourself and pass `--rules-file /path/to/submitting.md`.

The rules fingerprint and key assumptions are checked against the official guide. If the guide or
engine changes, preparation stops for review instead of guessing. `plan.json` is sealed; editing it
later requires a new experiment. Do not move a prepared/started run between machines.

You may run `.venv/bin/python -m pytest -q tests/tools/tune` now: tests are synthetic; the optional
SDK test only packs with validation disabled and reloads objects without ever calling `act`.
They are not sparring or tuning. Actual arena qualification is deferred until explicit start.

## 3. Start only when you explicitly decide to run

Open Codex on the PC in this clone and say: **Run the prepared eight-hour overnight sparring and tuning.**
Preparation on the Mac does not give a chat access to a separate PC; execute the run on the PC itself.
The command below is documented for that later step; do not execute it during setup:

```bash
nohup systemd-inhibit --what=sleep:idle --mode=block --why="Eight-hour poker evaluation" .venv/bin/python -m tools.tune.overnight run --run-dir results/overnight/night1 --start > results/overnight/night1/console.log 2>&1 &
```

This requests a sleep inhibitor only while the job lives and survives closing the terminal.
If local policy denies `systemd-inhibit`, keep the PC awake and run the same Python command without
that wrapper. Locking the screen is fine. Turning off or suspending the machine prevents computation.
No system power setting is permanently changed. `--workers N` sets a smaller CPU-token ceiling if
other workloads share the PC; default is the maximum guarded budget.

The `run` subcommand requires `--start`. There is no automatic scheduled start. The runtime first
qualifies every initial candidate and opponent through fresh-process packing/validation, then evaluates packed objects rather
than relying on access to a candidate's helper files.

## 4. What consumes the eight hours

The deadline is eight elapsed hours from the first explicit start, including resumed downtime.
The same command resumes the same run without granting another eight hours. About 2.5% is available
for initial qualification; unused preflight time goes into search. Search ends at hour 4, validation
at hour 5.6, and the final audit near hour 7.96; the remaining time is reserved for cleanup/reporting.
No new match starts in the last 20 seconds of its phase. In-flight jobs have process-tree timeouts.

- **Search:** 32 initial conservative variants, followed by smoothed discrete cross-entropy proposals
  and successive halving. Search is capped at about 96 candidates; extra time buys independent
  evidence for surviving settings rather than an unbounded grid. Controls keep original bluffing,
  no bluffs, measured-fold bluffs, single-barrel bluffs and fixed-prior adaptation available.
- **Parameters:** preflop opening-width shift, 3-bet bluff-frequency multiplier, postflop value/call/
  raise thresholds, bet-size multiplier, bluff gating, and the observation gates for both models.
  The runtime modifies only copied variants, never source strategy files. The 3-bet multiplier changes
  the bluff component; it does not pretend to solve a new full preflop equilibrium.
- **Development field:** eight equally weighted families, including the exact MIT-licensed starter,
  starter tweaks, true/sticky callers, maniacs, nits, raw-equity pot-odds players, preflop shovers,
  excessive 3-bettors and min-raisers. Multiple profiles rotate within each family.
- **Validation:** at most three finalists; shifted opponent profiles and a disjoint seed namespace.
  Rank with Bonferroni-adjusted intervals; require at least 30 full field blocks and no reliability
  failures to lock a challenger. Validation chooses one finalist, not a claimed winner.
- **Final audit:** that finalist is frozen before any final-test game. Fourteen equally weighted
  families include six unseen styles/controls: traps, delayed bluffs, postflop shoves, style switching,
  MainBot, and the unchanged combined default. Fresh seeds remain disjoint from search/validation.
  No test result can change settings or select another finalist.

There is always a defaults comparison on the **same duplicate deals**. A match runs 200 deals twice,
with independent processes for each half, so opponent learning is reset at realistic intervals.
The 200-deal length is the audited engine default, not an assertion that an organiser cannot choose
another length. Change the experimental design only after verifying any announced change.

## 5. Statistical safeguards and interpretation

The primary estimate is the equal-family average of **candidate minus default**. A statistical unit
is an independent field block: one freshly restarted duplicate match against every family at a
shared seed. Confidence intervals are computed across blocks, not by treating correlated hands,
two seats, or opponents sharing deals as independent observations.

The morning recommendation requires at least 30 complete final-test blocks, a positive paired 95%
lower confidence bound, at least +0.005 bb/hand (+0.5 bb/100) estimated improvement, no candidate or
reference reliability failures, and no family with a 95% upper bound below -0.10 bb/hand relative to
defaults. Otherwise it says to keep defaults. No significance or improvement is promised.
Internal strategy errors/timeouts, adapter errors and entry fallbacks also disqualify evidence even
if the arena safely played a move and recorded no fault. Intentional bank-guard fallbacks are counted
and reported separately. Student-t intervals remain approximate for non-normal returns. Individual-family comparisons and
development rankings are exploratory, not a second selection process. Timeout/phase-censored
incomplete blocks are reported as missing coverage. Real faults are retained and disqualify evidence;
large profits against a broken opponent are not accepted.

The report also shows worst-family performance, leave-one-family-out results, and sensitivity to
alternative family weights. These address specialization without pretending that a synthetic field
can guarantee performance against unknown teams. The final synthetic-field result should be treated
as evidence for a separate reviewed change, never a tournament-win probability.

## 6. Files waiting in the morning

Open `results/overnight/night1/reports/MORNING_REPORT.md` first. It links/explains:

| File | Contents |
|---|---|
| `reports/MORNING_REPORT.md` | Finalist vs defaults, absolute/paired bb/100, confidence intervals, coverage, per-family performance, robustness and speed |
| `reports/recommendation.json` | Whether a replacement was confirmed; frozen settings; explicitly `parameters_applied: false` |
| `reports/statistics.json` | Full summaries and state, including multiplicity-adjusted validation intervals |
| `reports/configurations.json` | Every tested parameter dictionary |
| `reports/matches.csv` | Every completed/failed/censored match, seeds, scores, faults, disabled reasons, timing, bank use |
| `reports/paired_comparisons.csv` | Exact candidate/default paired differences and usability flags for independent reanalysis |
| `results.sqlite` | Durable unique-job journal, including all failures |
| `jobs/JOB/attempt-*/hands.jsonl.gz` | Complete evaluator-only hands: cards, actions, outcomes, orientation and deal identifiers |
| `jobs/JOB/attempt-*/*.log` | Bot and worker diagnostics; interrupted attempts are preserved |
| `jobs/JOB/result.json` | Exact result plus per-street actions, position outcomes, internal fallback counters, latency histogram and ten lowest-return hands |
| `plan.json`, `rules.md`, `source/` | Sealed experiment, official rule snapshot and exact source/table versions |
| `console.log`, `state.json` | Progress, deadline, selected finalist lock, errors and resume state |

Latency p50/p95/p99 are explicitly histogram-bin upper bounds, not falsely precise quantiles. The
maximum, mean, decision count, faults and thinking-bank usage are recorded. Internal fallback
counters are retained; forced termination can leave internal telemetry partial,
which is marked separately from the exact arena fault counters. Missing final counters or a decision-count
mismatch disqualifies a match from healthy evidence and prevents a confirmed replacement. Full card information
exists only in evaluator audit files: it is never fed into a bot, used to predict deck seeds, or used
as a policy input. The bot sees only its own cards and the official public state.

Progress reports refresh about every five minutes and at phase changes. To regenerate a report after
the job stops, without playing more games:

```bash
.venv/bin/python -m tools.tune.overnight report --run-dir results/overnight/night1
```

Do not run a second report writer while the coordinator owns the lock; read the existing report.
To interrupt, send SIGINT/SIGTERM to the coordinator PID or use Ctrl-C for a foreground run. Its state
and complete results survive. Resume with the same start command. A stale OS file lock releases on
process death; on Linux, recorded surviving worker groups are reaped using boot/start-time identity
checks so reused PIDs are not trusted. Failed jobs are not silently deleted and rerun until favorable.

If the process stops because of low disk space (4GB reserve), a frozen-source mismatch, unavailable
dependencies, packing failure or another error, the latest report states that it is incomplete.
The raw journal remains available. No recommendation can replace an incomplete final audit.

## Rules and compliance

Source: [official event guide](https://poker-arena-site.vercel.app/data/submitting.md) and
[audited arena source](https://github.com/Manchester-AI-Society/poker_bot_infrastructure/tree/8b893461c0d020ae8ed9c78aed298cd698e025a0).
Python 3.14; standard library plus the pinned arena requirements; CPU-only; 10/20 blinds, 2000 chips
reset per hand; duplicate seats; fresh process each half; one second per move; 0.2 seconds/deal/half
thinking bank; 20-fault disable threshold; packed file at most 25MiB as enforced by `arena.pickling`.
Workers enforce the actual arena clock and fault rules, rather than relaxing them to make simulations
look healthy. Bots do not use the network, read external files, inspect other processes, attack the
arena, identify opponents by their implementation, or use deck seeds. Only the offline evaluator
reads/writes experiment files. No submissions or code changes happen automatically overnight.
