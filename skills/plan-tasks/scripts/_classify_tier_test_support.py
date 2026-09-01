"""Shared bootstrap and helpers for the classify_tier.py test suite.

test_classify_tier.py grew past the repo's 800-line file cap, so its tests
are split by theme across sibling test_classify_tier_*.py modules. This
module holds what all of them need: the by-path imports of classify_tier.py
and work_routing.py (the same technique classify_tier.py itself is not part
of an installable package, so neither module can be reached with a plain
``import``), plus the ``_classify``/``_run_cli`` call helpers every split
module builds its assertions on.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name("classify_tier.py")
_SPEC = importlib.util.spec_from_file_location("classify_tier", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
classify_tier = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(classify_tier)

_ROUTING_PATH = Path(__file__).parents[2] / "work" / "scripts" / "work_routing.py"
_ROUTING_SPEC = importlib.util.spec_from_file_location("work_routing", _ROUTING_PATH)
assert _ROUTING_SPEC is not None and _ROUTING_SPEC.loader is not None
work_routing = importlib.util.module_from_spec(_ROUTING_SPEC)
_ROUTING_SPEC.loader.exec_module(work_routing)


def _classify(
    files: list[str],
    text: str = "",
    lines_changed: int = 0,
    *,
    contract_edit: bool = False,
    algorithmic_risk: bool = False,
    default_model: str | None = None,
) -> dict:
    return classify_tier.classify(
        files=files,
        text=text,
        lines_changed=lines_changed,
        contract_edit=contract_edit,
        algorithmic_risk=algorithmic_risk,
        default_model=default_model,
    )


def _run_cli(
    tmp_path: Path,
    files: list[str],
    text: str,
    lines: int,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    files_file = tmp_path / "files.txt"
    files_file.write_text("\n".join(files) + "\n", encoding="utf-8")
    text_file = tmp_path / "text.txt"
    text_file.write_text(text + "\n", encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--files-file",
            str(files_file),
            "--text-file",
            str(text_file),
            "--lines",
            str(lines),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
