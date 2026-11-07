"""Static preparation only: snapshots and copied variants, never validate or play."""
from __future__ import annotations

import ast
import datetime as dt
import io
import json
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from .common import ARENA_SHA, RULES, SITE, atomic_json, digest, tree_hash
from .space import fields, initial_candidates

HELPERS = ("opponent.py", "preflop.py", "ranges.py", "equity_table.py")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()


def snapshot(root, target, ref="HEAD"):
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError(f"Tracked changes in {root}; commit/stash them before freezing a run")
    commit = git(root, "rev-parse", ref)
    archive = subprocess.check_output(["git", "-C", str(root), "archive", commit])
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(target, filter="data")
    return commit


def prepare(repo, arena, run, *, preflop_dir=None, preflop_ref="origin/lembzg/11-preflop-arena",
            count=32, seed=20261107, hours=8.0, deals=200, rules_file=None):
    repo, arena, run = Path(repo).resolve(), Path(arena).resolve(), Path(run).resolve()
    if run.exists():
        raise RuntimeError(f"Run directory already exists: {run}; use plan/report/resume, never overwrite")
    if not 8 <= count <= 128 or not 0 < hours <= 8 or deals != 200:
        raise ValueError("Use 8..128 candidates, 0 < hours <= 8, and the pinned 200-deal match length")
    if git(arena, "rev-parse", "HEAD") != ARENA_SHA:
        raise RuntimeError(f"Arena must be checked out at audited commit {ARENA_SHA}")
    # Retrieve rules before creating a run. This is preparation-only network access, never bot access.
    if rules_file:
        rules_text = Path(rules_file).read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(SITE + "/data/submitting.md", headers={"User-Agent": "guh-poker-preflight"})
        with urllib.request.urlopen(request, timeout=30) as response:
            rules_text = response.read(1_000_000).decode()
    for phrase in ("Python 3.14", "0.2 seconds", "1 second", "25 MB", "10/20"):
        if phrase not in rules_text:
            raise RuntimeError(f"Official rules no longer match audited assumptions ({phrase}); review before running")
    run.mkdir(parents=True)
    (run / "rules.md").write_text(rules_text, encoding="utf-8")
    source = run / "source"
    source.mkdir()
    repo_sha = snapshot(repo, source / "repo")
    arena_sha = snapshot(arena, source / "arena")
    helpers = source / "preflop"
    helpers.mkdir()
    local = Path(preflop_dir).resolve() if preflop_dir else source / "repo/bots/myteam"
    preflop_sha = None
    if not local.is_dir():
        preflop_sha = git(repo, "rev-parse", preflop_ref)
    for name in HELPERS:
        content = ((local / name).read_bytes() if local.is_dir() else subprocess.check_output(
            ["git", "-C", str(repo), "show", f"{preflop_sha}:bots/myteam/{name}"]))
        (helpers / name).write_bytes(content)
        ast.parse(content, filename=name)
    # Pin this runner too. Resume always re-execs the frozen runner, not a newer working copy.
    required = ["tools/tune/overnight.py", "adapters/arena/combo_bot_example.py", "bots/main/opponent.py"]
    if any(not (source / "repo" / name).is_file() for name in required):
        raise RuntimeError("Commit the overnight runner and combined candidate before preparing a run")
    plan = dict(schema=1, prepared_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                repo_sha=repo_sha, arena_sha=arena_sha, preflop_sha=preflop_sha,
                source_hash=tree_hash(source), rules=RULES, rules_source=SITE+"/data/submitting.md",
                rules_hash=digest(rules_text), seed=seed, hours=hours, deals=deals,
                candidates=initial_candidates(count, seed), fields=fields(),
                phase_fractions={"preflight": 0.025, "search": 0.475, "validation": 0.20,
                                 "test": 0.295, "finalize": 0.005},
                min_validation_blocks=30, min_test_blocks=30,
                practical_delta=0.005, max_family_regression=0.10,
                message="PREPARED ONLY. No games or tuning have run. Explicit run command required.")
    for item in plan["candidates"]:
        build_candidate(run, item)
    for phase in plan["fields"].values():
        for profiles in phase.values():
            for profile in profiles:
                build_opponent(run, profile)
    plan["artifact_hashes"] = {p.relative_to(run).as_posix(): tree_hash(p)
                               for folder in ("candidates", "opponents")
                               for p in sorted((run / folder).iterdir())}
    plan["plan_hash"] = digest(plan)
    atomic_json(run / "plan.json", plan)
    return plan


