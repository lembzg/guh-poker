"""Port the combined arena build to the organisers' final format (Manchester-AI-Society/poker_bot).

That format wants flat files next to model.py (no folders), a plain pickle of model.Model, and code without
os/threading/logging/inspect/json/pathlib. This script copies a built combo folder (adapters.arena.build
--strategy combo) into OUT as flat modules, rewrites imports, removes the flagged imports and embeds the
preflop ranking. model.py (from this folder) bridges their Model API to the unchanged ComboBot.

    python -m adapters.pokerbot.flatten BUILD_DIR OUT_DIR
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

# flat name -> path inside the built combo folder
MODULES = {
    "core_interface": "core/interface.py",
    "core_cards": "core/cards.py",
    "core_equity": "core/equity.py",
    "core_allin": "core/allin.py",
    "main_bot": "bots/main/bot.py",
    "main_fallback": "bots/main/fallback.py",
    "main_allin": "bots/main/allin.py",
    "main_postflop": "bots/main/postflop.py",
    "main_opponent": "bots/main/opponent.py",
    "arena_translate": "adapters/arena/translate.py",
    "team_preflop": "preflop.py",
    "team_opponent": "opponent.py",
    "team_ranges": "ranges.py",
    "team_equity_table": "equity_table.py",
    "combo_bot": "bot.py",
}

IMPORTS = [
    (r"\bfrom core\.(\w+) import", r"from core_\1 import"),
    (r"\bfrom bots\.main\.(\w+) import", r"from main_\1 import"),
    (r"\bfrom adapters\.arena\.translate import", "from arena_translate import"),
    (r"\bfrom player_sdk\.(models|bot_interface) import", "from arena_sdk import"),
    (r"^from opponent import", "from team_opponent import"),
    (r"^from preflop import", "from team_preflop import"),
    (r"^from equity_table import", "from team_equity_table import"),
    (r"^import ranges$", "import team_ranges as ranges"),
]


def patch_main_bot(src: str) -> str:
    src = src.replace("import inspect\nimport logging\nimport threading\n", "")
    src = src.replace('log = logging.getLogger("bots.main")',
                      "class _NoLog:\n    def warning(self, *a, **k):\n        pass\n\n    debug = warning\n\n\n"
                      "log = _NoLog()")
    # Our own postflop_action takes both optional extras; no signature inspection needed.
    src = re.sub(r"def _accepts\(fn, name: str\) -> bool:\n(?:    .*\n|\n)+?(?=\n\ndef )",
                 "def _accepts(fn, name: str) -> bool:\n    return fn is not None\n", src)
    # No threads: run the strategy inline (it is time-budgeted internally; ~10 ms per decision).
    src = re.sub(r"def _run_with_timeout\(fn, timeout_s: float\):\n(?:    .*\n|\n)+?(?=\n\nclass )",
                 "def _run_with_timeout(fn, timeout_s: float):\n    return fn()\n", src)
    for bad in ("inspect.", "threading.", "logging."):
        assert bad not in src, bad
    return src


def patch_equity(src: str, ranking: tuple[str, ...]) -> str:
    src = src.replace("import json\n", "").replace("from pathlib import Path\n", "")
    src = re.sub(r"^_DATA_DIR = .*\n", "", src, flags=re.M)
    src = re.sub(r"^_PREFLOP_RANKING = .*\n", "", src, flags=re.M)
    src = re.sub(r"_PREFLOP_RANKING_CLASSES: tuple\[str, \.\.\.\] = tuple\(\n.*\n",
                 "_PREFLOP_RANKING_CLASSES: tuple[str, ...] = " + repr(ranking) + "\n", src)
    for bad in ("json.", "Path(", "_DATA_DIR"):
        assert bad not in src, bad
    return src


def patch_combo(src: str) -> str:
    src = src.replace("import os\n", "")
    src = src.replace("self.rng.seed(os.urandom(16))", "self.rng.seed()")
    assert "os." not in src
    return src


def main(build: Path, out: Path) -> None:
    ranking = tuple(row[0] for row in json.loads((REPO / "core/data/preflop_ranking.json").read_text())["ranking"])
    out.mkdir(parents=True, exist_ok=True)
    for flat, rel in MODULES.items():
        src = (build / rel).read_text()
        for pat, rep in IMPORTS:
            src = re.sub(pat, rep, src, flags=re.M)
        if flat == "main_bot":
            src = patch_main_bot(src)
        elif flat == "core_equity":
            src = patch_equity(src, ranking)
        elif flat == "combo_bot":
            src = patch_combo(src)
        (out / f"{flat}.py").write_text(src)
    for name in ("model.py", "arena_sdk.py"):
        shutil.copy(HERE / name, out / name)


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
