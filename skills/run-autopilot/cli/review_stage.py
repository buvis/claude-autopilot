#!/usr/bin/env python3
"""Stage one review cycle's input files in code (PRD 00249).

`stage()` replaces the hand-staging of review-work-completion/SKILL.md step 3
(tasks and PRD files, gather-context.sh, the mechanical blocks, the ledger,
the engram pack, the Tests: line) and step 5's roster stamp. The existing
scripts run as subprocesses, unchanged; nothing here re-derives what they
compute.

`render_roster()` writes one prompt per roster persona through
work/scripts/render_prompt.py, applying SKILL.md step 4's substitution table;
`stage()` only ever passes it personas that passed preflight.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import frontmatter, schema, state, statectl, verification

_SKILLS = Path(__file__).resolve().parents[2]
_RWC_SCRIPTS = _SKILLS / "review-work-completion" / "scripts"
GATHER_SCRIPT = _RWC_SCRIPTS / "gather-context.sh"
MECH_SCRIPT = _RWC_SCRIPTS / "compute_mech_facts.py"
TAUT_SCRIPT = _RWC_SCRIPTS / "detect_tautological_tests.py"
REPLAY_SCRIPT = _RWC_SCRIPTS / "replay_tests_against_base.py"
RECORD_DISPATCH = _SKILLS / "work" / "scripts" / "record_dispatch.py"
RENDER_SCRIPT = _SKILLS / "work" / "scripts" / "render_prompt.py"
_RWC_REFS = _SKILLS / "review-work-completion" / "references"
CHECKLIST_FILE = _RWC_REFS / "review-dimensions.md"
CONSENSUS_RUBRIC = _RWC_REFS / "rubric.md"
OUTPUT_FORMATS = _RWC_REFS / "output-formats.md"
BLIND_RUBRIC = _SKILLS / "review-blindly" / "references" / "rubric.md"
# The plugin root's agents/: the installed cache dir when run from the
# plugin, this checkout's agents/ when run from source.
AGENTS_DIR = _SKILLS.parent / "agents"

ENGRAM = "engram"
ENGRAM_TIMEOUT_S = 300
SCRIPT_TIMEOUT_S = 540
SCRIPT_GRACE_S = 30
CAPSULE_REL = "docs/dev/project-management/meta/project-capsule.md"
TMP_REL = Path("docs/dev/tmp")
NO_PACK = "(no pack available this cycle)"
SETTLED_HEADING = "## Settled decisions — do not re-raise"
SETTLED_INTRO = (
    "> These calls were already made in an earlier cycle of this same review, with\n"
    "> the reasons given. Do not re-raise them. Raise a NEW finding only if you can\n"
    "> show the settled reason no longer holds."
)
NO_DIFF = "(no diff file this cycle)"
NO_RANGE = "(diff range unavailable; see the context file's Diff scope line)"
NO_MECH = "(no mechanical test checks this cycle)"
STORE_REL = "docs/dev/project-management"
PERSONAS = ("alice", "bob", "blake", "carl", "eve")
# Bob's doubt appendix: these eve.md sections, verbatim, in eve.md's order.
EVE_DOUBT_SECTIONS = (
    "Two lenses",
    "Categorize every residual finding",
    "Rubric verdicts",
)
CITATION_LINE = (
    "Cite files repo-relative as path:line (for example skills/work/SKILL.md:166), "
    'never absolute and never with a "(lines a-b)" suffix.'
)
INCREMENTAL_NOTE = (
    "This is an **incremental review** of the rework done since the previous "
    "review cycle — the diff is scoped to changes since then. Two jobs: (1) for "
    "each prior finding listed below, verify it is now resolved in the code; (2) "
    "review the scoped diff for any regression the rework introduced. You need "
    "not re-review unchanged code; the previous cycle already reviewed the full "
    "implementation."
)
TAUT_HEADING = "## Tautological test shapes"
REPLAY_HEADING = "## Fail-first replay"
REQUIRED_PERSONA_KEYS = ("name", "description", "tools")
CLI_REVIEWERS = ("bob", "carl")
# A lens is active when any of its personas is on the roster.
LENS_PERSONAS = {
    "consensus": ("alice", "bob", "carl"),
    "blind": ("blake",),
    "doubt": ("bob", "eve"),
    "fable": ("eve",),
    "ui": ("carl",),
}

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PERSONA_RE = re.compile(r"[a-z][a-z0-9_-]*")
_DIFF_HEADER_RE = re.compile(r"^diff --git a/.* b/(.+)$", re.MULTILINE)
_FINDINGS_RE = re.compile(
    r"^(#+)\s*Findings precedent\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_SCOPE_RE = re.compile(
    r"^_Diff scope: .*\((?:changes since|vs) ([^)\s]+)\)_$",
    re.MULTILINE,
)
_TAUT_RE = re.compile(rf"^{re.escape(TAUT_HEADING)}", re.MULTILINE)
_H2_RE = re.compile(r"^## ", re.MULTILINE)


def _git_out(repo_root: Path, *args: str) -> str | None:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    out = proc.stdout.strip()
    return out if proc.returncode == 0 and out else None


def _append(path: Path, block: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n" + block.rstrip() + "\n")


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_tasks(tasks: list[dict]) -> str:
    """One table row per task. A folded task keeps its own row; its shared
    commit and companion task ids sit in that row, never merged away."""
    if not tasks:
        return ""
    lines = [
        "| ID | Task | Status | Commit | Description | Shared with |",
        "|----|------|--------|--------|-------------|-------------|",
    ]
    for task in tasks:
        companions = task.get("companions") or []
        cells = [
            task.get("id"),
            task.get("name") or task.get("subject"),
            task.get("status"),
            task.get("commit"),
            task.get("description"),
            ", ".join(str(c) for c in companions),
        ]
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(lines) + "\n"


def _write_inputs(
    tmp_dir: Path,
    cycle_id: str,
    tasks: list[dict],
    prd_path: Path,
    design_doc: Path | None,
) -> tuple[Path, Path]:
    tasks_file = tmp_dir / f"review-tasks-{cycle_id}.md"
    tasks_file.write_text(render_tasks(tasks), encoding="utf-8")
    # The raw PRD, file-backed on its own (review-prd-raw-{cycle_id}.md) so
    # Blake can read it directly in _run_inputs instead of re-deriving it by
    # splitting the merged file below on the "## Design Doc" marker.
    prd_raw_text = Path(prd_path).read_text(encoding="utf-8").rstrip() + "\n"
    (tmp_dir / f"review-prd-raw-{cycle_id}.md").write_text(
        prd_raw_text,
        encoding="utf-8",
    )
    prd_text = prd_raw_text
    if design_doc is not None and Path(design_doc).is_file():
        design = Path(design_doc).read_text(encoding="utf-8").rstrip()
        prd_text += f"\n## Design Doc\n\n{design}\n"
    prd_file = tmp_dir / f"review-prd-{cycle_id}.md"
    prd_file.write_text(prd_text, encoding="utf-8")
    return tasks_file, prd_file


def _gather(repo_root: Path, since: str | None, cycle_id: str) -> dict:
    """Run gather-context.sh; {"ok": True, context, diff} or the refusal."""
    args = [
        "bash",
        str(GATHER_SCRIPT),
        *(["--since", since] if since else []),
        str(TMP_REL / f"review-tasks-{cycle_id}.md"),
        str(TMP_REL / f"review-prd-{cycle_id}.md"),
    ]
    proc = subprocess.run(
        args,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        error = proc.stderr.strip() or f"gather-context.sh exited {proc.returncode}"
        return {"ok": False, "error": error, "exit": proc.returncode}
    printed = [Path(line) for line in proc.stdout.splitlines() if line.strip()]
    context = next((p for p in printed if p.suffix == ".md"), None)
    diff = next((p for p in printed if p.suffix == ".diff"), None)
    if context is None:
        error = "gather-context.sh printed no context file"
        return {"ok": False, "error": error, "exit": 1}
    return {"ok": True, "context": context, "diff": diff}


def _killpg_or_gone(pgid: int, sig: int) -> None:
    """`os.killpg`, except a group that is already gone is a no-op: the race
    where the helper exits on its own between the timeout firing and the
    kill call must not propagate as an uncaught ProcessLookupError."""
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


def _run_script(
    script: Path,
    args: list[str],
    cwd: Path,
    timeout: float = SCRIPT_TIMEOUT_S,
) -> str:
    """A helper script's stdout; a failed run says so in the block instead.
    On timeout its session gets SIGTERM, then SIGKILL after SCRIPT_GRACE_S.
    SIGTERM/SIGHUP landing on the caller, mirroring verification._signal_error's
    guard shape, tears the helper's session down too and surfaces as a
    RuntimeError naming the signal instead of leaving it orphaned."""
    proc = None
    with verification._deferred_signals((signal.SIGTERM, signal.SIGHUP)) as guard:
        try:
            proc = subprocess.Popen(
                [sys.executable, str(script), *args],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
            guard.gate_started = True
            guard.raise_if_pending()
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _killpg_or_gone(proc.pid, signal.SIGTERM)
                try:
                    proc.communicate(timeout=SCRIPT_GRACE_S)
                except subprocess.TimeoutExpired:
                    _killpg_or_gone(proc.pid, signal.SIGKILL)
                    proc.communicate()
                return f"_{script.name} failed (timeout after {int(timeout)}s)_"
        except BaseException:
            guard.cleaning = True
            if proc is not None:
                # A signal landing right as Popen() returns can race the
                # helper's own exec: give it a moment to actually start
                # running before tearing it down, or it never gets the
                # chance to do anything, including write its own pid file.
                time.sleep(0.1)
            verification._kill_gate(proc)
            raise
    if proc.returncode != 0:
        detail = stderr.strip().splitlines()[-1:] or ["no stderr"]
        return f"_{script.name} failed (exit {proc.returncode}): {detail[0]}_"
    return stdout.strip()


def _append_mech_blocks(
    context: Path,
    diff: Path | None,
    repo_root: Path,
    base: str | None,
    replay_cmd: str | None,
) -> None:
    diff_text = diff.read_text(encoding="utf-8", errors="replace") if diff else ""
    changed = [
        path
        for path in dict.fromkeys(_DIFF_HEADER_RE.findall(diff_text))
        if (repo_root / path).is_file()
    ]
    if changed:
        _append(context, _run_script(MECH_SCRIPT, changed, repo_root))
        _append(context, _run_script(TAUT_SCRIPT, changed, repo_root))
    else:
        _append(context, "_No changed files remain for the mechanical checks._")
    if replay_cmd is None:
        return
    if base is None:
        _append(context, "replay: skipped (no diff-range base resolved)")
        return
    # replay_cmd is the PER-FILE pytest invocation, never the gate command.
    replay_args = ["--base", base, "--cmd", replay_cmd, "--timeout", "480"]
    _append(context, _run_script(REPLAY_SCRIPT, replay_args, repo_root))


def _ledger_block(settled_ledger: Path) -> tuple[str | None, str | None]:
    """(block, error). A malformed ledger is skipped and named, never fatal."""
    try:
        entries = json.loads(Path(settled_ledger).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return None, f"ledger skipped ({err})"
    if not isinstance(entries, list):
        return None, "ledger skipped (not a JSON list)"
    lines = [SETTLED_HEADING, "", SETTLED_INTRO, ""]
    for entry in entries:
        if isinstance(entry, dict):
            lines.append(
                f"- [{entry.get('disposition')}] {entry.get('severity')}: "
                f"{entry.get('issue')} ({entry.get('file')}) - "
                f"reason: {entry.get('reason')}",
            )
    return "\n".join(lines), None


def _pack_failure(proc: subprocess.CompletedProcess, repo_root: Path) -> str:
    output = f"{proc.stderr}\n{proc.stdout}"
    if "not inside a registered repo" in output:
        reason = f"not inside a registered repo; run `gita add {repo_root}`"
    else:
        reason = (output.strip().splitlines() or ["no output"])[-1]
    return f"failed (engram pack exit {proc.returncode}: {reason})"


def run_pack(
    repo_root: Path,
    cycle_id: str,
    prd_path: Path,
) -> tuple[Path | None, str]:
    """(pack path, status). Every failure is a status string, never a raise."""
    exe = shutil.which(ENGRAM)
    if exe is None:
        return None, f"failed ({ENGRAM} not found on PATH)"
    prd = str(Path(prd_path).resolve())
    cmd = [exe, "pack", "--cycle", cycle_id, "--prd", prd, "--capsule", CAPSULE_REL]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=ENGRAM_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"failed (engram pack timed out after {ENGRAM_TIMEOUT_S}s)"
    except OSError as err:
        return None, f"failed ({err})"
    if proc.returncode != 0:
        return None, _pack_failure(proc, repo_root)
    printed = [Path(line.strip()) for line in proc.stdout.splitlines() if line.strip()]
    expected = repo_root / TMP_REL / f"engram-pack-{cycle_id}.md"
    pack = next((p for p in printed if p.is_absolute() and p.suffix == ".md"), expected)
    if not pack.is_file():
        return None, "failed (no pack file written)"
    return pack, "ok"


def findings_section(pack: Path) -> str:
    """The pack's "Findings precedent" section body, up to the next heading
    at the same or a higher level."""
    text = pack.read_text(encoding="utf-8")
    match = _FINDINGS_RE.search(text)
    if match is None:
        return "(the pack has no Findings precedent section)"
    level = len(match.group(1))
    rest = text[match.end() :]
    stop = re.search(rf"^#{{1,{level}}}\s", rest, re.MULTILINE)
    return (rest[: stop.start()] if stop else rest).strip()


def _append_pack(context: Path, pack: Path | None) -> None:
    findings = NO_PACK if pack is None else findings_section(pack)
    _append(
        context,
        f"## Context Pack\n\nPack file: {pack or NO_PACK}\n\n"
        f"### Findings precedent\n\n{findings}",
    )


def _read_record(repo_root: Path) -> dict | None:
    path = repo_root / verification.RECORD_REL
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _tests_line(counts: tuple, suffix: str) -> str:
    return (
        f"Tests: {counts[0]} passed, {counts[1]} failed, {counts[2]} skipped {suffix}"
    )


def _gate_result_line(result: dict) -> str:
    """The human `Tests:` line for one fresh `run_gate` result."""
    if result["lock_timeout"]:
        return (
            "Tests: (gate skipped: another gate held the lock for "
            f"{int(verification.GATE_LOCK_TIMEOUT_S)}s)"
        )
    if result["head_moved"]:
        return "Tests: (gate skipped: HEAD moved during the lock wait)"
    if result["dirty"]:
        paths = ", ".join(result["dirty_paths"]) or "(no paths reported)"
        if result["passed"] is not None:
            counts = (result["passed"], result["failed"], result["skipped"])
            suffix = (
                "(suite run this cycle, then tree dirtied outside the "
                f"store: {paths})"
            )
            return _tests_line(counts, suffix)
        return f"Tests: (gate skipped: working tree dirty outside the store: {paths})"
    if result["timed_out"]:
        # TESTS_RE needs counts; zeros plus the suffix say none were read.
        suffix = (
            f"(suite timed out after {int(verification.GATE_TIMEOUT_S)}s, "
            "treated as failed)"
        )
        return _tests_line((0, 0, 0), suffix)
    if result["passed"] is None:
        return (
            f"Tests: counts unavailable (suite run this cycle, exit {result['exit']}, "
            "no PASS/FAIL/SKIP/EXIT summary line)"
        )
    counts = (result["passed"], result["failed"], result["skipped"])
    summary_exit = None
    if result.get("raw_line"):
        match = verification.SUMMARY_RE.search(result["raw_line"])
        if match:
            summary_exit = int(match.group(4))
    process_exit = result.get("exit")
    if process_exit not in (0, None):
        bad_exit = process_exit
    elif summary_exit not in (0, None):
        bad_exit = summary_exit
    else:
        return _tests_line(counts, "(suite run this cycle)")
    return _tests_line(
        counts, f"(suite run this cycle, exit {bad_exit}, treated as failed)"
    )


def run_gate_line(repo_root: Path, gate_command: str, cycle_id: str) -> dict:
    """Reuse the recorded gate when it still certifies HEAD, else run it once."""
    head = _git_out(repo_root, "rev-parse", "HEAD") or ""
    verdict, record = verification.reuse_verdict(
        _read_record(repo_root),
        repo_root,
        head,
        gate_command,
    )
    if verdict == "reused":
        counts = (record["passed"], record["failed"], record["skipped"])
        suffix = f"(reused from last-verification.json at {record['sha'][:7]})"
        return {
            "verdict": verdict,
            "tests_line": _tests_line(counts, suffix),
            "timed_out": False,
            "dirty_paths": [],
        }
    cycle = int(cycle_id) if cycle_id.isascii() and cycle_id.isdigit() else None
    log_path = repo_root / TMP_REL / f"gate-{cycle_id}.log"
    result = verification.run_gate(
        gate_command,
        repo_root,
        sha=head,
        cycle=cycle,
        log_path=log_path,
    )
    gate_spawned = not (
        result["lock_timeout"]
        or result["head_moved"]
        or (result["dirty"] and result["passed"] is None)
    )
    return {
        "verdict": verdict,
        "tests_line": _gate_result_line(result),
        "timed_out": result["timed_out"],
        "log": str(log_path) if gate_spawned else None,
        "dirty_paths": result["dirty_paths"],
    }


def preflight_persona(name: str) -> bool:
    """True only when agents/<name>.md opens with a closed `---` block whose
    name, description and tools keys are all non-empty."""
    if not _PERSONA_RE.fullmatch(name):
        return False
    try:
        text = (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    keys = frontmatter.declared(text)
    return all(keys.get(key) for key in REQUIRED_PERSONA_KEYS)


def _read(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    """The markdown section whose heading starts with `title`, heading
    included, up to the next heading at the same or a higher level."""
    match = re.search(rf"^(#+) {re.escape(title)}.*$", text, re.MULTILINE)
    if match is None:
        raise ValueError(f"no {title!r} section")
    level = len(match.group(1))
    stop = re.compile(rf"^#{{1,{level}}} ", re.MULTILINE).search(text, match.end())
    return text[match.start() : stop.start() if stop else len(text)].rstrip()


def _output_format(name: str) -> str:
    section = _section(_read(OUTPUT_FORMATS), "Agent Output Format")
    return f"{section}\n\nYour agent name is {name.upper()}."


def _incremental_block(prior_findings: Path) -> str:
    findings = _read(prior_findings).strip()
    return (
        f"## Incremental review\n\n{INCREMENTAL_NOTE}\n\n"
        f"### Prior cycle findings\n\n{findings}"
    )


def _prd_body(prd_file: Path, merged: str) -> str:
    """The blind PRD body: the file-backed raw sibling `_write_inputs()`
    stages next to `prd_file`, or the pre-"## Design Doc" slice of the
    merged text when that sibling isn't there."""
    cycle_id = prd_file.name.removeprefix("review-prd-").removesuffix(".md")
    raw_file = prd_file.parent / f"review-prd-raw-{cycle_id}.md"
    if raw_file.is_file():
        return _read(raw_file).strip()
    return merged.split("\n\n## Design Doc\n\n", 1)[0]


