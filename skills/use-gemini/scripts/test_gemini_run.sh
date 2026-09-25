#!/usr/bin/env bash
# Test harness for gemini-run.sh (macOS bash 3.2 compatible). Stubs the
# `copilot` and `gemini` binaries on PATH and asserts on their OBSERVABLE
# argv/stdin/exit codes, never on gemini-run.sh's internals. Modeled on
# use-codex/scripts/test_codex_run.sh.
set -u

GEMINI_RUN_SH="$(cd "$(dirname "$0")" && pwd)/gemini-run.sh"
[ -n "${1:-}" ] && GEMINI_RUN_SH="$1"

# ── assert helpers ────────────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
PASS() { echo "PASS: $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
FAIL() { echo "FAIL: $1 -- $2"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

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

# ── cleanup registry ──────────────────────────────────────────────────────────
_DIRS=()
cleanup() {
    local d
    for d in "${_DIRS[@]+"${_DIRS[@]}"}"; do
        rm -rf "$d"
    done
}
trap cleanup EXIT

WORK=$(mktemp -d)
_DIRS+=("$WORK")

# ── stub `copilot` and `gemini` binaries on PATH ──────────────────────────────
STUBDIR="$WORK/stub"
mkdir -p "$STUBDIR"

cat > "$STUBDIR/copilot" <<'STUB'
#!/bin/bash
printf '%s\n' "$@" > "${COPILOT_ARGV_FILE:?}"
if [ -n "${LIVE_STDERR_FILE:-}" ]; then
    printf '%s\n' 'APPROVAL_PROMPT' >&2
    attempts=0
    until grep -qF 'APPROVAL_PROMPT' "$LIVE_STDERR_FILE"; do
        attempts=$((attempts + 1))
        [ "$attempts" -lt 100 ] || exit 91
        sleep 0.02
    done
fi
cat > "${COPILOT_STDIN_FILE:?}"
[ -z "${STUB_LANES_DIR:-}" ] || { ls "$STUB_LANES_DIR" > "$STUB_LANES_SNAPSHOT_DIR/.list" 2>/dev/null; cp "$STUB_LANES_DIR"/* "$STUB_LANES_SNAPSHOT_DIR/" 2>/dev/null; }
echo "stub-copilot-ran"
[ -z "${COPILOT_STDOUT:-}" ] || printf '%s\n' "$COPILOT_STDOUT"
[ -z "${COPILOT_STDERR:-}" ] || printf '%s\n' "$COPILOT_STDERR" >&2
exit "${COPILOT_EXIT_CODE:-${STUB_EXIT_CODE:-0}}"
STUB
chmod +x "$STUBDIR/copilot"

cat > "$STUBDIR/gemini" <<'STUB'
#!/bin/bash
printf '%s\n' "$@" > "${GEMINI_ARGV_FILE:?}"
cat > "${GEMINI_STDIN_FILE:?}"
[ -z "${STUB_LANES_DIR:-}" ] || { ls "$STUB_LANES_DIR" > "$STUB_LANES_SNAPSHOT_DIR/.list" 2>/dev/null; cp "$STUB_LANES_DIR"/* "$STUB_LANES_SNAPSHOT_DIR/" 2>/dev/null; }
echo "stub-gemini-ran"
[ -z "${GEMINI_STDERR:-}" ] || printf '%s\n' "$GEMINI_STDERR" >&2
exit "${GEMINI_EXIT_CODE:-${STUB_EXIT_CODE:-0}}"
STUB
chmod +x "$STUBDIR/gemini"

# gemini-run.sh re-prepends mise's own PATH ahead of ours whenever `mise` is
# reachable, which would put the real binaries ahead of the stubs. Excluding
# mise's location from the PATH we hand to gemini-run.sh keeps that branch
# inert, so lookup always resolves to our stubs.
RUN_PATH="$STUBDIR:/usr/bin:/bin"

GEMINI_PROMPT="say hi from gemini"
PROMPT_FILE_T="$WORK/prompt.txt"
printf '%s' "$GEMINI_PROMPT" > "$PROMPT_FILE_T"

# run_gemini <name> [args...] — runs gemini-run.sh with SENTINEL data on the
# wrapper's own stdin; sets RC, STDOUT_F, STDERR_F, and per-test capture paths.
run_gemini() {
    local name="$1"
    shift
    export COPILOT_ARGV_FILE="$WORK/$name.copilot.argv"
    export COPILOT_STDIN_FILE="$WORK/$name.copilot.stdin"
    export GEMINI_ARGV_FILE="$WORK/$name.gemini.argv"
    export GEMINI_STDIN_FILE="$WORK/$name.gemini.stdin"
    STDOUT_F="$WORK/$name.stdout"
    STDERR_F="$WORK/$name.stderr"
    RC=0
    PATH="$RUN_PATH" bash "$GEMINI_RUN_SH" "$@" \
        > "$STDOUT_F" 2> "$STDERR_F" <<< 'SENTINEL_STDIN_DATA' || RC=$?
}

# ══ T1: plain -f run on the preferred copilot backend ═════════════════════════
run_gemini t1 -f "$PROMPT_FILE_T"

# 1. Child stdin must be redirected to /dev/null. Without the guard the child
#    inherits the wrapper's stdin and reads SENTINEL_STDIN_DATA (the PRD 00040
#    hang class: a child blocking on inherited stdin stalls unattended runs).
if [ -f "$COPILOT_STDIN_FILE" ] && [ ! -s "$COPILOT_STDIN_FILE" ]; then
    PASS "copilot child stdin is /dev/null"
else
    FAIL "copilot child stdin is /dev/null" \
         "stub captured $(wc -c < "$COPILOT_STDIN_FILE" 2>/dev/null | tr -d ' ' || echo '?') byte(s) of stdin; expected 0 (child inherited the wrapper's stdin instead of /dev/null)"
fi

# 2. Argv regression lock for the plain -f run (adding the stdin guard must
#    not perturb argv): --model <default> + read-review perms + -p <prompt>.
EXPECTED_ARGV_FILE="$WORK/t1.expected"
EXPECTED_MODEL="gemini-3.8-flash"
printf '%s\n' "--model" "$EXPECTED_MODEL" "--allow-all-tools" "--deny-tool=write" "-p" "$GEMINI_PROMPT" > "$EXPECTED_ARGV_FILE"
if diff -q "$EXPECTED_ARGV_FILE" "$COPILOT_ARGV_FILE" >/dev/null 2>&1; then
    PASS "plain -f argv is exactly: --model $EXPECTED_MODEL --allow-all-tools --deny-tool=write -p <PROMPT>"
else
    FAIL "plain -f argv is exactly: --model $EXPECTED_MODEL --allow-all-tools --deny-tool=write -p <PROMPT>" \
         "got: $(tr '\n' ' ' < "$COPILOT_ARGV_FILE" 2>/dev/null || echo '<no copilot invocation>')"
fi

# 3. Backend order: with both CLIs present, copilot is preferred and the
#    native gemini CLI is never invoked.
if [ ! -f "$GEMINI_ARGV_FILE" ]; then
    PASS "copilot preferred: native gemini CLI is not invoked when copilot exists"
else
    FAIL "copilot preferred: native gemini CLI is not invoked when copilot exists" \
         "gemini stub ran with argv: $(tr '\n' ' ' < "$GEMINI_ARGV_FILE")"
fi

# 4. Happy path exits 0 and surfaces the backend's output.
if [ "$RC" -eq 0 ] && grep -qF "stub-copilot-ran" "$STDOUT_F"; then
    PASS "plain -f run exits 0 and passes backend stdout through"
else
    FAIL "plain -f run exits 0 and passes backend stdout through" \
         "rc=$RC; stdout: $(cat "$STDOUT_F")"
fi

# ══ T2: -o tees output to the file ════════════════════════════════════════════
T2_OUT="$WORK/t2.out"
run_gemini t2 -f "$PROMPT_FILE_T" -o "$T2_OUT"

# 5. -o: output file receives the backend output.
if grep -qF "stub-copilot-ran" "$T2_OUT" 2>/dev/null; then
    PASS "-o: output file contains the backend output"
else
    FAIL "-o: output file contains the backend output" \
         "rc=$RC; -o file contents: $(cat "$T2_OUT" 2>/dev/null || echo '<missing>')"
fi

# ══ T3: GEMINI_BACKEND=gemini forces the native backend ═══════════════════════
export GEMINI_BACKEND=gemini
run_gemini t3 -f "$PROMPT_FILE_T"
unset GEMINI_BACKEND

# 6. Forced native backend: gemini argv is exactly --skip-trust -p <prompt>.
EXPECTED_NATIVE_ARGV_FILE="$WORK/t3.expected"
printf '%s\n' "--skip-trust" "-p" "$GEMINI_PROMPT" > "$EXPECTED_NATIVE_ARGV_FILE"
if diff -q "$EXPECTED_NATIVE_ARGV_FILE" "$GEMINI_ARGV_FILE" >/dev/null 2>&1; then
    PASS "GEMINI_BACKEND=gemini: native argv is exactly --skip-trust -p <PROMPT>"
else
    FAIL "GEMINI_BACKEND=gemini: native argv is exactly --skip-trust -p <PROMPT>" \
         "got: $(tr '\n' ' ' < "$GEMINI_ARGV_FILE" 2>/dev/null || echo '<no gemini invocation>')"
fi

# 7. Forced native backend: copilot is never invoked.
if [ ! -f "$COPILOT_ARGV_FILE" ]; then
    PASS "GEMINI_BACKEND=gemini: copilot is not invoked"
else
    FAIL "GEMINI_BACKEND=gemini: copilot is not invoked" \
         "copilot stub ran with argv: $(tr '\n' ' ' < "$COPILOT_ARGV_FILE")"
fi

# 8. Stdin guard holds on the native backend too.
if [ -f "$GEMINI_STDIN_FILE" ] && [ ! -s "$GEMINI_STDIN_FILE" ]; then
    PASS "native gemini child stdin is /dev/null"
else
    FAIL "native gemini child stdin is /dev/null" \
         "stub captured $(wc -c < "$GEMINI_STDIN_FILE" 2>/dev/null | tr -d ' ' || echo '?') byte(s) of stdin; expected 0"
fi

# ══ T4: copilot absent -> native gemini fallback ══════════════════════════════
FALLBACK_STUBDIR="$WORK/stub-gemini-only"
mkdir -p "$FALLBACK_STUBDIR"
cp "$STUBDIR/gemini" "$FALLBACK_STUBDIR/gemini"
SAVED_RUN_PATH="$RUN_PATH"
RUN_PATH="$FALLBACK_STUBDIR:/usr/bin:/bin"
run_gemini t4 -f "$PROMPT_FILE_T"
RUN_PATH="$SAVED_RUN_PATH"

# 9. Fallback order: with copilot absent, the native gemini CLI serves the run.
if [ -f "$GEMINI_ARGV_FILE" ] && argv_has_pair "$GEMINI_ARGV_FILE" "-p" "$GEMINI_PROMPT" && [ "$RC" -eq 0 ]; then
    PASS "copilot absent: falls back to the native gemini CLI"
else
    FAIL "copilot absent: falls back to the native gemini CLI" \
         "rc=$RC; gemini argv: $(tr '\n' ' ' < "$GEMINI_ARGV_FILE" 2>/dev/null || echo '<no gemini invocation>'); stderr: $(cat "$STDERR_F")"
fi

# ══ T5: -s/--silent maps to copilot's -s ══════════════════════════════════════
run_gemini t5 -s -f "$PROMPT_FILE_T"

# 10. -s: accepted and forwarded to the copilot backend as -s.
if [ "$RC" -eq 0 ] && grep -qxF -- "-s" "$COPILOT_ARGV_FILE" 2>/dev/null; then
    PASS "-s is accepted and forwarded to copilot"
else
    FAIL "-s is accepted and forwarded to copilot" \
         "rc=$RC; argv: $(tr '\n' ' ' < "$COPILOT_ARGV_FILE" 2>/dev/null || echo '<no copilot invocation>')"
fi

# ══ T6: missing prompt file -> stderr + non-zero + no dispatch ════════════════
run_gemini t6 -f "$WORK/does-not-exist.txt"

# 11. Missing prompt file: non-zero exit.
if [ "$RC" -ne 0 ]; then
    PASS "missing prompt file exits non-zero"
else
    FAIL "missing prompt file exits non-zero" "rc=0"
fi

# 12. Missing prompt file: the error lands on stderr, not stdout.
if grep -q "not found" "$STDERR_F" 2>/dev/null && ! grep -q "not found" "$STDOUT_F" 2>/dev/null; then
    PASS "missing prompt file: error text is on stderr"
else
    FAIL "missing prompt file: error text is on stderr" \
         "stderr: $(cat "$STDERR_F") -- stdout: $(cat "$STDOUT_F")"
fi

# 13. Missing prompt file: no backend is ever invoked.
if [ ! -f "$COPILOT_ARGV_FILE" ] && [ ! -f "$GEMINI_ARGV_FILE" ]; then
    PASS "missing prompt file: no backend CLI is invoked"
else
    FAIL "missing prompt file: no backend CLI is invoked" \
         "copilot: $(cat "$COPILOT_ARGV_FILE" 2>/dev/null || echo -) gemini: $(cat "$GEMINI_ARGV_FILE" 2>/dev/null || echo -)"
fi

# ══ T7: no prompt at all -> stderr + non-zero ═════════════════════════════════
run_gemini t7

# 14. Missing prompt: non-zero exit with the error on stderr.
if [ "$RC" -ne 0 ] && grep -qi "prompt required" "$STDERR_F" 2>/dev/null; then
    PASS "missing prompt exits non-zero with the error on stderr"
else
    FAIL "missing prompt exits non-zero with the error on stderr" \
         "rc=$RC; stderr: $(cat "$STDERR_F") -- stdout: $(cat "$STDOUT_F")"
fi

# ══ T8: child exit code propagates ════════════════════════════════════════════
export STUB_EXIT_CODE=7
run_gemini t8 -f "$PROMPT_FILE_T"
unset STUB_EXIT_CODE

# 15. Exit-code propagation: the wrapper's exit code equals the child's.
if [ "$RC" -eq 7 ]; then
    PASS "child exit code (7) propagates as gemini-run.sh's own exit code"
else
    FAIL "child exit code (7) propagates as gemini-run.sh's own exit code" \
         "got exit code $RC"
fi

# ══ T9: recursion guard ═══════════════════════════════════════════════════════
# A dispatch from inside a CLI agent must refuse with exit 3 and spawn no child.
# Both triggers are covered -- the depth counter (set by an outer runner) and the
# vendor marker (set by the CLI itself).
guard_case() {
    local name="$1" label="$2"
    shift 2
    export COPILOT_ARGV_FILE="$WORK/$name.copilot.argv"
    export COPILOT_STDIN_FILE="$WORK/$name.copilot.stdin"
    export GEMINI_ARGV_FILE="$WORK/$name.gemini.argv"
    export GEMINI_STDIN_FILE="$WORK/$name.gemini.stdin"
    rm -f "$COPILOT_ARGV_FILE" "$GEMINI_ARGV_FILE"
    local rc=0 out
    out=$(PATH="$RUN_PATH" env "$@" bash "$GEMINI_RUN_SH" -f "$PROMPT_FILE_T" 2>&1 < /dev/null) || rc=$?
    if [ "$rc" -eq 3 ] && [ ! -f "$COPILOT_ARGV_FILE" ] && [ ! -f "$GEMINI_ARGV_FILE" ]; then
        PASS "$label"
    else
        FAIL "$label" "exit: $rc (want 3) -- child argv files present: $(ls "$COPILOT_ARGV_FILE" "$GEMINI_ARGV_FILE" 2>/dev/null | tr '\n' ' ')(want none) -- output: $out"
    fi
}

# 16-18. Refuses nested dispatch, without invoking any backend.
guard_case t9a "AUTOPILOT_DISPATCH_DEPTH=1: refuses with exit 3, no backend call" AUTOPILOT_DISPATCH_DEPTH=1
guard_case t9b "CODEX_SESSION_ID set: refuses with exit 3, no backend call" CODEX_SESSION_ID=deadbeef
guard_case t9c "COPILOT_CLI set: refuses with exit 3, no backend call" COPILOT_CLI=1

# ══ T10: permanent rejection, fallback, and output isolation ════════════════
export COPILOT_EXIT_CODE=1
export COPILOT_STDERR="Error: Model \"$EXPECTED_MODEL\" from --model flag is not available."
export GEMINI_BACKEND=copilot
run_gemini t10 -f "$PROMPT_FILE_T" -o "$WORK/t10.out"
if [ "$RC" -eq 4 ] && grep -qF "$COPILOT_STDERR" "$STDERR_F" &&
   [ ! -e "$WORK/t10.out" ] && [ ! -f "$GEMINI_ARGV_FILE" ]; then
    PASS "forced unavailable model: exit 4, stderr reason, no output or fallback"
else
    FAIL "forced unavailable model" "rc=$RC; stderr: $(cat "$STDERR_F")"
fi

printf '%s\n' 'existing review' > "$WORK/existing.out"
run_gemini t10_existing -f "$PROMPT_FILE_T" -o "$WORK/existing.out"
if [ "$RC" -eq 4 ] && [ "$(cat "$WORK/existing.out")" = 'existing review' ]; then
    PASS "unavailability preserves an existing output file"
else
    FAIL "unavailability preserves an existing output file" "rc=$RC"
fi
unset GEMINI_BACKEND

run_gemini t11 -f "$PROMPT_FILE_T" -o "$WORK/t11.out"
if [ "$RC" -eq 0 ] && [ -f "$COPILOT_ARGV_FILE" ] &&
   [ -f "$GEMINI_ARGV_FILE" ] && [ ! -s "$GEMINI_STDIN_FILE" ] &&
   [ "$(cat "$WORK/t11.out")" = 'stub-gemini-ran' ] &&
   grep -qF 'trying native gemini fallback' "$STDERR_F"; then
    PASS "default rejection falls back successfully; output contains only native result"
else
    FAIL "default rejection fallback" "rc=$RC; stderr: $(cat "$STDERR_F")"
fi

export GEMINI_EXIT_CODE=1
export GEMINI_STDERR='IneligibleTierError: This client is no longer supported for Gemini Code Assist for individuals'
run_gemini t12 -f "$PROMPT_FILE_T" -o "$WORK/t12.out"
if [ "$RC" -eq 4 ] && [ -f "$COPILOT_ARGV_FILE" ] &&
   [ -f "$GEMINI_ARGV_FILE" ] && [ ! -e "$WORK/t12.out" ] &&
   grep -qF "$COPILOT_STDERR" "$STDERR_F" && grep -qF "$GEMINI_STDERR" "$STDERR_F"; then
    PASS "both backends rejected: native tried before exit 4, both reasons, no output"
else
    FAIL "both backends rejected" "rc=$RC; stderr: $(cat "$STDERR_F")"
fi

export GEMINI_BACKEND=gemini
export GEMINI_STDERR='{"reasonCode":"UNSUPPORTED_CLIENT","tierId":"free-tier"}'
run_gemini t13 -f "$PROMPT_FILE_T"
if [ "$RC" -eq 4 ] && [ ! -f "$COPILOT_ARGV_FILE" ] &&
   grep -qF "$GEMINI_STDERR" "$STDERR_F"; then
    PASS "native reasonCode rejection is classified without -o"
else
    FAIL "native reasonCode rejection" "rc=$RC"
fi
unset GEMINI_BACKEND GEMINI_EXIT_CODE GEMINI_STDERR

run_gemini t14 -m custom-model -f "$PROMPT_FILE_T"
if [ "$RC" -eq 4 ] && [ ! -f "$GEMINI_ARGV_FILE" ] &&
   argv_has_pair "$COPILOT_ARGV_FILE" --model custom-model; then
    PASS "explicit model never switches backends on rejection"
else
    FAIL "explicit model never switches backends" "rc=$RC"
fi

run_gemini t15 -r existing-session -f "$PROMPT_FILE_T"
if [ "$RC" -eq 4 ] && [ ! -f "$GEMINI_ARGV_FILE" ]; then
    PASS "resume never switches backends on rejection"
else
    FAIL "resume never switches backends" "rc=$RC"
fi

export COPILOT_STDERR='monthly quota exceeded'
export COPILOT_EXIT_CODE=7
run_gemini t16 -f "$PROMPT_FILE_T" -o "$WORK/t16.out"
if [ "$RC" -eq 7 ] && [ ! -f "$GEMINI_ARGV_FILE" ] &&
   [ "$(cat "$WORK/t16.out")" = 'stub-copilot-ran' ] &&
   grep -qF "$COPILOT_STDERR" "$STDERR_F"; then
    PASS "quota retains exit code and partial stdout without fallback"
else
    FAIL "quota retains exit code and partial stdout" "rc=$RC"
fi

export COPILOT_EXIT_CODE=0
export COPILOT_STDERR='IneligibleTierError mentioned in a successful diagnostic'
run_gemini t17 -f "$PROMPT_FILE_T"
if [ "$RC" -eq 0 ] && [ ! -f "$GEMINI_ARGV_FILE" ]; then
    PASS "successful stderr mentioning rejection is not classified as failure"
else
    FAIL "successful stderr mentioning rejection" "rc=$RC"
fi

export COPILOT_STDERR='generic failure'
for code in 3 4; do
    export COPILOT_EXIT_CODE="$code"
    run_gemini "t18_$code" -f "$PROMPT_FILE_T"
    if [ "$RC" -eq 1 ] && [ ! -f "$GEMINI_ARGV_FILE" ] &&
       grep -qF "exited $code (runtime failure)" "$STDERR_F"; then
        PASS "unclassified child exit $code cannot impersonate a reserved status"
    else
        FAIL "unclassified child exit $code" "rc=$RC"
    fi
done
unset COPILOT_EXIT_CODE COPILOT_STDERR

export GEMINI_BACKEND=typo
run_gemini t19 -f "$PROMPT_FILE_T"
if [ "$RC" -eq 1 ] && [ ! -f "$COPILOT_ARGV_FILE" ] &&
   [ ! -f "$GEMINI_ARGV_FILE" ] && grep -qF 'invalid GEMINI_BACKEND' "$STDERR_F"; then
    PASS "invalid backend fails before dispatch"
else
    FAIL "invalid backend" "rc=$RC"
fi
unset GEMINI_BACKEND

# ══ T20: interactive stderr must reach caller while backend is still running ═
export LIVE_STDERR_FILE="$WORK/t20.stderr"
run_gemini t20 -i "$GEMINI_PROMPT"
unset LIVE_STDERR_FILE
if [ "$RC" -eq 0 ] && grep -qF 'SENTINEL_STDIN_DATA' "$COPILOT_STDIN_FILE"; then
    PASS "interactive approval prompt is visible before child exits; stdin preserved"
else
    FAIL "interactive stderr visibility" "rc=$RC"
fi

export LIVE_STDERR_FILE="$WORK/t21.stderr"
run_gemini t21 -r existing-session
unset LIVE_STDERR_FILE
if [ "$RC" -eq 0 ] && grep -qF 'SENTINEL_STDIN_DATA' "$COPILOT_STDIN_FILE"; then
    PASS "bare resume approval prompt is visible before child exits; stdin preserved"
else
    FAIL "bare resume stderr visibility" "rc=$RC"
fi

export COPILOT_STDOUT='IneligibleTierError is a finding in the reviewed source'
export COPILOT_EXIT_CODE=7
run_gemini t22 -f "$PROMPT_FILE_T"
if [ "$RC" -eq 7 ] && [ ! -f "$GEMINI_ARGV_FILE" ]; then
    PASS "rejection words in model stdout cannot trigger classification or fallback"
else
    FAIL "stdout rejection words" "rc=$RC"
fi
unset COPILOT_STDOUT COPILOT_EXIT_CODE

# ══ T23-T27: live lane marker inside an autopilot loop ════════════════════════
# With _AUTOPILOT_LOOP non-empty the wrapper leaves <autopilot dir>/lanes/<pid>
# for its lifetime. The stubs copy the lanes dir out mid-run (STUB_LANES_DIR),
# since the marker is gone once the wrapper exits.
LANE_REPO="$WORK/lane-repo"
mkdir -p "$LANE_REPO/dev/local/autopilot" "$LANE_REPO/sub/deeper"
LANE_REPO=$(cd "$LANE_REPO" && pwd -P)
LANE_LANES_DIR="$LANE_REPO/dev/local/autopilot/lanes"

# run_lane_case <name> <loop value or empty> <cwd> [args...] -- snapshot lands
# in $WORK/<name>.snap; RC is the wrapper's exit code.
run_lane_case() {
    local name="$1" loop="$2" cwd="$3"
    shift 3
    mkdir -p "$WORK/$name.snap"
    RC=0
    (
        cd "$cwd" || exit 99
        unset _AUTOPILOT_LOOP
        [ -z "$loop" ] || export _AUTOPILOT_LOOP="$loop"
        export STUB_LANES_DIR="$LANE_LANES_DIR" STUB_LANES_SNAPSHOT_DIR="$WORK/$name.snap"
        run_gemini "$name" "$@"
        exit "$RC"
    ) || RC=$?
}

# T23. Loop set, cwd below dev/local/autopilot, copilot backend: one
#      integer-named marker during the run, line 1 'gemini', line 2 the -o
#      path; lanes dir empty after.
T23_OUT="$WORK/t23.out"
run_lane_case t23 1 "$LANE_REPO/sub/deeper" -f "$PROMPT_FILE_T" -o "$T23_OUT"
T23_SNAP="$WORK/t23.snap"
T23_NAME=$(ls "$T23_SNAP" 2>/dev/null)
T23_COUNT=$(ls "$T23_SNAP" 2>/dev/null | wc -l | tr -d ' ')
T23_L1=$(sed -n 1p "$T23_SNAP/$T23_NAME" 2>/dev/null)
T23_L2=$(sed -n 2p "$T23_SNAP/$T23_NAME" 2>/dev/null)
T23_EXTRA=$(sed -n '3,$p' "$T23_SNAP/$T23_NAME" 2>/dev/null)
if [ "$RC" -eq 0 ] && [ -f "$WORK/t23.copilot.argv" ] && [ "$T23_COUNT" = "1" ] &&
   printf '%s' "$T23_NAME" | grep -qxE '[0-9]+' &&
   [ "$T23_L1" = "gemini" ] && [ "$T23_L2" = "$T23_OUT" ] && [ -z "$T23_EXTRA" ] &&
   [ -d "$LANE_LANES_DIR" ] && [ -z "$(ls -A "$LANE_LANES_DIR")" ]; then
    PASS "_AUTOPILOT_LOOP=1 under dev/local/autopilot: one <pid> marker during the run holding 'gemini' (copilot backend) and the -o path, lanes dir empty after"
else
    FAIL "_AUTOPILOT_LOOP=1 lane marker" \
         "rc=$RC; entries: '$(printf '%s' "$T23_NAME" | tr '\n' ' ')' (count $T23_COUNT); line1='$T23_L1' line2='$T23_L2' extra='$T23_EXTRA' (want gemini / $T23_OUT / none); lanes after: $(ls -A "$LANE_LANES_DIR" 2>&1 | tr '\n' ' ')"
fi

# T24. Loop set, no -o: marker line 1 'gemini', line 2 empty.
rm -rf "$LANE_LANES_DIR"
run_lane_case t24 1 "$LANE_REPO" -f "$PROMPT_FILE_T"
T24_NAME=$(ls "$WORK/t24.snap" 2>/dev/null)
if [ "$RC" -eq 0 ] && [ "$(ls "$WORK/t24.snap" | wc -l | tr -d ' ')" = "1" ] &&
   [ "$(sed -n 1p "$WORK/t24.snap/$T24_NAME")" = "gemini" ] &&
   [ -z "$(sed -n '2,$p' "$WORK/t24.snap/$T24_NAME")" ]; then
    PASS "_AUTOPILOT_LOOP=1 without -o: marker line 1 is 'gemini', line 2 is empty"
else
    FAIL "_AUTOPILOT_LOOP=1 without -o" \
         "rc=$RC; entries: $(ls "$WORK/t24.snap" | tr '\n' ' '); content: $(cat "$WORK/t24.snap/$T24_NAME" 2>/dev/null | tr '\n' '|')"
fi

# T25. No _AUTOPILOT_LOOP: no marker written, no lanes dir created.
rm -rf "$LANE_LANES_DIR"
run_lane_case t25 "" "$LANE_REPO" -f "$PROMPT_FILE_T" -o "$WORK/t25.out"
if [ "$RC" -eq 0 ] && [ -f "$WORK/t25.copilot.argv" ] &&
   [ -z "$(ls "$WORK/t25.snap")" ] && [ ! -e "$LANE_LANES_DIR" ]; then
    PASS "_AUTOPILOT_LOOP unset: no lane marker is written and no lanes dir is created"
else
    FAIL "_AUTOPILOT_LOOP unset: no lane marker" \
         "rc=$RC; entries: $(ls "$WORK/t25.snap" | tr '\n' ' '); lanes dir: $(ls -A "$LANE_LANES_DIR" 2>&1 | tr '\n' ' ')"
fi

# T26. Loop set, no dev/local/autopilot at or above cwd: exit 0, nothing made.
LANE_BARE=$(mktemp -d)
_DIRS+=("$LANE_BARE")
run_lane_case t26 1 "$LANE_BARE" -f "$PROMPT_FILE_T" -o "$WORK/t26.out"
if [ "$RC" -eq 0 ] && [ -f "$WORK/t26.copilot.argv" ] && [ -z "$(ls -A "$LANE_BARE")" ]; then
    PASS "_AUTOPILOT_LOOP=1 with no dev/local/autopilot above cwd: exits 0 and creates nothing"
else
    FAIL "_AUTOPILOT_LOOP=1 with no autopilot dir" \
         "rc=$RC; cwd contents: $(ls -A "$LANE_BARE" | tr '\n' ' ')"
fi

# T27. Loop set, lane marked: the wrapper's private temp dir under TMPDIR is
#      still removed at exit.
LANE_TMPDIR=$(mktemp -d)
_DIRS+=("$LANE_TMPDIR")
rm -rf "$LANE_LANES_DIR"
RC=0
( export TMPDIR="$LANE_TMPDIR"; run_lane_case t27 1 "$LANE_REPO" -f "$PROMPT_FILE_T" -o "$WORK/t27.out"; exit "$RC" ) || RC=$?
if [ "$RC" -eq 0 ] && [ "$(ls "$WORK/t27.snap" | wc -l | tr -d ' ')" = "1" ] &&
   [ -z "$(ls -A "$LANE_TMPDIR")" ]; then
    PASS "_AUTOPILOT_LOOP=1 with a lane marker: the private temp dir under TMPDIR is removed at exit"
else
    FAIL "_AUTOPILOT_LOOP=1 TMPDIR cleanup" \
         "rc=$RC; lane entries: $(ls "$WORK/t27.snap" | tr '\n' ' '); TMPDIR leftovers: $(ls -A "$LANE_TMPDIR" | tr '\n' ' ')"
fi

# ══ summary ═══════════════════════════════════════════════════════════════════
echo ""
echo "SUMMARY: $PASS_COUNT passed, $FAIL_COUNT failed"

[ "$FAIL_COUNT" -eq 0 ]
