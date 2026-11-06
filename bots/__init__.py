"""Bot registry. Imports are lazy, so one broken bot doesn't break the others."""
from __future__ import annotations

import importlib

from core.interface import Bot

_REGISTRY = {
    "main": "bots.main.bot:MainBot",
    "v0": "bots.v0.adapter:V0Bot",
    "random": "harness.opponents:RandomBot",
    "always_call": "harness.opponents:AlwaysCall",
    "always_raise_pot": "harness.opponents:AlwaysRaisePot",
}


def make_bot(name: str, **cfg) -> Bot:
    """Build a registered bot. Raises ValueError for an unknown name."""
    if name not in _REGISTRY:
        raise ValueError(f"unknown bot {name!r}; choose from {sorted(_REGISTRY)}")
    module_name, class_name = _REGISTRY[name].split(":")
    return getattr(importlib.import_module(module_name), class_name)(**cfg)