def _run_inputs(
    context_file: Path,
    diff_file: Path | None,
    prd_file: Path,
    pack_file: Path | None,
    settled_ledger: Path | None,
    prior_findings: Path | None,
) -> dict:
    """Everything the per-persona plans draw on, read once."""
    context = Path(context_file).absolute()
    context_text = _read(context)
    diff_text = _read(diff_file) if diff_file else ""
    prd = _read(prd_file).strip()
    try:
        test_gate = _section(context_text, "Test gate")
    except ValueError:
        test_gate = None
    return {
        "context": context,
        "id": context.name.removeprefix("review-context-").removesuffix(".md"),
        "root": context.parents[len(TMP_REL.parts)],
        "diff": str(Path(diff_file).absolute()) if diff_file else NO_DIFF,
        "changed": list(dict.fromkeys(_DIFF_HEADER_RE.findall(diff_text))),
        "prd": prd,
        # Blake is blind: the PRD body only, never the design doc _write_inputs
        # appended onto prd_file for every other persona. _write_inputs()
        # stages the raw PRD as its own review-prd-raw-{id}.md file
        # alongside the merged one; read that file-backed copy directly when
        # it is there, instead of re-deriving it by splitting the merged
        # text on its "## Design Doc" marker (a caller that stages prd_file
        # without the raw sibling, e.g. a direct render_roster() call in
        # tests, still gets the split fallback).
        "prd_body": _prd_body(Path(prd_file), prd),
        "pack": str(pack_file) if pack_file else NO_PACK,
        "findings": findings_section(Path(pack_file)) if pack_file else NO_PACK,
        "ledger": _ledger_block(Path(settled_ledger))[0] if settled_ledger else None,
        "incremental": _incremental_block(prior_findings) if prior_findings else None,
        "test_gate": test_gate,
    }


