"""Declared conservative search space and sealed opponent splits."""
from __future__ import annotations

import random

from .common import digest

DEFAULT = dict(value_shift=0.0, call_shift=0.0, raise_eq=0.75, bet_scale=1.0,
               bluff_mode="original", bluff_fold=0.60, min_obs=15, model_obs=12,
               open_shift=0.0, three_bet_scale=1.0)
SPACE = dict(value_shift=[-0.03, -0.015, 0.0, 0.015, 0.03],
             call_shift=[-0.02, -0.01, 0.0, 0.01, 0.02], raise_eq=[0.70, 0.75, 0.80],
             bet_scale=[0.8, 1.0, 1.2], bluff_mode=["original", "off", "measured", "single"],
             bluff_fold=[0.55, 0.60, 0.65], min_obs=[10, 15, 25, 40],
             model_obs=[8, 12, 20, 30], open_shift=[-0.15, 0.0, 0.15],
             three_bet_scale=[0.8, 1.0, 1.2])


def candidate(config):
    return {"id": "baseline" if config == DEFAULT else "v-" + digest(config)[:12], "config": config}


def initial_candidates(count=32, seed=20261107):
    rng = random.Random(seed)
    configs = [dict(DEFAULT), {**DEFAULT, "bluff_mode": "off"},
               {**DEFAULT, "bluff_mode": "measured"}, {**DEFAULT, "bluff_mode": "single"},
               {**DEFAULT, "min_obs": 100000, "model_obs": 100000}]
    # Stratified marginal coverage, no hand-picked opponent-specific settings.
    columns = {}
    for key, values in SPACE.items():
        column = [values[i % len(values)] for i in range(count)]
        rng.shuffle(column)
        columns[key] = column
    for i in range(count):
        configs.append({key: column[i] for key, column in columns.items()})
    unique = {candidate(c)["id"]: candidate(c) for c in configs}
    return list(unique.values())[:count]


def offspring(elites, count, seed, seen):
    """Discrete cross-entropy proposal: smoothed elite marginals plus 25% global exploration."""
    rng = random.Random(seed)
    out = []
    for _ in range(count * 100):
        config = {}
        for key, values in SPACE.items():
            pool = [e[key] for e in elites] if elites and rng.random() >= 0.25 else values
            config[key] = rng.choice(pool)
        c = candidate(config)
        if c["id"] not in seen:
            seen.add(c["id"])
            out.append(c)
        if len(out) >= count:
            break
    return out


def fields():
    """Equal family weights. Profiles rotate by block; test families never select parameters."""
    def profiles(family, phase, variants):
        return [{"id": f"{phase}-{family}-{i}", "family": family,
                 "kind": kind, "params": params,
                 "cpu_cost": 2 if kind in ("equity", "main_reference", "combined_reference") else 1}
                for i, (kind, params) in enumerate(variants)]
    train = {
        "starter": [("official", {}), ("starter", {"margin": 0.08})],
        "station": [("station", {"looseness": 1.0}), ("station", {"looseness": 0.85})],
        "maniac": [("maniac", {"aggression": 0.65}), ("maniac", {"aggression": 0.85})],
        "nit": [("nit", {"threshold": 0.68}), ("nit", {"threshold": 0.74})],
        "equity": [("equity", {"margin": 0.03}), ("equity", {"margin": 0.08})],
        "shove": [("shove", {"threshold": 0.0}), ("shove", {"threshold": 0.55})],
        "threebet": [("threebet", {"aggression": 0.50}), ("threebet", {"aggression": 0.80})],
        "minraise": [("minraise", {"aggression": 0.70}), ("minraise", {"aggression": 1.0})],
    }
    validation = {
        "starter": [("starter", {"margin": 0.14, "size": 0.90})],
        "station": [("station", {"looseness": 0.82, "size": 0.45})],
        "maniac": [("maniac", {"aggression": 0.75, "size": 1.30})],
        "nit": [("nit", {"threshold": 0.71, "size": 0.45})],
        "equity": [("equity", {"margin": 0.05, "size": 0.45})],
        "shove": [("shove", {"threshold": 0.45})],
        "threebet": [("threebet", {"aggression": 0.65, "size": 0.90})],
        "minraise": [("minraise", {"aggression": 0.85})],
    }
    audit = dict(validation)
    audit.update({
        "trapper": [("trap", {"aggression": 0.25})],
        "delayed_bluff": [("delayed", {"aggression": 0.55})],
        "postflop_jammer": [("postjam", {"threshold": 0.48})],
        "switcher": [("switch", {"aggression": 0.50})],
        "main_reference": [("main_reference", {})],
        "combined_reference": [("combined_reference", {})],
    })
    return {phase: {family: profiles(family, phase, variants) for family, variants in pool.items()}
            for phase, pool in (("search", train), ("validation", validation), ("test", audit))}
