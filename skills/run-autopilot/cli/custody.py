#!/usr/bin/env python3
"""custody.py - the cap_critical custody core.

A `cap_critical` stall leaves the PRD's commits live on the protected branch.
This module records that custody durably so an attended `custody resolve`
(a later task) can find it: the range capture, the marker file, the
append-only journal under ledger/ (GC-exempt, the restore source when the
marker is trashed), the git-config locator, the hold-PRD refresh, and the
`batch.critical_on_master` mirror. `records.do_stall` drives it as step 4b
for `site == CUSTODY_SITE`; every write is idempotent so a retry re-runs
them all.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import notify_out, records, render_report, state

CUSTODY_SITE = "cap_critical"
MARKER_NAME = "critical-on-master"
JOURNAL_REL = "ledger/custody.jsonl"
CONFIG_KEY = "autopilot.custodyMarker"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
GIT_TIMEOUT_SECS = 30

_SHA_RE = re.compile(r"[0-9a-f]{40}")
# frontmatter._HEAD_LINES minus the two key lines refresh_hold_prd may add,
# so a block that closes within this bound still parses after the refresh.
_BLOCK_HEAD_LINES = 20
_HEADING_PATTERNS = (r"#{1,6} Problem Statement\s*$", r"# ")


class CustodyError(Exception):
    """A custody step failed; the message is the loud reason."""


@contextlib.contextmanager
def marker_lock(path: Path):
    """Exclusive flock on f"{path}.lock" for the marker read-modify-write."""
    with open(f"{path}.lock", "w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def append_journal(autopilot_dir: Path, row: dict) -> None:
    path = autopilot_dir / JOURNAL_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def read_journal(autopilot_dir: Path) -> list[dict]:
    """All rows; [] when absent. Raises CustodyError on an unreadable file
    or an unparseable line - never skips silently."""
    path = autopilot_dir / JOURNAL_REL
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as err:
        raise CustodyError(f"custody journal unreadable ({path}): {err}") from err
    rows = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as err:
            raise CustodyError(
                f"custody journal line {number} is not JSON: {err}"
            ) from err
        if not isinstance(row, dict):
            raise CustodyError(f"custody journal line {number} is not an object")
        rows.append(row)
    return rows


def _live_rows(rows: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """(last `recorded` row, last `resolving` row) per op_id with no
    `resolved` row."""
    resolved = {r.get("op_id") for r in rows if r.get("event") == "resolved"}
    live = [r for r in rows if r.get("op_id") not in resolved]
    recorded = {r["op_id"]: r for r in live if r.get("event") == "recorded"}
    resolving = {r["op_id"]: r for r in live if r.get("event") == "resolving"}
    return recorded, resolving


def unresolved_from_journal(autopilot_dir: Path) -> list[dict]:
    """Entries of `recorded` rows whose op_id has no `resolved` row."""
    recorded, _resolving = _live_rows(read_journal(autopilot_dir))
    return [{k: v for k, v in row.items() if k != "event"} for row in recorded.values()]


def compact_journal(autopilot_dir: Path) -> None:
    """Rewrite the journal atomically keeping one `recorded` row per
    unresolved op_id plus its `resolving` row; resolved history is dropped."""
    recorded, resolving = _live_rows(read_journal(autopilot_dir))
    rows = []
    for op_id, row in recorded.items():
        rows.append(row)
        if op_id in resolving:
            rows.append(resolving[op_id])
    path = autopilot_dir / JOURNAL_REL
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(row) + "\n" for row in rows)
    os.replace(tmp, path)


def pending(autopilot_dir: Path) -> list[dict]:
    """Marker entries ∪ unresolved journal entries by op_id; the marker copy
    wins. Raises CustodyError when either source is present but unreadable."""
    merged = {e["op_id"]: e for e in unresolved_from_journal(autopilot_dir)}
    merged.update((e["op_id"], e) for e in load_marker(autopilot_dir / MARKER_NAME))
    return list(merged.values())


def git_argv(repo_root: str, git_dir: str | None) -> list[str]:
    """The git prefix for a project: --git-dir/--work-tree when the repo is
    bare-backed, else -C."""
    if git_dir:
        return ["git", "--git-dir", git_dir, "--work-tree", repo_root]
    return ["git", "-C", repo_root]


def _git(argv: list[str], *args: str) -> str:
    """Run git, return stripped stdout; CustodyError on any failure."""
    try:
        proc = subprocess.run(
            [*argv, *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECS,
        )
    except (OSError, subprocess.SubprocessError) as err:
        raise CustodyError(f"git {' '.join(args)}: {err}") from err
    if proc.returncode != 0:
        detail = proc.stderr.strip() or f"exit {proc.returncode}"
        raise CustodyError(f"git {' '.join(args)}: {detail}")
    return proc.stdout.strip()


def capture_range(
    repo_root: str, git_dir: str | None, base: str
) -> tuple[str, int, str]:
    """("<base>..<end>", count, branch) with `end` = HEAD captured once."""
    if not _SHA_RE.fullmatch(base):
        raise CustodyError(f"base is not a 40-hex sha: {base!r}")
    if not Path(repo_root).is_dir():
        raise CustodyError(f"repo_root is not a directory: {repo_root}")
    argv = git_argv(repo_root, git_dir)
    end = _git(argv, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if base != EMPTY_TREE:
        _git(argv, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    count = int(_git(argv, "rev-list", "--count", f"{base}..{end}"))
    branch = _git(argv, "rev-parse", "--abbrev-ref", "HEAD")
    return f"{base}..{end}", count, branch


def project_root(autopilot_dir: Path) -> Path:
    if autopilot_dir.parts[-3:] == ("dev", "local", "autopilot"):
        return autopilot_dir.parents[2]
    return autopilot_dir.parent


def load_marker(path: Path) -> list[dict]:
    """[] when absent; CustodyError unless the file is {"entries": [dict...]}."""
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise CustodyError(f"custody marker unreadable ({path}): {err}") from err
    entries = raw.get("entries") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise CustodyError(f'custody marker is not {{"entries": [...]}}: {path}')
    return entries


def write_marker(path: Path, entries: list[dict]) -> None:
    """Atomically write {"entries": entries}; delete the file when empty."""
    if entries:
        state.atomic_write(path, {"entries": entries})
    else:
        path.unlink(missing_ok=True)


def upsert_entry(entries: list[dict], entry: dict) -> tuple[list[dict], bool]:
    """New list with `entry` replacing its op_id twin, else appended;
    second value True when appended."""
    op_id = entry["op_id"]
    if any(e.get("op_id") == op_id for e in entries):
        return [entry if e.get("op_id") == op_id else e for e in entries], False
    return [*entries, entry], True


def _notice_prefix(batch: str) -> str:
    return f"> **Custody (cap_critical, batch {batch}):**"


def _refresh_block(lines: list[str], entry: dict) -> list[str]:
    """Replace or append the two custody keys in a frontmatter block that
    closes within _BLOCK_HEAD_LINES; prepend a fresh block otherwise."""
    keys = {
        "critical_on_master": f"critical_on_master: {entry['commit_range']}",
        "ledger": f"ledger: deferred/{entry['batch']}-deferred.json#{entry['op_id']}",
    }
    close = None
    if lines and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:_BLOCK_HEAD_LINES], start=1):
            if line.strip() == "---":
                close = index
                break
    if close is None:
        return ["---", *keys.values(), "---", *lines]
    body = [keys.pop(line.partition(":")[0].strip(), line) for line in lines[1:close]]
    return [lines[0], *body, *keys.values(), *lines[close:]]


def _insert_notice(lines: list[str], notice: str) -> list[str]:
    """Insert `notice` after the Problem Statement heading, else after the
    first H1, else at the end - one blank line each side."""
    for pattern in _HEADING_PATTERNS:
        for index, line in enumerate(lines):
            if re.match(pattern, line):
                return [*lines[: index + 1], "", notice, "", *lines[index + 1 :]]
    body = lines[:-1] if lines and lines[-1] == "" else lines
    return [*body, "", notice, ""]


def refresh_hold_prd(text: str, entry: dict) -> str:
    """PURE. Upsert the custody frontmatter keys and this batch's notice
    line; every other byte of `text` is preserved. Idempotent."""
    lines = _refresh_block(text.split("\n"), entry)
    prefix = _notice_prefix(entry["batch"])
    notice = (
        f"{prefix} {entry['detail']} Commits {entry['commit_range']} "
        f"({entry['commits']}) are live on {entry['branch']}. "
        "Resolve with autopilot custody resolve."
    )
    if any(line.startswith(prefix) for line in lines):
        lines = [notice if line.startswith(prefix) else line for line in lines]
    else:
        lines = _insert_notice(lines, notice)
    return "\n".join(lines)


def migration_records(state: dict, op_id: str, prd: str) -> list[dict]:
    """PURE. One deferred record per pending state.deferred_decisions[i],
    keyed "<op_id>-dd<i>"; a decision keeps its own type and cycle."""
    return [
        {
            **decision,
            "type": decision.get("type", "deferred_decision"),
            "cycle": decision.get("cycle", state.get("cycle")),
            "prd": prd,
            "op_id": f"{op_id}-dd{index}",
        }
        for index, decision in enumerate(state.get("deferred_decisions") or [])
        if isinstance(decision, dict) and render_report._is_pending(decision)
    ]


def record_critical(
    *,
    autopilot_dir: Path,
    prds_dir: Path,
    current: dict,
    prd: str,
    op_id: str,
    detail: str,
    capture: dict,
) -> int | None:
    """do_stall step 4b under marker_lock: migration records, marker upsert,
    journal row, git-config locator, hold-PRD refresh (the last durable
    write), then one notification when this batch's notice was new. Every
    write is idempotent. Returns None on success, 9 on any failure."""
    batch_id = current["batch"]["id"]
    entry = {"prd": prd, "batch": batch_id, "op_id": op_id, "detail": detail, **capture}
    marker_path = (autopilot_dir / MARKER_NAME).absolute()
    hold_path = prds_dir / "hold" / prd
    prefix = _notice_prefix(batch_id)
    try:
        with marker_lock(marker_path):
            for record in migration_records(current, op_id, prd):
                records.record_defer(autopilot_dir, prd, batch_id, record)
            entries, _created = upsert_entry(load_marker(marker_path), entry)
            write_marker(marker_path, entries)
            append_journal(autopilot_dir, {"event": "recorded", **entry})
            argv = git_argv(entry["repo_root"], entry["git_dir"])
            _git(argv, "config", "--local", CONFIG_KEY, str(marker_path))
            text = hold_path.read_text(encoding="utf-8")
            created = not any(line.startswith(prefix) for line in text.splitlines())
            hold_path.write_text(refresh_hold_prd(text, entry), encoding="utf-8")
    except (OSError, ValueError, CustodyError):
        return 9
    if created:
        notify_out.notify(
            "autopilot 🔒 custody",
            f"{prd}: commits {entry['commit_range']} ({entry['commits']}) live on "
            f"{entry['branch']}; run autopilot custody resolve",
        )
    return None


def mirror_mutator(entry: dict):
    """fn(state)->state upserting `entry` into batch.critical_on_master."""

    def _upsert_mirror(s: dict) -> dict:
        new_s = dict(s)
        batch = dict(new_s.get("batch") or {})
        batch["critical_on_master"], _created = upsert_entry(
            list(batch.get("critical_on_master") or []),
            entry,
        )
        new_s["batch"] = batch
        return new_s

    return _upsert_mirror
