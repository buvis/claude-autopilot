#!/usr/bin/env python3
"""Stage one review cycle's input files in code (PRD 00249).

`stage()` replaces the hand-staging of review-work-completion/SKILL.md step 3
(tasks and PRD files, gather-context.sh, the mechanical blocks, the ledger,
the engram pack, the Tests: line) and step 5's roster stamp. The existing
scripts run as subprocesses, unchanged; nothing here re-derives what they
compute.

`render_roster()` is a STUB in this task: it returns {name: None} and writes
nothing. A later task replaces its body only; `stage()` already calls it with
the final signature and only ever passes it personas that passed preflight.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
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
# The plugin root's agents/: the installed cache dir when run from the
# plugin, this checkout's agents/ when run from source.
AGENTS_DIR = _SKILLS.parent / "agents"

ENGRAM = "engram"
ENGRAM_TIMEOUT_S = 300
CAPSULE_REL = "docs/dev/project-management/meta/project-capsule.md"
TMP_REL = Path("docs/dev/tmp")
NO_PACK = "(no pack available this cycle)"
SETTLED_HEADING = "## Settled decisions — do not re-raise"
SETTLED_INTRO = (
    "> These calls were already made in an earlier cycle of this same review, with\n"
    "> the reasons given. Do not re-raise them. Raise a NEW finding only if you can\n"
    "> show the settled reason no longer holds."
)
REQUIRED_PERSONA_KEYS = ("name", "description", "tools")
CLI_REVIEWERS = ("bob", "carl")
# A lens is active when any of its personas is on the roster.
LENS_PERSONAS = {
    "consensus": ("alice", "bob", "carl"),
    "blind": ("blake",),
    "doubt": ("bob", "eve"),
    "fable": ("eve",),
}

_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_PERSONA_RE = re.compile(r"[a-z][a-z0-9_-]*")
_DIFF_HEADER_RE = re.compile(r"^diff --git a/.* b/(.+)$", re.MULTILINE)
_FINDINGS_RE = re.compile(
    r"^(#+)\s*Findings precedent\s*$", re.MULTILINE | re.IGNORECASE
)


def _git_out(repo_root: Path, *args: str) -> str | None:
    proc = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
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
    prd_text = Path(prd_path).read_text(encoding="utf-8").rstrip() + "\n"
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
        args, cwd=repo_root, capture_output=True, text=True, check=False
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


def resolve_base(repo_root: Path, since: str | None) -> str | None:
    """The diff range's left side, as SKILL.md step 3 defines it: a valid
    `since` wins; otherwise the merge-base of HEAD with origin/HEAD, then
    master, then develop. None when nothing resolves."""
    if since:
        sha = _git_out(
            repo_root, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}"
        )
        if sha:
            return sha
    for candidate in ("origin/HEAD", "master", "develop"):
        sha = _git_out(repo_root, "merge-base", "HEAD", candidate)
        if sha:
            return sha
    return None


def _run_script(script: Path, args: list[str], cwd: Path) -> str:
    """A helper script's stdout; a failed run says so in the block instead."""
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()[-1:] or ["no stderr"]
        return f"_{script.name} failed (exit {proc.returncode}): {detail[0]}_"
    return proc.stdout.strip()


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
    replay_args = ["--base", base, "--cmd", replay_cmd]
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
                f"reason: {entry.get('reason')}"
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
    repo_root: Path, cycle_id: str, prd_path: Path
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
        f"## Context Pack\n\nPack file: {pack if pack else NO_PACK}\n\n"
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
    return f"Tests: {counts[0]} passed, {counts[1]} failed, {counts[2]} skipped {suffix}"


