#!/usr/bin/env bash
# Prints your identity: your GitHub login, lowercased. Your handoff is
# .agent/handoffs/<login>.md and your branches are <login>/<issue>-<slug>.
# Resolution order: 1. argument  2. $GH_LOGIN  3. gh api user
set -euo pipefail

login=${1:-${GH_LOGIN:-}}
[ -n "$login" ] || login=$(gh api user --jq .login 2>/dev/null || true)
if [ -z "$login" ]; then
  echo "Unknown identity: gh is not logged in. Fix: gh auth login (or export GH_LOGIN=<your-login>)" >&2
  exit 1
fi
echo "$login" | tr '[:upper:]' '[:lower:]'
