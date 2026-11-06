#!/usr/bin/env bash
# One-screen coordination snapshot. Usage: ./scripts/status.sh [login]
set -euo pipefail
cd "$(dirname "$0")/.."
export GH_REPO=${GH_REPO:-$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}  # never let gh pick the upstream remote

ME=$(scripts/me.sh "${1:-}") || exit 1
REPO=$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##')

git fetch -q origin 2>/dev/null || echo "(fetch failed — showing cached state)"

echo "== $ME | main: $(git log -1 --format='%h %s (%cr)' origin/main 2>/dev/null || echo 'no commits')"
branch=$(git branch --show-current)
if git rev-parse -q --verify origin/main >/dev/null; then
  read -r behind ahead < <(git rev-list --left-right --count origin/main...HEAD)
  dirty=$([ -n "$(git status --porcelain)" ] && echo ", uncommitted changes" || true)
  echo "   local: $branch (behind main $behind, ahead $ahead$dirty)"
fi

none() { [ -n "$1" ] && printf '%s\n' "$1" || echo "  (none)"; }

echo "== Waiting on you (review requests; open 'question' items that mention you)"
none "$( { gh pr list --state open --search "review-requested:$ME" --json number,title,author \
           --jq '.[] | "  PR #\(.number) review: \(.title) (@\(.author.login))"'
         gh api -X GET search/issues -f q="repo:$REPO is:open label:question mentions:$ME" \
           --jq '.items[] | "  #\(.number) question: \(.title)"'; } 2>/dev/null)"

# One call for every open issue, split into sections locally.
issues=$(gh issue list --state open --limit 100 --json number,title,labels,assignees,comments)
show() { # title, jq filter selecting issues
  echo "== $1"
  none "$(jq -r --arg me "$ME" "[.[] | ($2)] | .[] |
    \"  #\(.number) \(.title)\" +
    ([.labels[].name] | map(\" [\" + . + \"]\") | join(\"\")) +
    ([.assignees[].login] | if length > 0 then \" @\" + join(\" @\") else \"\" end) +
    (if (.comments | length) > 0 then \" (last comment @\(.comments[-1].author.login))\" else \"\" end)" <<<"$issues")"
}
mine='select([.assignees[].login | ascii_downcase] | index($me))'
show "Blocked" 'select(any(.labels[]; .name == "blocked"))'
show "Your issues" "$mine"
show "Teammates' issues" "select((.assignees | length) > 0) | select(([.assignees[].login | ascii_downcase] | index(\$me)) | not)"
show "Unclaimed (assign yourself: gh issue edit <n> --add-assignee @me)" 'select((.assignees | length) == 0)'

echo "== Open PRs"
gh pr list --state open --json number,title,author,isDraft,reviewDecision,statusCheckRollup --jq '
  if length == 0 then "  (none)" else .[] |
  ([.statusCheckRollup[]? | (.conclusion // .state // "") | ascii_upcase]) as $c |
  (if ($c|length)==0 then "no-ci"
   elif any($c[]; .=="FAILURE" or .=="ERROR" or .=="CANCELLED" or .=="TIMED_OUT") then "CI FAIL"
   elif all($c[]; .=="SUCCESS" or .=="SKIPPED" or .=="NEUTRAL") then "CI ok"
   else "CI running" end) as $ci |
  "  #\(.number) \(.title) @\(.author.login)\(if .isDraft then " [draft]" else "" end)" +
  " — \($ci)\(if .reviewDecision == "APPROVED" then ", approved" elif .reviewDecision == "CHANGES_REQUESTED" then ", CHANGES REQUESTED" else "" end)" end'
