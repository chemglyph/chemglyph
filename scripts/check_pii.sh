#!/usr/bin/env bash
# Scan staged files and the configured commit identity for maintainer-provided
# sensitive patterns (names, emails, phone numbers, company names).
#
# Patterns live in scripts/pii_patterns.txt, which is intentionally gitignored
# so real identities never enter the repository. When the file is missing or
# contains no effective patterns, the scan is skipped with a warning.
set -u

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
patterns_file="$repo_root/scripts/pii_patterns.txt"

if [[ ! -f "$patterns_file" ]]; then
  echo "WARNING: $patterns_file not found; skipping PII scan." >&2
  exit 0
fi

effective_patterns="$(grep -c -v -E '^[[:space:]]*(#|$)' "$patterns_file" || true)"
if [[ "${effective_patterns:-0}" -eq 0 ]]; then
  echo "WARNING: $patterns_file has no active patterns; skipping PII scan." >&2
  exit 0
fi

status=0

identity="$(git config user.name 2>/dev/null) $(git config user.email 2>/dev/null)"
if printf '%s\n' "$identity" | grep -E -f "$patterns_file" -q; then
  echo "ERROR: PII pattern matched the configured git identity ($identity)." >&2
  status=1
fi

while IFS= read -r file; do
  if git show ":${file}" 2>/dev/null | grep -E -f "$patterns_file" -q; then
    echo "ERROR: PII pattern matched staged file: ${file}" >&2
    status=1
  fi
done < <(git diff --cached --name-only --diff-filter=ACM)

if [[ "$status" -eq 0 ]]; then
  echo "PII scan passed."
fi
exit "$status"
