#!/usr/bin/env bash
# Pre-checkpoint inspection. Never commits or pushes — it tells you what's safe to.
# Usage: ./scripts/checkpoint.sh [login]          full check (exit 1 if handoff not ready)
#        ./scripts/checkpoint.sh --state [login]  git-state report only (used by resume.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

STATE_ONLY=0
[ "${1:-}" = "--state" ] && { STATE_ONLY=1; shift; }
ME=$(scripts/me.sh "${1:-}") || exit 1
HANDOFF=".agent/handoffs/$ME.md"
field() { grep -m1 -E "^$1:" "$HANDOFF" 2>/dev/null | sed -E "s/^$1:[[:space:]]*//"; }

branch=$(git branch --show-current); branch=${branch:-"(detached)"}
head=$(git log -1 --format='%h %s' 2>/dev/null || echo none)
SENSITIVE='(^|/)(\.env($|\.)|.*\.(pem|key|p12|pfx)$|id_(rsa|ed25519)|credentials|secrets?\.)'

echo "== Git state (branch $branch, HEAD $head)"
upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)
if [ -n "$upstream" ]; then
  unpushed=$(git log --oneline "$upstream"..HEAD)
  echo "   upstream: $upstream — unpushed commits: $(printf '%s' "$unpushed" | grep -c . || true)"
  [ -n "$unpushed" ] && printf '%s\n' "$unpushed" | sed 's/^/     /'
else
  echo "   upstream: none (branch never pushed — nothing here is visible to teammates)"
fi
list() { # label, git-command...
  local label=$1; shift; local out; out=$("$@")
  local n; n=$(printf '%s' "$out" | grep -c . || true)
  echo "   $label: $n"
  if [ "$n" -gt 0 ]; then printf '%s\n' "$out" | head -15 | sed 's/^/     /'; fi
}
list "staged (committed on next commit)" git diff --cached --name-status
list "unstaged (modified, not staged)"   git diff --name-status
list "untracked (not ignored)"           git ls-files --others --exclude-standard
stashes=$(git stash list | wc -l | tr -d ' ')
[ "$stashes" -gt 0 ] && echo "   stashes: $stashes (git stash list)"
risky=$( { git diff --cached --name-only; git diff --name-only; git ls-files --others --exclude-standard; } \
  | grep -E "$SENSITIVE" | grep -v '\.example$' | sort -u || true)
[ -n "$risky" ] && { echo "   ⚠ SENSITIVE-LOOKING — do NOT commit:"; printf '%s\n' "$risky" | sed 's/^/     /'; }

[ "$STATE_ONLY" -eq 1 ] && exit 0

echo "== Handoff check ($HANDOFF)"
problems=0
warn() { echo "   ⚠ $*"; problems=1; }
[ -f "$HANDOFF" ] || { warn "missing"; exit 1; }

updated=$(field Updated)
age=$(python3 - "$updated" <<'PY' 2>/dev/null || echo "?"
import sys; from datetime import datetime, timezone
print(max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(sys.argv[1])).total_seconds() // 60)))
PY
)
if [ "$age" = "?" ]; then warn "Updated: is not ISO-8601 (use: date -Iseconds)"
elif [ "$age" -gt 20 ]; then warn "Updated $age min ago — refresh it with verified progress"
else echo "   updated $age min ago"; fi

[ "$(field Branch)" = "$branch" ] || warn "Branch: says '$(field Branch)' but you are on '$branch'"
rec=$(field Commit | awk '{print $1}')
if [ -n "$rec" ] && [ "$rec" != none ]; then
  if ! git merge-base --is-ancestor "$rec" HEAD 2>/dev/null; then
    warn "Commit: $rec is not in this branch's history"
  else
    code_after=$(git diff --name-only "$rec" HEAD -- . ':!.agent/handoffs' | head -5)
    [ -n "$code_after" ] && warn "code committed after recorded Commit $rec (update Commit/Done): $(echo $code_after)"
  fi
fi
grep -q '^## Next steps' "$HANDOFF" && [ -n "$(sed -n '/^## Next steps/,$p' "$HANDOFF" | grep -E '^[0-9]+\.')" ] \
  || warn "## Next steps has no numbered steps"

echo "== Suggested checkpoint (review the lists above first)"
if [ "$branch" = main ]; then
  echo "   On main: commit ONLY $HANDOFF directly (docs exemption); put code on a branch first."
else
  echo "   git add <safe files> $HANDOFF && git commit -m 'wip(#<issue>): checkpoint — <what>' && git push -u origin $branch"
fi
[ "$problems" -eq 0 ] && echo "checkpoint: handoff READY" || { echo "checkpoint: handoff NOT READY"; exit 1; }
