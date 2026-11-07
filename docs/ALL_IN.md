# Heads-up all-in decisions (#39)

This note records research read on 2026-11-07, the applicable decision rules,
implementation assumptions, and verification. It does not claim a solved strategy
for unrestricted heads-up no-limit hold'em.

## Research and applicability

1. [PokerStars Learn: pot odds](https://www.pokerstars.com/poker/learn/lesson/pot-odds/)
   establishes the call-price comparison: required equity is additional chips to
   call divided by the pot after calling. Equity is evaluated against a range,
   with ties contributing half. Position and future betting affect ordinary calls;
   those future betting risks disappear when calling ends the betting.
2. [HoldemResources: heads-up Nash push/fold](https://www.holdemresources.net/hune)
   solves a restricted game: SB may shove or fold, BB may call or fold. Effective
   stack is the smaller hand-start stack before blinds. The provider cautions
   that pure push/fold is generally suited to around 10bb, and particularly poor
   above 20bb. These charts are not ordinary raise-defence ranges and do not
   solve limped pots, deep reraises, or postflop play. We did not copy its data or
   replace ordinary short-stack charts in this change.
3. [GTO Wizard: stack-to-pot ratio](https://blog.gtowizard.com/stack-to-pot-ratio/)
   relates the amount at risk to the existing reward. A low SPR alone does not
   make every shove profitable: the opponent's continuing range still matters.
   A hand's equity against the whole range can exceed its equity when called.
4. [Poker TDA rules](https://www.pokertda.com/view-poker-tda-rules/)
   distinguish full raises and incomplete all-ins: insufficient increments do
   not reopen action for a player who has already acted. Uncalled bets are
   returned. These are a rules reference; actual SDK legality remains authoritative.
5. Organisers' source at `8b89346`:
   [duel.py](https://github.com/Manchester-AI-Society/poker_bot_infrastructure/blob/8b89346/arena/duel.py)
   resets stacks each hand and swaps seats on duplicate deals;
   [action_engine.py](https://github.com/Manchester-AI-Society/poker_bot_infrastructure/blob/8b89346/game/action_engine.py)
   exposes raise bounds, permits short all-in raises and emits call amounts as
   added chips. See [ENVIRONMENT.md](ENVIRONMENT.md) and [PRODUCT.md](PRODUCT.md)
   for the documented scoring and limited observations.

**Application to this event:** maximize expected chips. Stack resets and chip
scoring do not justify an ICM/bubble or survival premium. This is an inference
from the documented event format, not a general recommendation for payout-based
elimination tournaments. No rake or antes are modeled by the current contract.

## Exact accounting, conditional on estimated equity

Let `H` and `V` be our and villain's existing hand commitments, `S` our hand-start
stack, and `C = min(legal.call_amount, S-H)` our additional call. For two players:

- Contestable final pot: `T = 2 * min(H+C, V)`.
- Required equity: `C / T`.
- Incremental call EV: `equity * T - C`; fold EV is zero from this decision.

Previously committed chips are sunk costs but remain part of the reward. Chips
villain cannot get matched are not a reward we can win. Example: we have 10 in,
10 left, villain has 100 in; calling 10 contests 40, with 80 returned. With certain
victory the incremental call EV is 30, not 110.

Calling is terminal if it exhausts either player's remaining stack, including
when villain covers us while retaining chips. Missing raise rights alone are not
proof of an all-in. Actual opponent starting stack comes from the optional
`GameState.opp_starting_stack`; old callers retain the equal-stack assumption.
The arena and harness now populate the actual field.

Terminal calls use raw showdown equity without draw/implied-odds bonuses,
reverse-implied-odds cushions, maniac threshold discounts, or stack-off penalties.
Those considerations belong in the range estimate or in decisions with further
betting. River equity enumerates every live opponent combo; earlier streets use
bounded Monte Carlo. Sampling error can still flip marginal decisions. Exact
zero-EV ties choose call; profitable board chops are not folded.

Initiating a shove is a different problem. Our derivation, with `P` the current
pot, `A` our added contestable chips, `B` villain's extra call, `F` fold probability,
and `E` equity *against callers*, is:

`EV(shove) = F*P + (1-F)*(E*(P+A+B)-A)`.

Neither current range equity nor low SPR alone supplies `F` and `E`. This change
retains existing initiation heuristics rather than claiming to solve them. It
corrects their actual amounts: near-all-in rounding compares added chips with
remaining effective chips; minimum legal raises remain authoritative; bluff EV
uses the size actually emitted after clamping/rounding. The offline EV scorer
also subtracts unmatched excess on short calls.

## Preflop opponent range assumptions

MainBot and v0 handle terminal preflop calls before ordinary chart lookup. A
`JamModel` counts effective jams versus observed decisions separately by:

- opponent's SB/BB role;
- number of earlier preflop raises: zero, one, or at least two;
- effective hand-start depth: at most 15bb versus deeper.

An effective jam reaches the smaller starting stack, even if the aggressor has
chips left. Prior jam fractions are 10%/6%/3% for deep contexts and 50%/35%/20%
for shallow contexts, with eight pseudo-observations and a 2% lower bound. These
are explicit engineering priors, not equilibrium results. Posterior fraction is
`(jams + 8*prior)/(decisions + 8)`. The current observed decision counts once;
repeated snapshots do not multiply it. Known terminal decisions from completed
hands enter the denominator before clearing per-hand deduplication, including
folds after our raise. Match reset clears all accumulated evidence.

The fraction maps to a strongest-first `top_percent_range`; the equity engine
removes blocked cards and samples weighted combinations. This assumes a merged,
strength-selected jam range. A polarized range, limp trap or nonstandard bot may
violate it. Frequency alone cannot identify range composition. A future upgrade
should fit size/action-conditioned ranges and compare them on held-out deals,
not silently label this approximation "optimal".

The arena never exposes SB folds that occur before our first turn. Learning an
SB open-jam frequency from only visible raises would be selection-biased. Arena
wrappers mark the observation stream as partial, and that particular context
keeps its prior; reraises can still learn from observed actions and inferred
nonterminal folds. A harness with complete HandResults can learn both roles.
No invisible SB folds or final showdown cards are invented. Complete-hand
callbacks with no prior decision reuse the latest observed depth metadata; this
is appropriate for this fixed-stack, fixed-blind event, and needs a richer
HandResult contract for arbitrary changing-stack leagues. The combined
candidate routes terminal preflop decisions through guarded MainBot and feeds
external nonterminal snapshots into the same learner.

## Safety and scope

The fast fallback proves whether a made straight-or-better is unbeatable by
checking attainable higher categories, accounting for hero blockers and all
remaining board cards. It never folds such a hand to an oversized bet. It is a
conservative proof using current rank: it does not assume hero will improve.
Lower made hands retain the inexpensive existing fallback heuristics.

v0's original Quant source and ordinary chart policy are unchanged. Its adapter
handles terminal calls separately, using the jam model preflop and its own
existing opponent-model implementation postflop. Blinds are initialized from
every state before observations, rather than assuming 1/2 chips.

If our raise covers the opponent's entire stack, the absence of another callback
cannot establish a fold. The arena adapter now leaves that outcome unknown. A
nonterminal pre-river bet with no later turn can still infer a fold. The final
hand and indistinguishable consecutive-hand snapshots remain API limitations.

No new runtime dependency, table download, solver, upload or deployment is
introduced. Helper modules are included by the arena builder. The separate
additive contract PR must land before this stacked implementation.

## Verification

Focused tests cover full/short/covering terminal calls, unequal stacks, minimum
raises, profitable ties, deep chart bypass, contextual frequency deduplication,
known terminal folds, partial-observation bias, v0 blinds, actual bet sizing,
no fabricated covering-bet fold, and unmatched excess in offline EV.
An exhaustive opponent-combo comparison checks the fallback proof on sampled
river hands. Full development and stdlib-only Python 3.14 checks and independent
review are recorded in [the change ledger](all-in-change-ledger.md).
Paired duplicate multi-seed measurements belong in [PRODUCT.md](PRODUCT.md).
