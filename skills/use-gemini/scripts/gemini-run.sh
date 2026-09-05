#!/bin/bash
# Run Gemini for code analysis/editing.
#
# Backend: prefers GitHub Copilot; falls back to native `gemini` when absent
# or permanently unavailable for a default prompt run.
# Override with GEMINI_BACKEND=copilot|gemini.
#
# Copilot billing note: every call spends Copilot AI credits (multiplier set by
# the model). The native gemini backend bills your Google/Gemini account with no
# Copilot multiplier. Per policy, Gemini-via-Copilot is allowed (Claude does not
# provide Gemini); only models Claude serves must stay off Copilot.

set -eo pipefail

# Recursion guard. Refuse to dispatch a CLI agent from inside a CLI agent.
# ponytail: depth backstop is the real guard; the marker check is a nicety.
# Exported by this script, never from settings.json - a nested CLI never sees
# that env block. Markers are documented in ../../use-codex/references/host-markers.md.
if [ -n "${AUTOPILOT_DISPATCH_DEPTH:-}" ] && [ "$AUTOPILOT_DISPATCH_DEPTH" -ge 1 ]; then
    echo "refusing nested dispatch (depth=$AUTOPILOT_DISPATCH_DEPTH)" >&2
    exit 3
fi
if [ -n "${CODEX_SESSION_ID:-}" ] || [ -n "${COPILOT_CLI:-}" ]; then
    echo "refusing nested dispatch (already inside a CLI agent)" >&2
    exit 3
fi
export AUTOPILOT_DISPATCH_DEPTH=$(( ${AUTOPILOT_DISPATCH_DEPTH:-0} + 1 ))

# Ensure mise-managed tools (copilot/gemini, plus build/test tools they invoke)
# are on PATH. Matches codex-run.sh / sonnet-run.sh.
if command -v mise &>/dev/null; then
    PATH="$(mise env -s bash < /dev/null 2>/dev/null | sed -n "s/^export PATH='\\(.*\\)'/\\1/p"):$PATH"
fi

resolve_bin() {
    # $1 = tool name; echoes path or empty
    local p
    p="$(command -v "$1" 2>/dev/null || true)"
    if [ -z "$p" ] && command -v mise &>/dev/null; then
        p="$(mise which "$1" 2>/dev/null || true)"
    fi
    echo "$p"
}

# Backend selection. Explicit backend/model/session choices never switch CLIs.
BACKEND="${GEMINI_BACKEND:-}"
case "$BACKEND" in
    ""|copilot|gemini) ;;
    *) echo "ERROR: invalid GEMINI_BACKEND: $BACKEND" >&2; exit 1 ;;
esac
COPILOT_BIN="$(resolve_bin copilot)"
GEMINI_BIN="$(resolve_bin gemini)"
if [ -z "$BACKEND" ]; then
    if [ -n "$COPILOT_BIN" ]; then
        BACKEND="copilot"
    elif [ -n "$GEMINI_BIN" ]; then
        BACKEND="gemini"
    fi
fi
if [ "$BACKEND" = "copilot" ] && [ -z "$COPILOT_BIN" ]; then
    echo "ERROR: GEMINI_BACKEND=copilot but the copilot CLI was not found." >&2
    exit 1
fi
if [ "$BACKEND" = "gemini" ] && [ -z "$GEMINI_BIN" ]; then
    echo "ERROR: GEMINI_BACKEND=gemini but the gemini CLI was not found." >&2
    exit 1
fi
if [ -z "$BACKEND" ]; then
    echo "ERROR: neither 'copilot' nor 'gemini' CLI found." >&2
    echo "Install one (e.g. 'mise use -g npm:@github/copilot' or 'mise use -g npm:@google/gemini-cli') and retry." >&2
    exit 1
fi

# Single production pin, verified in copilot /model on 2026-09-05.
# Override with -m. The native gemini backend keeps the CLI default unless -m.
DEFAULT_COPILOT_MODEL="gemini-3.8-flash"

MODEL=""          # empty = backend default
MODE="prompt"     # prompt, interactive, resume, continue
APPROVAL=""       # auto_edit | yolo (intent; mapped per backend)
RAW_DIRS=()
PROMPT=""
PROMPT_FILE=""
OUTPUT_FILE=""
RESUME_ID=""
SILENT=""

