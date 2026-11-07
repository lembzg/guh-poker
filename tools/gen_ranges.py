"""Generate bots/myteam/ranges.py: 169-hand preflop strategy tables.

    python tools/gen_ranges.py

The reference (docs/heads-up-preflop-complete-reference.md, section 15.1) has
frequency targets but no hand-by-hand chart. So node FREQUENCIES below are
anchored to the reference, while the HANDS that fill them come from a heuristic
score: all-in equity vs the estimated opposing range, plus a playability bonus.
That composition is heuristic, not solver output.

Each table is solved to its target with 6/4/12 combo weights, using a soft edge
so that hands near a boundary are mixed (section 10.1).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bots" / "myteam"))

from equity_table import COMBOS, HANDS, INDEX, equity_vs_weights  # noqa: E402

OUT = ROOT / "bots" / "myteam" / "ranges.py"
RANK_ORDER = "23456789TJQKA"
TOTAL = 1326

# Target action frequencies, as a share of hands reaching the node.
SB_OPEN_TARGETS = {"SB_FIRST_IN": 0.88, "SB_FIRST_IN_TIGHT": 0.75, "SB_FIRST_IN_WIDE": 0.97}
# Open size in chips -> (assumed open range, 3-bet, call).
BB_VS_OPEN_TARGETS = {
    40: (0.92, 0.20, 0.58),
    50: (0.88, 0.22, 0.45),
    60: (0.75, 0.19, 0.38),
    80: (0.55, 0.15, 0.29),
    120: (0.35, 0.11, 0.19),
    200: (0.20, 0.08, 0.10),
    400: (0.10, 0.05, 0.05),
}
BLUFF_SHARE_OF_3BET = 0.22
BB_LIMP_TARGETS = {"BB_VS_LIMP": (0.24, 0.14), "BB_VS_LIMP_WIDE": (0.32, 0.18)}
SB_VS_3BET_CALL = 0.52

FOUR_BET_VALUE = {
    "AA": 1, "KK": 1, "QQ": 1, "AKs": 1, "AKo": 1,
    "JJ": 0.6, "TT": 0.35, "AQs": 0.6, "AQo": 0.2,
}
FOUR_BET_VALUE_WIDE = {
    **FOUR_BET_VALUE, "JJ": 1, "TT": 0.8, "AQs": 1, "AQo": 0.7, "99": 0.3,
}
FOUR_BET_BLUFF = {
    "A5s": 0.9, "A4s": 0.9, "A3s": 0.9, "A2s": 0.9,
    "K9s": 0.7, "K8s": 0.7, "K7s": 0.7, "K6s": 0.7, "K5s": 0.7,
}
FIVE_BET_JAM = {
    "AA": 1, "KK": 1, "QQ": 1, "AKs": 1, "AKo": 1,
    "JJ": 0.35, "TT": 0.15, "AQs": 0.3,
}
THREE_BET_BLUFF_ORDER = [
    "A5s", "A4s", "A3s", "A2s", "K5s", "K4s", "K3s", "K2s", "Q6s", "Q5s",
    "J7s", "T7s", "97s", "86s", "75s", "65s", "54s", "K9o", "Q9o", "K8o",
    "J9o", "Q8o", "K7o", "T9o", "K6o", "98o", "87o", "A5o", "A4o", "76o",
]


def parts(hand: str) -> tuple[int, int, bool, bool]:
    high = RANK_ORDER.index(hand[0]) + 2
    low = RANK_ORDER.index(hand[1]) + 2
    return high, low, hand[0] == hand[1], hand.endswith("s")


def playability(hand: str) -> float:
    """Equity realisation bonus: suited and connected hands play better."""
    high, low, pair, suited = parts(hand)
    if pair:
        return 0.02
    gap = high - low
    bonus = 0.025 if suited else 0.0
    bonus += {1: 0.012, 2: 0.008, 3: 0.004}.get(gap, 0.0)
    return bonus


def soft_top(scores, target, reach=None, soft=10.0, cap=None):
    """Probability per hand so the highest scorers total ``target`` combos."""
    reach = reach or {h: 1.0 for h in HANDS}
    cap = cap or {h: 1.0 for h in HANDS}
    order = sorted(HANDS, key=lambda h: -scores[h])

    def build(threshold):
        result = {}
        cumulative = 0.0
        for hand in order:
            mass = COMBOS[INDEX[hand]] * reach[hand] * cap[hand]
            midpoint = cumulative + mass / 2
            share = (threshold + soft - midpoint) / (2 * soft)
            result[hand] = max(0.0, min(1.0, share)) * cap[hand]
            cumulative += mass
        return result

    def mass_of(probabilities):
        return sum(
            COMBOS[INDEX[h]] * reach[h] * probabilities[h] for h in HANDS
        )

    low, high = -2 * soft, TOTAL + 2 * soft
    for _ in range(60):
        middle = (low + high) / 2
        if mass_of(build(middle)) < target:
            low = middle
        else:
            high = middle
    return build((low + high) / 2)


def weights_of(probabilities) -> list[float]:
    return [probabilities[h] for h in HANDS]


def strength_vs(probabilities) -> dict[str, float]:
    weights = weights_of(probabilities)
    return {h: equity_vs_weights(h, weights) for h in HANDS}


def main() -> None:
    eq_any = {h: equity_vs_weights(h, [1.0] * 169) for h in HANDS}
    sb_score = {h: eq_any[h] + playability(h) for h in HANDS}

    tables: dict[str, dict] = {}
    opens = {}
    for name, target in SB_OPEN_TARGETS.items():
        probability = soft_top(sb_score, target * TOTAL, soft=14)
        opens[name] = probability
        tables[name] = {
            h: (probability[h], 0.0, 1 - probability[h]) for h in HANDS
        }

    bb_vs_open = {}
    for size, (open_share, three_bet, call) in BB_VS_OPEN_TARGETS.items():
        opener = soft_top(sb_score, open_share * TOTAL, soft=14)
        versus = strength_vs(opener)
        bluff_mass = three_bet * BLUFF_SHARE_OF_3BET * TOTAL
        value_mass = three_bet * TOTAL - bluff_mass
        value = soft_top(versus, value_mass, soft=8)
        bluff = {h: 0.0 for h in HANDS}
        left = bluff_mass
        for hand in THREE_BET_BLUFF_ORDER:
            if left <= 0:
                break
            room = 1 - value[hand]
            combos = COMBOS[INDEX[hand]]
            take = min(room, 0.7, left / combos)
            bluff[hand] = max(0.0, take)
            left -= bluff[hand] * combos
        remaining = {h: 1 - value[h] - bluff[h] for h in HANDS}
        call_score = {h: versus[h] + playability(h) for h in HANDS}
        calling = soft_top(
            call_score, call * TOTAL, soft=12, cap=remaining
        )
        bb_vs_open[size] = {
            h: (value[h], bluff[h], calling[h],
                max(0.0, 1 - value[h] - bluff[h] - calling[h]))
            for h in HANDS
        }
    tables["BB_VS_OPEN"] = bb_vs_open

    # The 3-bet and 4-bet ranges below assume play against our own baseline.
    three_bet_range = {
        h: bb_vs_open[50][h][0] + bb_vs_open[50][h][1] for h in HANDS
    }

    junk_score = {}
    for hand in HANDS:
        high, low, pair, suited = parts(hand)
        connected = high - low <= 2
        if pair or suited or connected:
            junk_score[hand] = -1.0
        else:
            junk_score[hand] = high / 14 - low / 40
    for name, (value_share, bluff_share) in BB_LIMP_TARGETS.items():
        value = soft_top(eq_any, value_share * TOTAL, soft=10)
        remaining = {h: 1 - value[h] for h in HANDS}
        bluff = soft_top(
            junk_score, bluff_share * TOTAL, soft=8, cap=remaining
        )
        tables[name] = {
            h: (value[h], bluff[h], max(0.0, 1 - value[h] - bluff[h]))
            for h in HANDS
        }

    reach = opens["SB_FIRST_IN"]
    versus_three = strength_vs(three_bet_range)
    for name, value_map in (
        ("SB_VS_3BET", FOUR_BET_VALUE),
        ("SB_VS_3BET_WIDE", FOUR_BET_VALUE_WIDE),
    ):
        value = {h: float(value_map.get(h, 0.0)) for h in HANDS}
        bluff = {h: float(FOUR_BET_BLUFF.get(h, 0.0)) for h in HANDS}
        remaining = {h: max(0.0, 1 - value[h] - bluff[h]) for h in HANDS}
        score = {h: versus_three[h] + playability(h) for h in HANDS}
        reach_mass = sum(COMBOS[INDEX[h]] * reach[h] for h in HANDS)
        calling = soft_top(
            score, SB_VS_3BET_CALL * reach_mass, reach=reach, soft=10,
            cap=remaining,
        )
        tables[name] = {
            h: (value[h], bluff[h], calling[h],
                max(0.0, 1 - value[h] - bluff[h] - calling[h]))
            for h in HANDS
        }

    four_bet_range = {
        h: tables["SB_VS_3BET"][h][0] + tables["SB_VS_3BET"][h][1]
        for h in HANDS
    }
    versus_four = strength_vs(
        {h: reach[h] * four_bet_range[h] for h in HANDS}
    )
    bb_vs_four = {}
    for hand in HANDS:
        jam = float(FIVE_BET_JAM.get(hand, 0.0))
        # Price is 27.3% (240 into 880); require about 40% to allow for being out
        # of position, with a soft edge to mix boundary hands.
        share = max(0.0, min(1.0, (versus_four[hand] - 0.385) / 0.04))
        calling = (1 - jam) * share
        bb_vs_four[hand] = (jam, 0.0, calling, max(0.0, 1 - jam - calling))
    tables["BB_VS_4BET"] = bb_vs_four

    # Reached only when an exploit limps. Price is 35.7% (50 into 140).
    iso_table = {}
    iso_range = {
        h: tables["BB_VS_LIMP"][h][0] + tables["BB_VS_LIMP"][h][1]
        for h in HANDS
    }
    versus_iso = strength_vs(iso_range)
    for hand in HANDS:
        value = float(FOUR_BET_VALUE.get(hand, 0.0))
        share = max(0.0, min(1.0, (versus_iso[hand] - 0.38) / 0.04))
        calling = (1 - value) * share
        iso_table[hand] = (value, 0.0, calling, max(0.0, 1 - value - calling))
    tables["SB_VS_ISO"] = iso_table

    ranking = sorted(HANDS, key=lambda h: -eq_any[h])

    def round_row(row):
        return tuple(round(float(x), 3) for x in row)

    lines = [
        '"""GENERATED by tools/gen_ranges.py. Do not edit by hand.',
        "",
        "Row formats (probabilities):",
        "  SB_FIRST_IN*        (raise, limp, fold)",
        "  BB_VS_OPEN[size]    (3-bet value, 3-bet bluff, call, fold)",
        "  BB_VS_LIMP*         (raise value, raise bluff, check)",
        "  SB_VS_3BET*         (4-bet value, 4-bet bluff, call, fold)",
        "  BB_VS_4BET          (jam, unused, call, fold)",
        "  SB_VS_ISO           (raise, unused, call, fold)",
        '"""',
        "# ruff: noqa",
        "",
        f"EQ_ANY = { {h: round(eq_any[h], 4) for h in HANDS}!r}",
        f"RANKING = {tuple(ranking)!r}",
    ]
    for name, table in tables.items():
        if name == "BB_VS_OPEN":
            continue
        rows = {h: round_row(table[h]) for h in HANDS}
        lines.append(f"{name} = {rows!r}")
    lines.append("BB_VS_OPEN = {")
    for size, table in bb_vs_open.items():
        rows = {h: round_row(table[h]) for h in HANDS}
        lines.append(f"    {size}: {rows!r},")
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
