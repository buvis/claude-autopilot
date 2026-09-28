#!/usr/bin/env bash
# Regression: gather-context.sh reuses the caller's cycle id from
# review-prd-{id}.md so tmp review debris is PRD-linked (and dies with its
# PRD in purge-devtmp) instead of carrying an unlinkable epoch-pid name.
set -u

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1 — $2"; exit 1; }

# Resolved from this script's own location, like test_codex_doubt_guard.sh:
# the skill lives in the plugin now, not under ~/.claude/skills/.
SCRIPT="$(cd "$(dirname "$0")" && pwd)/gather-context.sh"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT
cd "$DIR"
git init -q .
git commit -q --allow-empty -m init
mkdir -p docs/dev/tmp
echo "tasks" > docs/dev/tmp/review-tasks-00042c1.md
echo "prd" > docs/dev/tmp/review-prd-00042c1.md

OUT="$(bash "$SCRIPT" docs/dev/tmp/review-tasks-00042c1.md docs/dev/tmp/review-prd-00042c1.md)"
echo "$OUT" | grep -q "review-context-00042c1\.md" \
  || FAIL "prd-linked id" "expected review-context-00042c1.md in: $OUT"
PASS "context file reuses caller cycle id"

OUT2="$(bash "$SCRIPT")"
echo "$OUT2" | grep -qE "review-context-[0-9]{9,}-[0-9]+\.md" \
  || FAIL "fallback id" "expected epoch-pid name in: $OUT2"
PASS "fallback epoch-pid id when no prd file given"
