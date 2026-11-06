# Tournament environment: reverse-engineering notes

_Empty until we receive the system. Whoever holds the `env` ticket owns this file. Everyone else adds findings by commenting on that ticket, or with a tiny direct commit if the finding is obviously right._

Record **observed facts** with how you verified them: "sent a raise of 1 chip below the min-raise → server replied `ERR invalid`". Keep guesses in a separate section.

## Protocol
- Transport (TCP/HTTP/websocket/stdin-stdout/function call):
- Message format and an annotated sample of one full hand:
- How actions are encoded (fold/check/call/raise; raise-to vs raise-by; hand-total vs street-total):
- How the hand result and the opponent's cards (on showdown) are reported:

## Rules as enforced (vs rules as written)
- Min-raise / all-in edge cases:
- Time-out behaviour:
- Illegal-action behaviour:

## Mapping to our contract
How each environment field maps to `GameState` / `Action` in `docs/API.md`. Note any field the contract is missing.

## Exploitable observations
Anything about the environment or the likely opponents we could use: deterministic deck seeds, fixed hand counts, time budget slack, opponent tendencies.

## Open questions
