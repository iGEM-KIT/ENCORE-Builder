#!/bin/bash
# Copies the changes of the commits since the last synced GitHub commit onto the GitLab main
# as ONE new commit. The two repositories have different histories (GitLab also has a few
# files of its own), so a plain push is rejected and a force push would destroy GitLab's history.
#
# Usage:  scripts/sync-gitlab.sh <last-synced-github-commit> "<commit message>"
# Needs a git remote named "gitlab" (git remote add gitlab <url of the GitLab repository>).
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <last-synced-github-commit> \"<commit message>\"" >&2
  exit 1
fi
base="$1"
message="$2"

git fetch gitlab
work="$(mktemp -d)"
trap 'git worktree remove --force "$work" 2>/dev/null || true; git branch -D gitlab-sync >/dev/null 2>&1 || true' EXIT

git worktree add -q -b gitlab-sync "$work" gitlab/main
git diff "$base" HEAD > "$work.patch"
(cd "$work" && git apply --index "$work.patch" && git commit -q -m "$message" && git push gitlab gitlab-sync:main)
rm -f "$work.patch"
