#!/usr/bin/env bash
# Recovery brief after /compact, /clear, or a new session. Read-only.
# Usage: ./scripts/resume.sh [login]
set -euo pipefail
cd "$(dirname "$0")/.."
export GH_REPO=${GH_REPO:-$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}  # never let gh pick the upstream remote

ME=$(scripts/me.sh "${1:-}") || exit 1
HANDOFF=".agent/handoffs/$ME.md"
field() { grep -m1 -E "^$1:" "$2" 2>/dev/null | sed -E "s/^$1:[[:space:]]*//"; }

git fetch -q --prune origin 2>/dev/null || echo "(fetch failed — remote state may be stale)"

echo "######## RECOVERY BRIEF — $ME ########"
echo "== Your handoff ($HANDOFF)"
if [ -f "$HANDOFF" ]; then
  for f in Updated Status Task Branch Commit; do echo "   $f: $(field "$f" "$HANDOFF")"; done
  echo "   Next steps:"; sed -n '/^## Next steps/,$p' "$HANDOFF" | grep -E '^[0-9]+\.' | head -5 | sed 's/^/     /'
else
  echo "   ⚠ missing — new here? cp .agent/handoffs/_template.md $HANDOFF (see docs/ONBOARDING.md)."
  echo "     Otherwise reconstruct it from git log and your issues/PRs."
fi

echo "== Discrepancies (handoff vs reality)"
issues=0; d() { echo "   ⚠ $*"; issues=1; }
branch=$(git branch --show-current)
rec_branch=$(field Branch "$HANDOFF"); rec_commit=$(field Commit "$HANDOFF" | awk '{print $1}')
[ -n "$rec_branch" ] && [ "$rec_branch" != "$branch" ] && d "handoff says branch '$rec_branch', you are on '$branch'"
if [ -n "$rec_branch" ] && [ "$rec_branch" != main ]; then
  if git rev-parse -q --verify "origin/$rec_branch" >/dev/null; then
    [ "$(git rev-parse "origin/$rec_branch")" != "$(git rev-parse -q --verify "$rec_branch" 2>/dev/null || echo x)" ] \
      && d "local '$rec_branch' differs from origin/$rec_branch (pull or push needed?)"
  else
    pr=$(gh pr list --head "$rec_branch" --state all --limit 1 --json number,state --jq '.[0] | "#\(.number) \(.state)"' 2>/dev/null || true)
    case "$pr" in
      *MERGED) d "origin/$rec_branch is gone and PR $pr — work is on main; mark Done, start next task";;
      *) d "origin/$rec_branch not found (never pushed?) ${pr:+— PR $pr}";;
    esac
  fi
fi
if [ -n "$rec_commit" ] && [ "$rec_commit" != none ]; then
  if ! git cat-file -e "$rec_commit^{commit}" 2>/dev/null; then d "recorded Commit $rec_commit does not exist locally"
  elif ! git merge-base --is-ancestor "$rec_commit" HEAD; then d "recorded Commit $rec_commit is not in HEAD's history"
  else
    after=$(git diff --name-only "$rec_commit" HEAD -- . ':!.agent/handoffs' | head -5)
    [ -n "$after" ] && d "code changed after the recorded Commit (handoff may be stale): $(echo $after)"
  fi
fi
[ -n "$(git status --porcelain)" ] && d "working tree has uncommitted changes — see Git state; were they in the handoff?"
task_n=$(field Task "$HANDOFF" | grep -oE '#[0-9]+' | tr -d '#' | head -1 || true)
if [ -n "$task_n" ]; then
  st=$(gh issue view "$task_n" --json state,assignees --jq '.state + " @" + ([.assignees[].login]|join(" @"))' 2>/dev/null || echo "?")
  echo "   task #$task_n on GitHub: $st"
  case "$st" in CLOSED*) d "task #$task_n is CLOSED on GitHub — don't redo it";; esac
fi
[ "$issues" -eq 0 ] && echo "   none found"

./scripts/checkpoint.sh --state "$ME"

echo "== Teammates' latest PUSHED handoffs (their local work is invisible to you)"
# Teammates = handoff files on main + branch prefixes on origin. Each read from their newest branch.
{ git ls-tree --name-only origin/main .agent/handoffs/ 2>/dev/null | sed -E 's#.*/##; s#\.md$##'
  git for-each-ref --format='%(refname:short)' refs/remotes/origin/ | sed -nE 's#^origin/([^/]+)/.*#\1#p'
} | grep -vxE "_template|$ME" | sort -u | while read -r who; do
  src=$(git for-each-ref --sort=-committerdate --count=1 --format='%(refname:short)' "refs/remotes/origin/$who/")
  src=${src:-origin/main}
  if git cat-file -e "$src:.agent/handoffs/$who.md" 2>/dev/null; then
    tmp=$(mktemp); git show "$src:.agent/handoffs/$who.md" >"$tmp"
    echo "   $who: $(field Status "$tmp") | $(field Task "$tmp") | updated $(field Updated "$tmp") ($src)"
    rm -f "$tmp"
  fi
done

./scripts/status.sh "$ME"
echo "######## Next: read CLAUDE.md + your handoff in full, resolve every ⚠ above, then continue Next steps. ########"
