import json

from tools.tune.common import RULES
from tools.tune.report import export
from tools.tune.space import DEFAULT, fields


def record(candidate, family, block, score):
    return dict(id=f"{candidate}-{family}-{block}", kind="match", phase="test", candidate=candidate,
                family=family, opponent="test-"+family, block=block, seed=block, deals=200, ok=True,
                result=dict(status="complete", deals_completed=200, mean_bb=score, hands_played=400,
                            faults_a=0, faults_b=0, disabled_a=None, disabled_b=None))


def inputs():
    plan = dict(fields=fields(), plan_hash="p", repo_sha="repo", arena_sha="arena", min_test_blocks=30,
                practical_delta=0.005, max_family_regression=0.10, rules=RULES)
    state = dict(phase="complete", selected="v", source_integrity=True, selection_pack_validated=True,
                 candidates={"v": dict(config={**DEFAULT, "bluff_mode": "off"})})
    return plan, state


def test_search_winner_cannot_be_promoted_after_negative_blind_test(tmp_path):
    plan, state = inputs()
    rows = []
    for block in range(35):
        for family in plan["fields"]["test"]:
            rows += [record("baseline", family, block, 1), record("v", family, block, 0.9)]
    result = export(tmp_path, plan, state, rows, final=True)
    assert result["status"] == "keep_defaults_no_confirmed_replacement"
    assert not result["parameters_applied"]
    assert result["suggested_config"] == DEFAULT
    assert len((tmp_path / "reports/matches.csv").read_text().splitlines()) == len(rows)+1


def test_positive_test_needs_minimum_blocks_and_no_faults(tmp_path):
    plan, state = inputs()
    rows = []
    for block in range(35):
        for family in plan["fields"]["test"]:
            rows += [record("baseline", family, block, 0), record("v", family, block, 0.1)]
    result = export(tmp_path, plan, state, rows, final=True)
    assert result["status"] == "confirmed_on_synthetic_field"
    assert not result["bot_files_changed"]
    rows[-1]["result"]["faults_a"] = 1
    assert export(tmp_path, plan, state, rows, final=True)["status"] == "keep_defaults_no_confirmed_replacement"
    rows = [r for r in rows if r["block"] < 5]
    assert export(tmp_path, plan, state, rows, final=True)["status"] == "keep_defaults_no_confirmed_replacement"


def test_report_before_start_is_safe_and_clear(tmp_path):
    plan, _ = inputs()
    state = dict(phase="not_started", candidates={})
    result = export(tmp_path, plan, state, [])
    assert result["test"] is None
    assert "Final test not available" in (tmp_path / "reports/MORNING_REPORT.md").read_text()
    assert json.loads((tmp_path / "reports/recommendation.json").read_text())["parameters_applied"] is False


def test_missing_final_internal_counters_cannot_confirm_winner(tmp_path):
    plan, state = inputs()
    rows = [record(c, f, b, 0.1 if c == "v" else 0)
            for b in range(35) for f in plan["fields"]["test"] for c in ("baseline", "v")]
    rows[-1]["telemetry_complete"] = False
    result = export(tmp_path, plan, state, rows, final=True)
    assert result["status"] == "keep_defaults_no_confirmed_replacement"
    assert result["test"]["failures"] == 1
