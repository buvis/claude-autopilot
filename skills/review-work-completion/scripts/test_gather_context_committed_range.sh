#!/usr/bin/env bash
# Regression: gather-context.sh's git calls must diff the committed range
# (DIFF_BASE..HEAD), not DIFF_BASE against the working tree. A single-ref
# `git diff "$DIFF_BASE"` compares that commit to the live working tree, so
# uncommitted edits and the dirty-tree-only case leak into a review that is
# supposed to show only what the PRD committed.
set -u

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1 — $2"; exit 1; }

SCRIPT="$(cd "$(dirname "$0")" && pwd)/gather-context.sh"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT

# Builds a fresh repo at $1 with a master base (base.py) and a checked-out
# feature branch that adds a.py and b.py, matching test_gather_context_paths.sh.
setup_repo() {
  mkdir -p "$1"
  cd "$1"
  git init -q -b master .
  echo "base" > base.py
  git add base.py
  git commit -q -m init
  git checkout -q -b feature
  echo "a" > a.py
  git add a.py
  git commit -q -m "add a"
  echo "b" > b.py
  git add b.py
  git commit -q -m "add b"
}

# --- Scenario 1: uncommitted + untracked dirt stays out of the diff ---
setup_repo "$DIR/scenario1"
echo "dirty" >> base.py
echo "scratch" > scratch.py

OUT1="$(bash "$SCRIPT")"
DIFF_FILE1="$(echo "$OUT1" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"

[ -n "$DIFF_FILE1" ] || FAIL "scenario1: diff path printed" "stdout: $OUT1"
[ -f "$DIFF_FILE1" ] || FAIL "scenario1: diff file exists" "missing $DIFF_FILE1"

grep -q "^diff --git a/a.py b/a.py" "$DIFF_FILE1" \
  || FAIL "scenario1: diff has a.py" "expected a.py hunk in $DIFF_FILE1: $(cat "$DIFF_FILE1")"
grep -q "^diff --git a/b.py b/b.py" "$DIFF_FILE1" \
  || FAIL "scenario1: diff has b.py" "expected b.py hunk in $DIFF_FILE1: $(cat "$DIFF_FILE1")"
if grep -q "base\.py" "$DIFF_FILE1"; then
  FAIL "scenario1: diff excludes base.py" "found base.py reference in $DIFF_FILE1: $(cat "$DIFF_FILE1")"
fi
if grep -q "scratch\.py" "$DIFF_FILE1"; then
  FAIL "scenario1: diff excludes scratch.py" "found scratch.py reference in $DIFF_FILE1: $(cat "$DIFF_FILE1")"
fi
PASS "uncommitted edits stay out of the diff"

# --- Scenario 2: --since diffs the committed range, not the working tree ---
setup_repo "$DIR/scenario2"
INIT_SHA="$(git -C "$DIR/scenario2" rev-parse master)"
echo "dirty" >> base.py

OUT2="$(bash "$SCRIPT" --since "$INIT_SHA")"
DIFF_FILE2="$(echo "$OUT2" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"

[ -n "$DIFF_FILE2" ] || FAIL "scenario2: diff path printed" "stdout: $OUT2"
[ -f "$DIFF_FILE2" ] || FAIL "scenario2: diff file exists" "missing $DIFF_FILE2"

grep -q "^diff --git a/a.py b/a.py" "$DIFF_FILE2" \
  || FAIL "scenario2: diff has a.py" "expected a.py hunk in $DIFF_FILE2: $(cat "$DIFF_FILE2")"
grep -q "^diff --git a/b.py b/b.py" "$DIFF_FILE2" \
  || FAIL "scenario2: diff has b.py" "expected b.py hunk in $DIFF_FILE2: $(cat "$DIFF_FILE2")"
if grep -q "base\.py" "$DIFF_FILE2"; then
  FAIL "scenario2: diff excludes base.py" "found base.py reference in $DIFF_FILE2: $(cat "$DIFF_FILE2")"
fi
PASS "--since diffs the committed range"

# --- Scenario 3: dirt alone on the base branch never makes a review ---
setup_repo "$DIR/scenario3"
git -C "$DIR/scenario3" checkout -q master
cd "$DIR/scenario3"
echo "dirty" >> base.py

set +e
ERR3="$(bash "$SCRIPT" 2>&1 1>/dev/null)"
EXIT3=$?
set -e

[ "$EXIT3" -eq 3 ] || FAIL "scenario3: exits 3" "got exit $EXIT3, stderr: $ERR3"
echo "$ERR3" | grep -qi "empty diff" \
  || FAIL "scenario3: empty diff refusal on stderr" "stderr: $ERR3"
PASS "dirt alone never makes a review"