def copy_runtime(run, out):
    source = run / "source/repo"
    out.mkdir(parents=True)
    for folder in ("core", "bots/main", "adapters/arena"):
        shutil.copytree(source / folder, out / folder)
    for folder in ("bots", "adapters"):
        shutil.copy2(source / folder / "__init__.py", out / folder / "__init__.py")
    for name in HELPERS:
        shutil.copy2(run / "source/preflop" / name, out / name)


def build_candidate(run, item):
    run = Path(run)
    out = run / "candidates" / item["id"]
    if out.exists():
        if (out / "identity.json").exists() and json.loads((out / "identity.json").read_text()) == item:
            return out
        raise RuntimeError("Candidate folder already exists with a different identity")
    copy_runtime(run, out)
    shutil.copy2(run / "source/repo/adapters/arena/combo_bot_example.py", out / "entry.py")
    shutil.copy2(run / "source/repo/tools/tune/runtime.py", out / "tuning_runtime.py")
    (out / "config_data.py").write_text("CONFIG = " + repr(item["config"]) + "\n", encoding="utf-8")
    (out / "bot.py").write_text('''"""Offline evaluation copy; parameters never modify the production bot."""
import atexit
import hashlib
import json
from player_sdk.bot_interface import PokerBot
from config_data import CONFIG
from tuning_runtime import configure, configure_instance
import entry

class EvaluationBot(PokerBot):
    def __init__(self):
        configure(CONFIG)
        self.inner = entry.ComboBot()
        configure_instance(self.inner, CONFIG)
        self.seeded = False
        self.decisions = 0
        self.seat = None

    def summary(self, final=True):
        print("OVERNIGHT_METRICS " + json.dumps(dict(seat=self.seat, final=final,
            decisions=self.decisions, fallbacks=dict(self.inner._post.bot.fallbacks),
            observed_hands=self.inner._post.bot.model.hands)), flush=True)

    def act(self, state):
        if not self.seeded:
            # Identical visible first state gives variants identical mixing RNG seeds.
            key = repr((state.hole_cards, state.my_index, 91837)).encode()
            self.inner.rng.seed(int.from_bytes(hashlib.sha256(key).digest()[:8], "big"))
            self.inner._started = True
            self.seeded = True
            self.seat = state.my_index
            atexit.register(self.summary)
        response = self.inner.act(state)
        self.decisions += 1
        if self.decisions % 64 == 0:
            self.summary(final=False)
        return response
''', encoding="utf-8")
    atomic_json(out / "identity.json", item)
    return out


def build_opponent(run, profile):
    out = run / "opponents" / profile["id"]
    if profile["kind"] == "combined_reference":
        shutil.copytree(run / "candidates/baseline", out)
        return out
    copy_runtime(run, out)
    # Credit and preserve the organisers' exact starter. Tweaks use its strength functions.
    starter = run / "source/arena/bots/starter/bot.py"
    shutil.copy2(starter, out / "official_starter.py")
    shutil.copy2(run / "source/arena/LICENSE", out / "LICENSE.organiser")
    if profile["kind"] == "main_reference":
        (out / "bot.py").write_text('''from player_sdk.bot_interface import PokerBot
from player_sdk.models import Response
from adapters.arena.translate import ArenaAdapter
from bots.main.bot import MainBot
class MainReference(PokerBot):
    def __init__(self):
        self.adapter = ArenaAdapter(MainBot(), Response)
    def act(self, state):
        return self.adapter.act(state)
''', encoding="utf-8")
    elif profile["kind"] == "official":
        shutil.copy2(starter, out / "bot.py")
    else:
        shutil.copy2(run / "source/repo/tools/tune/sparring.py", out / "bot.py")
    (out / "profile_data.py").write_text("PROFILE = " + repr(profile) + "\n", encoding="utf-8")
    return out
