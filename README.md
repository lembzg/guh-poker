# guh-poker

Our heads-up no-limit hold'em bot for a bot-vs-bot tournament. It plays solid default poker, adapts to exploit the opposing bot, and never acts illegally or times out.

- How we work (3 people, each with a Claude Code agent coordinating through GitHub): [CLAUDE.md](CLAUDE.md)
- New here? [docs/ONBOARDING.md](docs/ONBOARDING.md)
- Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · contracts: [docs/API.md](docs/API.md) · rules and results: [docs/PRODUCT.md](docs/PRODUCT.md)

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 -m harness.run --a main --b always_call --hands 2000 --seed 1 --duplicate
```
