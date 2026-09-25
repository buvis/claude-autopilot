#!/usr/bin/env bash
# Test harness for codex-run.sh (macOS bash 3.2 compatible). Stubs the `codex`
# binary on PATH and asserts on its OBSERVABLE argv/stdin, never on
# codex-run.sh's internals. Extend this file with more assertions/invocations
# as codex-run.sh grows new behavior (thread-id capture, resume, etc.).
set -u

# Shared assert helpers, stub `codex` binary, and run_codex_run() live in
# codex_run_test_lib.sh (also sourced by test_codex_run_resume.sh) -- see
# that file for CODEX_RUN_SH resolution and the stub's behavior.
source "$(cd "$(dirname "$0")" && pwd)/codex_run_test_lib.sh"

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

read_argv_array "$STUB_ARGV_FILE"
DASH_PLAIN_LAST_IDX=$(( ${#ARGV_ARR[@]} - 1 ))

# 2b. Leading-dash prompt file, plain path: codex child stdin is the file's
#     bytes, verbatim -- never argv-parsed as a flag. DASH_PROMPT_FILE itself
#     ends in a trailing newline (printf's own '\n'), so this same byte-exact
#     diff also proves trailing-newline preservation -- folds in case 44
#     (no longer a separate invocation). Also checks the final argv token is
#     the literal "-" stdin marker.
if diff -q "$DASH_PROMPT_FILE" "$STUB_STDIN_FILE" >/dev/null 2>&1 && \
   [ "${ARGV_ARR[$DASH_PLAIN_LAST_IDX]:-}" = "-" ]; then
    PASS "-f PROMPTFILE with a leading-dash first line, plain path: codex child stdin is the file's bytes verbatim, trailing newline included, and the final argv token is '-'"
else
    FAIL "-f PROMPTFILE with a leading-dash first line, plain path: codex child stdin is the file's bytes verbatim, trailing newline included, and the final argv token is '-'" \
         "stub captured stdin: $(cat "$STUB_STDIN_FILE" 2>/dev/null | tr '\n' '|'); expected file contents: $(cat "$DASH_PROMPT_FILE" 2>/dev/null | tr '\n' '|') -- argv: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
fi

# 2c. Leading-dash prompt file, json path: same -f PROMPTFILE delivery, but
#     via the --emit-thread-id/-o invocation shape (case 3-10 below) instead
#     of the plain-string path -- codex child stdin is still the file's bytes
#     verbatim, and the final argv token is still the literal "-" stdin
#     marker, never argv-parsed as a flag.
DASH_JSON_THREAD_ID_FILE="$STUBDIR/dash_json_thread_id.out"
DASH_JSON_OUTFILE="$STUBDIR/dash_json.out"
rm -f "$DASH_JSON_THREAD_ID_FILE" "$DASH_JSON_OUTFILE"

run_codex_run --emit-thread-id "$DASH_JSON_THREAD_ID_FILE" -o "$DASH_JSON_OUTFILE" -f "$DASH_PROMPT_FILE" \
    > /dev/null 2>/dev/null < /dev/null

read_argv_array "$STUB_ARGV_FILE"
DASH_JSON_LAST_IDX=$(( ${#ARGV_ARR[@]} - 1 ))
if grep -qxF -- "--json" "$STUB_ARGV_FILE" && \
   argv_has_pair "$STUB_ARGV_FILE" "--output-last-message" "$DASH_JSON_OUTFILE" && \
   diff -q "$DASH_PROMPT_FILE" "$STUB_STDIN_FILE" >/dev/null 2>&1 && \
   [ "${ARGV_ARR[$DASH_JSON_LAST_IDX]:-}" = "-" ]; then
    PASS "-f PROMPTFILE with a leading-dash first line, json path: argv carries --json and --output-last-message <-o target>, codex child stdin is the file's bytes verbatim and the final argv token is '-'"
else
    FAIL "-f PROMPTFILE with a leading-dash first line, json path: argv carries --json and --output-last-message <-o target>, codex child stdin is the file's bytes verbatim and the final argv token is '-'" \
         "stub captured stdin: $(cat "$STUB_STDIN_FILE" 2>/dev/null | tr '\n' '|'); expected file contents: $(cat "$DASH_PROMPT_FILE" 2>/dev/null | tr '\n' '|') -- argv: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
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
#     stdin is exactly the prompt, never the wrapper's SENTINEL stdin. Also
#     checks the final argv token is exactly "-" -- the literal marker that
#     tells codex to read its instructions from stdin; asserting only that
#     "-" appears somewhere in argv would also match an unrelated flag
#     value, so this checks the final position.
read_argv_array "$STUB_ARGV_FILE"
FINALTOK_LAST_IDX=$(( ${#ARGV_ARR[@]} - 1 ))
if child_stdin_is_prompt "$THREAD_PROMPT" && [ "${ARGV_ARR[$FINALTOK_LAST_IDX]:-}" = "-" ]; then
    PASS "--emit-thread-id: codex child stdin is exactly the prompt, never the wrapper's stdin, and the final argv token is the literal '-' stdin marker"
else
    FAIL "--emit-thread-id: codex child stdin is exactly the prompt, never the wrapper's stdin, and the final argv token is the literal '-' stdin marker" \
         "stub captured stdin: $(cat "$STUB_STDIN_FILE" 2>/dev/null | tr '\n' '|'); expected exactly the prompt '$THREAD_PROMPT' with no trace of SENTINEL_STDIN_DATA -- argv: $(tr '\n' ' ' < "$STUB_ARGV_FILE")"
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

# 42. Unreadable prompt file: exit 1, last stderr line is exactly the
#     'failed to read prompt file' error, codex never invoked. The cat
#     invocation inside codex-run.sh's own guard has its stderr unredirected,
#     so a "Permission denied" line from cat precedes the guard's own
#     echo'd error -- match the LAST line exactly rather than the whole
#     file, since that's still an exact (non-substring) match on the text
#     codex-run.sh itself prints, and distinguishes it from the old runner's
#     different "ERROR: Prompt required" message just the same. Skipped (not
#     failed) when the current user is root (uid 0), since root can read
#     chmod 000 files regardless of mode bits -- gate on the uid itself, not
#     on file readability, so a PATH shim that fakes `id -u` can exercise
#     this branch.
if [ "$(id -u)" = "0" ]; then
    SKIP "unreadable prompt file: running as root, chmod 000 files are still readable"
else
    run_codex_run -f "$UNREADABLE_FILE" \
        > "$UNREADABLE_STDOUT_FILE" 2> "$UNREADABLE_STDERR_FILE" < /dev/null
    UNREADABLE_EXIT=$?

    if [ "$UNREADABLE_EXIT" -eq 1 ] && \
       [ "$(tail -n 1 "$UNREADABLE_STDERR_FILE" 2>/dev/null)" = "ERROR: failed to read prompt file: $UNREADABLE_FILE" ] && \
       [ ! -s "$STUB_ARGV_FILE" ]; then
        PASS "unreadable prompt file: exit 1, exact 'failed to read prompt file' error on stderr, codex never invoked"
    else
        FAIL "unreadable prompt file: exit 1, exact 'failed to read prompt file' error on stderr, codex never invoked" \
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
# Live lane marker: inside an autopilot loop (_AUTOPILOT_LOOP non-empty) the
# wrapper leaves <autopilot dir>/lanes/<pid> for its lifetime. The stub copies
# the lanes dir out mid-run (STUB_LANES_DIR), since the marker is gone after.
# =============================================================================
LANE_REPO=$(mktemp -d)
_DIRS+=("$LANE_REPO")
LANE_REPO=$(cd "$LANE_REPO" && pwd -P)
mkdir -p "$LANE_REPO/dev/local/autopilot" "$LANE_REPO/a/b/c/d/e"
LANE_LANES_DIR="$LANE_REPO/dev/local/autopilot/lanes"
LANE_PROMPT_FILE="$LANE_REPO/prompt.txt"
printf '%s\n' "review the lane case" > "$LANE_PROMPT_FILE"

# run_lane_case <snapshot dir> <loop value or empty> <cwd> [args...]
run_lane_case() {
    local snap="$1" loop="$2" cwd="$3"
    shift 3
    mkdir -p "$snap"
    (
        cd "$cwd" || exit 99
        unset _AUTOPILOT_LOOP
        [ -z "$loop" ] || export _AUTOPILOT_LOOP="$loop"
        export STUB_LANES_DIR="$LANE_LANES_DIR" STUB_LANES_SNAPSHOT_DIR="$snap"
        run_codex_run "$@" > /dev/null 2>&1 < /dev/null
    )
}

# 45. Loop set, cwd five levels below a dev/local/autopilot, a foreign marker
#     (999999, another lane) already present: during the run the lanes dir
#     holds the foreign marker plus one marker named by the wrapper's own pid
#     (a live process running codex-run.sh), line 1 'codex', line 2 the -o
#     path; after the run only the foreign marker remains, unchanged.
LANE_SNAP="$LANE_REPO/.snap-loop"
LANE_OUT="$LANE_REPO/lane-review.out"
LANE_FOREIGN="$LANE_REPO/.foreign-marker"
printf 'codex\n/somewhere/else.out\n' > "$LANE_FOREIGN"
mkdir -p "$LANE_LANES_DIR"
cp "$LANE_FOREIGN" "$LANE_LANES_DIR/999999"
run_lane_case "$LANE_SNAP" 1 "$LANE_REPO/a/b/c/d/e" -f "$LANE_PROMPT_FILE" -o "$LANE_OUT"
LANE_RC=$?
LANE_COUNT=$(ls "$LANE_SNAP" 2>/dev/null | wc -l | tr -d ' ')
LANE_NAMES=$(ls "$LANE_SNAP" 2>/dev/null | grep -vx 999999)
LANE_LINE1=$(sed -n 1p "$LANE_SNAP/$LANE_NAMES" 2>/dev/null)
LANE_LINE2=$(sed -n 2p "$LANE_SNAP/$LANE_NAMES" 2>/dev/null)
LANE_EXTRA=$(sed -n '3,$p' "$LANE_SNAP/$LANE_NAMES" 2>/dev/null)
LANE_CMD=$(cat "$LANE_SNAP/.cmd.$LANE_NAMES" 2>/dev/null)
if [ "$LANE_RC" -eq 0 ] && [ "$LANE_COUNT" = "2" ] && \
   [ -f "$LANE_SNAP/999999" ] && printf '%s' "$LANE_NAMES" | grep -qxE '[0-9]+' && \
   case "$LANE_CMD" in *codex-run.sh*) true ;; *) false ;; esac && \
   [ "$LANE_LINE1" = "codex" ] && [ "$LANE_LINE2" = "$LANE_OUT" ] && [ -z "$LANE_EXTRA" ] && \
   [ "$(ls -A "$LANE_LANES_DIR")" = "999999" ] && cmp -s "$LANE_FOREIGN" "$LANE_LANES_DIR/999999"; then
    PASS "_AUTOPILOT_LOOP=1 five levels under dev/local/autopilot: a marker named by the wrapper's pid holding 'codex' and the -o path during the run, removed after, foreign marker untouched"
else
    FAIL "_AUTOPILOT_LOOP=1 five levels under dev/local/autopilot: a marker named by the wrapper's pid holding 'codex' and the -o path during the run, removed after, foreign marker untouched" \
         "rc=$LANE_RC; during-run entries: $(ls "$LANE_SNAP" 2>/dev/null | tr '\n' ' ')(count $LANE_COUNT, want 999999 + own pid); own='$LANE_NAMES' cmd='$LANE_CMD' (want codex-run.sh); line1='$LANE_LINE1' line2='$LANE_LINE2' extra lines='$LANE_EXTRA' (want codex / $LANE_OUT / none); lanes after: $(ls -A "$LANE_LANES_DIR" 2>&1 | tr '\n' ' ')(want 999999 unchanged)"
fi

# 46. Loop set, no -o: the marker's second line is empty.
rm -rf "$LANE_LANES_DIR"
LANE_SNAP_NOOUT="$LANE_REPO/.snap-noout"
run_lane_case "$LANE_SNAP_NOOUT" 1 "$LANE_REPO" -f "$LANE_PROMPT_FILE"
LANE_NOOUT_NAME=$(ls "$LANE_SNAP_NOOUT" 2>/dev/null)
if [ "$(ls "$LANE_SNAP_NOOUT" 2>/dev/null | wc -l | tr -d ' ')" = "1" ] && \
   [ "$(sed -n 1p "$LANE_SNAP_NOOUT/$LANE_NOOUT_NAME")" = "codex" ] && \
   [ -z "$(sed -n '3,$p' "$LANE_SNAP_NOOUT/$LANE_NOOUT_NAME")" ] && \
   [ -z "$(sed -n 2p "$LANE_SNAP_NOOUT/$LANE_NOOUT_NAME")" ]; then
    PASS "_AUTOPILOT_LOOP=1 without -o: marker line 1 is 'codex', line 2 is empty"
else
    FAIL "_AUTOPILOT_LOOP=1 without -o: marker line 1 is 'codex', line 2 is empty" \
         "entries: $(ls "$LANE_SNAP_NOOUT" 2>/dev/null | tr '\n' ' '); content: $(cat "$LANE_SNAP_NOOUT/$LANE_NOOUT_NAME" 2>/dev/null | tr '\n' '|')"
fi

# 47. No _AUTOPILOT_LOOP: no marker is written, no lanes dir is created.
rm -rf "$LANE_LANES_DIR"
LANE_SNAP_OFF="$LANE_REPO/.snap-off"
run_lane_case "$LANE_SNAP_OFF" "" "$LANE_REPO" -f "$LANE_PROMPT_FILE" -o "$LANE_OUT"
if [ -z "$(ls "$LANE_SNAP_OFF")" ] && [ ! -e "$LANE_LANES_DIR" ]; then
    PASS "_AUTOPILOT_LOOP unset: no lane marker is written and no lanes dir is created"
else
    FAIL "_AUTOPILOT_LOOP unset: no lane marker is written and no lanes dir is created" \
         "during-run entries: $(ls "$LANE_SNAP_OFF" | tr '\n' ' '); lanes dir: $(ls -A "$LANE_LANES_DIR" 2>&1 | tr '\n' ' ')"
fi

# 48. Loop set but no dev/local/autopilot at or above cwd: exit 0, nothing made.
LANE_BARE=$(mktemp -d)
_DIRS+=("$LANE_BARE")
LANE_BARE_SNAP=$(mktemp -d)
_DIRS+=("$LANE_BARE_SNAP")
run_lane_case "$LANE_BARE_SNAP" 1 "$LANE_BARE" -f "$LANE_PROMPT_FILE" -o "$LANE_BARE_SNAP/review.out"
LANE_BARE_RC=$?
if [ "$LANE_BARE_RC" -eq 0 ] && [ -z "$(ls -A "$LANE_BARE")" ]; then
    PASS "_AUTOPILOT_LOOP=1 with no dev/local/autopilot above cwd: exits 0 and creates nothing"
else
    FAIL "_AUTOPILOT_LOOP=1 with no dev/local/autopilot above cwd: exits 0 and creates nothing" \
         "rc=$LANE_BARE_RC; cwd contents: $(ls -A "$LANE_BARE" | tr '\n' ' ')"
fi

# =============================================================================
echo ""
echo "SUMMARY: $PASS_COUNT passed, $FAIL_COUNT failed"

[ "$FAIL_COUNT" -eq 0 ]
