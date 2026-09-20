"""Render fast-track spec cards from a PRD (PRD 00206) - one card per CardPlan.

`lane.plan_cards` (loaded by path from `skills/run-autopilot/cli/lane.py`)
owns the split; this script only renders what it planned, then loads every
card back through `card.load_card` so nothing the lane would refuse is left
in `--out`. A field it cannot derive stops the run with exit 2 and
`cards_from_prd.py: <field>: <message>` on stderr, the `card.py` idiom, and
the PRD takes the full loop with reason `uncardable`.

    python3 cards_from_prd.py <prd> --out <dir>

The cwd is the repo root: every `## Files` entry and `sample_test` resolves
from it.
"""

from __future__ import annotations

import argparse
import importlib.util
import posixpath
import re
import sys
from pathlib import Path

_CLI_DIR = Path(__file__).resolve().parents[2] / "run-autopilot" / "cli"

_GATE_PREFIXES = ("uv run ", "python -m pytest", "pytest", "bash ")
_CHAIN_TOKENS = ("&&", ";", "|")
_MODELS = ("sonnet", "opus")
_BACKTICK_SPAN = re.compile(r"`([^`]+)`")
# A bare `::test_name` continues the file of the id before it, the way a
# PRD's acceptance line lists several tests of one file.
_TEST_ID = re.compile(r"(?:([\w./-]+\.(?:py|sh)))?::(test_\w+)")
_TEST_FILE = re.compile(r"[\w./-]+/test_[\w-]+\.(py|sh)")
_PHASE_HEADING = re.compile(r"^### Phase \d+:")
_PHASE_PARENTS = ("## Tasks", "## Implementation Phases")
_CONSTRAINT_HEADINGS = ("## Constraints", "### Non-Goals", "## Non-Goals", "## Risks")
_SUCCESS_HEADING = "## Success Criteria"


def _load_by_path(name: str, path: Path):
    """Load a sibling module by path (the `classify_tier._load_is_test_path`
    idiom), registered in sys.modules so its dataclasses resolve."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lane = _load_by_path("lane", _CLI_DIR / "lane.py")
frontmatter = _load_by_path("frontmatter", _CLI_DIR / "frontmatter.py")
card = _load_by_path("card", Path(__file__).with_name("card.py"))


class RenderError(Exception):
    """A card the renderer cannot derive, carrying the field that stopped it."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


# ── PRD sections ─────────────────────────────────────────────────────────────


def _section(lines: list[str], headings: tuple[str, ...]) -> list[str] | None:
    """Body lines under the first of `headings` present, up to the next
    heading of the same or a higher level; None when none is present."""
    for heading in headings:
        if heading not in lines:
            continue
        level = len(heading) - len(heading.lstrip("#"))
        body: list[str] = []
        for line in lines[lines.index(heading) + 1 :]:
            if re.match(rf"^#{{1,{level}}} ", line):
                break
            body.append(line.rstrip())
        return body
    return None


def _phase_bodies(lines: list[str]) -> dict[str, list[str]]:
    """Raw body lines per `### Phase N:` heading under `## Tasks` or
    `## Implementation Phases`, keyed by the heading text (lane's terms)."""
    bodies: dict[str, list[str]] = {}
    under_parent = False
    current: list[str] | None = None
    for line in lines:
        if line.startswith("## "):
            under_parent = line.strip() in _PHASE_PARENTS
            current = None
        elif line.startswith("### "):
            current = None
            if under_parent and _PHASE_HEADING.match(line):
                current = bodies.setdefault(line[4:].strip(), [])
        elif current is not None:
            current.append(line)
    return bodies


def _commands(text: str) -> list[str]:
    """The backticked commands in `text` that begin with a gate prefix."""
    return [
        span.strip()
        for span in _BACKTICK_SPAN.findall(text)
        if span.strip().startswith(_GATE_PREFIXES)
    ]


# ── fields ───────────────────────────────────────────────────────────────────


def _item(stem: str, n: int) -> str:
    return f"{stem}-c{n}".lower().replace("_", "-")


def _model(declared: dict[str, str]) -> str:
    value = declared.get("default_model", "")
    return value if value in _MODELS else "sonnet"


def _test_ids(task_items: tuple[str, ...], root: Path) -> tuple[list[str], list[str]]:
    """(ids whose file exists on disk, ids whose file the PRD is about to
    create), in order of appearance, deduplicated."""
    shipped: list[str] = []
    to_write: list[str] = []
    for item in task_items:
        path = ""
        for found, name in _TEST_ID.findall(item):
            path = found or path
            if not path:
                continue
            test_id = f"{path}::{name}"
            bucket = shipped if (root / path).is_file() else to_write
            if test_id not in bucket:
                bucket.append(test_id)
    return shipped, to_write


def _framework(text: str) -> str:
    if re.search(r"test_[\w-]+\.py\b", text):
        return "pytest"
    if re.search(r"test_[\w-]+\.sh\b", text):
        return "bash"
    raise RenderError("framework", "the PRD names no test_*.py or test_*.sh file")


