#!/usr/bin/env bash
# Regression: gather-context.sh writes its review files under the repo
# root's docs/dev/tmp/, not under whatever subdirectory it was run from.
# A run from skills/review-work-completion/scripts/ once left a stray
# docs/dev/tmp/ tree inside the plugin's scripts folder.
set -u

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1 — $2"; exit 1; }

SCRIPT="$(cd "$(dirname "$0")" && pwd)/gather-context.sh"
DIR="$(mktemp -d)"
trap 'rm -rf "$DIR"' EXIT

REPO="$DIR/repo"
mkdir -p "$REPO"
cd "$REPO"
git init -q -b master .
echo "base" > base.py
git add base.py
git commit -q -m init
git checkout -q -b feature
mkdir -p sub/deeper
echo "a" > sub/deeper/a.py
git add sub/deeper/a.py
git commit -q -m "add a"

cd "$REPO/sub/deeper"
OUT="$(bash "$SCRIPT")" || FAIL "run from subdirectory" "exit $?, stdout: $OUT"

[ ! -e "$REPO/sub/deeper/docs" ] \
  || FAIL "no stray tree in cwd" "found $REPO/sub/deeper/docs"
PASS "run from subdirectory: no docs/ tree created in the cwd"

CTX="$(ls "$REPO"/docs/dev/tmp/review-context-*.md 2>/dev/null)"
DIFF="$(ls "$REPO"/docs/dev/tmp/review-diff-*.diff 2>/dev/null)"
[ -n "$CTX" ] || FAIL "context at repo root" "none under $REPO/docs/dev/tmp; stdout: $OUT"
[ -n "$DIFF" ] || FAIL "diff at repo root" "none under $REPO/docs/dev/tmp; stdout: $OUT"
PASS "run from subdirectory: context and diff land in the repo root's docs/dev/tmp"

grep -q "^diff --git a/sub/deeper/a.py b/sub/deeper/a.py" "$DIFF" \
  || FAIL "diff content" "expected sub/deeper/a.py hunk in $DIFF"
PASS "run from subdirectory: diff covers the whole repo"
