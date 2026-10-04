#!/usr/bin/env bash
# Gathers review context into docs/dev/tmp/
# Usage: gather-context.sh [--since <ref>] [tasks_file] [prd_summary_file]
#   --since <ref>:    diff base for an incremental review (rework cycles);
#                     when omitted or invalid, diffs against the branch base
#   tasks_file:       path to file containing tasks markdown (optional)
#   prd_summary_file: path to file containing PRD summary (optional)
# Outputs: paths to created files (one per line)
# Exits 3 (no diff/context file written) when a full review (no --since)
# resolves to an empty diff - a repo worked on directly on its base branch
# otherwise hands reviewers a silent, empty "full review".

set -euo pipefail

PROJECT_ROOT="$(pwd)"

# Parse args: optional `--since <ref>` flag, then up to two positionals.
SINCE_REF=""
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --since)
      SINCE_REF="${2:-}"
      shift
      [[ $# -gt 0 ]] && shift
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done
TASKS_FILE="${POSITIONAL[0]:-}"
PRD_FILE="${POSITIONAL[1]:-}"

TASKS_MD=""
PRD_SUMMARY=""
[[ -n "$TASKS_FILE" && -f "$TASKS_FILE" ]] && TASKS_MD="$(cat "$TASKS_FILE")"
[[ -n "$PRD_FILE" && -f "$PRD_FILE" ]] && PRD_SUMMARY="$(cat "$PRD_FILE")"

TMP_DIR="$PROJECT_ROOT/docs/dev/tmp"
mkdir -p "$TMP_DIR"

# Determine base branch
BASE_BRANCH=""
CURRENT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)

# Try: remote default branch (most reliable)
if [[ -z "$BASE_BRANCH" ]]; then
  BASE_BRANCH=$(git -C "$PROJECT_ROOT" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || true)
fi

# Try: find merge-base with common defaults
if [[ -z "$BASE_BRANCH" ]]; then
  for candidate in master develop; do
    if git -C "$PROJECT_ROOT" rev-parse --verify "$candidate" >/dev/null 2>&1; then
      BASE_BRANCH="$candidate"
      break
    fi
  done
fi

# Try: first parent of current branch's root commit (feature branch base)
if [[ -z "$BASE_BRANCH" && -n "$CURRENT_BRANCH" ]]; then
  # Get the merge-base between HEAD and all remote tracking branches
  for remote_branch in $(git -C "$PROJECT_ROOT" branch -r 2>/dev/null | grep -v HEAD | head -5); do
    if MERGE_BASE=$(git -C "$PROJECT_ROOT" merge-base HEAD "$remote_branch" 2>/dev/null); then
      BASE_BRANCH="$remote_branch"
      break
    fi
  done
fi

# Resolve the diff base: an explicit, valid --since <ref> (incremental
# rework review) overrides the detected branch base.
DIFF_BASE="$BASE_BRANCH"
DIFF_SCOPE="full review (vs ${BASE_BRANCH:-unknown base})"
SINCE_APPLIED=""
if [[ -n "$SINCE_REF" ]] && git -C "$PROJECT_ROOT" cat-file -e "$SINCE_REF" >/dev/null 2>&1; then
  DIFF_BASE="$SINCE_REF"
  DIFF_SCOPE="incremental review (changes since ${SINCE_REF})"
  SINCE_APPLIED=1
fi

# Scope both diff calls to the paths listed in the review-paths marker
# file, when present and non-empty; otherwise diff the whole repo as before.
REVIEW_PATHS_MARKER="$PROJECT_ROOT/docs/dev/project-management/autopilot/review-paths"
REVIEW_PATHS=()
if [[ -s "$REVIEW_PATHS_MARKER" ]]; then
  while IFS= read -r review_path; do
    [[ -n "$review_path" ]] && REVIEW_PATHS+=("$review_path")
  done < "$REVIEW_PATHS_MARKER"
fi
if [[ ${#REVIEW_PATHS[@]} -gt 0 ]]; then
  DIFF_SCOPE="path-scoped review (${#REVIEW_PATHS[@]} paths from docs/dev/project-management/autopilot/review-paths)"
fi

PATH_ARGS=()
if [[ ${#REVIEW_PATHS[@]} -gt 0 ]]; then
  PATH_ARGS=(-- "${REVIEW_PATHS[@]}")
fi

# A full review (no --since) that resolves to an empty diff, or that found
# no base branch to diff against at all, would otherwise hand reviewers a
# silently empty review (PRD 00237: a repo worked on directly on its base
# branch diffs against itself at a clean HEAD).
if [[ -z "$SINCE_APPLIED" ]]; then
  if [[ -z "$DIFF_BASE" ]]; then
    echo "gather-context: empty diff against ${DIFF_BASE}; pass --since <work_start_sha> for a full review" >&2
    exit 3
  fi
  DIFF_QUIET_ERR="$(git -C "$PROJECT_ROOT" diff --quiet "$DIFF_BASE" ${PATH_ARGS[@]+"${PATH_ARGS[@]}"} 2>&1)" && DIFF_QUIET_EXIT=0 || DIFF_QUIET_EXIT=$?
  if [[ "$DIFF_QUIET_EXIT" -ge 2 ]]; then
    echo "$DIFF_QUIET_ERR" >&2
    exit "$DIFF_QUIET_EXIT"
  elif [[ "$DIFF_QUIET_EXIT" -eq 0 ]]; then
    echo "gather-context: empty diff against ${DIFF_BASE}; pass --since <work_start_sha> for a full review" >&2
    exit 3
  fi
fi

# Track all created files
CREATED_FILES=()
# Reuse the caller's cycle id (review-prd-{id}.md) so review debris is
# PRD-linked so purge-devtmp can preserve live work; fall back to epoch-pid.
_ID="$(date +%s)-$$"
if [[ -n "$PRD_FILE" ]]; then
  _BASE="$(basename "$PRD_FILE" .md)"
  [[ "$_BASE" == review-prd-* ]] && _ID="${_BASE#review-prd-}"
fi
CONTEXT_FILE="$TMP_DIR/review-context-${_ID}.md"
CREATED_FILES+=("$CONTEXT_FILE")

{
  echo "# Review Context"
  echo
  echo "## Completed Tasks"
  echo
  if [[ -n "$TASKS_MD" ]]; then
    echo "$TASKS_MD"
  else
    echo "_No tasks provided_"
  fi
  echo
  echo "## Code Changes"
  echo

  if [[ -n "$DIFF_BASE" ]]; then
    echo "### Changed Files"
    echo "_Diff scope: ${DIFF_SCOPE}_"
    echo
    echo '```'
    git -C "$PROJECT_ROOT" diff "$DIFF_BASE" --stat ${PATH_ARGS[@]+"${PATH_ARGS[@]}"} 2>/dev/null || echo "_No diff available_"
    echo '```'
    echo
    DIFF_FILE="$TMP_DIR/review-diff-${_ID}.diff"
    git -C "$PROJECT_ROOT" diff "$DIFF_BASE" ${PATH_ARGS[@]+"${PATH_ARGS[@]}"} > "$DIFF_FILE" 2>/dev/null || echo "_No diff available_" > "$DIFF_FILE"
    CREATED_FILES+=("$DIFF_FILE")
    echo "### Diff Content"
    echo "Full diff available at: $DIFF_FILE"
    echo
    DIFF_LINES=$(wc -l < "$DIFF_FILE")
    echo "($DIFF_LINES lines)"
  else
    echo "_No base branch found for diff_"
  fi
  echo
  echo "## PRD Requirements"
  echo
  if [[ -n "$PRD_SUMMARY" ]]; then
    echo "$PRD_SUMMARY"
  else
    echo "_No PRD summary provided_"
  fi
} > "$CONTEXT_FILE"

# Output all created files
for f in "${CREATED_FILES[@]}"; do
  echo "$f"
done