def _mech_checks(context: str) -> str:
    """The tautology and replay blocks stage() appended, verbatim."""
    starts = list(_TAUT_RE.finditer(context))
    if not starts:
        return NO_MECH
    rest = context[starts[-1].start() :]
    for heading in _H2_RE.finditer(rest, 1):
        if not rest.startswith(REPLAY_HEADING, heading.start()):
            return rest[: heading.start()].rstrip()
    return rest.rstrip()


def _eve_inputs(run: dict) -> str:
    """agent-invocation.md's five Eve run inputs."""
    context = _read(run["context"])
    scope = _SCOPE_RE.search(context)
    diff_range = f"{scope.group(1)}..HEAD" if scope else NO_RANGE
    changed = "\n".join(run["changed"]) or NO_DIFF
    return "\n\n".join(
        [
            f"## PRD\n{run['prd_body']}",
            f"## Diff range\n{diff_range}",
            f"## Changed files\n{changed}",
            f"## Findings precedent\n{run['findings']}",
            f"## Mechanical test checks\n{_mech_checks(context)}",
        ],
    )


def _filesystem_notes(root: Path) -> str | None:
    """agent-invocation.md § Blake: Filesystem notes, when its trigger holds."""
    store = root / STORE_REL
    if not (store.is_symlink() or root.name.startswith(".")):
        return None
    return (
        "## Filesystem notes\n"
        f"Project root: {root}\n"
        f"`{STORE_REL}` realpath: {store.resolve()}\n"
        "`rg --files` does not descend into dot-directories or follow this "
        "symlink; list or Read the realpath directly."
    )


