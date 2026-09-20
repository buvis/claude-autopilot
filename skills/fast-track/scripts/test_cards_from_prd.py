"""Tests for cards_from_prd.py (PRD 00206): the renderer that turns
`lane.plan_cards`' plan into spec cards `card.load_card` accepts, or refuses
naming the field.

The raw 00188, 00189 and 00201 are read from 00204's frozen copies under
`skills/run-autopilot/cli/golden/lanes/`; the repaired 00188 (its seven
non-repo-relative paths rewritten under `skills/run-autopilot/`) and the
synthetic 25-path PRD live under `fixtures/lanes/` beside this file. Every
render resolves paths from the repo root, as the lane does.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRIPT = HERE / "cards_from_prd.py"
FIXTURES = HERE / "fixtures" / "lanes"
FROZEN = REPO / "skills" / "run-autopilot" / "cli" / "golden" / "lanes"


def _frozen(number: str) -> Path:
    (path,) = FROZEN.glob(f"{number}-*.md")
    return path


def _renderer():
    spec = importlib.util.spec_from_file_location("cards_from_prd", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["cards_from_prd"] = module
    spec.loader.exec_module(module)
    return module


cards = _renderer()
card = cards.card


def _run(prd: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(prd), "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def _fields(path: Path) -> dict[str, str]:
    keys, _body = card._split_frontmatter(path.read_text(encoding="utf-8"))
    return keys


def test_repaired_00188_renders_two_cards_load_card_accepts(tmp_path: Path) -> None:
    paths = cards.render_cards(FIXTURES / "00188-repaired.md", tmp_path, REPO)
    assert [p.name for p in paths] == ["00188-repaired-c1.md", "00188-repaired-c2.md"]
    first, second = (card.load_card(p) for p in paths)
    for loaded in (first, second):
        assert "skills/run-autopilot/cli/render_report.py" in loaded.files
        assert len(loaded.files) <= 12
    assert (first.suite, second.suite) == ("per-item", "batch")
    assert first.gates[0] == (
        "uv run --no-project --with pytest python -m pytest -q "
        "skills/run-autopilot/cli/test_convergence.py"
    )
    assert "skills/run-autopilot/cli/convergence.py" in first.files
    assert "CHANGELOG.md" in second.files and second.docs.strip() == "CHANGELOG.md"


def test_raw_00188_is_refused_on_a_relative_path(tmp_path: Path) -> None:
    out = tmp_path / "cards"
    proc = _run(_frozen("00188"), out)
    assert proc.returncode == 2, proc.stdout
    assert proc.stderr.startswith("cards_from_prd.py: files: cli/test_loop.py")
    assert list(out.glob("*")) == []


def test_raw_00189_renders_one_card_load_card_accepts(tmp_path: Path) -> None:
    (path,) = cards.render_cards(_frozen("00189"), tmp_path, REPO)
    loaded = card.load_card(path)
    assert len(loaded.files) == 11
    assert loaded.suite == "batch"
    assert loaded.tests == []
    assert loaded.framework == "pytest"
    assert loaded.sample_test == "skills/run-autopilot/cli/test_policy.py"
    assert loaded.model == "opus"  # default_model: opus


def test_00201_renders_one_card_with_tests_to_write(tmp_path: Path) -> None:
    (path,) = cards.render_cards(_frozen("00201"), tmp_path, REPO)
    loaded = card.load_card(path)
    assert loaded.tests == []
    assert loaded.framework == "pytest"
    assert loaded.sample_test.startswith("skills/run-autopilot/")
    assert (REPO / loaded.sample_test).is_file()
    assert loaded.constraints.lstrip().startswith("Tests to write: ")
    first_line = loaded.constraints.strip().splitlines()[0]
    assert "test_brief.py::test_renders_the_documented_shape" in first_line
    assert "test_brief.py::test_missing_fields_render_as_none" in first_line
    assert "pytest -q skills/run-autopilot/cli/test_brief.py" in loaded.gates


def test_twenty_five_paths_exit_two_naming_cards(tmp_path: Path) -> None:
    out = tmp_path / "cards"
    proc = _run(FIXTURES / "twenty-five-paths.md", out)
    assert proc.returncode == 2
    assert proc.stderr.startswith("cards_from_prd.py: cards:")
    # render_cards raises before it creates --out, so nothing is left behind.
    assert not out.exists()


def test_invalid_utf8_prd_exits_two_naming_prd(tmp_path: Path) -> None:
    prd = tmp_path / "latin1.md"
    prd.write_bytes(b"---\ndesign: skip\n---\n\n# Caf\xe9\n")
    proc = _run(prd, tmp_path / "cards")
    assert proc.returncode == 2
    assert proc.stderr.startswith("cards_from_prd.py: prd:")
    assert "Traceback" not in proc.stderr


def test_write_failure_on_a_later_card_rolls_back_the_first(tmp_path: Path, monkeypatch) -> None:
    written: list[Path] = []
    real_write = Path.write_text

    def flaky(self: Path, *args, **kwargs):
        written.append(self)
        if self.name.endswith("-c2.md"):
            # A disk-full write truncates the file before it fails.
            self.write_bytes(b"---\nitem: partial")
            raise OSError(28, "No space left on device")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky)
    with pytest.raises(cards.RenderError) as caught:
        cards.render_cards(FIXTURES / "00188-repaired.md", tmp_path, REPO)
    assert caught.value.field == "out"
    assert len(written) == 2
    assert not any(p.exists() for p in written), "card 1 and the partial card 2 are gone"


def test_item_slugs_match_card_py() -> None:
    assert cards._item("00188_Record-Convergence", 2) == "00188-record-convergence-c2"
    assert card._ITEM.fullmatch(cards._item("00201-write-a-brief-v1", 1))


def test_gates_drop_chained_commands_loud(capsys) -> None:
    items = ("- [ ] Run `pytest -q x | head -3` and `uv run --no-project pytest -q y`",)
    assert cards._gates(items, [], None) == ["uv run --no-project pytest -q y"]
    assert "dropped chained command: pytest -q x | head -3" in capsys.readouterr().err
    with pytest.raises(cards.RenderError) as caught:
        cards._gates(("- [ ] Run `pytest -q x && pytest -q z`",), [], None)
    assert caught.value.field == "gates"


def test_glob_file_entry_is_refused(tmp_path: Path) -> None:
    with pytest.raises(cards.RenderError) as caught:
        cards._check_files(("agents/*.md",), REPO)
    assert caught.value.field == "files"
    prd = tmp_path / "glob.md"
    prd.write_text(
        (FIXTURES / "twenty-five-paths.md")
        .read_text(encoding="utf-8")
        .replace("└── m25.py", "└── *.py"),
        encoding="utf-8",
    )
    proc = _run(prd, tmp_path / "cards")
    assert proc.returncode == 2 and "cards_from_prd.py: cards:" in proc.stderr


def test_model_follows_default_model_else_sonnet() -> None:
    assert cards._model({"default_model": "opus"}) == "opus"
    assert cards._model({"default_model": "sonnet"}) == "sonnet"
    assert cards._model({"default_model": "haiku"}) == "sonnet"
    assert cards._model({}) == "sonnet"


def test_changelog_field_is_the_task_that_names_it(tmp_path: Path) -> None:
    first, second = cards.render_cards(FIXTURES / "00188-repaired.md", tmp_path, REPO)
    # `none`, the literal fast-track § Card skips the CHANGELOG edit on, not
    # the PRD's "empty": an empty value would request an empty entry.
    assert _fields(first)["changelog"] == "none"
    changelog = _fields(second)["changelog"]
    assert changelog.startswith("- [ ] Document the row in")
    assert "CHANGELOG" in changelog
    assert card.load_card(first).docs.strip() == "none"
