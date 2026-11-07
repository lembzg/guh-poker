"""Read-only analysis of saved games; writes reports, never changes bots or selections."""
from __future__ import annotations

import csv
import datetime as dt
import os
from pathlib import Path

from .common import atomic_json
from .space import DEFAULT
from .stats import healthy, robustness, summarize
from .worker import LATENCY_BINS_MS


def quantile_upper(hist, q):
    total = sum(hist)
    if not total:
        return None
    at = q * total
    acc = 0
    for index, count in enumerate(hist):
        acc += count
        if acc >= at:
            return LATENCY_BINS_MS[index] if index < len(LATENCY_BINS_MS) else None


def telemetry(rows):
    latency = [0]*(len(LATENCY_BINS_MS)+1)
    actions, hands, fallbacks, positions = {}, {}, {}, {}
    incomplete_metric_halves = 0
    count, total, worst, bank = 0, 0.0, 0.0, 0.0
    for row in rows:
        data = row.get("latency", {})
        count += data.get("count", 0)
        total += data.get("sum_ms", 0)
        worst = max(worst, data.get("max_ms", 0))
        bank = max(bank, row.get("bank_fraction_max", 0))
        for i, n in enumerate(data.get("hist", [])):
            latency[i] += n
        for target, name in ((actions, "actions"), (hands, "hand_counts")):
            for k, n in row.get(name, {}).items():
                target[k] = target.get(k, 0) + n
        for packet in row.get("bot_metrics", {}).values():
            incomplete_metric_halves += not packet.get("final", False)
            for reason, n in packet.get("fallbacks", {}).items():
                fallbacks[reason] = fallbacks.get(reason, 0) + n
        for position, value in row.get("positions", {}).items():
            current = positions.setdefault(position, {"hands": 0, "net_bb": 0.0})
            current["hands"] += value["hands"]
            current["net_bb"] += value["net_bb"]
    return dict(decisions=count, mean_ms=total/count if count else None, max_ms=worst,
                p50_upper_ms=quantile_upper(latency, 0.50), p95_upper_ms=quantile_upper(latency, 0.95),
                p99_upper_ms=quantile_upper(latency, 0.99), bank_fraction_max=bank,
                actions=actions, hands=hands, internal_counters=fallbacks, positions=positions,
                incomplete_metric_halves=incomplete_metric_halves)


def format_ci(item, scale=100):
    if item["mean"] is None:
        return "insufficient data"
    mean = item["mean"] * scale
    if item["low"] is None:
        return f"{mean:+.3f} (CI unavailable)"
    return f"{mean:+.3f} [{item['low']*scale:+.3f}, {item['high']*scale:+.3f}]"