def _plan(name: str, run: dict) -> tuple[str, dict[str, str], list[str | None]]:
    """(persona source, placeholder values, run-input blocks appended after
    the render) for one persona, per SKILL.md step 4's table."""
    source = _read(AGENTS_DIR / f"{name}.md")
    history = [run["ledger"], run["incremental"]]
    if name == "blake":  # blind every cycle: the PRD, never the diff or history
        values = {
            "PRD": run["prd_body"],
            "RUBRIC": _read(BLIND_RUBRIC).strip(),
            "OUTPUT_FORMAT": _output_format(name),
        }
        return source, values, [run["test_gate"], _filesystem_notes(run["root"])]
    if name == "eve":
        return source, {"PACK_FINDINGS": run["findings"]}, [_eve_inputs(run), *history]
    values = {
        "CONTEXT_FILE": str(run["context"]),
        "DIFF_FILE": run["diff"],
        "PACK_FILE": run["pack"],
        "REVIEW_CHECKLIST": _read(CHECKLIST_FILE).strip(),
        "RUBRIC": _read(CONSENSUS_RUBRIC).strip(),
        "OUTPUT_FORMAT": _output_format(name),
    }
    if name == "bob":
        eve = _read(AGENTS_DIR / "eve.md")
        appendix = [_section(eve, title) for title in EVE_DOUBT_SECTIONS]
        source = "\n\n".join([source.rstrip(), *appendix])
        values["PACK_FINDINGS"] = run["findings"]
        source = f"{source.rstrip()}\n\n{CITATION_LINE}\n"
    return source, values, history


