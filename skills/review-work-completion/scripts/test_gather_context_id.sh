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

# --- Regression: --since pointing at HEAD itself (an unambiguously valid
# ref that resolves to an empty diff) must never trip the refusal, even
# though the diff it produces is empty (PRD 00244 finding 2) ---
set +e
OUT4="$(bash "$SCRIPT" --since "$HEAD_SHA")"
CODE4=$?
set -e
[[ "$CODE4" -eq 0 ]] || FAIL "--since HEAD exit code" "expected exit 0, got $CODE4: $OUT4"
DIFF_FILE4="$(echo "$OUT4" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"
[[ -n "$DIFF_FILE4" ]] || FAIL "--since HEAD diff path printed" "stdout: $OUT4"
[[ -e "$DIFF_FILE4" ]] || FAIL "--since HEAD diff file created" "missing file: $DIFF_FILE4"
[[ ! -s "$DIFF_FILE4" ]] || FAIL "--since HEAD diff file empty" "expected an empty diff file, got content in: $DIFF_FILE4"
PASS "--since pointing at HEAD itself never refuses, even though the diff is empty"

# --- Regression: an unresolvable --since ref never actually applies, so a
# clean HEAD must still hit the same refusal a bare call would hit, not a
# silent fallback "success" (PRD 00244 findings 1 and 5) ---
INVALID_SINCE="0000000000000000000000000000000000000000"
set +e
ERR2="$(bash "$SCRIPT" --since "$INVALID_SINCE" 2>&1 >/dev/null)"
CODE5=$?
set -e
[[ "$CODE5" -eq 3 ]] || FAIL "invalid --since exit code" "expected exit 3, got $CODE5: $ERR2"
echo "$ERR2" | grep -qF "gather-context: empty diff against master; pass --since <work_start_sha> for a full review" \
  || FAIL "invalid --since message" "expected the no-since refusal message, got: $ERR2"
PASS "an unresolvable --since ref falls back to the branch base and still refuses an empty diff"

echo "y" > later.py
git add later.py
git commit -q -m later

OUT3="$(bash "$SCRIPT" --since "$HEAD_SHA")"
DIFF_FILE3="$(echo "$OUT3" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"
[[ -n "$DIFF_FILE3" ]] || FAIL "with --since diff path printed" "stdout: $OUT3"
[[ -s "$DIFF_FILE3" ]] || FAIL "with --since diff is non-empty" "expected a non-empty diff file: $DIFF_FILE3"
PASS "the same range with --since gets a non-empty diff, never refused"
