"""Paired match-cluster inference; never count correlated hands as independent samples."""
from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from functools import lru_cache


def _beta_fraction(a, b, x):
    tiny = 1e-300
    c, d = 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / max(tiny, d)
    h = d
    for m in range(1, 501):
        aa = m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m))
        d = 1 + aa * d
        c = 1 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1))
        d = 1 + aa * d
        c = 1 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        change = d * c
        h *= change
        if abs(change - 1) < 1e-13:
            return h
    raise ArithmeticError("incomplete beta did not converge")


def _ibeta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    term = math.exp(math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b)
                    + a*math.log(x) + b*math.log1p(-x))
    if x < (a+1) / (a+b+2):
        return term * _beta_fraction(a, b, x) / a
    return 1 - term * _beta_fraction(b, a, 1-x) / b


@lru_cache(maxsize=4096)
def t_quantile(probability, df):
    if not 0.5 < probability < 1 or df < 1:
        raise ValueError("invalid Student-t quantile arguments")
    def cdf(t):
        return 1 - 0.5 * _ibeta(df/2, 0.5, df / (df + t*t))
    low, high = 0.0, 1.0
    while cdf(high) < probability:
        high *= 2
    for _ in range(70):
        middle = (low + high) / 2
        if cdf(middle) < probability:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def interval(values, alpha=0.05):
    values = list(values)
    n = len(values)
    mean = statistics.fmean(values) if values else None
    if n < 2:
        return dict(n=n, mean=mean, low=None, high=None, se=None)
    se = statistics.stdev(values) / math.sqrt(n)
    radius = t_quantile(1-alpha/2, n-1) * se
    return dict(n=n, mean=mean, low=mean-radius, high=mean+radius, se=se)


def valid(row):
    r = row.get("result", {})
    return (row.get("ok") is True and r.get("status") == "complete"
            and r.get("deals_completed") == row["deals"] and r.get("mean_bb") is not None)


def healthy(row):
    r = row.get("result", {})
    return (valid(row) and not r.get("faults_a") and not r.get("faults_b")
            and not r.get("disabled_a") and not r.get("disabled_b"))


def reliability_failure(row):
    r = row.get("result", {})
    if r.get("faults_a") or r.get("faults_b") or r.get("disabled_a") or r.get("disabled_b"):
        return True
    # End-of-phase cancellation is missing evidence, never a bot fault or a usable score.
    return not healthy(row) and not row.get("censored", False)


def summarize(rows, candidate, phase, families, alpha=0.05):
    chosen = [r for r in rows if r["phase"] == phase and r["candidate"] == candidate]
    base = {(r["family"], r["opponent"], r["block"]): r for r in rows
            if r["phase"] == phase and r["candidate"] == "baseline"}
    by_family = defaultdict(list)
    clusters, raw_clusters = defaultdict(dict), defaultdict(dict)
    for row in chosen:
        other = base.get((row["family"], row["opponent"], row["block"]))
        # Preserve all rows in raw exports. Opponent faults/incomplete jobs cannot provide evidence.
        if not other or not healthy(other) or not healthy(row):
            continue
        difference = row["result"]["mean_bb"] - other["result"]["mean_bb"]
        clusters[row["block"]][row["family"]] = difference
        raw_clusters[row["block"]][row["family"]] = row["result"]["mean_bb"]
        by_family[row["family"]].append(difference)
    complete = sorted(b for b, family_rows in clusters.items() if set(families) <= family_rows.keys())
    values = [statistics.fmean(clusters[b][f] for f in families) for b in complete]
    absolute = [statistics.fmean(raw_clusters[b][f] for f in families) for b in complete]
    family_ci = {f: interval([clusters[b][f] for b in complete], alpha) for f in families}
    family_absolute = {f: interval([raw_clusters[b][f] for b in complete], alpha) for f in families}
    failures = sum(reliability_failure(r) for r in chosen)
    result = dict(candidate=candidate, phase=phase, paired=interval(values, alpha),
                  absolute=interval(absolute, alpha), family=family_ci, family_absolute=family_absolute,
                  failures=failures, reference_failures=sum(reliability_failure(r) for r in base.values()),
                  unusable_jobs=sum(not healthy(r) for r in chosen),
                  jobs=len(chosen), complete_blocks=complete,
                  hands=sum(r.get("result", {}).get("hands_played", 0) for r in chosen),
                  faults=sum(r.get("result", {}).get("faults_a", 0) for r in chosen),
                  disabled=sum(bool(r.get("result", {}).get("disabled_a")) for r in chosen))
    means = [v["mean"] for v in family_ci.values() if v["mean"] is not None]
    result["worst_family_delta"] = min(means) if means else None
    result["leave_one_family_out"] = ([
        (sum(means)-m)/(len(means)-1) for m in means] if len(means)>1 else [])
    result["block_tail_5pct"] = statistics.fmean(sorted(values)[:max(1, math.ceil(len(values)*0.05))]) if values else None
    return result


def robustness(family_means, seed=941, repetitions=2000):
    """Sensitivity to arbitrary alternative family weights, not a probability of tournament victory."""
    if not family_means:
        return None
    rng = random.Random(seed)
    scores = []
    for _ in range(repetitions):
        w = [rng.expovariate(1) for _ in family_means]
        scores.append(sum(x*y for x, y in zip(w, family_means)) / sum(w))
    scores.sort()
    return {"positive_fraction": sum(s>0 for s in scores)/len(scores),
            "p05": scores[int(0.05*len(scores))], "p50": statistics.median(scores),
            "description": "Dirichlet(1) family-weight sensitivity; exploratory, not a calibrated probability"}