def _render_one(name: str, run: dict, scratch: Path) -> Path | None:
    """Render one persona through render_prompt.py; None on its non-zero exit.
    Run inputs are appended after the render, so text they carry is never
    scanned for placeholders."""
    source, values, appends = _plan(name, run)
    persona = scratch / f"{name}.md"
    persona.write_text(source, encoding="utf-8")
    out = run["context"].parent / f"{name}-prompt-{run['id']}.md"
    cmd = [sys.executable, str(RENDER_SCRIPT), str(persona), "--out", str(out)]
    for key, value in values.items():
        value_file = scratch / f"{name}-{key}.txt"
        value_file.write_text(value, encoding="utf-8")
        cmd += ["--set-file", f"{key}={value_file}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(f"render_roster: {name}: {proc.stderr.strip()}", file=sys.stderr)
        return None
    blocks = [_read(out).strip(), *(block.rstrip() for block in appends if block)]
    out.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return out


def render_roster(
    context_file: Path,
    diff_file: Path,
    prd_file: Path,
    pack_file: Path | None,
    settled_ledger: Path | None,
    prior_findings: Path | None,
    roster: list[str],
) -> dict[str, Path | None]:
    """Write docs/dev/tmp/{name}-prompt-{id}.md for each roster PERSONA name
    ({id} from review-context-{id}.md). A persona whose render fails, or a
    name outside PERSONAS, maps to None; the others still render."""
    rendered: dict[str, Path | None] = dict.fromkeys(roster)
    try:
        run = _run_inputs(
            context_file,
            diff_file,
            prd_file,
            pack_file,
            settled_ledger,
            prior_findings,
        )
    except (OSError, ValueError) as err:
        print(
            f"render_roster: inputs unreadable, nothing rendered: {err}",
            file=sys.stderr,
        )
        return rendered
    with tempfile.TemporaryDirectory() as scratch:
        for name in roster:
            if name not in PERSONAS:
                print(f"render_roster: {name}: not a review persona", file=sys.stderr)
                continue
            try:
                rendered[name] = _render_one(name, run, Path(scratch))
            except (OSError, ValueError) as err:
                print(f"render_roster: {name}: {err}", file=sys.stderr)
    return rendered


def _render_prompts(
    staged: dict,
    roster: list[str],
    settled_ledger: Path | None,
    prior_findings: Path | None = None,
) -> dict[str, str | None]:
    # Preflight runs here, in stage(), and render_roster only ever receives
    # the personas that passed it: a failed persona stays None in the result
    # without render_roster's per-persona logic ever seeing it.
    survivors = [name for name in roster if preflight_persona(name)]
    rendered = render_roster(
        staged["context"],
        staged["diff"],
        staged["prd"],
        staged["pack"],
        settled_ledger,
        prior_findings,
        survivors,
    )
    prompts: dict[str, str | None] = dict.fromkeys(roster)
    for name in survivors:
        path = rendered.get(name)
        prompts[name] = str(path) if path else None
    return prompts


def _open_row(
    kind: str,
    cycle_id: str,
    prompt: str | None,
    cwd: Path,
) -> tuple[str | None, str | None]:
    """(dispatch id, error). Best-effort: every failure is returned, not raised."""
    if prompt is None:
        return None, f"{kind}: no prompt rendered, no dispatch row opened"
    cmd = [
        sys.executable,
        str(RECORD_DISPATCH),
        "start",
        "--kind",
        kind,
        "--task",
        f"review-{cycle_id}",
        "--prompt-file",
        prompt,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return None, f"{kind}: record_dispatch failed ({err})"
    printed = proc.stdout.split()
    if proc.returncode != 0 or len(printed) < 2:
        detail = proc.stderr.strip()
        return None, f"{kind}: record_dispatch exit {proc.returncode}: {detail}"
    return printed[-1], None


def _arm(
    state_path: Path,
    roster: list[str],
    prompts: dict,
    cycle_id: str,
    summary: dict,
) -> None:
    """Autopilot mode only: stamp state.review_lenses, open the CLI rows."""
    lenses = {
        lens: "running"
        for lens, personas in LENS_PERSONAS.items()
        if any(persona in roster for persona in personas)
    }
    tokens = statectl.parse_path("review_lenses")
    try:
        statectl.mutate(state_path, lambda data: statectl.do_set(data, tokens, lenses))
        summary["review_lenses"] = lenses
    except (state.StateError, schema.SchemaError, statectl.UsageError, OSError) as err:
        summary["review_lenses"] = f"failed ({err})"
        summary["errors"].append(f"review_lenses stamp failed: {err}")
    # record_dispatch walks up from its cwd to the autopilot dir holding state.
    cwd = Path(state_path).resolve().parent
    for kind in CLI_REVIEWERS:
        if kind in roster:
            row_id, error = _open_row(kind, cycle_id, prompts.get(kind), cwd)
            summary["dispatch_rows"][kind] = row_id
            if error:
                summary["errors"].append(error)


def _build_summary(
    tasks_file: Path,
    prd_file: Path,
    context: Path,
    diff: Path | None,
    state_path: Path | None,
) -> dict:
    """The summary dict's shape before the context/pack/gate blocks land."""
    return {
        "ok": True,
        "mode": "standalone" if state_path is None else "autopilot",
        "tasks_file": str(tasks_file),
        "prd_file": str(prd_file),
        "context_file": str(context),
        "diff_file": str(diff) if diff else None,
        "dispatch_rows": dict.fromkeys(CLI_REVIEWERS),
        "errors": [],
    }


def _append_context_blocks(
    context: Path,
    diff: Path | None,
    repo_root: Path,
    base: str | None,
    replay_cmd: str | None,
    settled_ledger: Path | None,
    cycle_id: str,
    prd_path: Path,
    gate_command: str,
    summary: dict,
) -> Path | None:
    """Append the mech, ledger, pack and gate blocks to `context`. Returns
    the pack path for the prompt-rendering step."""
    _append_mech_blocks(context, diff, repo_root, base, replay_cmd)
    if settled_ledger is not None:
        block, error = _ledger_block(settled_ledger)
        if block:
            _append(context, block)
        else:
            summary["errors"].append(error)
    pack, summary["pack"] = run_pack(repo_root, cycle_id, prd_path)
    _append_pack(context, pack)
    try:
        summary["gate"] = run_gate_line(repo_root, gate_command, cycle_id)
    except OSError as err:
        summary["gate"] = {
            "verdict": "error",
            "tests_line": f"Tests: (gate failed to run: {err})",
            "timed_out": False,
        }
        summary["errors"].append(f"gate failed: {err}")
    _append(context, f"## Test gate\n\n{summary['gate']['tests_line']}")
    return pack


def _replay_base(context: Path, repo_root: Path) -> str | None:
    # Not a 2nd resolver: anchors gather-context.sh's own base (7b1f589).
    base = scope.group(1) if (scope := _SCOPE_RE.search(_read(context))) else None
    return (_git_out(repo_root, "merge-base", "HEAD", base) or base) if base else None


def _tmp_escape_refusal(tmp_dir: Path, repo_root: Path) -> dict | None:
    if tmp_dir.resolve().is_relative_to(repo_root.resolve()):
        return None
    return {
        "ok": False,
        "error": f"{TMP_REL} resolves outside the repo; refusing to stage",
        "exit": 2,
    }


def stage(
    cycle_id: str,
    tasks: list[dict],
    prd_path: Path,
    design_doc: Path | None,
    roster: list[str],
    repo_root: Path,
    gate_command: str,
    replay_cmd: str | None,
    since: str | None = None,
    state_path: Path | None = None,
    settled_ledger: Path | None = None,
    prior_findings: Path | None = None,
) -> dict:
    """Stage every input file of one review cycle (PRD 00249 design doc,
    steps 1-9; step 9 only when `state_path` is given). Returns the summary
    dict, or {"ok": False, "error": ..., "exit": n} when gather-context.sh
    refuses (exit 3 on an empty diff), stderr intact and never retried."""
    if not _ID_RE.fullmatch(cycle_id):
        raise ValueError(f"cycle_id {cycle_id!r} is not a safe file-name id")
    started = time.monotonic()
    repo_root = Path(repo_root)
    tmp_dir = repo_root / TMP_REL
    if refusal := _tmp_escape_refusal(tmp_dir, repo_root):
        return refusal
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tasks_file, prd_file = _write_inputs(tmp_dir, cycle_id, tasks, prd_path, design_doc)
    gathered = _gather(repo_root, since, cycle_id)
    if not gathered["ok"]:
        return gathered
    context, diff = gathered["context"], gathered["diff"]
    summary = _build_summary(tasks_file, prd_file, context, diff, state_path)
    pack = _append_context_blocks(
        context,
        diff,
        repo_root,
        _replay_base(context, repo_root),
        replay_cmd,
        settled_ledger,
        cycle_id,
        prd_path,
        gate_command,
        summary,
    )
    staged = {"context": context, "diff": diff, "prd": prd_file, "pack": pack}
    summary["prompts"] = _render_prompts(staged, roster, settled_ledger, prior_findings)
    if state_path is not None:
        _arm(state_path, roster, summary["prompts"], cycle_id, summary)
    summary["elapsed_s"] = round(time.monotonic() - started, 3)
    return summary
