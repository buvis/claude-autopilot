"""PreToolUse hook: enforce where working documents live.

Two layers, one gate (merged 2026-08-23):

1. PRD lifecycle dirs (backlog/, wip/, hold/, done/) exist under
   `docs/dev/project-management/prds/` only, never at repo root (Edit/Write/MultiEdit + Bash).
   Replaces the old enforce-prd-location.sh / enforce-prd-location-bash.sh
   pair; branches on `tool_name`.
2. The docs/dev/project-management layout contract (aegis rules/working-documents.md) holds at
   write time: root holds no files (named keepers live in meta/), new
   top-level dirs are forbidden
   (workspaces go under tmp/), .trash/ is GC-owned, and files directly in
   prds/ must sit in a lifecycle subdir. File tools only - aegis's
   block_devlocal_redirects.py funnels shell redirects into the Write tool,
   which lands here; `mv`/`cp` into docs/dev/project-management via Bash bypasses both gates
   (warden owns Bash; accepted gap).

KEEP_NAMES and KNOWN_DIRS mirror purge_devlocal.py; the test suite asserts
the two stay in sync rather than importing across trees. The purge-devlocal
GC reclaims debris after the fact; this hook stops it landing.
"""

import os
import shlex
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import allow, block, read_input, resolve_toplevel

LIFECYCLE_DIRS = ("backlog", "wip", "hold", "done")
STORE_PARTS = ("docs", "dev", "project-management")

KEEP_NAMES = {
    "project-capsule.md",
    "decisions.md",
    "troubleshooting.md",
    "assumptions.md",
    "agoge-profile.md",
    "ecc-cursor",
    "upstream-cursor",
}
KNOWN_DIRS = {
    "prds",
    "designs",
    "reviews",
    "plans",
    "tmp",
    "autopilot",
    "meta",
    "discovery",
    "specs",
    "notes",
    "walkthroughs",
    "audit-results",
    "spikes",
}

FS_MUTATING_COMMANDS = frozenset(
    {"mv", "cp", "rm", "rsync", "ln", "mkdir", "rmdir", "scp", "tar"},
)


def _block_path_msg(rel: str) -> str:
    return f"""\
BLOCKED: `{rel}` looks like a PRD lifecycle path at repo root.

PRDs must live under `docs/dev/project-management/prds/`:
  - docs/dev/project-management/prds/backlog/    (planned, not started)
  - docs/dev/project-management/prds/wip/        (actively implementing)
  - docs/dev/project-management/prds/hold/       (parked)
  - docs/dev/project-management/prds/done/       (completed)

If this is a PRD, retry with `docs/dev/project-management/prds/{rel}`.
If this is genuinely something else that must live at repo root, rename the directory to avoid clashing with PRD lifecycle folders."""


def _block_bash_msg(matches: list[str]) -> str:
    formatted = "\n".join(f"  {m}" for m in matches)
    return f"""\
BLOCKED: command references a repo-root `backlog/`, `wip/`, `hold/`, or `done/` directory.

PRDs must live under `docs/dev/project-management/prds/`:
  - docs/dev/project-management/prds/backlog/    (planned, not started)
  - docs/dev/project-management/prds/wip/        (actively implementing)
  - docs/dev/project-management/prds/hold/       (parked)
  - docs/dev/project-management/prds/done/       (completed)

Offending references in the command:
{formatted}

If this is a PRD move, retry with `docs/dev/project-management/prds/<lifecycle>/` paths on both sides.
If this is genuinely an unrelated directory, rename it to avoid clashing with PRD lifecycle folders."""


