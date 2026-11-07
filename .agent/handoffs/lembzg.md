# Handoff — lembzg

Updated: 2026-11-07T01:04:18.042312+00:00
Status: ready
Task: #39 Research and correct heads-up all-in decisions (PRs #41, #43)
Branch: lembzg/39-allin-logic
Commit: 473c0d4 Record all-in research verification and packed arena results (#39)

## Done
- Researched PokerStars pot odds, HRC restricted HU Nash charts, TDA raise rules, GTO Wizard SPR and organisers @8b89346; design, sources and limitations in docs/ALL_IN.md.
- Pushed additive opponent-stack contract in PR #41, implementation b2fef33 and verification in PR #43; both draft, stacked on existing #34 candidate.
- Fixed contestable pots, unequal stacks, terminal-call chart bypass and margins, effective sizing, unbeatable fallback hands, completed-fold learning, partial observation bias, v0 model blinds, covering-bet inference and offline short-call EV.
- Independent review passed after resolving its findings; all acceptance evidence is in docs/all-in-change-ledger.md.

## In progress
- No implementation work remains in this requested scope. PR stack awaits normal shared-contract/dependency review; no merge or upload performed.

## Files touched
- core/allin.py plus optional opp_starting_stack in core/interface.py; bots/main/allin.py, bot.py, postflop.py, fallback.py, ev.py; v0 adapter/README.
- Arena build/translation/combo wrapper, harness stack producer, focused tests, research/architecture/API/environment/product docs and single change ledger.

## Tests
- Full dev Python 3.12: python -m pytest -q --disable-warnings → 215 passed (7 existing eval7 deprecation warnings).
- Final focused stdlib Python 3.14 → 58 passed; independent reviewer separately ran 79 dev / 44 stdlib checks, all passed.
- Baseline/candidate each 7,200 hands, seeds 101/202/303, duplicate 400-hand matches: zero illegal actions/errors. Per-run CIs and latency in PRODUCT.md; candidate maximum observed decision 154.30ms.
- Arena source main/combo each validate 40 hands with zero faults; pack fresh-process validation passes, 300KB/536KB. Unpacked payloads vs @shove each 400 hands, seeds 404/505: zero faults; thinking 7.7s/6.2s.
- scripts/check.sh → OK; git diff --check → clean; implementation PR GitHub quality gate passed before final documentation/handoff refresh.

## Bugs / blockers
- No blocking review findings. Range composition/priors and finite MC remain approximations; arena hides early SB folds, so that open-frequency context deliberately retains prior.
- Ordinary shove initiation and existing short-stack charts remain heuristic; no claim of universally optimal NLHE play. No-decision HandResults reuse last depth metadata, suitable for current fixed-stack event.

## Decisions & dependencies
- User explicitly requested deep research, fixes and push. No new runtime dependency or merge/submission authorized as part of this work.
- PR #41 base eulabet/combo-proto (#34); PR #43 base lembzg/allin-contract (#41). Shared contract delivered separately per repository rules.
- Combo source validation uses #32 helpers c457065a; #32 remains separate, no helper table copied into this repository.
- Dev/arena environments remain in /private/tmp/claude-501/-Users-arryl-Desktop-guh-poker/bdb98b8b-e1f1-428f-90b3-812c4dd5d3bb/scratchpad/. Benchmarks and packed smoke artifacts are scratch under /Users/arryl/Documents/Codex/2026-11-07/i-d/work/.

## Next steps
1. Review dependency stack #34 → #41 → #43; preserve contract-first shared review and rebase as prerequisites land.
2. For any future strategy claim, test held-out duplicate seeds and arena partial-observation behavior; retain measured CIs and latency.
3. Choose actual tournament entry/team separately; rebuild and pack only after approved integration. No submission was uploaded.
