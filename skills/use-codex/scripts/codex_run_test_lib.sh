# Shared test harness for codex-run.sh's test scripts (test_codex_run.sh,
# test_codex_run_resume.sh). Sourced by both, not standalone-runnable.
# macOS bash 3.2 compatible. Stubs the `codex` binary on PATH and asserts on
# its OBSERVABLE argv/stdin, never on codex-run.sh's internals.

CODEX_RUN_SH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/codex-run.sh"
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
