# Overnight sparring report

Status: **complete**. Confirmed replacement: **no**. No production changes applied.

All scores below are bb/100; family-balanced paired differences compare the same deals with defaults.
Completed match records: 29445; healthy: 29445; played hands: 11,778,000.

Frozen runner c559880ae9ba74de425574778040e114fdec68a6; bot 1177bfe68b9319baafd017f608fe5debba438899; arena 8b893461c0d020ae8ed9c78aed298cd698e025a0; plan e1b0fee3cbb851be07733cd0c8a8b42cce2dd6c8496ed08b0bff3f76299a9808.

## Final test (locked finalist, fresh seeds and unseen families)

Finalist `v-7175bd690aa6`: paired improvement **+14.706 [+12.339, +17.073]**; 305 complete independent field blocks.
Absolute equal-family score: +283.503 [+279.263, +287.743].

| Family | Absolute bb/100 [95% CI] | Paired improvement [95% CI] | Blocks |
|---|---:|---:|---:|
| combined_reference | -74.563 [-80.524, -68.602] | -74.563 [-80.524, -68.602] | 305 |
| delayed_bluff | +376.847 [+365.813, +387.880] | +88.860 [+79.369, +98.351] | 305 |
| equity | +359.662 [+349.815, +369.509] | +29.086 [+23.189, +34.983] | 305 |
| main_reference | -51.096 [-57.201, -44.990] | -53.073 [-58.863, -47.284] | 305 |
| maniac | +616.087 [+593.850, +638.323] | +26.172 [+6.165, +46.180] | 305 |
| minraise | +1361.850 [+1343.854, +1379.847] | +36.837 [+24.133, +49.541] | 305 |
| nit | +67.481 [+64.911, +70.050] | -6.397 [-7.662, -5.132] | 305 |
| postflop_jammer | +181.816 [+166.899, +196.733] | -0.119 [-8.205, +7.966] | 305 |
| shove | +96.267 [+84.286, +108.248] | +0.006 [-0.208, +0.221] | 305 |
| starter | +126.545 [+119.471, +133.618] | +12.519 [+9.113, +15.925] | 305 |
| station | +469.434 [+459.538, +479.330] | +111.366 [+103.333, +119.399] | 305 |
| switcher | +64.881 [+61.751, +68.011] | +0.666 [-1.595, +2.928] | 305 |
| threebet | +162.768 [+153.491, +172.045] | +7.507 [-0.249, +15.264] | 305 |
| trapper | +211.065 [+201.980, +220.151] | +27.021 [+21.999, +32.042] | 305 |

Alternative family-weight sensitivity: 89.8% of Dirichlet(1) weights gave positive estimated improvement. This is exploratory, not a win probability.
Leaving any one family out: +7.271 to +21.573 bb/100.
Worst 5% of field-block differences average: -27.722 bb/100.

## Exploration and validation (not independent proof of superiority)

| Phase | Candidate | Paired bb/100 [nominal CI] | Blocks | Failed jobs |
|---|---|---:|---:|---:|
| search | v-985754155d03 | +56.036 [-50.537, +162.609] | 2 | 0 |
| search | v-ea1900bfe10a | +53.692 [-372.482, +479.866] | 2 | 0 |
| search | v-14ad9aa63342 | +53.341 [-385.957, +492.638] | 2 | 0 |
| search | v-a7200a8ff9b4 | +48.506 [-89.237, +186.249] | 2 | 0 |
| search | v-252f3b5906f7 | +46.943 [-484.226, +578.112] | 2 | 0 |
| search | v-d70c0820062e | +44.609 [-183.963, +273.182] | 2 | 0 |
| search | v-ff788b5d1519 | +42.794 [+0.569, +85.020] | 6 | 0 |
| search | v-156f8b9b0bd5 | +42.535 [-231.810, +316.880] | 2 | 0 |
| search | v-8673ae8ec54e | +41.370 [-131.236, +213.976] | 2 | 0 |
| search | v-b4006365faba | +41.070 [-73.583, +155.724] | 2 | 0 |
| search | v-1c8343876b06 | +39.361 [-208.589, +287.311] | 2 | 0 |
| search | v-e65549e36908 | +38.529 [+23.049, +54.009] | 6 | 0 |
| validation | v-7175bd690aa6 | +31.890 [+27.436, +36.345] | 188 | 0 |
| validation | v-e4b3759ccbca | +31.732 [+27.098, +36.366] | 188 | 0 |
| validation | v-7d276cd3abe3 | +27.877 [+23.080, +32.674] | 188 | 0 |
| validation | baseline | +0.000 [+0.000, +0.000] | 188 | 0 |

## Reliability and speed

Finalist decisions: 3,781,803; mean latency ms: 10.367864376795048; max ms: 144.683; p95/p99 histogram upper bounds ms: 50 / 50.
Maximum observed half-bank usage: 34.7%.
Internal fallback/bookkeeping counters: {}; partial telemetry halves: 0.
Descriptive position outcomes (not hand-IID confidence intervals): {'big_blind': {'hands': 854000, 'net_bb': 1907728.300000003}, 'button': {'hands': 854000, 'net_bb': 2934503.349999999}}.
Full faults, disabled reasons, timing and results—including failed jobs—are in matches.csv/results.sqlite.
Action counts, hand outcomes, worst losses and full evaluator-only hand histories are saved with each job.
Parameter dictionaries for every candidate are in configurations.json; the locked finalist is in recommendation.json.
Protected search ablations compare original bluffing, no bluffs, measured-fold bluffs, single-barrel bluffs and fixed priors.

## Limits and next action

- Synthetic opponents cannot represent unknown tournament entrants exactly.
- Only the locked finalist has a confirmatory final-test interpretation.
- Development rankings and per-family intervals are exploratory; no hand-level IID inference.
- Latency quantiles are histogram upper bounds including process startup.
- 8-hour deadline/cancellation may leave an incomplete last block; coverage is shown, not imputed.

Inspect recommendation.json and the frozen config. Apply nothing automatically; any change is a separate review.