usage() {
    echo "Usage: $0 [options] [prompt]"
    echo ""
    echo "Backend: $BACKEND (copilot preferred, gemini fallback)."
    echo "copilot default model: $DEFAULT_COPILOT_MODEL. Override backend with GEMINI_BACKEND=copilot|gemini."
    echo ""
    echo "Options:"
    echo "  -m, --model MODEL      Override model (copilot default: $DEFAULT_COPILOT_MODEL)"
    echo "  -i, --interactive      Interactive mode with initial prompt"
    echo "  -a, --allow-tools      Auto-approve edit tools"
    echo "  -y, --yolo             Auto-approve all tools"
    echo "  -s, --silent           Quiet output (copilot only; gemini -p is already clean)"
    echo "  -d, --dir DIR          Include extra directory in the workspace (can repeat)"
    echo "  -f, --file FILE        Read prompt from file"
    echo "  -o, --output FILE      Save stdout after classification (also streams to stdout)"
    echo "  -r, --resume [ID]      Resume session ('latest' or index; default: latest)"
    echo "  -c, --continue         Resume most recent session"
    echo "  -h, --help             Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 'Analyze the codebase'"
    echo "  $0 -a -f /tmp/prompt.txt"
    echo "  GEMINI_BACKEND=gemini $0 -f /tmp/prompt.txt   # use native Gemini CLI"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--model)
            MODEL="$2"
            shift 2
            ;;
        -i|--interactive)
            MODE="interactive"
            shift
            ;;
        -a|--allow-tools)
            APPROVAL="auto_edit"
            shift
            ;;
        -y|--yolo)
            APPROVAL="yolo"
            shift
            ;;
        -s|--silent)
            SILENT="1"
            shift
            ;;
        -d|--dir)
            RAW_DIRS+=("$2")
            shift 2
            ;;
        -f|--file)
            PROMPT_FILE="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -r|--resume)
            MODE="resume"
            if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                RESUME_ID="$2"
                shift
            fi
            shift
            ;;
        -c|--continue)
            MODE="continue"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            PROMPT="$1"
            shift
            ;;
    esac
done

# Read prompt from file if specified
if [ -n "$PROMPT_FILE" ]; then
    if [ ! -f "$PROMPT_FILE" ]; then
        echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
        exit 1
    fi
    PROMPT=$(cat "$PROMPT_FILE")
fi

# Keep stderr separate for classification; never classify the model's prose.
RUN_TMP=$(mktemp -d) || exit 1
trap 'rm -rf "$RUN_TMP"' EXIT
mkfifo "$RUN_TMP/stderr.pipe" || exit 1

permanently_unavailable() {
    grep -Eiq 'Model "[^"]+" from --model flag is not available|IneligibleTierError|reasonCode[^[:alnum:]]+UNSUPPORTED_CLIENT' "$RUN_TMP/stderr"
}

# Preserve ordinary failure output for salvage, but do not publish a rejected
# backend's partial output. An existing destination is left untouched on exit 4.
run_cmd() {
    local rc=0 stderr_pid
    # Stream prompts/diagnostics immediately, then wait for tee to finish before
    # classifying. Merely redirecting stderr to a file hides interactive prompts.
    tee "$RUN_TMP/stderr" < "$RUN_TMP/stderr.pipe" >&2 &
    stderr_pid=$!
    if [ -n "$OUTPUT_FILE" ]; then
        "$@" 2> "$RUN_TMP/stderr.pipe" | tee "$RUN_TMP/stdout" || rc=$?
    else
        "$@" 2> "$RUN_TMP/stderr.pipe" || rc=$?
    fi
    wait "$stderr_pid" || return 1
    if [ "$rc" -ne 0 ] && permanently_unavailable; then
        echo "ERROR: $BACKEND permanently unavailable (model/client tier rejected)." >&2
        return 4
    fi
    if [ -n "$OUTPUT_FILE" ]; then
        cat "$RUN_TMP/stdout" > "$OUTPUT_FILE" || return 1
    fi
    # Reserve 3 for the recursion guard and 4 for classified unavailability.
    case "$rc" in
        3|4) echo "ERROR: $BACKEND exited $rc (runtime failure)." >&2; return 1 ;;
    esac
    return "$rc"
}