def run_gate_line(repo_root: Path, gate_command: str, cycle_id: str) -> dict:
    """Reuse the recorded gate when it still certifies HEAD, else run it once."""
    head = _git_out(repo_root, "rev-parse", "HEAD") or ""
    verdict, record = verification.reuse_verdict(
        _read_record(repo_root), repo_root, head
    )
    if verdict == "reused":
        counts = (record["passed"], record["failed"], record["skipped"])
        suffix = f"(reused from last-verification.json at {record['sha'][:7]})"
        return {"verdict": verdict, "tests_line": _tests_line(counts, suffix),
                "timed_out": False}
    cycle = int(cycle_id) if cycle_id.isascii() and cycle_id.isdigit() else None
    result = verification.run_gate(gate_command, repo_root, sha=head, cycle=cycle)
    if result["timed_out"]:
        # TESTS_RE needs counts; zeros plus the suffix say none were read.
        suffix = (
            f"(suite timed out after {int(verification.GATE_TIMEOUT_S)}s, "
            "treated as failed)"
        )
        line = _tests_line((0, 0, 0), suffix)
    elif result["passed"] is None:
        line = (
            f"Tests: counts unavailable (suite run this cycle, exit {result['exit']}, "
            "no PASS/FAIL/SKIP/EXIT summary line)"
        )
    else:
        counts = (result["passed"], result["failed"], result["skipped"])
        line = _tests_line(counts, "(suite run this cycle)")
    return {"verdict": verdict, "tests_line": line, "timed_out": result["timed_out"]}


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


def render_roster(
    context_file: Path,
    diff_file: Path,
    prd_file: Path,
    pack_file: Path | None,
    settled_ledger: Path | None,
    prior_findings: Path | None,
    roster: list[str],
) -> dict[str, Path | None]:
    """STUB for this task — real implementation is a later task. Returns
    {name: None for name in roster} and writes nothing."""
    return {name: None for name in roster}


def _render_prompts(
    staged: dict, roster: list[str], settled_ledger: Path | None
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
        None,
        survivors,
    )
    prompts: dict[str, str | None] = {name: None for name in roster}
    for name in survivors:
        path = rendered.get(name)
        prompts[name] = str(path) if path else None
    return prompts


def _open_row(
    kind: str, cycle_id: str, prompt: str | None, cwd: Path
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
            cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        return None, f"{kind}: record_dispatch failed ({err})"
    printed = proc.stdout.split()
    if proc.returncode != 0 or len(printed) < 2:
        detail = proc.stderr.strip()
        return None, f"{kind}: record_dispatch exit {proc.returncode}: {detail}"
    return printed[-1], None


def _arm(
    state_path: Path, roster: list[str], prompts: dict, cycle_id: str, summary: dict
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
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tasks_file, prd_file = _write_inputs(tmp_dir, cycle_id, tasks, prd_path, design_doc)
    gathered = _gather(repo_root, since, cycle_id)
    if not gathered["ok"]:
        return gathered
    context, diff = gathered["context"], gathered["diff"]
    summary: dict = {
        "ok": True,
        "mode": "standalone" if state_path is None else "autopilot",
        "tasks_file": str(tasks_file),
        "prd_file": str(prd_file),
        "context_file": str(context),
        "diff_file": str(diff) if diff else None,
        "dispatch_rows": {kind: None for kind in CLI_REVIEWERS},
        "errors": [],
    }
    base = resolve_base(repo_root, since)
    _append_mech_blocks(context, diff, repo_root, base, replay_cmd)
    if settled_ledger is not None:
        block, error = _ledger_block(settled_ledger)
        if block:
            _append(context, block)
        else:
            summary["errors"].append(error)
    pack, summary["pack"] = run_pack(repo_root, cycle_id, prd_path)
    _append_pack(context, pack)
    summary["gate"] = run_gate_line(repo_root, gate_command, cycle_id)
    _append(context, f"## Test gate\n\n{summary['gate']['tests_line']}")
    staged = {"context": context, "diff": diff, "prd": prd_file, "pack": pack}
    summary["prompts"] = _render_prompts(staged, roster, settled_ledger)
    if state_path is not None:
        _arm(state_path, roster, summary["prompts"], cycle_id, summary)
    summary["elapsed_s"] = round(time.monotonic() - started, 3)
    return summary
