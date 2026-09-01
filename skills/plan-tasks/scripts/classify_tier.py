"""Model-tier classification for /plan-tasks — one task's shape decides its tier.

Pure decision core plus a thin CLI the planner shells out to. The rules are
checked in order and the first match wins, so the recorded `tier_reason` names
the rule that paid for the tier. A batch-wide `default_model` acts as a floor:
it only ever lifts a task, and when it does the reason says `floor`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_is_test_path():
    """Borrow the /work test-path predicate so both skills judge paths alike."""
    path = Path(__file__).resolve().parents[2] / "work" / "scripts" / "work_routing.py"
    spec = importlib.util.spec_from_file_location("work_routing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.is_test_path


is_test_path = _load_is_test_path()

# Declarative manifests: an edit here is packaging work however the prose reads.
# Matched on the basename, exactly and case-sensitively, at any depth.
_PACKAGING_BASENAMES = frozenset(
    {
        "plugin.json",
        "marketplace.json",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "setup.py",
        "setup.cfg",
        "MANIFEST.in",
        "Pipfile",
        "Pipfile.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "mise.toml",
        ".mise.toml",
        ".tool-versions",
        "requirements.txt",
        "requirements-dev.txt",
        "requirements-test.txt",
    },
)

# Phrases that buy the cheap tier. Closed list, matched as substrings of the
# lowercased text: adding one is a routing decision, not a wording tweak.
_MECHANICAL_PHRASES = (
    "add log",
    "rename",
    "add test for",
    "port",
    "mirror",
    "inline",
    "extract constant",
    "update import",
    "bump version",
)

_MECHANICAL_MAX_FILES = 2
_MECHANICAL_MAX_LINES = 50

_MODEL_ORDER = {"haiku": 0, "sonnet": 1, "opus": 2}


def is_packaging_path(path: str) -> bool:
    """True when a repo-relative path is a packaging manifest or plugin metadata."""
    segments = path.split("/")
    if ".claude-plugin" in segments:
        return True
    return segments[-1] in _PACKAGING_BASENAMES


def classify(
    files: list[str],
    text: str,
    lines_changed: int,
    contract_edit: bool = False,
    algorithmic_risk: bool = False,
    default_model: str | None = None,
) -> dict:
    """Pick the model tier for one task and record why."""
    model, reason = _tier_from_shape(
        files,
        text,
        lines_changed,
        contract_edit,
        algorithmic_risk,
    )
    model, reason = _apply_floor(model, reason, default_model)
    return {"model": model, "tier_reason": reason}


def _tier_from_shape(
    files: list[str],
    text: str,
    lines_changed: int,
    contract_edit: bool,
    algorithmic_risk: bool,
) -> tuple[str, str]:
    if files and all(is_test_path(path) for path in files):
        return "sonnet", "test_port"
    if files and all(is_packaging_path(path) for path in files):
        return "sonnet", "packaging"
    if contract_edit:
        return "opus", "contract"
    if algorithmic_risk:
        return "opus", "algorithmic_risk"
    if (
        _is_mechanical(text)
        and len(files) <= _MECHANICAL_MAX_FILES
        and lines_changed <= _MECHANICAL_MAX_LINES
    ):
        return "haiku", "mechanical"
    return "sonnet", "default"


def _is_mechanical(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _MECHANICAL_PHRASES)


def _apply_floor(model: str, reason: str, default_model: str | None) -> tuple[str, str]:
    if default_model is None:
        return model, reason
    if default_model not in _MODEL_ORDER:
        print(
            f"classify_tier: ignoring unknown default model {default_model!r}",
            file=sys.stderr,
        )
        return model, reason
    if _MODEL_ORDER[default_model] > _MODEL_ORDER[model]:
        return default_model, "floor"
    return model, reason


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a task's model tier.")
    parser.add_argument("--files-file")
    parser.add_argument("--text-file")
    parser.add_argument("--lines", type=int, default=0)
    parser.add_argument("--contract-edit", action="store_true")
    parser.add_argument("--algorithmic-risk", action="store_true")
    parser.add_argument("--default-model")
    args = parser.parse_args(argv)

    if not args.files_file or not args.text_file:
        print(
            "classify_tier: --files-file and --text-file are both required",
            file=sys.stderr,
        )
        return 1
    try:
        raw_files = Path(args.files_file).read_text(encoding="utf-8")
        text = Path(args.text_file).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"classify_tier: cannot read input file: {exc}", file=sys.stderr)
        return 1

    result = classify(
        files=[line.strip() for line in raw_files.splitlines() if line.strip()],
        text=text,
        lines_changed=args.lines,
        contract_edit=args.contract_edit,
        algorithmic_risk=args.algorithmic_risk,
        default_model=args.default_model,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
