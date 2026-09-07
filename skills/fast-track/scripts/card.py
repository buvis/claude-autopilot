"""Spec-card parser for /fast-track — one hand-written card in, one Card out.

The card is the only input the lane is assembled from, so nothing here guesses:
an absent section, an unknown enum value, a chained gate line or a card past the
lane's size bounds all stop the load and name the offending field. The CLI turns
that refusal into exit 2 with the field on stderr; a good card prints as JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_ITEM = re.compile(r"[a-z0-9-]+")
_MODELS = ("sonnet", "opus")
_SUITES = ("batch", "per-item")
_CHAIN_TOKENS = ("&&", ";", "|")
_MAX_FILES = 12
_MAX_GOAL_LINES = 40
_TOO_LARGE = "card too large for the lane; write a PRD"

# Heading text -> Card attribute. All seven are required, and the order is the
# order they are reported missing in.
_SECTIONS = {
    "Goal": "goal",
    "Tests": "tests",
    "Files": "files",
    "Constraints": "constraints",
    "Docs": "docs",
    "Gates": "gates",
    "Transport impact": "transport_impact",
}


class CardError(Exception):
    """A card the lane refuses, carrying the field that earned the refusal."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(f"{field}: {message}")
        self.field = field


@dataclass
class Card:
    """Everything the lane reads. Prose sections stay prose, lists stay lists."""

    item: str
    model: str
    suite: str
    changelog: str
    framework: str | None
    sample_test: str | None
    goal: str
    tests: list[str]
    files: list[str]
    constraints: str
    docs: str
    gates: list[str]
    transport_impact: str


def _split_frontmatter(text: str) -> tuple[dict[str, str], list[str]]:
    """Split the opening `---` block into keys, and return the body lines."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in lines[1:]:
        raise CardError("frontmatter", "card must open with a closed --- block")
    end = lines.index("---", 1)
    keys = {}
    for line in lines[1:end]:
        if line.strip():
            key, _, value = line.partition(":")
            keys[key.strip()] = value.strip()
    return keys, lines[end + 1 :]


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    """Collect the body lines under each known `## ` heading."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        if line.startswith("## "):
            current = _SECTIONS.get(line[3:].strip())
            if current:
                sections[current] = []
        elif current:
            sections[current].append(line)
    return sections


def _require_sections(sections: dict[str, list[str]]) -> None:
    for name in _SECTIONS.values():
        if name not in sections:
            raise CardError(name, "card is missing this ## section")


def _require_choice(keys: dict[str, str], field: str, allowed: tuple[str, ...]) -> str:
    value = keys.get(field, "")
    if value not in allowed:
        raise CardError(field, f"unknown {field} {value!r}; use one of {allowed}")
    return value


def _items(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def _check_gates(gates: list[str]) -> None:
    for gate in gates:
        if any(token in gate for token in _CHAIN_TOKENS):
            raise CardError("gates", f"gate line chains commands: {gate}")


def load_card(path: Path) -> Card:
    """Parse one spec card, or raise CardError naming the field that failed."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CardError("card", str(exc)) from exc
    keys, body = _split_frontmatter(text)
    sections = _split_sections(body)
    _require_sections(sections)

    tests = _items(sections["tests"])
    framework = keys.get("framework") or None
    sample_test = keys.get("sample_test") or None
    if not tests:
        if not framework:
            raise CardError("framework", "an empty ## Tests section needs a framework")
        if not sample_test:
            raise CardError("sample_test", "an empty ## Tests section needs a sample")

    gates = _items(sections["gates"])
    _check_gates(gates)

    files = _items(sections["files"])
    if len(files) > _MAX_FILES:
        raise CardError("files", f"{len(files)} files past {_MAX_FILES}: {_TOO_LARGE}")

    goal = "\n".join(sections["goal"])
    if len(goal.strip().splitlines()) > _MAX_GOAL_LINES:
        raise CardError("goal", f"goal past {_MAX_GOAL_LINES} lines: {_TOO_LARGE}")

    item = keys.get("item", "")
    if not _ITEM.fullmatch(item):
        raise CardError("item", f"item {item!r} is not a slug matching [a-z0-9-]+")

    return Card(
        item=item,
        model=_require_choice(keys, "model", _MODELS),
        suite=_require_choice(keys, "suite", _SUITES),
        changelog=keys.get("changelog", ""),
        framework=framework,
        sample_test=sample_test,
        goal=goal,
        tests=tests,
        files=files,
        constraints="\n".join(sections["constraints"]),
        docs="\n".join(sections["docs"]),
        gates=gates,
        transport_impact="\n".join(sections["transport_impact"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse a fast-track spec card.")
    parser.add_argument("card", help="path to the spec card")
    args = parser.parse_args(argv)

    try:
        card = load_card(Path(args.card))
    except CardError as exc:
        print(f"card.py: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(card), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
