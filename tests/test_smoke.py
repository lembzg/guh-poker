"""Confirms pytest collects from the repo root and the shared core imports."""

from core.interface import Action


def test_core_imports():
    assert Action("fold").kind == "fold"
