"""Copied into isolated candidate folders. Pure stdlib; never reads run files or opponent cards."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace


def configure(config):
    import opponent
    from bots.main import postflop as pf

    opponent.MIN_OBS = config["min_obs"]
    pf.VALUE_EQ = {s: v + config["value_shift"] for s, v in pf.VALUE_EQ.items()}
    pf.CALL_MARGIN = {s: v + config["call_shift"] for s, v in pf.CALL_MARGIN.items()}
    pf.RAISE_EQ = config["raise_eq"]
    if config["bet_scale"] != 1:
        original_bet = pf._bet
        def sized(state, fraction):
            return original_bet(state, fraction * config["bet_scale"])
        pf._bet = sized

    if config["bluff_mode"] != "original":
        from core.interface import Action
        original_knobs, checked, facing = pf.knobs, pf._checked_to, pf._facing_bet
        def knobs(opp):
            k = original_knobs(opp)
            values = dict(vars(k))
            values["observed_fold"] = getattr(opp, "fold_to_bet", None) is not None
            values["observed_cbet"] = getattr(opp, "fold_to_cbet", None) is not None
            return SimpleNamespace(**values)
        def allowed(state, k):
            if config["bluff_mode"] == "off":
                return False
            if config["bluff_mode"] == "single" and (
                    state.street != 2 or any(a.street > 1 and a.actor == "me" and a.kind == "raise"
                                            for a in state.history)):
                return False
            return k.observed_fold and k.fold_to_bet >= config["bluff_fold"]
        def checked_to(state, eq, k, street, spr, wet, draw, rng):
            action = checked(state, eq, k, street, spr, wet, draw, rng)
            threshold = pf.VALUE_EQ[street] - (0.05 if k.station else 0) + (
                0.03 if k.folder and not k.station else 0)
            if action.kind == "raise" and eq < threshold and not allowed(state, k):
                return Action("check")
            return action
        def facing_bet(state, eq, k, street, spr, wet, draw, rng):
            if not allowed(state, k):
                # Only folder triggers the original semi-bluff branch; leave call/value thresholds intact.
                k = SimpleNamespace(**{**vars(k), "folder": False})
            return facing(state, eq, k, street, spr, wet, draw, rng)
        pf.knobs, pf._checked_to, pf._facing_bet = knobs, checked_to, facing_bet


def configure_instance(inner, config):
    # Each variant has a private copied helper module and a fresh process each half.
    model = inner.model
    sb, bb = model.sb_knobs, model.bb_knobs
    def sb_knobs():
        knobs = sb()
        return replace(knobs, open_shift=max(-1, min(1, knobs.open_shift + config["open_shift"])))
    def bb_knobs():
        knobs = bb()
        return replace(knobs, bluff_mult=max(0, min(1.6, knobs.bluff_mult * config["three_bet_scale"])))
    model.sb_knobs, model.bb_knobs = sb_knobs, bb_knobs
    post_model = inner._post.bot.model
    if post_model is None:
        raise RuntimeError("combined candidate requires the #19 opponent model")
    post_model.min_samples = config["model_obs"]
