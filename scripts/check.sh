#!/usr/bin/env bash
# Single quality gate. CI runs exactly this script; run it locally before every PR.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
err() { echo "✗ $*"; fail=1; }

# Tracked + new (non-ignored) files, so local runs catch files not yet committed.
files() { git ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' f; do [ -f "$f" ] && printf '%s\0' "$f"; done; }

# 1. Leftover merge-conflict markers
if files | xargs -0 grep -nE '^(<{7}|>{7})( |$)' 2>/dev/null; then
  err "merge conflict markers found"
fi

# 2. Committed secrets files (.env.example is fine)
if git ls-files | grep -E '(^|/)\.env($|\.)' | grep -v '\.example$'; then
  err ".env file is tracked — remove it and use .env.example"
fi

# 3. Large files (>5 MB) — keep the repo fast to clone
while IFS= read -r -d '' f; do
  size=$(wc -c <"$f" | tr -d ' ')
  [ "$size" -gt 5242880 ] && err "large file (>5MB): $f"
done < <(files)

# 4. Shell scripts parse
for s in scripts/*.sh; do bash -n "$s" || err "syntax error in $s"; done

# 5. JSON config parses
for j in .claude/settings.json; do
  [ -f "$j" ] && { python3 -m json.tool "$j" >/dev/null 2>&1 || err "invalid JSON: $j"; }
done

# 6. Handoff files exist and keep the machine-checked header keys
for h in .agent/handoffs/*.md; do
  [ -f "$h" ] || { err "no handoff files in .agent/handoffs/"; continue; }
  for k in Updated Status Task Branch Commit; do grep -qE "^$k:" "$h" || err "$h lacks '$k:' header"; done
  grep -q '^## Next steps' "$h" || err "$h lacks '## Next steps'"
done

# 7. Python parses (no deps needed).
if command -v python3 >/dev/null; then
  pydirs=$(ls -d core bots harness adapters tools tests 2>/dev/null || true)
  [ -n "$pydirs" ] && { python3 -m compileall -q $pydirs >/dev/null || err "Python syntax errors (python3 -m compileall -q $pydirs)"; }
fi

# 8. Install the requirements and run the tests.
if command -v python3 >/dev/null; then
  python3 -m pip install -q -r requirements.txt || err "could not install requirements.txt"
  python3 -m pytest -q || err "tests failed"
else
  err "python3 not found"
fi

if [ "$fail" -ne 0 ]; then echo "check: FAILED"; exit 1; fi
echo "check: OK"
