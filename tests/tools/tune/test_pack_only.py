"""Optional real-SDK serialization check. NEVER calls act, validate, match or play_pairing."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools.tune.build import build_candidate, build_opponent
from tools.tune.common import atomic_json, read_json
from tools.tune.space import DEFAULT, candidate, initial_candidates


@pytest.mark.skipif(not os.environ.get("ARENA_ROOT") or not os.environ.get("PREFLOP_DIR"),
                    reason="set ARENA_ROOT and PREFLOP_DIR for no-game SDK packing checks")
def test_fresh_process_packing_and_loading_without_playing(tmp_path):
    if sys.version_info[:2] != (3, 14):
        pytest.skip("actual submission serialization requires Python 3.14")
    repo = Path(__file__).resolve().parents[3]
    arena = Path(os.environ["ARENA_ROOT"]).resolve()
    source = tmp_path / "source/repo"
    for folder in ("tools", "core", "bots", "adapters"):
        shutil.copytree(repo / folder, source / folder, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(Path(os.environ["PREFLOP_DIR"]), tmp_path / "source/preflop")
    shutil.copytree(arena / "bots/starter", tmp_path / "source/arena/bots/starter")
    shutil.copy2(arena / "LICENSE", tmp_path / "source/arena/LICENSE")
    labels = []
    variants = initial_candidates(8, 1)[:5] + [candidate({**DEFAULT, "model_obs": 20, "min_obs": 25,
        "value_shift": 0.03, "raise_eq": 0.80, "bet_scale": 1.2, "open_shift": 0.15,
        "three_bet_scale": 1.2, "bluff_mode": "measured"})]
    for item in variants:
        folder = build_candidate(tmp_path, item)
        labels.append((item["id"], folder))
    for kind in ("official", "equity", "trap", "main_reference", "combined_reference"):
        profile = dict(id="test-"+kind, kind=kind, family=kind, params={})
        folder = build_opponent(tmp_path, profile)
        labels.append((profile["id"], folder))
    for label, folder in labels:
        job = dict(id=label, kind="pack", arena=str(arena), source=str(folder),
                   label=label, target=str(tmp_path / "packed" / label), validate=False)
        job_path, result_path = tmp_path / "job.json", tmp_path / "result.json"
        atomic_json(job_path, job)
        subprocess.run([sys.executable, "-m", "tools.tune.worker", "--job", str(job_path),
                        "--result", str(result_path)], cwd=source, check=True, capture_output=True, timeout=60)
        result = read_json(result_path)
        assert result["ok"] and result["bytes"] < 25*1024*1024
        # Hide source helpers completely and load in another interpreter without the project on sys.path.
        folder.rename(folder.with_name(folder.name+"-hidden"))
        code = ("from pathlib import Path; from arena.pickling import load_pickled_bot; "
                "from player_sdk.bot_interface import PokerBot; "
                f"b=load_pickled_bot(Path({result['payload']!r})); assert isinstance(b,PokerBot); "
                "print('loaded; no act calls')")
        subprocess.run([sys.executable, "-c", code], cwd=arena, check=True,
                       capture_output=True, timeout=60, env={**os.environ, "PYTHONPATH": ""})
