import pytest

from tools.tune.space import fields
from tools.tune.stats import interval, reliability_failure, summarize, t_quantile


def row(candidate, block, family="a", score=0.0, **extra):
    return dict(id=f"{candidate}-{family}-{block}", kind="match", phase="test", candidate=candidate,
                family=family, opponent=family, block=block, seed=block, deals=200, ok=True,
                result=dict(status="complete", deals_completed=200, mean_bb=score,
                            hands_played=400, faults_a=0, faults_b=0, disabled_a=None, disabled_b=None), **extra)


@pytest.mark.parametrize("df,expected", [(1, 12.706204736), (9, 2.262157163), (30, 2.042272456)])
def test_student_t_known_quantiles(df, expected):
    assert t_quantile(0.975, df) == pytest.approx(expected, rel=1e-8)


def test_ci_with_one_block_does_not_claim_certainty():
    assert interval([1.0])["low"] is None
    assert interval([])["mean"] is None


def test_cluster_uncertainty_does_not_shrink_with_duplicated_opponent_noise():
    data = []
    for block in range(40):
        for family in ("a", "b", "c", "d"):
            data.extend([row("baseline", block, family),
                         row("v", block, family, score=(block % 5-2)/10)])
    one = summarize(data, "v", "test", ["a"])
    four = summarize(data, "v", "test", ["a", "b", "c", "d"])
    assert one["paired"] == four["paired"]
    assert four["paired"]["n"] == 40  # not 160 matches or 64,000 correlated hands


def test_missing_opponent_discards_entire_field_block_not_imputed_zero():
    data = [row("baseline", 0, "a"), row("v", 0, "a", 100),
            row("baseline", 0, "b")]
    result = summarize(data, "v", "test", ["a", "b"])
    assert result["paired"]["n"] == 0
    assert result["absolute"]["mean"] is None


def test_same_deal_baseline_is_subtracted_before_confidence_interval():
    data = []
    for b in range(40):
        huge_luck = (-1)**b * 50
        data += [row("baseline", b, score=huge_luck), row("v", b, score=huge_luck+0.1)]
    result = summarize(data, "v", "test", ["a"])
    assert result["paired"]["mean"] == pytest.approx(0.1)
    assert result["paired"]["low"] > 0.099


def test_faults_do_not_become_winning_evidence():
    data = [row("baseline", 0), row("v", 0, score=100)]
    data[1]["result"]["faults_a"] = 1
    result = summarize(data, "v", "test", ["a"])
    assert result["failures"] == 1
    assert result["paired"]["n"] == 0


def test_administrative_censoring_is_missing_evidence_but_not_a_bot_fault():
    r = row("v", 0, censored=True)
    r["result"]["status"] = "incomplete"
    assert not reliability_failure(r)
    r["result"]["faults_a"] = 1
    assert reliability_failure(r)  # a real fault is never hidden by a phase boundary


def test_final_field_contains_unseen_families_and_shifted_profiles():
    split = fields()
    assert len(split["search"]) == 8 and len(split["test"]) == 14
    assert len(set(split["test"]) - set(split["search"])) == 6
    assert {p["id"] for group in split["search"].values() for p in group}.isdisjoint(
        {p["id"] for group in split["validation"].values() for p in group})