def _root_msg(name: str) -> str:
    if name in KEEP_NAMES:
        return f"""\
BLOCKED: `{name}` would land in docs/dev/project-management ROOT. It is a named keeper, and its
canonical home is `docs/dev/project-management/meta/{name}` - write it there."""
    keepers = ", ".join(sorted(KEEP_NAMES))
    return f"""\
BLOCKED: `{name}` would land in docs/dev/project-management ROOT. Root holds no files: the named
keepers ({keepers}) live in `docs/dev/project-management/meta/`, everything else in a dir below.

- Throwaway output -> `docs/dev/tmp/{name}` (prefix the 5-digit PRD number
  when one applies, so it dies with the PRD).
- Durable artifact -> a curated dir (discovery/, notes/, audit-results/, ...).
- Genuinely a new keeper -> add it to KEEP_NAMES in BOTH
  ~/.claude/hooks/enforce_prd_location.py and
  ~/.claude/skills/purge-devlocal/scripts/purge_devlocal.py, then write it
  under `docs/dev/project-management/meta/`.
- Editing an existing stray? `mv` it under docs/dev/tmp/ first, then edit."""


def _meta_msg(name: str) -> str:
    return f"""\
BLOCKED: `meta/{name}` - docs/dev/project-management/meta/ holds ONLY the named keepers
({", ".join(sorted(KEEP_NAMES))}).

Throwaway output goes to `docs/dev/tmp/`, durable artifacts to a curated
dir. A genuinely new keeper gets added to KEEP_NAMES (hook + GC) first."""


def _foreign_msg(top: str) -> str:
    return f"""\
BLOCKED: `{top}/` is not a docs/dev/project-management top-level dir. New top-level dirs are
forbidden (they become GC blind spots); the vocabulary is:
{", ".join(sorted(KNOWN_DIRS))}.

One-off workspaces belong under `docs/dev/tmp/{top}/` (PRD-numbered when one
applies). Curated content goes in an existing curated dir."""


def _trash_msg() -> str:
    return """\
BLOCKED: `.trash/` is owned by the purge-devlocal GC. Never write there by
hand - run the purge-devlocal skill to trash files, or `mv` a file OUT to
restore it."""


def _prds_root_msg(rel: str) -> str:
    return f"""\
BLOCKED: `{rel}` sits directly in docs/dev/project-management/prds/ - PRDs live in a lifecycle
subdir (prds/backlog/, prds/wip/, prds/hold/, prds/done/).

Not a PRD? Plans go in docs/dev/project-management/plans/ (PRD-numbered) or docs/dev/tmp/."""


def _rel_in_devlocal(file_path: str) -> tuple[str, ...] | None:
    """Store-relative parts of file_path when it targets a docs/dev/project-management store.

    Matches both spellings of a store: a literal `docs/dev/project-management` path segment
    (any repo), and the resolved symlink target of ~/.claude/docs/dev/project-management -
    sessions write through either. Deliberately does NOT resolve() the given
    path: resolving would erase the `docs/dev/project-management` segment of a symlinked store.
    """
    norm = os.path.normpath(os.path.expanduser(file_path))
    parts = Path(norm).parts
    for i in range(len(parts) - 2):
        if parts[i : i + 3] == STORE_PARTS:
            return parts[i + 3 :]
    target = os.path.realpath(str(Path.home() / ".claude" / "docs" / "dev" / "project-management"))
    # realpath BOTH sides here (only here): the target is fully resolved, so
    # the candidate must be too (/var vs /private/var on macOS).
    real = os.path.realpath(norm)
    if real.startswith(target + os.sep):
        return Path(real[len(target) + 1 :]).parts
    return None


def _check_devlocal_layout(rel: tuple[str, ...]) -> str | None:
    """Return a block reason if a store-relative path violates the layout."""
    top = rel[0]
    if len(rel) == 1:
        return _root_msg(top)
    if top == "meta":
        if len(rel) == 2 and rel[1] in KEEP_NAMES:
            return None
        return _meta_msg("/".join(rel[1:]))
    if top == ".trash":
        return _trash_msg()
    if top == "prds":
        if len(rel) >= 3 and rel[1] in LIFECYCLE_DIRS:
            return None
        return _prds_root_msg("/".join(rel))
    if top not in KNOWN_DIRS:
        return _foreign_msg(top)
    return None


