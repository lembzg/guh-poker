# Onboarding (≈10 min)

## 1. Access
- Ask lembzg for write access to `lembzg/guh-poker`, then accept the invitation.
- Install and log in: `git`, the GitHub CLI (`gh auth login`, then `gh auth setup-git`), Claude Code (`claude`).
- Check that `gh api user --jq .login` and `git config user.name` both show **your own** account.

## 2. Clone
```bash
git clone git@github.com:lembzg/guh-poker.git && cd guh-poker
```
You don't need git-lfs. Upstream's LFS data is gone (see CLAUDE.md), and `.lfsconfig` skips it.

## 3. Start your agent
Run `claude` in the repo and **accept the trust prompt** the first time. Until you do, the shared allowlist and SessionStart hook in `.claude/settings.json` are ignored. Then paste:

> You're joining a team of 3 Claude Code agents, one per person, coordinating only through GitHub in this repo. We're building a heads-up NLHE tournament bot on a DyypHoldem fork. Onboard yourself:
> 1. Read CLAUDE.md, then docs/PLAN.md, docs/PRODUCT.md, docs/ARCHITECTURE.md and docs/API.md. Don't read code yet. Later, read only the folder your ticket Owns.
> 2. Check that `gh api user --jq .login` and `git config user.name` are my account and that `gh repo view` works. If not, stop and tell me.
> 3. Run `chmod +x scripts/*.sh`. If `.agent/handoffs/<me.sh output>.md` is missing, create it from `_template.md`. Add me to the Team table in docs/PLAN.md. Run `./scripts/check.sh`, commit both files directly to main, `git pull --rebase`, and push.
> 4. Run `./scripts/status.sh` and answer anything waiting on me.
> 5. Give me a short status update: who I am, what's on the board, what's unclaimed and which ticket you recommend. Don't claim a ticket until I say go.

Returning teammates just prompt: *"Recover per CLAUDE.md and give me a status update."*

### Optional: drive from your phone
Run `claude remote-control --name guh-poker-<login>`, open it in the Claude mobile app, and turn on push notifications for permission prompts in `/config`. Keep the laptop awake with `caffeinate -dimsu &`.

## 4. Smoke test the coordination (5 min, once)
1. Everyone: *"Run status."* Pass: everyone sees the same `main` commit and everyone else's handoff line.
2. Someone who isn't the captain: *"Comment on the interface ticket asking the captain one question, with the `question` label."* Captain: *"Check status and handle anything waiting on you."* Pass: the captain finds and answers it without being told the issue number.

If any step needs a human to relay a message between agents, the protocol failed. Fix CLAUDE.md, not the agents.
