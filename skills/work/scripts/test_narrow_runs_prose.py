"""Tests binding the live text of the narrow-test-run sentence — the
instruction that Tess, Devon, and Ivan each run only the task's own test
files (never a whole suite or a whole directory) mid-task, with the full
suite running once at the end.

Mirrors test_adversarial_cap_prose.py's and test_devon_round_prose.py's
pattern: resolve each target file's path relative to this file, read it
once at module level, and assert on short, reword-resistant substrings,
each with a failure message naming what drifted.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_WORK_DIR = _SCRIPTS_DIR.parent
_SKILLS_DIR = _WORK_DIR.parent
_REPO_ROOT = _SKILLS_DIR.parent

_SKILL_MD = _WORK_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_TESS_PROMPT = _WORK_DIR / "references" / "tess-prompt.md"
_TESS_PROMPT_TEXT = _TESS_PROMPT.read_text()

_IVAN_AGENT = _REPO_ROOT / "agents" / "ivan.md"
_IVAN_AGENT_TEXT = _IVAN_AGENT.read_text()

_ADVERSARIAL_TEST_PROMPT = _WORK_DIR / "references" / "adversarial-test-prompt.md"
_ADVERSARIAL_TEXT = _ADVERSARIAL_TEST_PROMPT.read_text()

_TESS_RETRY_PROMPT = _WORK_DIR / "references" / "tess-retry-prompt.md"
_TESS_RETRY_PROMPT_TEXT = _TESS_RETRY_PROMPT.read_text()

_MODULE_PATH = _SCRIPTS_DIR / "render_prompt.py"
_SPEC = importlib.util.spec_from_file_location("render_prompt", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
render_prompt = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(render_prompt)

# The complete narrow-test-run sentence, verbatim, as it appears in every
# pinned file below — held once so every test asserts against this same
# literal text instead of a prefix or a file-vs-file comparison.
NARROW = (
    "Run only the test files this task names (the tests you wrote, or the "
    "failing tests in your prompt), with `-q --tb=line`. Never run a whole "
    "test directory or `dev/bin/release-checks`: the orchestrator runs the "
    "full suite once, after every task. Read the pass count and exit code "
    "from that one run; never re-run a suite to recover a number."
)

# The paragraph NARROW must directly follow in the dispatch-prologue files.
_ANCHOR = "Read every file before your first Edit to it."


def _norm(text: str) -> str:
    """Collapse every run of whitespace (including line-wrap newlines) to a
    single space, so a substring check doesn't break when markdown wraps a
    sentence across lines at a point the needle spells as a plain space."""
    return " ".join(text.split())


def _section(
    text: str, path: Path, start_anchor: str, end_anchor: str | None = None
) -> str:
    """Slice `text` from `start_anchor` up to `end_anchor`, or to the end of
    `text` when `end_anchor` is None — for a section that is the last one in
    its file, so there is no next heading to bound it against.

    Asserts `start_anchor` is present (and, when given, that `end_anchor`
    follows it) first, naming `path` and the missing anchor, so a drifted
    heading fails loudly instead of raising a bare `ValueError: substring
    not found`.
    """
    assert start_anchor in text, (
        f"{path}: expected section anchor {start_anchor!r} — not found."
    )
    start = text.index(start_anchor)
    if end_anchor is None:
        return text[start:]
    assert end_anchor in text[start:], (
        f"{path}: expected section anchor {end_anchor!r} after "
        f"{start_anchor!r} — not found."
    )
    end = text.index(end_anchor, start)
    return text[start:end]


def _assert_narrow_once_and_adjacent(text: str, path: Path) -> None:
    """Assert NARROW appears exactly once in `text` and, split on blank
    lines, is the paragraph immediately following the one starting with
    `_ANCHOR` — adjacency, not merely ordering."""
    norm_text = _norm(text)
    norm_narrow = _norm(NARROW)
    count = norm_text.count(norm_narrow)
    assert count == 1, (
        f"{path}: expected the NARROW sentence exactly once — found {count}."
    )

    paragraphs = text.split("\n\n")
    norm_anchor = _norm(_ANCHOR)
    anchor_index = next(
        (i for i, p in enumerate(paragraphs) if _norm(p).startswith(norm_anchor)),
        None,
    )
    narrow_index = next(
        (i for i, p in enumerate(paragraphs) if _norm(p).startswith(norm_narrow)),
        None,
    )
    assert anchor_index is not None, (
        f"{path}: expected a standalone paragraph starting {_ANCHOR!r} — "
        "not found."
    )
    assert narrow_index is not None, (
        f"{path}: expected a standalone paragraph starting with the NARROW "
        "sentence — not found."
    )
    assert narrow_index == anchor_index + 1, (
        f"{path}: expected the NARROW paragraph directly after the "
        f"{_ANCHOR!r} paragraph (adjacent) — found it out of place "
        "(ordering without adjacency)."
    )


def test_tess_and_ivan_carry_the_narrow_sentence() -> None:
    for text, path in (
        (_IVAN_AGENT_TEXT, _IVAN_AGENT),
        (_TESS_PROMPT_TEXT, _TESS_PROMPT),
    ):
        _assert_narrow_once_and_adjacent(text, path)


def test_tess_retry_prompt_carries_the_narrow_sentence() -> None:
    _assert_narrow_once_and_adjacent(_TESS_RETRY_PROMPT_TEXT, _TESS_RETRY_PROMPT)


def test_adversarial_prompt_carries_narrow_in_feedback_section() -> None:
    norm_narrow = _norm(NARROW)
    count = _norm(_ADVERSARIAL_TEXT).count(norm_narrow)
    assert count == 1, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected the NARROW sentence exactly "
        f"once in the file — found {count}."
    )
    feedback_section = _section(
        _ADVERSARIAL_TEXT,
        _ADVERSARIAL_TEST_PROMPT,
        "## Feedback to Tess (when Devon succeeds)",
    )
    assert "```" in feedback_section, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected a fenced template under "
        "'Feedback to Tess' — no opening fence found."
    )
    fence_start = feedback_section.index("```") + len("```")
    assert "```" in feedback_section[fence_start:], (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected a closing fence for the "
        "'Feedback to Tess' template — not found."
    )
    fence_end = feedback_section.index("```", fence_start)
    fenced_template = feedback_section[fence_start:fence_end]
    assert norm_narrow in _norm(fenced_template), (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected the NARROW sentence inside "
        "the 'Feedback to Tess' fenced template — not found there."
    )


def test_devon_runner_is_the_tasks_test_files() -> None:
    runner_line = _section(
        _ADVERSARIAL_TEXT, _ADVERSARIAL_TEST_PROMPT, "Test runner command:", "\n"
    )
    assert _norm("runs ONLY this task's test files") in _norm(runner_line), (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected \"runs ONLY this task's "
        'test files" on the Test runner command line — not found there.'
    )
    assert _norm("e.g. npm test, pytest, cargo test") not in _norm(
        _ADVERSARIAL_TEXT
    ), (
        f"{_ADVERSARIAL_TEST_PROMPT}: found the old generic runner-"
        "command placeholder 'e.g. npm test, pytest, cargo test' — it "
        "should have been replaced by the narrow, task-scoped wording."
    )


def test_devon_rules_forbid_a_directory_run() -> None:
    rules_section = _section(
        _ADVERSARIAL_TEXT, _ADVERSARIAL_TEST_PROMPT, "Rules:", "Output format:"
    )
    needle = _norm(
        "Run only the test runner command above, once per exploit; "
        "never a whole test directory."
    )
    normalized = _norm(rules_section)
    assert normalized.endswith(needle), (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected the Devon Rules list to end "
        f"with {needle!r} as its last rule — not found there."
    )


def test_devon_process_step_runs_test_runner_command() -> None:
    process_section = _section(
        _ADVERSARIAL_TEXT, _ADVERSARIAL_TEST_PROMPT, "Process:", "Rules:"
    )
    new_wording = "Run the test runner command above against your wrong implementation"
    old_wording = "Run the test suite against your wrong implementation"
    assert new_wording in process_section, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected Process step 3 to read "
        f"{new_wording!r} — not found."
    )
    assert old_wording not in process_section, (
        f"{_ADVERSARIAL_TEST_PROMPT}: found the old Process step 3 wording "
        f"{old_wording!r} — it should have been replaced by the "
        "test-runner-command wording."
    )


def test_devon_rule_six_is_a_single_physical_line() -> None:
    rules_section = _section(
        _ADVERSARIAL_TEXT, _ADVERSARIAL_TEST_PROMPT, "Rules:", "Output format:"
    )
    rule_six_text = (
        "Run only the test runner command above, once per exploit; "
        "never a whole test directory."
    )
    lines = [line.strip() for line in rules_section.splitlines() if line.strip()]
    rule_six_line = next((line for line in lines if line.startswith("6.")), None)
    assert rule_six_line is not None, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected a Rule 6 line starting "
        "'6.' in the Rules list — not found."
    )
    expected = f"6. {rule_six_text}"
    assert rule_six_line == expected, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected Rule 6 as the single "
        f"physical line {expected!r} — found {rule_six_line!r} (it may "
        "have been hard-wrapped across two lines)."
    )


def test_devon_context_selection_includes_test_runner_row() -> None:
    needle = _norm(
        "| Test runner command (the task's test files only) | So Devon "
        "can verify exploits without a full-suite run per attempt |"
    )
    assert needle in _norm(_ADVERSARIAL_TEXT), (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected the Context Selection table "
        f"row {needle!r} — not found."
    )


def test_work_skill_names_rework_mode() -> None:
    sentence_one = _norm(
        "The full suite runs once at the end (why: "
        "`references/design-rationale.md` § narrow verification)."
    )
    sentence_two = _norm(
        "This holds in rework mode and for every subagent prompt (Tess, "
        "Devon, Ivan): each carries the same narrow-run sentence."
    )
    needle = f"{sentence_one} {sentence_two}"
    assert needle in _norm(_SKILL_TEXT), (
        f"{_SKILL_MD}: expected {needle!r} directly adjacent — not found. "
        "The rework-mode sentence has drifted away from directly "
        "following 'The full suite runs once at the end...'."
    )


def test_render_tess_prompt_contains_narrow_once(tmp_path: Path) -> None:
    out_path = tmp_path / "out.txt"
    exit_code = render_prompt.main(
        [
            str(_TESS_PROMPT),
            "--out",
            str(out_path),
            "--set",
            "TASK_SUBJECT=x",
            "--set",
            "TASK_DESCRIPTION=x",
            "--set",
            "TASK_ACCEPTANCE_CRITERIA=x",
            "--set",
            "SAMPLE_TEST_FILE=x",
            "--set",
            "PUBLIC_INTERFACES=x",
            "--set",
            "TEST_FRAMEWORK=x",
        ]
    )
    assert exit_code == 0, f"{_TESS_PROMPT}: render_prompt.py exited {exit_code}."

    norm_narrow = _norm(NARROW)
    rendered = _norm(out_path.read_text())
    count = rendered.count(norm_narrow)
    assert count == 1, (
        f"{_TESS_PROMPT}: expected the rendered output to contain the "
        f"NARROW sentence exactly once — found {count}."
    )