def export(run, plan, state, rows, *, final=False):
    run = Path(run)
    directory = run / "reports"
    directory.mkdir(exist_ok=True)
    selected = state.get("selected", "baseline")
    phases = sorted({r["phase"] for r in rows})
    summaries = {}
    for phase in phases:
        field_phase = "test" if phase.startswith("stress") else phase
        families = list(plan["fields"][field_phase])
        ids = sorted({r["candidate"] for r in rows if r["phase"] == phase})
        summaries[phase] = [summarize(rows, identity, phase, families) for identity in ids]
    test = next((s for s in summaries.get("test", []) if s["candidate"] == selected), None)
    qualified = bool(final and state.get("phase") == "complete" and selected != "baseline" and test
                     and state.get("selection_pack_validated", False)
                     and test["paired"]["n"] >= plan["min_test_blocks"]
                     and test["paired"]["low"] is not None and test["paired"]["low"] > 0
                     and test["paired"]["mean"] >= plan["practical_delta"] and not test["failures"]
                     and not test["reference_failures"]
                     and all(v["high"] is None or v["high"] >= -plan["max_family_regression"]
                             for v in test["family"].values()) and state.get("source_integrity", False))
    recommendation = dict(
        status="confirmed_on_synthetic_field" if qualified else "keep_defaults_no_confirmed_replacement",
        finalist=selected, suggested_config=(state["candidates"][selected]["config"] if qualified else DEFAULT),
        parameters_applied=False, bot_files_changed=False, test=test,
        confidence_note="95% paired Student-t intervals across independent match/field blocks; approximate under non-normal returns. No universal anti-overfitting guarantee.",
        limitations=["Synthetic opponents cannot represent unknown tournament entrants exactly.",
                     "Only the locked finalist has a confirmatory final-test interpretation.",
                     "Development rankings and per-family intervals are exploratory; no hand-level IID inference.",
                     "Latency quantiles are histogram upper bounds including process startup.",
                     "8-hour deadline/cancellation may leave an incomplete last block; coverage is shown, not imputed."])
    atomic_json(directory / "recommendation.json", recommendation)
    atomic_json(directory / "configurations.json", state.get("candidates", {}))
    atomic_json(directory / "statistics.json", dict(
        generated_utc=dt.datetime.now(dt.timezone.utc).isoformat(), state=state, summaries=summaries,
        telemetry=telemetry(rows), total_jobs=len(rows), healthy_jobs=sum(healthy(r) for r in rows)))
    # Persist raw outcomes including failed/stubbed games. No silent deletion of bad results.
    path = directory / "matches.csv"
    temp = path.with_suffix(".csv.tmp")
    columns = ["id", "phase", "candidate", "family", "opponent", "block", "seed", "deals", "ok",
               "status", "bb_per_hand", "bb_per_100", "hands", "faults_a", "faults_b", "disabled_a",
               "disabled_b", "think_a_s", "decisions", "latency_max_ms", "bank_fraction_max", "error"]
    with temp.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, columns)
        writer.writeheader()
        for row in rows:
            result = row.get("result", {})
            score = result.get("mean_bb")
            data = {key: row.get(key) for key in columns}
            data.update(status=result.get("status"), bb_per_hand=score, bb_per_100=score*100 if score is not None else None,
                        hands=result.get("hands_played"), faults_a=result.get("faults_a"),
                        faults_b=result.get("faults_b"), disabled_a=result.get("disabled_a"),
                        disabled_b=result.get("disabled_b"), think_a_s=result.get("think_a"),
                        decisions=row.get("latency", {}).get("count"),
                        latency_max_ms=row.get("latency", {}).get("max_ms"))
            writer.writerow(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    references = {(r["phase"], r["family"], r["opponent"], r["block"]): r for r in rows
                  if r["candidate"] == "baseline"}
    paired_path = directory / "paired_comparisons.csv"
    temporary = paired_path.with_suffix(".csv.tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["phase", "candidate", "family", "opponent", "block", "seed",
                         "candidate_bb_per_100", "default_bb_per_100", "delta_bb_per_100", "usable"])
        for row in rows:
            other = references.get((row["phase"], row["family"], row["opponent"], row["block"]))
            if row["candidate"] == "baseline":
                continue
            a = row.get("result", {}).get("mean_bb")
            b = other.get("result", {}).get("mean_bb") if other else None
            writer.writerow([row["phase"], row["candidate"], row["family"], row["opponent"],
                             row["block"], row["seed"], a*100 if a is not None else None,
                             b*100 if b is not None else None,
                             (a-b)*100 if a is not None and b is not None else None,
                             healthy(row) and other is not None and healthy(other)])
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, paired_path)
    lines = ["# Overnight sparring report", "", f"Status: **{state.get('phase', 'not started')}**. "
             f"Confirmed replacement: **{'yes' if qualified else 'no'}**. No production changes applied.", "",
             "All scores below are bb/100; family-balanced paired differences compare the same deals with defaults.",
             f"Completed match records: {len(rows)}; healthy: {sum(healthy(r) for r in rows)}; "
             f"played hands: {sum(r.get('result', {}).get('hands_played', 0) for r in rows):,}.", "",
             f"Frozen runner {plan['repo_sha']}; bot {plan.get('bot_sha', plan['repo_sha'])}; "
             f"arena {plan['arena_sha']}; plan {plan['plan_hash']}.", "",
             "## Final test (locked finalist, fresh seeds and unseen families)", ""]
    if state.get("last_error"):
        lines[3:3] = [f"Stopped/error: {state['last_error']}", ""]
    if state.get("interrupted"):
        lines[3:3] = ["Interrupted before completion; no confirmatory recommendation is applied.", ""]
    if test:
        lines += [f"Finalist `{selected}`: paired improvement **{format_ci(test['paired'])}**; "
                  f"{test['paired']['n']} complete independent field blocks.",
                  f"Absolute equal-family score: {format_ci(test['absolute'])}.", "",
                  "| Family | Absolute bb/100 [95% CI] | Paired improvement [95% CI] | Blocks |", "|---|---:|---:|---:|"]
        for family, value in test["family"].items():
            lines.append(f"| {family} | {format_ci(test['family_absolute'][family])} | {format_ci(value)} | {value['n']} |")
        means = [v["mean"] for v in test["family"].values() if v["mean"] is not None]
        sensitivity = robustness(means)
        if sensitivity:
            lines += ["", f"Alternative family-weight sensitivity: {sensitivity['positive_fraction']:.1%} "
                      "of Dirichlet(1) weights gave positive estimated improvement. This is exploratory, not a win probability."]
        loo = test["leave_one_family_out"]
        if loo:
            lines.append(f"Leaving any one family out: {min(loo)*100:+.3f} to {max(loo)*100:+.3f} bb/100.")
        lines.append(f"Worst 5% of field-block differences average: {test['block_tail_5pct']*100:+.3f} bb/100."
                     if test["block_tail_5pct"] is not None else "No tail estimate available.")
    else:
        lines.append("Final test not available. Search winners are exploratory; keep defaults.")
    lines += ["", "## Exploration and validation (not independent proof of superiority)", "",
              "| Phase | Candidate | Paired bb/100 [nominal CI] | Blocks | Failed jobs |",
              "|---|---|---:|---:|---:|"]
    for phase, values in summaries.items():
        if phase == "test":
            continue
        ranked = sorted(values, key=lambda v: v["paired"]["mean"] if v["paired"]["mean"] is not None else -1e9, reverse=True)
        for value in ranked[:12]:
            lines.append(f"| {phase} | {value['candidate']} | {format_ci(value['paired'])} | "
                         f"{value['paired']['n']} | {value['failures']} |")
    selected_rows = [r for r in rows if r["phase"] == "test" and r["candidate"] == selected]
    detail = telemetry(selected_rows)
    lines += ["", "## Reliability and speed", "", f"Finalist decisions: {detail['decisions']:,}; "
              f"mean latency ms: {detail['mean_ms']}; max ms: {detail['max_ms']:.3f}; "
              f"p95/p99 histogram upper bounds ms: {detail['p95_upper_ms']} / {detail['p99_upper_ms']}.",
              f"Maximum observed half-bank usage: {detail['bank_fraction_max']:.1%}.",
              f"Internal fallback/bookkeeping counters: {detail['internal_counters']}; "
              f"partial telemetry halves: {detail['incomplete_metric_halves']}.",
              f"Descriptive position outcomes (not hand-IID confidence intervals): {detail['positions']}.",
              "Full faults, disabled reasons, timing and results—including failed jobs—are in matches.csv/results.sqlite.",
              "Action counts, hand outcomes, worst losses and full evaluator-only hand histories are saved with each job.",
              "Parameter dictionaries for every candidate are in configurations.json; the locked finalist is in recommendation.json.",
              "Protected search ablations compare original bluffing, no bluffs, measured-fold bluffs, single-barrel bluffs and fixed priors.",
              "", "## Limits and next action", ""]
    lines += ["- " + text for text in recommendation["limitations"]]
    lines += ["", "Inspect recommendation.json and the frozen config. Apply nothing automatically; any change is a separate review.", ""]
    text = "\n".join(lines)
    temporary = directory / "MORNING_REPORT.md.tmp"
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, directory / "MORNING_REPORT.md")
    return recommendation
