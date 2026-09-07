#!/usr/bin/env bash
# Re-encrypt the current master file and push it live to GitHub Pages.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$HERE/build.sh" "$@"
cd "$HERE"
git add -A docs
if git diff --cached --quiet; then
  echo "no changes to publish"
else
  git commit -q -m "Update planner ($(date '+%Y-%m-%d %H:%M'))"
  git push -q origin main
  echo "published — live in ~1 minute"
fi
