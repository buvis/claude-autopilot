#!/usr/bin/env python3
"""Tests for cli/lane.py - the effort-lane classifier (PRD 00204).

The seven ordered rules are the contract, so every `reason` slug gets its
own case; the path extractor is pinned on the frozen backlog under
`cli/golden/lanes/`, whose 15 PRDs are the classifier's regression set.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cli import frontmatter, lane

CLI_DIR = Path(__file__).resolve().parent
LANES = CLI_DIR / "golden" / "lanes"


def _frozen(number: str) -> str:
    (path,) = LANES.glob(f"{number}-*.md")
    return path.read_text(encoding="utf-8")


def _prd(
    *tree: str,
    design: str | None = "skip",
    lane_key: str | None = None,
    tasks: tuple[str, ...] = ("- [ ] Do the thing - Acceptance: it is done",),
    problem: str = "One line of problem.",
) -> str:
    """A minimal standard-template PRD with the given tree entries."""
    head = ["---", "catchup: skip"]
    if design is not None:
        head.append(f"design: {design}")
    if lane_key is not None:
        head.append(f"lane: {lane_key}")
    head.append("---")
    body = [
        "",
        "# A PRD",
        "",
        "### Problem Statement",
        "",
        problem,
        "",
        "### Repository Structure",
        "",
        "```",
        *tree,
        "```",
        "",
        "## Implementation Phases",
        "",
        "### Phase 0: Foundation",
        "",
        *tasks,
        "",
    ]
    return "\n".join(head + body)


def _declared(text: str) -> dict[str, str]:
    return frontmatter.declared(text)


# ── named paths ──────────────────────────────────────────────────────────────


def test_named_paths_rebuilds_tree_glyphs_and_splits_commas() -> None:
    paths = lane.named_paths(_frozen("00201"))
    assert len(paths) == 10
    assert "skills/run-autopilot/references/phase-review.md" in paths
    assert "skills/run-autopilot/references/phase-build.md" in paths
    assert "skills/run-autopilot/cli/brief.py" in paths
    assert "skills/run-autopilot/SKILL.md" in paths


def test_named_paths_reads_location_spans_and_skips_symbols() -> None:
    paths = lane.named_paths(_frozen("00189"))
    assert len(paths) == 11
    assert not any("_add_check_plan" in path for path in paths)
    assert "skills/run-autopilot/cli/__main__.py" in paths
    assert "dev/bin/release-checks" in paths
    assert "CHANGELOG.md" in paths


def test_line_suffix_is_stripped_before_kind() -> None:
    text = "- **Location**: `cli/__main__.py:756-782`, `cli/gate.py:64`\n"
    assert lane.named_paths(text) == ("cli/__main__.py", "cli/gate.py")
    assert lane.is_production_path("cli/__main__.py")


def test_named_paths_are_deduplicated_in_first_appearance_order() -> None:
    text = _prd("a/", "├── x.py", "└── y.md") + "\n- **Location**: `a/y.md`, `a/x.py`\n"
    assert lane.named_paths(text) == ("a/x.py", "a/y.md")


def test_named_paths_is_empty_without_a_tree_or_a_location_line() -> None:
    assert lane.named_paths("# Prose\n\nSee `cli/loop.py` in passing.\n") == ()


# ── path kinds ───────────────────────────────────────────────────────────────


def test_hook_basename_forms() -> None:
    assert lane.is_hook_path("hooks/x.py")
    assert lane.is_hook_path("hooks/hooks.json")
    assert lane.is_hook_path("hooks.json")
    assert lane.is_hook_path("skills/run-autopilot/scripts/foo_hook.py")
    assert not lane.is_hook_path("hookshelf/x.py")
    assert not lane.is_hook_path("skills/x/hooks")


def test_predicates_are_loaded_by_path_not_copied() -> None:
    assert lane.is_test_path.__module__ == "work_routing"
    assert lane.is_packaging_path.__module__ == "classify_tier"
    source = (CLI_DIR / "lane.py").read_text(encoding="utf-8")
    assert "_TEST_DIR_SEGMENTS" not in source
    assert "_PACKAGING_BASENAMES" not in source


def test_production_path_excludes_tests_docs_and_packaging() -> None:
    assert lane.is_production_path("cli/loop.py")
    assert lane.is_production_path("dev/bin/release-checks")
    assert not lane.is_production_path("cli/test_loop.py")
    assert not lane.is_production_path("references/phase-build.md")
    assert not lane.is_production_path("notes.txt")
    assert not lane.is_production_path("README.rst")
    assert not lane.is_production_path("pyproject.toml")
    assert not lane.is_production_path(".claude-plugin/plugin.json")


def test_security_regex_fires_on_a_path_not_on_prose() -> None:
    assert lane.securityish("auth/login.py")
    assert lane.securityish("cli/sessionStore.py")
    assert not lane.securityish("cli/brief.py")
    text = _prd(
        "skills/run-autopilot/",
        "└── cli/",
        "    └── brief.py",
    ).replace("# A PRD", "# Session brief")
    assert lane.classify(text, _declared(text)).reason != "security_path"


# ── classify: the seven rules ────────────────────────────────────────────────


def test_override_wins() -> None:
    text = _prd("hooks/", "└── guard.py", lane_key="solo")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("solo", "override")


def test_invalid_override_is_ignored_by_classify() -> None:
    text = _prd("docs/", "└── guide.md", lane_key="fast")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("solo", "no_production_code")


def test_hook_rule() -> None:
    text = _prd("hooks/", "└── guard.py")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("full", "hook")


def test_security_path_rule() -> None:
    text = _prd("auth/", "└── login.py")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("full", "security_path")


def test_unparsed_rule() -> None:
    text = "---\ndesign: skip\n---\n\n# Prose only\n\nNo paths here.\n"
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("full", "unparsed")
    assert verdict.paths == ()


def test_design_rule() -> None:
    text = _prd("cli/", "└── loop.py", design="run")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("full", "design")


def test_design_absent_counts_as_run() -> None:
    text = _prd("cli/", "└── loop.py", design=None)
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("full", "design")
    invalid = _prd("cli/", "└── loop.py", design="maybe")
    assert lane.classify(invalid, _declared(invalid)).reason == "design"


def test_no_production_code_rule() -> None:
    text = _prd("docs/", "├── guide.md", "└── test_guide.py", "CHANGELOG.md")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason) == ("solo", "no_production_code")
    assert verdict.prod_paths == ()


def test_card_sized_rule() -> None:
    text = _prd("cli/", "├── loop.py", "└── test_loop.py")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason, verdict.cards) == ("fast-track", "card_sized", 1)
    assert verdict.prod_paths == ("cli/loop.py",)


def test_uncardable_rule() -> None:
    text = _prd("cli/", "├── loop.py", "└── agents/*.md")
    verdict = lane.classify(text, _declared(text))
    assert (verdict.lane, verdict.reason, verdict.cards) == ("full", "uncardable", 0)


def test_default_model_never_decides_the_lane() -> None:
    text = _prd("cli/", "└── loop.py").replace("catchup: skip", "default_model: opus")
    assert lane.classify(text, _declared(text)).lane == "fast-track"


# ── plan_cards ───────────────────────────────────────────────────────────────


def test_plan_cards_joins_wrapped_task_items_before_counting() -> None:
    wrapped = (
        "- [ ] Widen the gate to cover the new field and pin it",
        "  with a prose test that reads the section by heading",
        "  (depends on: nothing) - Acceptance: the pin is green",
    )
    text = _prd("cli/", "└── loop.py", tasks=wrapped)
    (plan,) = lane.plan_cards(text)
    assert plan.task_items == (" ".join(line.strip() for line in wrapped),)
    assert len(plan.goal_lines) == 2  # one problem line, one joined item


def test_plan_cards_ignores_dependency_graph_phase_suffixes() -> None:
    tree = ["cli/"] + [f"├── m{i}.py" for i in range(13)]
    text = _prd(*tree) + "\n".join(
        [
            "",
            "## Dependency Graph",
            "",
            "### Foundation Layer (Phase 0)",
            "- [ ] not a task",
            "### Core Layer (Phase 1)",
            "- [ ] not a task either",
            "",
        ]
    )
    # 13 paths never fit one card and the PRD has ONE real phase, so the
    # two layer headings must not be mistaken for a two-phase split.
    assert lane.plan_cards(text) == []


def test_plan_cards_gives_unnamed_files_to_every_card() -> None:
    plans = lane.plan_cards(_frozen("00188"))
    assert [plan.phase for plan in plans] == ["Phase 0: Foundation", "Phase 1: Core"]
    for plan in plans:
        assert "skills/run-autopilot/cli/render_report.py" in plan.files
        assert len(plan.files) <= 12
        assert len(plan.goal_lines) <= 40
    assert "skills/run-autopilot/cli/convergence.py" in plans[0].files
    assert "skills/run-autopilot/cli/convergence.py" not in plans[1].files


def test_plan_cards_refuses_a_glob_path() -> None:
    text = _prd("agents/", "└── *.md", "CHANGELOG.md")
    assert "agents/*.md" in lane.named_paths(text)
    assert lane.plan_cards(text) == []


def test_plan_cards_refuses_three_phases_over_twelve_paths() -> None:
    tree = ["cli/"] + [f"├── m{i}.py" for i in range(13)]
    phases = []
    for n in range(3):
        phases += [f"### Phase {n}: Step {n}", "", f"- [ ] Edit m{n}.py", ""]
    text = _prd(*tree).replace("### Phase 0: Foundation\n", "\n".join(phases))
    assert lane.plan_cards(text) == []


def test_plan_cards_whole_prd_goal_is_problem_then_items() -> None:
    text = _prd("cli/", "└── loop.py", problem="Line one.\nLine two.")
    (plan,) = lane.plan_cards(text)
    assert plan.phase is None
    assert plan.files == ("cli/loop.py",)
    assert plan.goal_lines == ("Line one.", "Line two.", *plan.task_items)


# ── effective ────────────────────────────────────────────────────────────────


def test_effective_forces_full_when_off_or_unreleased(monkeypatch) -> None:
    assert lane.effective("full", "off") == "full"
    assert lane.effective("solo", "off") == "full"
    monkeypatch.setattr(lane, "RELEASED_LANES", frozenset({"full"}))
    assert lane.effective("solo", None) == "full"
    assert lane.effective("fast-track", "") == "full"
    assert lane.effective("full", None) == "full"
    monkeypatch.setattr(lane, "RELEASED_LANES", frozenset({"full", "solo"}))
    assert lane.effective("solo", None) == "solo"


def test_security_regex_is_the_fanout_regex() -> None:
    # The JS source, ported verbatim: the same alternation, plural suffix and
    # open-ended auth stems.
    pattern = lane.SECURITY_RE.pattern
    assert pattern.startswith("(?<![a-z0-9])(?:(?:exec|eval|auth|token|password")
    assert "authenticat|authoriz|permission|login|forbidden|acl)" in pattern
    assert re.search(lane.SECURITY_RE, "secrets.yml")
    assert not re.search(lane.SECURITY_RE, "execute")
    assert not re.search(lane.SECURITY_RE, "hashmap")


# ── frontmatter.declared ─────────────────────────────────────────────────────


def test_declared_returns_pairs_or_empty() -> None:
    text = "---\ncatchup: skip\nlane: solo\ntitle: a: b\n---\n\n# PRD\n"
    assert frontmatter.declared(text) == {
        "catchup": "skip",
        "lane": "solo",
        "title": "a: b",
    }
    assert frontmatter.declared("# no block\n") == {}
    assert frontmatter.declared("---\ncatchup: skip\n# never closed\n") == {}
    late = "---\n" + "k: v\n" * 30 + "---\n"
    assert frontmatter.declared(late) == {}, "the _HEAD_LINES window applies"


# ── the frozen backlog ───────────────────────────────────────────────────────

# `cards` is `len(plan_cards(text))` on every row, as the Verdict contract
# says, so a full- or solo-routed PRD that would also fit a card reports it
# (the PRD's own table wrote 0 there; the rule wins, the row was corrected).
_AGREED = {
    "00187": ("full", "hook", 0),
    "00188": ("fast-track", "card_sized", 2),
    "00189": ("fast-track", "card_sized", 1),
    "00190": ("fast-track", "card_sized", 1),
    "00191": ("full", "hook", 1),
    "00192": ("full", "design", 0),
    "00194": ("full", "design", 1),
    "00195": ("full", "design", 1),
    "00196": ("full", "hook", 1),
    "00197": ("solo", "no_production_code", 1),
    "00198": ("full", "uncardable", 0),
    "00199": ("full", "design", 1),
    "00200": ("full", "hook", 1),
    "00201": ("fast-track", "card_sized", 1),
    "00202": ("full", "hook", 1),
}


@pytest.mark.parametrize("number", sorted(_AGREED))
def test_reviewed_backlog_classifies_as_agreed(number: str) -> None:
    text = _frozen(number)
    verdict = lane.classify(text, frontmatter.declared(text))
    assert (verdict.lane, verdict.reason, verdict.cards) == _AGREED[number]


def test_reviewed_backlog_is_fifteen_prds() -> None:
    assert len(list(LANES.glob("*.md"))) == 15 == len(_AGREED)
