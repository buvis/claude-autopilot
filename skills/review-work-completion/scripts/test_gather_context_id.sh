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
BASE_SHA="$(git rev-parse HEAD)"
# A diff base resolved from the current branch name is always the current
# branch itself here (no divergent branch exists), so every call below
# must pass --since an earlier sha to get a non-empty diff.
echo "x" > change.py
git add change.py
git commit -q -m change
mkdir -p docs/dev/tmp
echo "tasks" > docs/dev/tmp/review-tasks-00042c1.md
echo "prd" > docs/dev/tmp/review-prd-00042c1.md

OUT="$(bash "$SCRIPT" --since "$BASE_SHA" docs/dev/tmp/review-tasks-00042c1.md docs/dev/tmp/review-prd-00042c1.md)"
echo "$OUT" | grep -q "review-context-00042c1\.md" \
  || FAIL "prd-linked id" "expected review-context-00042c1.md in: $OUT"
PASS "context file reuses caller cycle id"

OUT2="$(bash "$SCRIPT" --since "$BASE_SHA")"
echo "$OUT2" | grep -qE "review-context-[0-9]{9,}-[0-9]+\.md" \
  || FAIL "fallback id" "expected epoch-pid name in: $OUT2"
PASS "fallback epoch-pid id when no prd file given"

# --- Regression: an empty full-review diff is refused, not silently
# reviewed (PRD 00244/00237) ---
mkdir -p "$DIR/clean"
cd "$DIR/clean"
git init -q -b master .
git commit -q --allow-empty -m init
HEAD_SHA="$(git rev-parse HEAD)"

set +e
ERR="$(bash "$SCRIPT" 2>&1 >/dev/null)"
CODE=$?
set -e
[[ "$CODE" -eq 3 ]] || FAIL "empty diff exit code" "expected exit 3, got $CODE: $ERR"
echo "$ERR" | grep -qF "gather-context: empty diff against master; pass --since <work_start_sha> for a full review" \
  || FAIL "empty diff message" "expected the refusal message, got: $ERR"
PASS "a full review without --since at a clean HEAD refuses with exit 3"

echo "y" > later.py
git add later.py
git commit -q -m later

OUT3="$(bash "$SCRIPT" --since "$HEAD_SHA")"
DIFF_FILE3="$(echo "$OUT3" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"
[[ -n "$DIFF_FILE3" ]] || FAIL "with --since diff path printed" "stdout: $OUT3"
[[ -s "$DIFF_FILE3" ]] || FAIL "with --since diff is non-empty" "expected a non-empty diff file: $DIFF_FILE3"
PASS "the same range with --since gets a non-empty diff, never refused"
