#!/usr/bin/env bash
# Create/update the workflow labels on GitHub and remove the retired two-agent ones. Idempotent.
# Owner = issue assignee, progress = PR state, so there are no owner or status labels.
set -euo pipefail
export GH_REPO=${GH_REPO:-$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##')}  # never let gh pick the upstream remote

label() { gh label create "$1" --color "$2" --description "$3" --force; }

label "P0"       "b60205" "Needed to field a working bot — do first"
label "blocked"  "000000" "Cannot proceed; see latest comment"
label "question" "d876e3" "Open question for the @mentioned person; they remove the label when answered"
label "shared"   "fbca04" "Touches shared files — needs the integration captain's review"
label "contract" "e99695" "Changes docs/API.md"
label "decision" "bfdadc" "Architectural proposal needing approval"
label "env"      "0e8a16" "Needs the tournament system (not released yet)"

