import pytest

import bots


def test_unknown_name_is_a_value_error():
    with pytest.raises(ValueError, match="unknown bot"):
        bots.make_bot("nope")


def test_builds_by_import_path_and_passes_cfg(monkeypatch):
    monkeypatch.setitem(bots._REGISTRY, "fake", "fractions:Fraction")
    assert bots.make_bot("fake", numerator=3) == 3


def test_a_broken_bot_only_fails_when_requested(monkeypatch):
    monkeypatch.setitem(bots._REGISTRY, "broken", "no_such_module:Bot")
    with pytest.raises(ImportError):
        bots.make_bot("broken")
    assert "broken" in bots._REGISTRY