run_copilot() {
    local model="${MODEL:-$DEFAULT_COPILOT_MODEL}"
    echo "gemini-run: backend=copilot model=$model" >&2
    local dirs=()
    local d
    for d in "${RAW_DIRS[@]}"; do dirs+=(--add-dir "$d"); done
    [ -n "$SILENT" ] && dirs+=(-s)   # -s belongs to copilot; group with extras

    # Permission mapping. Copilot's non-interactive (-p / resume) mode REQUIRES
    # auto-approval or it blocks on a prompt; with no -a/-y we auto-approve reads
    # but deny the write tool to preserve read-only-review intent.
    local perms=()
    local noninteractive_perms=()
    if [ "$APPROVAL" = "yolo" ]; then
        perms=(--yolo); noninteractive_perms=(--yolo)
    elif [ "$APPROVAL" = "auto_edit" ]; then
        perms=(--allow-all-tools); noninteractive_perms=(--allow-all-tools)
    else
        noninteractive_perms=(--allow-all-tools --deny-tool=write)
    fi

    case $MODE in
        interactive)
            [ -z "$PROMPT" ] && { echo "ERROR: Prompt required for interactive mode" >&2; exit 1; }
            run_cmd "$COPILOT_BIN" --model "$model" "${perms[@]}" "${dirs[@]}" -i "$PROMPT"
            ;;
        continue)
            run_cmd "$COPILOT_BIN" --model "$model" "${noninteractive_perms[@]}" "${dirs[@]}" --continue
            ;;
        resume)
            local rflag=(--resume)
            [ -n "$RESUME_ID" ] && [ "$RESUME_ID" != "latest" ] && rflag=(--resume="$RESUME_ID")
            if [ -n "$PROMPT" ]; then
                run_cmd "$COPILOT_BIN" --model "$model" "${noninteractive_perms[@]}" "${dirs[@]}" "${rflag[@]}" -p "$PROMPT" < /dev/null
            else
                run_cmd "$COPILOT_BIN" --model "$model" "${noninteractive_perms[@]}" "${dirs[@]}" "${rflag[@]}"
            fi
            ;;
        prompt)
            [ -z "$PROMPT" ] && { echo "ERROR: Prompt required" >&2; exit 1; }
            # Headless (-p) dispatch: guard child stdin so an unattended
            # background run can never hang on a child reading the inherited
            # stdin (PRD 00040 hang class). Interactive and bare-resume modes
            # keep stdin - they need the TTY.
            run_cmd "$COPILOT_BIN" --model "$model" "${noninteractive_perms[@]}" "${dirs[@]}" -p "$PROMPT" < /dev/null
            ;;
    esac
}

run_gemini() {
    echo "gemini-run: backend=gemini model=${MODEL:-CLI-default}" >&2
    # Flags common to every invocation. --skip-trust avoids the workspace-trust
    # prompt blocking headless (-p) runs.
    local common=(--skip-trust)
    [ -n "$MODEL" ] && common+=(-m "$MODEL")
    case $APPROVAL in
        auto_edit) common+=(--approval-mode auto_edit) ;;
        yolo) common+=(--approval-mode yolo) ;;
    esac
    local d
    for d in "${RAW_DIRS[@]}"; do common+=(--include-directories "$d"); done

    case $MODE in
        resume)
            local id="${RESUME_ID:-latest}"
            if [ -n "$PROMPT" ]; then
                run_cmd "$GEMINI_BIN" "${common[@]}" --resume "$id" -p "$PROMPT" < /dev/null
            else
                run_cmd "$GEMINI_BIN" "${common[@]}" --resume "$id"
            fi
            ;;
        continue)
            run_cmd "$GEMINI_BIN" "${common[@]}" --resume latest
            ;;
        interactive)
            [ -z "$PROMPT" ] && { echo "ERROR: Prompt required for interactive mode" >&2; exit 1; }
            run_cmd "$GEMINI_BIN" "${common[@]}" -i "$PROMPT"
            ;;
        prompt)
            [ -z "$PROMPT" ] && { echo "ERROR: Prompt required" >&2; exit 1; }
            # Headless (-p) dispatch: guard child stdin (PRD 00040 hang
            # class). Interactive and bare-resume modes keep the TTY.
            run_cmd "$GEMINI_BIN" "${common[@]}" -p "$PROMPT" < /dev/null
            ;;
    esac
}

if [ "$BACKEND" = "copilot" ]; then
    rc=0
    run_copilot || rc=$?
    if [ "$rc" -eq 4 ] && [ -z "${GEMINI_BACKEND:-}" ] &&
       [ -z "$MODEL" ] && [ "$MODE" = "prompt" ] && [ -n "$GEMINI_BIN" ]; then
        echo "gemini-run: trying native gemini fallback after permanent rejection." >&2
        BACKEND=gemini
        run_gemini
    else
        exit "$rc"
    fi
else
    run_gemini
fi
