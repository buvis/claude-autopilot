"""Wiring pins for the fast-track driver (SKILL.md, lane-dispatch.md).

The prose pins next door ask whether each section tells the reader to do the
right thing; these ask whether the sections are wired to each other and to the
scripts they cite: the test author's render inputs, the codex persona's doubt
sections, the four planner calls and the telemetry directory. The planner CLI
those calls run is pinned in test_fast_track_wiring_cli.py; the unit reader
both lean on is fast_track_wiring_testutil.py. Lives here because
test_fast_track_prose.py is at the file size limit.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest


def _sibling(name: str) -> ModuleType:
    """A helper module read from beside this file, never from an install path."""
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).with_name(f"{name}.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_wiring = _sibling("fast_track_wiring_testutil")
_testutil = _wiring.prose

_SKILL_MD = _testutil.SKILL_MD
_LANE_DISPATCH = _SKILL_MD.parent / "references" / "lane-dispatch.md"

_Passage = _testutil.Passage
_section = _testutil.section
_code_fragments = _testutil.code_fragments
_sentences_carrying = _testutil.sentences_carrying
_asserted = _testutil.asserted
_assert_live = _testutil.assert_live
_assert_unopposed = _testutil.assert_unopposed
_Unit = _wiring.Unit
_units = _wiring.units
_skill_units = _wiring.skill_units
_under = _wiring.under
_live = _wiring.live
_spoken = _wiring.spoken
_pasteable_lines = _wiring.pasteable_lines
_first_line = _wiring.first_line
_plan_call = _wiring.plan_call
_json_operand = _wiring.json_operand
_json_written_above = _wiring.json_written_above

_RENDER_FLAG = re.compile(
    r'--set(?:-(cmd|file))?\s+([A-Z_][A-Z0-9_]*)=("(?:[^"\\]|\\.)*"|<[^>]*>|\S+)',
)
_ITEM_LEDGER = "dev/local/autopilot/dispatch-metrics.jsonl"
_FINDING_KEYS = ("severity", "title", "file", "lane")
_CONSTRAINTS = "dev/local/tmp/fast-track-<item>-constraints.txt"
# The directory itself, not `dev/local/autopilot-cache`: the recorders walk up
# to the exact path, and `mkdir -p` of a sibling leaves them writing nothing.
_TELEMETRY_DIR = re.compile(r"dev/local/autopilot(?![\w-])")
_MAKES_TELEMETRY_DIR = re.compile(r"mkdir -p (?:\S+ )*dev/local/autopilot(?![\w-])")
# The Roster dispatches the kinds the planner printed and nothing else; a
# sentence that mentions the printed list is not one bound by it.
_BINDS_KINDS = re.compile(
    r"(?:only|exactly|each of|one\b.{0,30}?\bper)\s+(?:the|those|these)?\s*"
    r"(?:printed\s+)?kinds?\b"
    r"|\bkinds?\s+(?:it|the\s+planner|the\s+call|`?lanes`?)\s+print(?:s|ed)\b",
    re.IGNORECASE,
)
_UNBINDS_KINDS = re.compile(
    r"\bwhatever\b|\bregardless\b|\bevery lane\b|\bcost estimate\b|\bnot the plan\b",
    re.IGNORECASE,
)
_ABOUT_KINDS = re.compile(r"\bkinds?\b|\bplanner\b|\bplan_lanes\b|\blane plan\b")
_DISPATCHES = re.compile(r"\b(?:dispatch|open|send)\w*\b", re.IGNORECASE)
_CARRIES_COUNTS = re.compile(
    r"(?=.*\breport\b)(?=.*\b(?:print(?:s|ed)?|counts?|lines|output|numbers?)\b)",
    re.IGNORECASE | re.DOTALL,
)
_RECOUNTS = re.compile(
    r"\boverwrite|\breplace|your own tally|from memory|\bremember",
    re.IGNORECASE,
)
_JSON_ARRAY = re.compile(
    r"json\.dumps\b|(?=.*\bJSON\b)(?=.*\b(?:array|list)\b)",
    re.DOTALL,
)
_COLUMNS = re.compile(r"\bcolumns?\b|\bpipes\b", re.IGNORECASE)
_CASE_SPAN = re.compile(r"`(?:commit|branch)`")
# Bob's prompt is `agents/bob.md` plus Eve's two sections with the pack
# placeholder filled; a step naming fewer than all five composes another prompt,
# and one naming all five while keeping Eve's out composes the bare persona.
_BOB_WORDS = (r"\bbob\b", r"\beve\b", "Two lenses", "Rubric verdicts", "PACK_FINDINGS")
_BOB_STEP = tuple(re.compile(probe, re.IGNORECASE) for probe in _BOB_WORDS)
_EVES_PART = r"(?:Two lenses|Rubric verdicts|\beve\b)"
_DROPPED = r"\b(?:alone|stays? out|without|never|not)\b"
_BOB_WITHOUT_EVE = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (f"{_DROPPED}.*{_EVES_PART}", f"{_EVES_PART}.*{_DROPPED}")
)


def _writes_json_rows(text: str) -> bool:
    # A JSON array of objects keyed by the four names, said so: a markdown table
    # saved under a `.json` name, "columns" and pipes and all, exits the planner 2.
    quoted = all(f'"{key}"' in text for key in _FINDING_KEYS)
    spanned = all(f"`{key}`" in text for key in _FINDING_KEYS)
    keyed = quoted or (spanned and re.search(r"\bkeys?\b", text) is not None)
    return bool(_JSON_ARRAY.search(text)) and keyed and not _COLUMNS.search(text)


def _bound_case(units: list[_Unit], word: str, meaning: str) -> bool:
    # What a `commit` or `branch` span governs runs from the span to the next
    # such span or the sentence end, so one sentence swapping both binds neither.
    for unit in units:
        for sentence in _sentences_carrying(unit.text, f"`{word}`"):
            spans = list(_CASE_SPAN.finditer(sentence))
            for i, span in enumerate(spans):
                if span.group(0) != f"`{word}`":
                    continue
                end = spans[i + 1].start() if i + 1 < len(spans) else len(sentence)
                owned = sentence if len(spans) == 1 else sentence[span.start() : end]
                if re.search(meaning, owned):
                    return True
    return False


def _composes_bob(step: str) -> bool:
    both_headings = "Two lenses" in step and "Rubric verdicts" in step
    return bool(re.search(r"\bbob\.md\b", step)) and (
        bool(re.search(r"\beve\.md\b", step)) or both_headings
    )


@pytest.mark.parametrize("path", [_SKILL_MD, _LANE_DISPATCH], ids=["skill", "lanes"])
def test_the_test_author_is_rendered_from_item_goal_files_and_constraints(path) -> None:
    # An earlier draft passed the goal as subject and the empty `## Tests` as brief.
    text = path.read_text(encoding="utf-8")
    blocks = [u for u in _units(text) if u.is_code and "tess-prompt.md" in u.text]
    assert blocks, f"{path}: no fenced block renders `tess-prompt.md`."
    for block in blocks:
        flags = {
            key: (kind or "set", value.strip('"'))
            for kind, key, value in _RENDER_FLAG.findall(block.text)
        }
        subject = flags.get("TASK_SUBJECT")
        assert subject == ("set", "<item>"), (
            f"{path}: `TASK_SUBJECT` is {subject}, not the literal `<item>`."
        )
        kind, value = flags.get("TASK_DESCRIPTION", ("", ""))
        assert kind == "cmd" and value.startswith("cat "), (
            f"{path}: `TASK_DESCRIPTION` is `--set-{kind} {value}`, not a file read."
        )
        for staged in ("fast-track-<item>-goal.txt", "fast-track-<item>-files.txt"):
            assert staged in value, f"{path}: `TASK_DESCRIPTION` omits `{staged}`."
        criteria = flags.get("TASK_ACCEPTANCE_CRITERIA")
        assert criteria == ("file", _CONSTRAINTS), (
            f"{path}: `TASK_ACCEPTANCE_CRITERIA` is {criteria}, not `{_CONSTRAINTS}`."
        )


@pytest.mark.parametrize(
    ("path", "stem"),
    [(_SKILL_MD, r"\broster"), (_LANE_DISPATCH, r"\bbob\b|\bcodex\b")],
    ids=["skill-roster", "lanes-codex"],
)
def test_bobs_prompt_is_bob_plus_eves_two_sections_with_pack_findings_filled(
    path,
    stem,
) -> None:
    # review-work-completion's Bob: `agents/bob.md` plus Eve's `## Two lenses` and
    # `## Rubric verdicts` with `{PACK_FINDINGS}` filled, as a step, not a caption.
    units = [u for u in _units(path.read_text(encoding="utf-8")) if _under(u, stem)]
    assert units, f"{path}: nothing sits under a heading matching `{stem}`."
    live = [u for u in units if _live(u)]
    named = [u for u in live if all(p.search(_spoken(u)) for p in _BOB_STEP)]
    assert named, (
        f"{path}: no live block or paragraph under `{stem}` names Bob, Eve, `Two "
        "lenses`, `Rubric verdicts` and `PACK_FINDINGS` together, comments aside."
    )
    steps = [
        s
        for u in named
        for s in (_pasteable_lines(u) or _sentences_carrying(u.text, "Write tool"))
    ]
    assert any(_composes_bob(step) for step in steps), (
        f"{path}: no pasteable line or `Write tool` sentence under `{stem}` reads "
        "both `bob.md` and `eve.md` (or Eve's two headings); the composition is "
        f"described, never done: {steps[:2]}."
    )
    # testutil's assert_unopposed names SKILL.md in its complaint; this pin runs
    # over lane-dispatch.md too, so the reversal check is spelt out here.
    reversed_ = sorted(
        {
            sentence.strip()
            for u in live
            for pattern in _BOB_WITHOUT_EVE
            for sentence in _sentences_carrying(_spoken(u), pattern)
            if _asserted(sentence, pattern)
        },
    )
    assert not reversed_, (
        f"{path}: Bob's composition names Eve's sections and then keeps them out: "
        f"{reversed_[:3]}. The five words are there; the doubt lens is not."
    )


def test_the_lane_plan_is_printed_before_the_first_dispatch_and_read_after() -> None:
    # Between the card parse and the first row, with a later instruction that
    # dispatches the printed kinds and no other lane.
    call = _plan_call("lanes")
    for flag in ("--tests-present", "--workflow-available", "--carl-available"):
        assert flag in call.text, f"{_SKILL_MD}: `{call.text}` passes no `{flag}`."
    card = _first_line("scripts/card.py")
    first = _first_line("record_dispatch.py start")
    assert card.at < call.at < first.at, (
        f"{_SKILL_MD}: the `lanes` call (unit {call.at}) is not between the card "
        f"parse ({card.at}) and the first dispatch ({first.at})."
    )
    about = [
        _Passage(u.headings, u.text, False)
        for u in _skill_units()
        if not u.is_code and u.at > call.at and _ABOUT_KINDS.search(u.text)
    ]
    bound = _assert_live(
        [p for p in about if _BINDS_KINDS.search(p.text)],
        _BINDS_KINDS,
        missing="no sentence after the `lanes` call binds the roster to the kinds "
        "it printed (`exactly those kinds`, `only the printed kinds`).",
        cancelled="the printed lane kinds are named only to be set aside.",
    )
    binding = [s for p in bound for s in _sentences_carrying(p.text, _BINDS_KINDS)]
    assert any(_DISPATCHES.search(s) for s in binding), (
        f"{_SKILL_MD}: the printed kinds bind something other than a dispatch."
    )
    _assert_unopposed(
        about,
        _UNBINDS_KINDS,
        complaint="the printed kinds are read as an estimate the roster ignores:",
    )


def test_verify_targets_reads_the_table_as_a_findings_file_before_victor() -> None:
    # Over a findings file written from the table, before the victor render.
    call = _plan_call("verify-targets")
    table = _first_line("consolidate_findings.py")
    victor = _first_line("agents/victor.md")
    assert table.at < call.at < victor.at, (
        f"{_SKILL_MD}: the `verify-targets` call (unit {call.at}) is not between "
        f"the consolidated table ({table.at}) and the victor render ({victor.at})."
    )
    writers = _json_written_above(call)
    assert any(_writes_json_rows(u.text) for u in writers), (
        f"{_SKILL_MD}: the step writing `{_json_operand(call)}` never says it is a "
        f"JSON array of objects with the row keys {_FINDING_KEYS}, or calls them "
        f"columns: {[u.text for u in writers][:1]}. The planner exits 2 on a table."
    )


def test_the_exit_rule_branches_on_the_word_exit_action_prints() -> None:
    # It prints `commit` or `branch` over what survived verification; the Exit
    # section carries both as its cases, each bound to its own outcome.
    call = _plan_call("exit-action")
    verify = _plan_call("verify-targets")
    victor = _first_line("agents/victor.md")
    park = _first_line("git branch fast-track/<item> HEAD")
    assert verify.at < call.at < park.at, (
        f"{_SKILL_MD}: the `exit-action` call (unit {call.at}) is not between "
        f"`verify-targets` ({verify.at}) and the parking `git branch` ({park.at})."
    )
    assert _json_operand(call) != _json_operand(verify), (
        f"{_SKILL_MD}: `exit-action` reads `{_json_operand(call)}`, the raised set "
        "`verify-targets` read; a refuted CRITICAL would still park the item."
    )
    writers = _json_written_above(call)
    survivors = re.compile(r"surviv|confirmed")
    assert any(u.at > victor.at and survivors.search(u.text) for u in writers), (
        f"{_SKILL_MD}: `{_json_operand(call)}` is written before the victor render "
        f"(unit {victor.at}) or without naming the surviving or confirmed set, so it "
        "cannot hold what verification left standing."
    )
    exit_prose = [
        u for u in _skill_units() if not u.is_code and _under(u, r"\bexit") and _live(u)
    ]
    words = {
        fragment
        for u in exit_prose
        for fragment in _code_fragments(_Passage(u.headings, u.text, False))
    }
    assert {"commit", "branch"} <= words, (
        f"{_SKILL_MD}: the Exit section's code spans are {sorted(words)}; without "
        "both `commit` and `branch` it does not branch on the printed word."
    )
    assert _bound_case(exit_prose, "branch", r"\bpark|fast-track/<item>"), (
        f"{_SKILL_MD}: no Exit sentence binds `branch` to parking the commits "
        "under `fast-track/<item>`."
    )
    assert _bound_case(exit_prose, "commit", r"working branch|next card"), (
        f"{_SKILL_MD}: no Exit sentence binds `commit` to the commits staying on "
        "the working branch and the lane taking the next card."
    )


def test_the_report_counts_the_items_dispatches_out_of_the_ledger_by_kind() -> None:
    # Cost is read out of the ledger rows, after the exit rule, and the report
    # carries the counts as printed, never a tally from memory.
    call = _plan_call("count")
    exit_rule = _plan_call("exit-action")
    assert _under(call, r"\bledger|\breport") and call.at > exit_rule.at, (
        f"{_SKILL_MD}: the `count` call sits under {call.headings}, not in Ledgers "
        "or Report after the exit rule, and misses the rows the item has yet to open."
    )
    operands = rf"count\s+{re.escape(_ITEM_LEDGER)}\s+<item>(?:\s|$)"
    assert re.search(operands, call.text), (
        f"{_SKILL_MD}: `{call.text}` does not count `{_ITEM_LEDGER}` for `<item>`."
    )
    after = [
        _Passage(u.headings, u.text, False)
        for u in _skill_units()
        if not u.is_code and u.at > call.at
    ]
    _assert_live(
        [p for p in after if _CARRIES_COUNTS.search(p.text)],
        _CARRIES_COUNTS,
        missing="no sentence after the `count` call puts the counts it printed "
        "into the report.",
        cancelled="the printed counts are named only to be set aside.",
    )
    _assert_unopposed(
        after,
        _RECOUNTS,
        complaint="the printed counts are retallied from memory before the report:",
    )


def test_preconditions_create_the_telemetry_directory_before_any_dispatch() -> None:
    # Both recorders exit 0 and write nothing when `dev/local/autopilot/` is absent.
    live = _assert_live(
        [p for p in _section("Preconditions") if _TELEMETRY_DIR.search(p.text)],
        _TELEMETRY_DIR,
        missing="the preconditions never name `dev/local/autopilot` itself.",
        cancelled="the telemetry directory is named only to be waved off.",
    )
    creates = re.compile(r"\bcreat(?:e|es|ed|ing)\b")
    made = [
        p
        for p in live
        if any(_MAKES_TELEMETRY_DIR.search(f) for f in _code_fragments(p))
        or any(creates.search(s) for s in _sentences_carrying(p.text, _TELEMETRY_DIR))
    ]
    assert made, (
        f"{_SKILL_MD}: `dev/local/autopilot` is named but nothing creates that "
        f"exact path: {[p.text for p in live][:2]}. Checking for it, or making a "
        "sibling of it, is not making it."
    )