def _check_file_path(file_path: str) -> str | None:
    """Return a block reason if file_path violates the rules, else None."""
    if not file_path:
        return None
    # Lifecycle check first, on the RESOLVED path: a symlink escape
    # (docs/dev/project-management/prds/sneak -> repo-root backlog/) resolves OUT of docs/dev/project-management
    # and must block with the resolved location, not the layout message.
    resolved = Path(file_path).resolve()
    root = resolve_toplevel(str(resolved))
    if root is not None:
        try:
            rel_parts = resolved.relative_to(Path(root).resolve()).parts
        except ValueError:
            rel_parts = ()
        if (
            rel_parts
            and rel_parts[:4] != (*STORE_PARTS, "prds")
            and rel_parts[0] in LIFECYCLE_DIRS
        ):
            return _block_path_msg("/".join(rel_parts))
    # Inside a docs/dev/project-management store (checked on the GIVEN path - resolving would
    # erase the symlinked store's docs/dev/project-management segment), the layout contract
    # decides the rest, including the prds lifecycle-subdir requirement.
    rel = _rel_in_devlocal(file_path)
    if rel:
        return _check_devlocal_layout(rel)
    return None


def _validate_file_mode(data: dict) -> None:
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    if tool == "MultiEdit":
        for edit in tool_input.get("edits") or []:
            if not isinstance(edit, dict):
                continue
            reason = _check_file_path(edit.get("file_path") or "")
            if reason:
                block(reason)
    else:
        reason = _check_file_path(tool_input.get("file_path") or "")
        if reason:
            block(reason)


def _validate_bash_mode(data: dict) -> None:
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return
    try:
        tokens = shlex.split(cmd, comments=True)
    except ValueError:
        return
    # ponytail: token-presence, not argument-position - a compound command
    # whose fs-mutating verb is bundled oddly can still slip a bare word
    # past, and an unrelated bare word in a command that happens to contain
    # `rm` will block; upgrade path is per-command argument-position parsing.
    has_fs_mutator = any(t in FS_MUTATING_COMMANDS for t in tokens)
    matches: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        # A whitespace-split token can still hide a path after an = -
        # VAR=backlog/x.md or --log-file=backlog/x.md - splitting on
        # every = reproduces the old regex's (^|\s|=) boundary set
        # (shlex.split already handles the ^/whitespace cases).
        for segment in token.split("="):
            candidate = segment.removeprefix("./")
            parts = PurePosixPath(candidate).parts
            if not parts:
                continue
            if parts[:4] == (*STORE_PARTS, "prds"):
                continue
            if parts[0] in LIFECYCLE_DIRS and (
                len(parts) > 1 or segment.endswith("/") or has_fs_mutator
            ):
                key = f"{parts[0]}/"
                if key not in seen:
                    seen.add(key)
                    matches.append(key)
    if matches:
        block(_block_bash_msg(sorted(matches)))


def main() -> None:
    try:
        data = read_input()
        tool = data.get("tool_name", "")
        if tool in {"Edit", "Write", "MultiEdit"}:
            _validate_file_mode(data)
        elif tool == "Bash":
            _validate_bash_mode(data)
    except Exception as exc:
        # block()/allow() raise SystemExit (BaseException), so a real block
        # still fires; only an UNEXPECTED error lands here. Fail open but LOUD
        # — a policy hook that crashes silently disables the gate with no
        # signal (PRD 00086 R4).
        print(f"policy hook degraded: enforce_prd_location: {exc}", file=sys.stderr)
    allow()


def run(payload):
    """Dispatcher entry point (hooks/dispatch.py). The handler owns its own
    capture: `capture_main` feeds `payload` as stdin, captures stdout/stderr and
    maps main()'s exit, so run() RETURNS the (exit_code, stdout, stderr) triple
    the dispatcher surfaces unchanged. `_common` is imported here, not at module
    scope, so the standalone `__main__` path is unaffected."""
    from _common import capture_main

    return capture_main(main, payload)


if __name__ == "__main__":
    main()
