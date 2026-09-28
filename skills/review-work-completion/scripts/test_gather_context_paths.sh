#!/usr/bin/env bash
# Regression: gather-context.sh scopes both git diff calls to the paths
# listed in docs/dev/project-management/autopilot/review-paths when that
# marker file exists and is non-empty, and behaves exactly like today
# (unscoped whole-repo diff) when the marker is absent or empty.
set -u

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1 — $2"; exit 1; }

# Resolved from this script's own location, like test_gather_context_id.sh:
# the skill lives in the plugin now, not under ~/.claude/skills/.
SCRIPT="$(cd "$(dirname "$0")" && pwd)/gather-context.sh"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT

MARKER_PATH="docs/dev/project-management/autopilot/review-paths"

# Builds a fresh repo at $1 with a master base and a checked-out feature
# branch that touches a.py and b.py, so gather-context.sh finds a diff
# base without needing --since.
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

# --- Scenario 1: marker present and non-empty scopes both diff calls ---
setup_repo "$DIR/scoped"
mkdir -p "$(dirname "$MARKER_PATH")"
echo "a.py" > "$MARKER_PATH"

OUT="$(bash "$SCRIPT")"
CTX_FILE="$(echo "$OUT" | grep -o 'docs/dev/tmp/review-context-[^ ]*\.md')"
DIFF_FILE="$(echo "$OUT" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"

[ -n "$CTX_FILE" ] || FAIL "scoped: context path printed" "stdout: $OUT"
[ -n "$DIFF_FILE" ] || FAIL "scoped: diff path printed" "stdout: $OUT"
[ -f "$CTX_FILE" ] || FAIL "scoped: context file exists" "missing $CTX_FILE"
[ -f "$DIFF_FILE" ] || FAIL "scoped: diff file exists" "missing $DIFF_FILE"
PASS "marker present: both context and diff files are created"

grep -qF "_Diff scope: path-scoped review (1 paths from docs/dev/project-management/autopilot/review-paths)_" "$CTX_FILE" \
  || FAIL "scoped: scope line" "expected path-scoped scope line in $CTX_FILE: $(cat "$CTX_FILE")"
PASS "marker present: scope line names the marker and path count"

grep -q "^diff --git a/a.py b/a.py" "$DIFF_FILE" \
  || FAIL "scoped: diff has a.py" "expected a.py hunk in $DIFF_FILE: $(cat "$DIFF_FILE")"
PASS "marker present: diff includes the listed path"

if grep -q "b\.py" "$DIFF_FILE"; then
  FAIL "scoped: diff excludes b.py" "found b.py reference in $DIFF_FILE: $(cat "$DIFF_FILE")"
fi
PASS "marker present: diff excludes the unlisted path"

# --- Scenario 2: no marker file at all — unscoped, unchanged behavior ---
setup_repo "$DIR/no-marker"

OUT2="$(bash "$SCRIPT")"
CTX_FILE2="$(echo "$OUT2" | grep -o 'docs/dev/tmp/review-context-[^ ]*\.md')"
DIFF_FILE2="$(echo "$OUT2" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"

[ -f "$CTX_FILE2" ] || FAIL "no marker: context file exists" "missing $CTX_FILE2 in: $OUT2"
[ -f "$DIFF_FILE2" ] || FAIL "no marker: diff file exists" "missing $DIFF_FILE2 in: $OUT2"

grep -qE '_Diff scope: full review \(vs [^)]+\)_' "$CTX_FILE2" \
  || FAIL "no marker: scope line" "expected full review scope line in $CTX_FILE2: $(cat "$CTX_FILE2")"
PASS "no marker file: scope line stays unscoped full review"

grep -q "^diff --git a/a.py b/a.py" "$DIFF_FILE2" \
  || FAIL "no marker: diff has a.py" "expected a.py hunk in $DIFF_FILE2"
grep -q "^diff --git a/b.py b/b.py" "$DIFF_FILE2" \
  || FAIL "no marker: diff has b.py" "expected b.py hunk in $DIFF_FILE2"
PASS "no marker file: diff stays unscoped (whole-repo diff)"

# --- Scenario 3: empty marker file — behaves exactly as if absent ---
setup_repo "$DIR/empty-marker"
mkdir -p "$(dirname "$MARKER_PATH")"
: > "$MARKER_PATH"

OUT3="$(bash "$SCRIPT")"
CTX_FILE3="$(echo "$OUT3" | grep -o 'docs/dev/tmp/review-context-[^ ]*\.md')"
DIFF_FILE3="$(echo "$OUT3" | grep -o 'docs/dev/tmp/review-diff-[^ ]*\.diff')"

[ -f "$CTX_FILE3" ] || FAIL "empty marker: context file exists" "missing $CTX_FILE3 in: $OUT3"
[ -f "$DIFF_FILE3" ] || FAIL "empty marker: diff file exists" "missing $DIFF_FILE3 in: $OUT3"

grep -qE '_Diff scope: full review \(vs [^)]+\)_' "$CTX_FILE3" \
  || FAIL "empty marker: scope line" "expected full review scope line in $CTX_FILE3: $(cat "$CTX_FILE3")"
PASS "empty marker file: scope line stays unscoped full review"

grep -q "^diff --git a/a.py b/a.py" "$DIFF_FILE3" \
  || FAIL "empty marker: diff has a.py" "expected a.py hunk in $DIFF_FILE3"
grep -q "^diff --git a/b.py b/b.py" "$DIFF_FILE3" \
  || FAIL "empty marker: diff has b.py" "expected b.py hunk in $DIFF_FILE3"
PASS "empty marker file: diff stays unscoped (whole-repo diff)"
