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

# --- Regression: a repo with no detectable base branch at all (no
# master/develop branch, no origin remote) and no --since must still
# refuse an empty diff, not silently skip the check because DIFF_BASE
# resolved empty (code review finding) ---
mkdir -p "$DIR/nobase"
cd "$DIR/nobase"
git init -q -b weirdbranch .
git commit -q --allow-empty -m init

set +e
ERR3="$(bash "$SCRIPT" 2>&1 >/dev/null)"
CODE6=$?
set -e
[[ "$CODE6" -eq 3 ]] || FAIL "no base branch exit code" "expected exit 3, got $CODE6: $ERR3"
echo "$ERR3" | grep -qF "gather-context: empty diff against ; pass --since <work_start_sha> for a full review" \
  || FAIL "no base branch message" "expected the empty-diff refusal message, got: $ERR3"
PASS "a repo with no detectable base branch and no --since still refuses with exit 3"

# --- Regression: when git diff --quiet against the detected base branch
# itself fails (not merely reports an empty diff), the script must fail
# loud with git's own error, not swallow it into the generic empty-diff
# refusal (code review finding) ---
mkdir -p "$DIR/badref"
cd "$DIR/badref"
git init -q -b master .
git commit -q --allow-empty -m init
echo "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" > .git/refs/heads/master

set +e
ERR4="$(bash "$SCRIPT" 2>&1 >/dev/null)"
CODE7=$?
set -e
[[ "$CODE7" -ge 2 ]] || FAIL "git diff --quiet failure exit code" "expected exit >=2, got $CODE7: $ERR4"
echo "$ERR4" | grep -qF "fatal" \
  || FAIL "git diff --quiet failure message" "expected git's own fatal error, got: $ERR4"
echo "$ERR4" | grep -qF "gather-context: empty diff against" \
  && FAIL "git diff --quiet failure message" "expected git's own error, not the empty-diff refusal: $ERR4"
PASS "a git diff --quiet failure against the detected base branch fails loud instead of the empty-diff refusal"

# --- Regression (agoge #19): a full review diffs against the merge-base with
# the base branch, not its moved tip, so work the base gained since the branch
# point is never shown as removed ---
mkdir -p "$DIR/advanced"
cd "$DIR/advanced"
git init -q -b master .
echo "a" > a.txt
git add a.txt
git commit -q -m init
git checkout -q -b feature
echo "f" > feature.py
git add feature.py
git commit -q -m feature
git checkout -q master
echo "m" > moved.txt
git add moved.txt
git commit -q -m "base moved on"
git checkout -q feature

OUT5="$(bash "$SCRIPT")"
DIFF_FILE5="$(echo "$OUT5" | grep -o '[^ ]*review-diff-[^ ]*\.diff')"
[[ -n "$DIFF_FILE5" && -e "$DIFF_FILE5" ]] || FAIL "advanced master diff file" "stdout: $OUT5"
grep -qF "feature.py" "$DIFF_FILE5" \
  || FAIL "advanced master keeps the branch work" "feature.py missing from the diff"
grep -qF "moved.txt" "$DIFF_FILE5" \
  && FAIL "advanced master is not shown as removed" "moved.txt (added on master after the branch point) appears in the diff"
PASS "advanced master is not shown as removed"

# --- Regression (agoge #19): a repo whose base branch is `main` resolves a
# base instead of refusing for want of one ---
mkdir -p "$DIR/mainonly"
cd "$DIR/mainonly"
git init -q -b main .
git commit -q --allow-empty -m init
git checkout -q -b feature
echo "f" > feature.py
git add feature.py
git commit -q -m feature

set +e
OUT6="$(bash "$SCRIPT" 2>/dev/null)"
CODE8=$?
set -e
[[ "$CODE8" -eq 0 ]] || FAIL "main-only repo resolves a base" "expected exit 0, got $CODE8: $OUT6"
CONTEXT6="$(echo "$OUT6" | grep -o '[^ ]*review-context-[^ ]*\.md')"
grep -qF "full review (vs main)" "$CONTEXT6" \
  || FAIL "main-only repo resolves a base" "expected scope 'full review (vs main)' in $CONTEXT6"
PASS "main-only repo resolves a base"

# --- Regression (agoge #19): a --since ref that does not resolve warns on
# stderr instead of being dropped silently; the review still falls back to the
# branch base ---
set +e
ERR5="$(bash "$SCRIPT" --since "$INVALID_SINCE" 2>&1 >/dev/null)"
CODE9=$?
set -e
[[ "$CODE9" -eq 0 ]] || FAIL "bad --since still falls back" "expected exit 0, got $CODE9: $ERR5"
echo "$ERR5" | grep -qF -e "--since" \
  || FAIL "bad --since warns on stderr" "expected a warning naming --since, got: '$ERR5'"
echo "$ERR5" | grep -qF "$INVALID_SINCE" \
  || FAIL "bad --since warns on stderr" "expected the bad ref $INVALID_SINCE in the warning, got: '$ERR5'"
PASS "bad --since warns on stderr"
