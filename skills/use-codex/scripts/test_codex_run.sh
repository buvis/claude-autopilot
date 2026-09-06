#!/usr/bin/env bash
# Test harness for codex-run.sh (macOS bash 3.2 compatible). Stubs the `codex`
# binary on PATH and asserts on its OBSERVABLE argv/stdin, never on
# codex-run.sh's internals. Extend this file with more assertions/invocations
# as codex-run.sh grows new behavior (thread-id capture, resume, etc.).
set -u

CODEX_RUN_SH="$(cd "$(dirname "$0")" && pwd)/codex-run.sh"
[ -n "${1:-}" ] && CODEX_RUN_SH="$1"

# ── assert helpers ────────────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
PASS() { echo "PASS: $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
FAIL() { echo "FAIL: $1 -- $2"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

# Reads FILE (one argv token per line, as the stub writes it) into the
# global ARGV_ARR indexed array. Bash 3.2 has no mapfile/readarray.
read_argv_array() {
    ARGV_ARR=()
    local _line
    while IFS= read -r _line; do
        ARGV_ARR+=("$_line")
    done < "$1"
}

# True (exit 0) if FILE contains NEEDLE immediately followed by VALUE as
# consecutive argv tokens.
argv_has_pair() {
    local file="$1" needle="$2" value="$3" prev="" tok
    while IFS= read -r tok; do
        if [ "$prev" = "$needle" ] && [ "$tok" = "$value" ]; then
            return 0
        fi
        prev="$tok"
    done < "$file"
    return 1
}

# True (exit 0) if STUB_STDIN_FILE holds exactly PROMPT's bytes, no more, no
# less (a diff against PROMPT's exact bytes already proves no sentinel
# wrapper stdin leaked through).
child_stdin_is_prompt() {
    local prompt="$1" expected="$STUBDIR/_stdin_expected.tmp"
    printf '%s' "$prompt" > "$expected"
    diff -q "$expected" "$STUB_STDIN_FILE" >/dev/null 2>&1
}

# ── cleanup registry ────────────────────────────────────────────────────────────
_DIRS=()
cleanup() {
    local d
    for d in "${_DIRS[@]+"${_DIRS[@]}"}"; do
        rm -rf "$d"
    done
}
trap cleanup EXIT

# ── stub `codex` binary on PATH ────────────────────────────────────────────────
STUBDIR=$(mktemp -d)
_DIRS+=("$STUBDIR")

STUB_ARGV_FILE="$STUBDIR/argv.log"
STUB_STDIN_FILE="$STUBDIR/stdin.log"

cat > "$STUBDIR/codex" <<'STUB'
#!/bin/bash
printf '%s\n' "$@" > "$STUB_ARGV_FILE"
cat > "$STUB_STDIN_FILE"

# Multi-invocation bookkeeping (opt-in: only when the caller sets
# STUB_ALL_ARGV_FILE). Appends this call's argv to a cumulative log with a
# delimiter, and bumps an invocation counter, so tests that trigger more
# than one codex call per run (resume -> fresh fallback) can verify BOTH
# calls happened.
if [ -n "${STUB_ALL_ARGV_FILE:-}" ]; then
    COUNT=$(cat "$STUB_INVOKE_COUNT_FILE" 2>/dev/null)
    COUNT=${COUNT:-0}
    COUNT=$((COUNT + 1))
    printf '%s' "$COUNT" > "$STUB_INVOKE_COUNT_FILE"
    {
        printf '%s\n' "=== invocation $COUNT ==="
        printf '%s\n' "$@"
    } >> "$STUB_ALL_ARGV_FILE"
fi

# Simulate codex's JSON path when --output-last-message <FILE> is present:
# write the review text to that file and emit JSONL events on stdout. Legacy
# (no --output-last-message) path is untouched below.
LAST_MSG_FILE=""
PREV_ARG=""
IS_RESUME=""
for arg in "$@"; do
    if [ "$PREV_ARG" = "--output-last-message" ]; then
        LAST_MSG_FILE="$arg"
    fi
    if [ "$arg" = "resume" ]; then
        IS_RESUME=1
    fi
    PREV_ARG="$arg"
done

# Forced-failure hooks: STUB_FAIL_RESUME/STUB_FAIL_FRESH make this
# invocation exit non-zero (distinguished by whether its argv is a resume
# call), simulating a real codex failure. A forced-fail invocation writes
# neither the output file nor the JSONL events, like a real failed run.
if [ -n "$IS_RESUME" ] && [ -n "${STUB_FAIL_RESUME:-}" ]; then
    exit "$STUB_FAIL_RESUME"
fi
if [ -z "$IS_RESUME" ] && [ -n "${STUB_FAIL_FRESH:-}" ]; then
    exit "$STUB_FAIL_FRESH"
fi

if [ -n "$LAST_MSG_FILE" ]; then
    printf '%s' "STUB REVIEW OUTPUT" > "$LAST_MSG_FILE"
    # STUB_SUPPRESS_THREAD_STARTED (opt-in): omit the thread.started event,
    # simulating a resumed session that doesn't re-announce its thread id.
    # Default (unset) behavior is unchanged for every other test.
    if [ -z "${STUB_SUPPRESS_THREAD_STARTED:-}" ]; then
        echo '{"type":"thread.started","thread_id":"11111111-2222-3333-4444-555555555555"}'
    fi
    echo '{"type":"item.completed"}'
    echo '{"type":"turn.completed"}'
fi

exit 0
STUB
chmod +x "$STUBDIR/codex"

# codex-run.sh re-prepends mise's own PATH ahead of ours whenever `mise` is
# reachable, and mise's PATH includes /opt/homebrew/bin (the REAL codex
# binary), which would shadow the stub. Excluding mise's location from the
# PATH we hand to codex-run.sh keeps that branch inert, so lookup always
# resolves to our stub.
RUN_PATH="$STUBDIR:/usr/bin:/bin"

# Resets the stub capture files, then runs codex-run.sh against the stub with
# args "$@". Extra STUB_*/env var prefixes and redirections stay at the call
# site, exactly as they did before this reset-and-invoke boilerplate was
# extracted.
run_codex_run() {
    : > "$STUB_ARGV_FILE"
    : > "$STUB_STDIN_FILE"
    PATH="$RUN_PATH" STUB_ARGV_FILE="$STUB_ARGV_FILE" STUB_STDIN_FILE="$STUB_STDIN_FILE" \
        bash "$CODEX_RUN_SH" "$@"
}

# =============================================================================
# Single invocation feeds both assertions below: sentinel, non-empty, non-EOF
# stdin on the wrapper's own stdin, no permission flags.
# =============================================================================
SENTINEL_PROMPT="analyze the sentinel case"
run_codex_run "$SENTINEL_PROMPT" <<< 'SENTINEL_STDIN_DATA'

# 1. Codex child stdin must be exactly the prompt, delivered via a pipe --
#    never the wrapper's own stdin. Without the guard the child inherits the
#    wrapper's stdin and would read SENTINEL_STDIN_DATA.
if child_stdin_is_prompt "$SENTINEL_PROMPT"; then
    PASS "codex child stdin is exactly the prompt, never the wrapper's stdin"
else
    FAIL "codex child stdin is exactly the prompt, never the wrapper's stdin" \
         "stub captured stdin: $(cat "$STUB_STDIN_FILE" 2>/dev/null | tr '\n' '|'); expected exactly the prompt '$SENTINEL_PROMPT' with no trace of SENTINEL_STDIN_DATA"
fi

# 2. Argv regression lock: the prompt moves off argv entirely, replaced by
#    the literal "-" positional that tells codex to read stdin.
EXPECTED_ARGV_FILE="$STUBDIR/argv.expected"
printf '%s\n' "exec" "--skip-git-repo-check" "--sandbox" "read-only" "-" > "$EXPECTED_ARGV_FILE"

if diff -q "$EXPECTED_ARGV_FILE" "$STUB_ARGV_FILE" >/dev/null 2>&1; then
    PASS "no-flag argv is exactly: codex exec --skip-git-repo-check --sandbox read-only -"
else
    FAIL "no-flag argv is exactly: codex exec --skip-git-repo-check --sandbox read-only -" \
         "got: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
fi

# =============================================================================
# -f PROMPTFILE: a prompt whose first line looks like a CLI flag (leading
# dash) must never be argv-parsed -- it is delivered to the codex child
# verbatim on stdin, byte for byte, exactly like any other prompt.
# =============================================================================
DASH_PROMPT_FILE="$STUBDIR/dash_prompt.txt"
printf '%s\n' "- [ ] item" > "$DASH_PROMPT_FILE"
run_codex_run -f "$DASH_PROMPT_FILE" > /dev/null 2>/dev/null < /dev/null

# 2b. Leading-dash prompt file: codex child stdin is the file's bytes,
#     verbatim -- never argv-parsed as a flag.
if diff -q "$DASH_PROMPT_FILE" "$STUB_STDIN_FILE" >/dev/null 2>&1; then
    PASS "-f PROMPTFILE with a leading-dash first line: codex child stdin is the file's bytes verbatim"
else
    FAIL "-f PROMPTFILE with a leading-dash first line: codex child stdin is the file's bytes verbatim" \
         "stub captured stdin: $(cat "$STUB_STDIN_FILE" 2>/dev/null | tr '\n' '|'); expected file contents: $(cat "$DASH_PROMPT_FILE" 2>/dev/null | tr '\n' '|')"
fi

# =============================================================================
# --emit-thread-id JSON path: codex invoked with --json/--output-last-message,
# thread id captured from the thread.started event, review text delivered via
# -o (tee-parity), raw JSONL surfaced only as stderr liveness markers.
# =============================================================================
FIXED_UUID="11111111-2222-3333-4444-555555555555"
THREAD_PROMPT="analyze the thread case"
THREAD_ID_FILE="$STUBDIR/thread_id.out"
JSON_OUTFILE="$STUBDIR/review.out"
JSON_STDOUT_FILE="$STUBDIR/thread.stdout"
JSON_STDERR_FILE="$STUBDIR/thread.stderr"
rm -f "$THREAD_ID_FILE" "$JSON_OUTFILE"

run_codex_run --emit-thread-id "$THREAD_ID_FILE" -o "$JSON_OUTFILE" "$THREAD_PROMPT" \
    > "$JSON_STDOUT_FILE" 2> "$JSON_STDERR_FILE" <<< 'SENTINEL_STDIN_DATA'

# 3. codex is invoked on the JSON path: argv contains --json.
if grep -qxF -- "--json" "$STUB_ARGV_FILE"; then
    PASS "--emit-thread-id: codex argv contains --json"
else
    FAIL "--emit-thread-id: codex argv contains --json" \
         "argv: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
fi

# 4. --output-last-message's value is exactly the -o target (the review text
#    is delivered via --output-last-message, not plain stdout).
OUTLAST_VALUE=""
PREV_TOK=""
while IFS= read -r TOK; do
    if [ "$PREV_TOK" = "--output-last-message" ]; then
        OUTLAST_VALUE="$TOK"
    fi
    PREV_TOK="$TOK"
done < "$STUB_ARGV_FILE"

if [ "$OUTLAST_VALUE" = "$JSON_OUTFILE" ]; then
    PASS "--emit-thread-id: codex argv --output-last-message value is the -o target"
else
    FAIL "--emit-thread-id: codex argv --output-last-message value is the -o target" \
         "got --output-last-message value '$OUTLAST_VALUE', expected '$JSON_OUTFILE' -- argv: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
fi

# 5. Thread id captured: THREADFILE holds exactly the thread.started uuid
#    (plus optional trailing newline), nothing else.
if [ "$(cat "$THREAD_ID_FILE" 2>/dev/null)" = "$FIXED_UUID" ]; then
    PASS "--emit-thread-id: THREADFILE contains exactly the thread.started uuid"
else
    FAIL "--emit-thread-id: THREADFILE contains exactly the thread.started uuid" \
         "got: $(cat "$THREAD_ID_FILE" 2>/dev/null || echo '<missing>')"
fi

# 6. Output contract: OUTFILE gets the review text.
if grep -qF "STUB REVIEW OUTPUT" "$JSON_OUTFILE" 2>/dev/null; then
    PASS "--emit-thread-id: OUTFILE contains the review text"
else
    FAIL "--emit-thread-id: OUTFILE contains the review text" \
         "OUTFILE contents: $(cat "$JSON_OUTFILE" 2>/dev/null || echo '<missing>')"
fi

# 7. Output contract: codex-run.sh's own stdout also carries the review text
#    (tee-parity for downstream consumers).
if grep -qF "STUB REVIEW OUTPUT" "$JSON_STDOUT_FILE"; then
    PASS "--emit-thread-id: codex-run.sh stdout contains the review text"
else
    FAIL "--emit-thread-id: codex-run.sh stdout contains the review text" \
         "stdout contents: $(cat "$JSON_STDOUT_FILE")"
fi

# 8. Output contract: raw JSONL events must never leak onto codex-run.sh's
#    own stdout.
if grep -qF "thread.started" "$JSON_STDOUT_FILE"; then
    FAIL "--emit-thread-id: raw JSONL does not leak onto stdout" \
         "stdout contents: $(cat "$JSON_STDOUT_FILE")"
else
    PASS "--emit-thread-id: raw JSONL does not leak onto stdout"
fi

# 9. Liveness markers: every JSONL event codex emits gets a
#    'codex-event: <type>' marker on stderr.
if grep -qxF "codex-event: thread.started" "$JSON_STDERR_FILE" && \
   grep -qxF "codex-event: item.completed" "$JSON_STDERR_FILE" && \
   grep -qxF "codex-event: turn.completed" "$JSON_STDERR_FILE"; then
    PASS "--emit-thread-id: stderr carries a codex-event marker per JSONL event"
else
    FAIL "--emit-thread-id: stderr carries a codex-event marker per JSONL event" \
         "stderr contents: $(cat "$JSON_STDERR_FILE" | tr '\n' '|')"
fi

# 10. stdin guard still applies on the JSON-path codex invocation: the child
#     stdin is exactly the prompt, never the wrapper's SENTINEL stdin.
if child_stdin_is_prompt "$THREAD_PROMPT"; then
    PASS "--emit-thread-id: codex child stdin is exactly the prompt, never the wrapper's stdin"
else
    FAIL "--emit-thread-id: codex child stdin is exactly the prompt, never the wrapper's stdin" \
         "stub captured stdin: $(cat "$STUB_STDIN_FILE" 2>/dev/null | tr '\n' '|'); expected exactly the prompt '$THREAD_PROMPT' with no trace of SENTINEL_STDIN_DATA"
fi

# =============================================================================
# --emit-thread-id without -o must fail fast and never invoke codex.
# =============================================================================
NOOUT_THREAD_ID_FILE="$STUBDIR/thread_id_noout.out"
NOOUT_STDOUT_FILE="$STUBDIR/noout.stdout"
NOOUT_STDERR_FILE="$STUBDIR/noout.stderr"

run_codex_run --emit-thread-id "$NOOUT_THREAD_ID_FILE" "analyze without -o" \
    > "$NOOUT_STDOUT_FILE" 2> "$NOOUT_STDERR_FILE" < /dev/null
NOOUT_EXIT=$?

# 11. Missing -o is a hard error: exit 1.
if [ "$NOOUT_EXIT" -eq 1 ]; then
    PASS "--emit-thread-id without -o exits 1"
else
    FAIL "--emit-thread-id without -o exits 1" \
         "got exit code $NOOUT_EXIT"
fi

# 12. Error message names the missing requirement. Per the design contract the
#     message is `ERROR: --emit-thread-id requires -o`, so it must reference the
#     `-o` flag and the requirement (matches "requires"/"required"); it need not
#     contain the literal word "output".
if grep -qi "require" "$NOOUT_STDOUT_FILE" "$NOOUT_STDERR_FILE" 2>/dev/null && \
   grep -qF -- "-o" "$NOOUT_STDOUT_FILE" "$NOOUT_STDERR_FILE" 2>/dev/null; then
    PASS "--emit-thread-id without -o: error message names the -o requirement"
else
    FAIL "--emit-thread-id without -o: error message names the -o requirement" \
         "stdout: $(cat "$NOOUT_STDOUT_FILE") -- stderr: $(cat "$NOOUT_STDERR_FILE")"
fi

# 13. codex must never be invoked when the -o/--emit-thread-id pairing is invalid.
if [ -s "$STUB_ARGV_FILE" ]; then
    FAIL "--emit-thread-id without -o: codex is never invoked" \
         "argv file non-empty: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
else
    PASS "--emit-thread-id without -o: codex is never invoked"
fi

# =============================================================================
# Usage errors must land on stderr (stdout is reserved for model output and
# the tee'd run log), with a non-zero exit.
# =============================================================================
STDERR_ERR_STDOUT_FILE="$STUBDIR/stderr_err.stdout"
STDERR_ERR_STDERR_FILE="$STUBDIR/stderr_err.stderr"

run_codex_run -f "$STUBDIR/does-not-exist.txt" \
    > "$STDERR_ERR_STDOUT_FILE" 2> "$STDERR_ERR_STDERR_FILE" < /dev/null
STDERR_ERR_EXIT=$?

# 38. Missing prompt file: non-zero exit, error text on stderr and NOT stdout.
if [ "$STDERR_ERR_EXIT" -ne 0 ] && \
   grep -q "not found" "$STDERR_ERR_STDERR_FILE" 2>/dev/null && \
   ! grep -q "not found" "$STDERR_ERR_STDOUT_FILE" 2>/dev/null; then
    PASS "missing prompt file: non-zero exit with the error on stderr, not stdout"
else
    FAIL "missing prompt file: non-zero exit with the error on stderr, not stdout" \
         "exit: $STDERR_ERR_EXIT -- stdout: $(cat "$STDERR_ERR_STDOUT_FILE") -- stderr: $(cat "$STDERR_ERR_STDERR_FILE")"
fi

# =============================================================================
# Recursion guard: a dispatch from inside a CLI agent must refuse with exit 3
# and spawn no child. Both triggers are covered -- the depth counter (set by an
# outer codex-run.sh) and the vendor marker (set by the CLI itself).
# =============================================================================
guard_case() {
    # $1 = human label, $2.. = VAR=VALUE env assignments that should trip it
    local label="$1"
    shift
    : > "$STUB_ARGV_FILE"
    local out
    out=$(PATH="$RUN_PATH" STUB_ARGV_FILE="$STUB_ARGV_FILE" STUB_STDIN_FILE="$STUB_STDIN_FILE" \
        env "$@" bash "$CODEX_RUN_SH" "probe" 2>&1 < /dev/null)
    local rc=$?
    if [ "$rc" -eq 3 ] && [ ! -s "$STUB_ARGV_FILE" ]; then
        PASS "$label"
    else
        FAIL "$label" "exit: $rc (want 3) -- stub argv bytes: $(wc -c < "$STUB_ARGV_FILE" | tr -d ' ') (want 0) -- output: $out"
    fi
}

# 39-41. Refuses nested dispatch, without invoking codex.
guard_case "AUTOPILOT_DISPATCH_DEPTH=1: refuses with exit 3, no codex call" AUTOPILOT_DISPATCH_DEPTH=1
guard_case "CODEX_SESSION_ID set: refuses with exit 3, no codex call" CODEX_SESSION_ID=deadbeef
guard_case "COPILOT_CLI set: refuses with exit 3, no codex call" COPILOT_CLI=1

# =============================================================================
# -f FILE where FILE exists but cannot be read: a permission failure must be
# reported as an error, never silently treated as an empty/truncated prompt.
# =============================================================================
UNREADABLE_FILE="$STUBDIR/unreadable_prompt.txt"
printf '%s\n' "some prompt text" > "$UNREADABLE_FILE"
chmod 000 "$UNREADABLE_FILE"
UNREADABLE_STDOUT_FILE="$STUBDIR/unreadable.stdout"
UNREADABLE_STDERR_FILE="$STUBDIR/unreadable.stderr"

# 42. Unreadable prompt file: non-zero exit, error names the file on stderr,
#     codex never invoked. Skipped (as a PASS) rather than failed spuriously
#     if the current user (e.g. root) can read anything regardless of mode
#     bits, since chmod 000 can't produce an unreadable file in that case.
if [ -r "$UNREADABLE_FILE" ]; then
    PASS "unreadable prompt file: skipped -- current user can read chmod 000 files"
else
    run_codex_run -f "$UNREADABLE_FILE" \
        > "$UNREADABLE_STDOUT_FILE" 2> "$UNREADABLE_STDERR_FILE" < /dev/null
    UNREADABLE_EXIT=$?

    if [ "$UNREADABLE_EXIT" -ne 0 ] && \
       grep -qF "$UNREADABLE_FILE" "$UNREADABLE_STDERR_FILE" 2>/dev/null && \
       [ ! -s "$STUB_ARGV_FILE" ]; then
        PASS "unreadable prompt file: non-zero exit, error names the file, codex never invoked"
    else
        FAIL "unreadable prompt file: non-zero exit, error names the file, codex never invoked" \
             "exit: $UNREADABLE_EXIT -- stderr: $(cat "$UNREADABLE_STDERR_FILE" 2>/dev/null) -- argv file bytes: $(wc -c < "$STUB_ARGV_FILE" 2>/dev/null | tr -d ' ')"
    fi
fi

# =============================================================================
# -f FILE containing only a single newline: whitespace-only content is still
# "no prompt" -- must be treated exactly like an empty/missing prompt, not
# silently passed through to codex.
# =============================================================================
WHITESPACE_PROMPT_FILE="$STUBDIR/whitespace_prompt.txt"
printf '\n' > "$WHITESPACE_PROMPT_FILE"
WHITESPACE_STDOUT_FILE="$STUBDIR/whitespace.stdout"
WHITESPACE_STDERR_FILE="$STUBDIR/whitespace.stderr"

run_codex_run -f "$WHITESPACE_PROMPT_FILE" \
    > "$WHITESPACE_STDOUT_FILE" 2> "$WHITESPACE_STDERR_FILE" < /dev/null
WHITESPACE_EXIT=$?

# 43. Whitespace-only prompt file: exit 1, "Prompt required" on stderr, codex
#     never invoked.
if [ "$WHITESPACE_EXIT" -eq 1 ] && \
   grep -qF "Prompt required" "$WHITESPACE_STDERR_FILE" 2>/dev/null && \
   [ ! -s "$STUB_ARGV_FILE" ]; then
    PASS "-f PROMPTFILE containing only a newline: exit 1, 'Prompt required' on stderr, codex never invoked"
else
    FAIL "-f PROMPTFILE containing only a newline: exit 1, 'Prompt required' on stderr, codex never invoked" \
         "exit: $WHITESPACE_EXIT -- stderr: $(cat "$WHITESPACE_STDERR_FILE" 2>/dev/null) -- argv file bytes: $(wc -c < "$STUB_ARGV_FILE" 2>/dev/null | tr -d ' ')"
fi

# =============================================================================
# -f FILE whose contents end in a trailing newline: the bytes delivered to
# the codex child's stdin must equal the file's bytes exactly, trailing
# newline included -- a comparison that trims/normalizes whitespace would
# pass even if the newline were dropped.
# =============================================================================
TRAILING_NL_FILE="$STUBDIR/trailing_newline_prompt.txt"
printf 'analyze the trailing newline case\n' > "$TRAILING_NL_FILE"

run_codex_run -f "$TRAILING_NL_FILE" > /dev/null 2>/dev/null < /dev/null

# 44. Trailing-newline prompt file: codex child stdin is byte-for-byte
#     identical to the file's contents, trailing newline included.
if diff -q "$TRAILING_NL_FILE" "$STUB_STDIN_FILE" >/dev/null 2>&1; then
    PASS "-f PROMPTFILE ending in a newline: codex child stdin is byte-identical, trailing newline included"
else
    FAIL "-f PROMPTFILE ending in a newline: codex child stdin is byte-identical, trailing newline included" \
         "stub captured stdin bytes: $(wc -c < "$STUB_STDIN_FILE" 2>/dev/null | tr -d ' '); expected file bytes: $(wc -c < "$TRAILING_NL_FILE" 2>/dev/null | tr -d ' ')"
fi

# =============================================================================
# --emit-thread-id JSON dispatch path: the final token of the codex child's
# argv must be the literal "-" that tells codex to read its instructions
# from stdin. The existing cases on this path assert --json is present and
# --output-last-message carries the -o target, but nothing asserts the final
# token specifically -- asserting only that "-" appears somewhere in argv
# would also match an unrelated flag value.
# =============================================================================
FINALTOK_THREAD_ID_FILE="$STUBDIR/finaltok_thread_id.out"
FINALTOK_OUTFILE="$STUBDIR/finaltok.out"

run_codex_run --emit-thread-id "$FINALTOK_THREAD_ID_FILE" -o "$FINALTOK_OUTFILE" "analyze the final-token case" \
    > /dev/null 2>/dev/null < /dev/null

read_argv_array "$STUB_ARGV_FILE"

# 45. --emit-thread-id JSON path: the final argv token is exactly "-".
FINALTOK_LAST_IDX=$(( ${#ARGV_ARR[@]} - 1 ))
if [ "${ARGV_ARR[$FINALTOK_LAST_IDX]:-}" = "-" ]; then
    PASS "--emit-thread-id: final argv token is the literal '-' stdin marker"
else
    FAIL "--emit-thread-id: final argv token is the literal '-' stdin marker" \
         "argv: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
fi

# =============================================================================
echo ""
echo "SUMMARY: $PASS_COUNT passed, $FAIL_COUNT failed"

[ "$FAIL_COUNT" -eq 0 ]
