from pathlib import Path

import pytest

from adapters.arena.build import PREFLOP_FILES, REPO, build


def helpers(path):
    path.mkdir()
    for name in PREFLOP_FILES:
        (path / name).write_text(f"# {name}\n")
    return path


def test_combo_build_includes_helpers_and_real_postflop_model(tmp_path):
    source = helpers(tmp_path / "source")
    out = tmp_path / "combo"
    copied = build("test", out, "combo", source)
    for name in PREFLOP_FILES:
        assert (out / name).read_bytes() == (source / name).read_bytes()
        assert name in copied
    assert "class ComboBot" in (out / "bot.py").read_text()
    assert (out / "bots/main/opponent.py").is_file()
    assert (out / "core/data/preflop_ranking.json").is_file()


def test_main_build_keeps_original_entry_point(tmp_path):
    out = tmp_path / "main"
    build("test", out)
    assert "class GuhPokerBot" in (out / "bot.py").read_text()
    assert not (out / "preflop.py").exists()


def test_missing_combo_source_preserves_existing_build(tmp_path):
    out = tmp_path / "combo"
    out.mkdir()
    (out / "bot.py").write_text("previous working build")
    with pytest.raises(SystemExit, match="combo dependencies missing"):
        build("test", out, "combo", tmp_path / "missing")
    assert (out / "bot.py").read_text() == "previous working build"


def test_output_cannot_replace_source_or_repo(tmp_path):
    source = helpers(tmp_path / "source")
    with pytest.raises(ValueError, match="overwrite"):
        build("test", source, "combo", source)
    with pytest.raises(ValueError, match="overwrite"):
        build("test", REPO)


def test_preflop_source_requires_combo(tmp_path):
    with pytest.raises(ValueError, match="requires"):
        build("test", tmp_path / "main", preflop_dir=Path("unused"))
