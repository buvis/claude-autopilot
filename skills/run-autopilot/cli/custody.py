#!/usr/bin/env python3
"""custody.py - the cap_critical custody core.

A `cap_critical` stall leaves the PRD's commits live on the protected branch.
This module records that custody durably so the attended `custody resolve`
(`resolve` below) can find it: the range capture, the marker file, the
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
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import notify_out, records, render_report, schema, state

CUSTODY_SITE = "cap_critical"
MARKER_NAME = "critical-on-master"
JOURNAL_REL = "ledger/custody.jsonl"
CONFIG_KEY = "autopilot.custodyMarker"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
GIT_TIMEOUT_SECS = 30
_UNFINISHED = ("REVERT_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "sequencer")

_SHA_RE = re.compile(r"[0-9a-f]{40}")
# The line `git revert` writes; reconciliation on a rerun is keyed on it.
_REVERTS_RE = re.compile(r"^This reverts commit ([0-9a-f]{40})\.$", re.MULTILINE)
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
        if not isinstance(row.get("op_id"), str):
            raise CustodyError(f"custody journal line {number} has no string op_id")
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


def _git(argv: list[str], *args: str, ok: tuple[int, ...] = (0,)) -> str:
    """Run git, return stripped stdout; CustodyError on a timeout or any
    exit outside `ok`."""
    try:
        proc = subprocess.run(
            [*argv, *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECS,
        )
    except (OSError, subprocess.SubprocessError) as err:
        raise CustodyError(f"git {' '.join(args)}: {err}") from err
    if proc.returncode not in ok:
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
    if not all(isinstance(e.get("op_id"), str) for e in entries):
        raise CustodyError(f"custody marker entry has no string op_id: {path}")
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
    line (the detail's whitespace runs collapsed to one space so it stays
    one line); every other byte of `text` is preserved. Idempotent."""
    lines = _refresh_block(text.split("\n"), entry)
    prefix = _notice_prefix(entry["batch"])
    notice = (
        f"{prefix} {' '.join(entry['detail'].split())} Commits {entry['commit_range']} "
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


def marker_entry(prd: str, batch: str, op_id: str, detail: str, capture: dict) -> dict:
    """PURE. The one custody marker entry: the four scalars plus every
    capture key copied verbatim, as a new dict."""
    return {"prd": prd, "batch": batch, "op_id": op_id, "detail": detail, **capture}


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
    write is idempotent. Returns None on success, 9 on any failure with
    the reason on stderr."""
    batch_id = current["batch"]["id"]
    entry = marker_entry(prd, batch_id, op_id, detail, capture)
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
    except (OSError, ValueError, CustodyError) as err:
        print(f"autopilot: cap_critical custody write failed: {err}", file=sys.stderr)
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


def _drop_mirror(op_id: str):
    """fn(state)->state removing `op_id` from batch.critical_on_master."""

    def _remove(s: dict) -> dict:
        batch = dict(s.get("batch") or {})
        batch["critical_on_master"] = [
            e for e in batch.get("critical_on_master") or [] if e.get("op_id") != op_id
        ]
        return {**s, "batch": batch}

    return _remove


def _recorded_choice(autopilot_dir: Path, entry: dict) -> str | None:
    """The `choice` of an `<op_id>-resolve` record already in the batch
    ledger (the durable boundary of an earlier run), else None."""
    path = autopilot_dir / "deferred" / f"{entry['batch']}-deferred.json"
    if not path.exists():
        return None
    try:
        items = json.loads(path.read_text(encoding="utf-8")).get("items") or []
    except (OSError, ValueError, AttributeError) as err:
        raise CustodyError(f"batch ledger unreadable ({path}): {err}") from err
    op_id = f"{entry['op_id']}-resolve"
    for item in items:
        if isinstance(item, dict) and item.get("op_id") == op_id:
            return item.get("choice")
    return None


def _refuse_unless_clean(argv: list[str], entry: dict) -> None:
    """CustodyError naming the fix when HEAD is not the entry's branch or
    an unfinished revert/merge/cherry-pick sits in the git dir."""
    head_branch = _git(argv, "rev-parse", "--abbrev-ref", "HEAD")
    if head_branch != entry["branch"]:
        raise CustodyError(f"checkout {entry['branch']} first (HEAD is {head_branch})")
    git_dir = Path(entry["repo_root"]) / _git(argv, "rev-parse", "--git-dir")
    for leftover in _UNFINISHED:
        if (git_dir / leftover).exists():
            raise CustodyError(f"{git_dir / leftover} exists: finish or abort it first")


def _reverted_targets(
    autopilot_dir: Path,
    argv: list[str],
    op_id: str,
    choice: str,
    targets: list[str],
) -> set[str]:
    """Targets some commit in head_before..HEAD reverts, per the journaled
    intent row; a first run journals the intent (head_before = HEAD now)
    and reports none."""
    _recorded, resolving = _live_rows(read_journal(autopilot_dir))
    intent = resolving.get(op_id)
    if intent is None:
        head = _git(argv, "rev-parse", "HEAD")
        append_journal(
            autopilot_dir,
            {
                "event": "resolving",
                "op_id": op_id,
                "choice": choice,
                "head_before": head,
            },
        )
        return set()
    bodies = _git(argv, "rev-list", "--format=%B", f"{intent['head_before']}..HEAD")
    return set(_REVERTS_RE.findall(bodies)) & set(targets)


def _pin_custody_branch(argv: list[str], stem: str, end: str) -> None:
    """Create custody/<stem> at the range end; one already there is fine,
    one anywhere else is a CustodyError."""
    ref = f"refs/heads/custody/{stem}"
    at = _git(argv, "rev-parse", "--verify", "--quiet", ref, ok=(0, 1))
    if at == end:
        return
    if at:
        raise CustodyError(f"{ref} exists at {at}, not at the range end {end}")
    _git(argv, "branch", f"custody/{stem}", end)


def _apply_git(autopilot_dir: Path, entry: dict, choice: str) -> int | None:
    """Step 3 for revert / branch-and-revert (`accept` touches nothing):
    refuse a wrong or mid-operation checkout, journal the intent, reconcile
    a rerun, pin the custody branch, revert. None when done; 5 with the
    operator's fix on stderr when git refused or failed (custody retained,
    git left as it is)."""
    if choice == "accept":
        return None
    argv = git_argv(entry["repo_root"], entry.get("git_dir"))
    base, end = entry["commit_range"].split("..")
    try:
        _refuse_unless_clean(argv, entry)
        targets = _git(
            argv, "rev-list", end if base == EMPTY_TREE else f"{base}..{end}"
        ).split()
        reverted = _reverted_targets(
            autopilot_dir, argv, entry["op_id"], choice, targets
        )
        if reverted and reverted != set(targets):
            raise CustodyError("partial revert; finish by hand, then --choice accept")
        if choice == "branch-and-revert":
            _pin_custody_branch(argv, entry["prd"].removesuffix(".md"), end)
        if not reverted:
            _git(argv, "revert", "--no-edit", *targets)
    except CustodyError as err:
        print(f"autopilot: could not revert {entry['prd']}: {err}", file=sys.stderr)
        return 5
    return None


def _cleanup(
    autopilot_dir: Path,
    state_path: Path,
    marker_path: Path,
    entries: list[dict],
    entry: dict,
    choice: str,
) -> int | None:
    """Step 5, every write idempotent: the `resolved` row, the marker minus
    this op_id, the locator when no custody for this repo_root remains, the
    state mirror when state.json exists, then the journal compaction. 9 when
    the mirror write fails (the journal has closed the custody by then)."""
    op_id = entry["op_id"]
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    append_journal(
        autopilot_dir,
        {
            "event": "resolved",
            "op_id": op_id,
            "prd": entry["prd"],
            "choice": choice,
            "at": at,
        },
    )
    write_marker(
        marker_path, [e for e in load_marker(marker_path) if e.get("op_id") != op_id]
    )
    others = [e for e in entries if e["op_id"] != op_id]
    if not any(e.get("repo_root") == entry["repo_root"] for e in others):
        argv = git_argv(entry["repo_root"], entry.get("git_dir"))
        _git(argv, "config", "--local", "--unset", CONFIG_KEY, ok=(0, 5))
    if state_path.exists():
        try:
            state.transaction(
                state_path,
                _drop_mirror(op_id),
                validator=lambda s: schema.require(s.get("batch"), dict, "batch"),
            )
        except (state.StateError, schema.SchemaError, OSError) as err:
            print(f"autopilot: mirror stale, custody closed: {err}", file=sys.stderr)
            return 9
    compact_journal(autopilot_dir)
    return None


def _resolve_locked(
    autopilot_dir: Path,
    state_path: Path,
    marker_path: Path,
    prd: str,
    choice: str,
) -> int:
    stem = Path(prd).name.removesuffix(".md")
    entries = pending(autopilot_dir)
    entry = next((e for e in entries if e["prd"].removesuffix(".md") == stem), None)
    if entry is None:
        print(
            f"autopilot: no pending custody for {prd} (pass the PRD stem, filename or path)",
            file=sys.stderr,
        )
        return 1
    recorded = _recorded_choice(autopilot_dir, entry)
    if recorded is None:
        refused = _apply_git(autopilot_dir, entry, choice)
        if refused is not None:
            return refused
        records.record_defer(
            autopilot_dir,
            entry["prd"],
            entry["batch"],
            {
                "type": "custody",
                "choice": choice,
                "commit_range": entry["commit_range"],
                "op_id": f"{entry['op_id']}-resolve",
            },
        )
        recorded = choice
    elif recorded != choice:
        print(
            f"autopilot: {entry['prd']} already resolved as {recorded}; finishing cleanup",
            file=sys.stderr,
        )
    failed = _cleanup(autopilot_dir, state_path, marker_path, entries, entry, recorded)
    if failed is not None:
        return failed
    print(f"custody: {entry['prd']} resolved ({recorded})")
    return 0 if recorded == choice else 1


def resolve(*, autopilot_dir: Path, state_path: Path, prd: str, choice: str) -> int:
    """The attended `custody resolve`, all under marker_lock: find the
    pending entry by PRD stem, let a choice already in the batch ledger win,
    else run git for the choice and record it, then clean every custody
    source. Exit codes: 0 | 1 no pending entry, or a different choice was
    already recorded | 5 git refused or failed | 9 a source read or write
    failed."""
    marker_path = (autopilot_dir / MARKER_NAME).absolute()
    try:
        with marker_lock(marker_path):
            return _resolve_locked(autopilot_dir, state_path, marker_path, prd, choice)
    except (OSError, ValueError, CustodyError) as err:
        print(f"autopilot: custody resolve failed: {err}", file=sys.stderr)
        return 9