def _sample_test(text: str, root: Path) -> str:
    for match in _TEST_FILE.finditer(text):
        if (root / match.group(0)).is_file():
            return match.group(0)
    raise RenderError("sample_test", "no test file the PRD names exists on disk")


def _check_files(files: tuple[str, ...], root: Path) -> None:
    for entry in files:
        if "*" in entry:
            raise RenderError(
                "files", f"{entry} is a glob; the lane's allowlist is literal"
            )
        if "/" not in entry:
            ok = (root / entry).is_file()
        else:
            ok = (root / posixpath.dirname(entry)).is_dir()
        if not ok:
            raise RenderError("files", f"{entry} does not resolve from the repo root")


def _gates(
    task_items: tuple[str, ...],
    phase_bodies: list[list[str]],
    success: list[str] | None,
) -> list[str]:
    found = _commands(" ".join(task_items))
    for body in phase_bodies:
        for line in body:
            if line.lstrip().startswith("**Exit Criteria**"):
                found += _commands(line)
    found += _commands("\n".join(success or []))
    gates: list[str] = []
    for command in found:
        if any(token in command for token in _CHAIN_TOKENS):
            print(
                f"cards_from_prd.py: gates: dropped chained command: {command}",
                file=sys.stderr,
            )
        elif command not in gates:
            gates.append(command)
    if not gates:
        raise RenderError("gates", "no uv run / pytest / bash command left to run")
    return gates


def _constraints(to_write: list[str], lines: list[str]) -> str:
    parts: list[str] = []
    if to_write:
        parts.append("Tests to write: " + ", ".join(to_write))
    section = _section(lines, _CONSTRAINT_HEADINGS)
    if section is not None and "".join(section).strip():
        parts.append("\n".join(section).strip())
    return "\n\n".join(parts) if parts else "none"


# ── render ───────────────────────────────────────────────────────────────────


def _render(
    plan, n: int, total: int, text: str, declared: dict, stem: str, root: Path
) -> str:
    lines = text.splitlines()
    bodies = _phase_bodies(lines)
    own = [bodies[plan.phase]] if plan.phase else list(bodies.values())
    shipped, to_write = _test_ids(plan.task_items, root)
    changelog_task = next((t for t in plan.task_items if "CHANGELOG.md" in t), "")
    head = [
        "---",
        f"item: {_item(stem, n)}",
        f"model: {_model(declared)}",
        f"suite: {'batch' if n == total else 'per-item'}",
        # `none` is the literal fast-track § Card skips the CHANGELOG edit on;
        # an empty value would ask the implementor for an empty entry.
        f"changelog: {changelog_task or 'none'}",
    ]
    if not shipped:
        head.append(f"framework: {_framework(text)}")
        head.append(f"sample_test: {_sample_test(text, root)}")
    head.append("---")
    _check_files(plan.files, root)
    gates = _gates(plan.task_items, own, _section(lines, (_SUCCESS_HEADING,)))
    sections = [
        ("Goal", "\n".join(plan.goal_lines)),
        ("Tests", "\n".join(shipped)),
        ("Files", "\n".join(plan.files)),
        ("Constraints", _constraints(to_write, lines)),
        ("Docs", "CHANGELOG.md" if changelog_task else "none"),
        ("Gates", "\n".join(gates)),
        ("Transport impact", "none"),
    ]
    body = "".join(f"\n## {name}\n\n{content}\n" for name, content in sections)
    return "\n".join(head) + "\n" + body


def render_cards(prd_path: Path, out_dir: Path, root: Path) -> list[Path]:
    """Write one card per CardPlan under `out_dir` and return their paths;
    on the first refusal (a field, a card the lane refuses, a failed write)
    remove every written card and raise."""
    try:
        text = prd_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RenderError("prd", str(exc)) from exc
    plans = lane.plan_cards(text)
    if not plans:
        raise RenderError(
            "cards", "lane.plan_cards refused the PRD; it takes the full loop"
        )
    declared = frontmatter.declared(text)
    stem = prd_path.name.removesuffix(".md")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        for n, plan in enumerate(plans, start=1):
            rendered = _render(plan, n, len(plans), text, declared, stem, root)
            path = out_dir / f"{_item(stem, n)}.md"
            try:
                path.write_text(rendered, encoding="utf-8")
            except OSError as exc:
                raise RenderError("out", str(exc)) from exc
            written.append(path)
            card.load_card(path)
    except (RenderError, card.CardError):
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render fast-track cards from a PRD.")
    parser.add_argument("prd", help="path to the PRD")
    parser.add_argument(
        "--out", required=True, help="directory the cards are written to"
    )
    args = parser.parse_args(argv)
    try:
        paths = render_cards(Path(args.prd), Path(args.out), Path.cwd())
    except (RenderError, card.CardError) as exc:
        print(f"cards_from_prd.py: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        # `out_dir.mkdir` is the one write outside render_cards' rollback.
        print(f"cards_from_prd.py: out: {exc}", file=sys.stderr)
        return 2
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
