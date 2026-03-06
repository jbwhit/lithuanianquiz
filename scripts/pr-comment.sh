#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/pr-comment.sh <pr-number> [gh-pr-comment-options...] <<'BODY'
  Your markdown comment here.
  BODY

Examples:
  scripts/pr-comment.sh 6 <<'EOF'
  Addressed all review comments.

  - Ran `uv run --extra dev ruff check .`
  - Ran `uv run --extra dev pytest`
  EOF

  scripts/pr-comment.sh 6 --repo jbwhit/lithuanianquiz <<'EOF'
  Looks good.
  EOF
USAGE
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

pr_number="$1"
shift

if [[ ! "$pr_number" =~ ^[0-9]+$ ]]; then
  echo "Error: <pr-number> must be numeric (got: $pr_number)" >&2
  exit 1
fi

body="$(cat)"
if [[ -z "${body//[[:space:]]/}" ]]; then
  cat <<'ERR' >&2
Error: Empty comment body on stdin.
Pass a non-empty markdown body via stdin (recommended with a single-quoted heredoc).
ERR
  usage >&2
  exit 1
fi

printf '%s' "$body" | gh pr comment "$pr_number" "$@" --body-file /dev/stdin
