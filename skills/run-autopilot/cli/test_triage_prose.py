"""Prose pins for the three `autopilot mint-stubs` call sites of PRD 00195:
the loop-mode cap-out bullet in `references/phase-review.md` (after a
successful `cap_critical` stall), Phase 9 step 6 in `references/phase-done.md`
(after the deferred migration) and the loop-mode batch end there (before
`phase-done --outcome drained`, with `{s} stubs` in the notification), plus
the `batch.minted_stubs` row in `references/state-schema.md`.

Same pattern as test_custody_prose.py: slice the section that must carry
the instruction, assert short reword-resistant substrings in order, and
sweep each slice for the negation that would invert it. The custody
contracts the mint sits behind (stall exit table, review roster) are pinned
unchanged here so the mint cannot silently reorder them.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.custody_prose_testutil import (
    _PHASE_REVIEW,
    _RECOVERY,
    _RECOVERY_TEXT,
    _REVIEW_TEXT,
    _ROSTER_SENTENCE,
    _SKILL_DIR,
    _assert_absent,
    _assert_in_order,
    _assert_present,
    _section,
)

_REFERENCES = _SKILL_DIR / "references"
_PHASE_DONE = _REFERENCES / "phase-done.md"
_DONE_TEXT = _PHASE_DONE.read_text()
_STATE_SCHEMA = _REFERENCES / "state-schema.md"
_SCHEMA_TEXT = _STATE_SCHEMA.read_text()
_REPO_ROOT = _SKILL_DIR.parent.parent
_RELEASE_CHECKS = _REPO_ROOT / "dev" / "bin" / "release-checks"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"

_MINT = "autopilot mint-stubs --batch"
_CAP_OUT_LEAD = "- **Loop mode (`$_AUTOPILOT_LOOP` set) — cap-out defers, never pauses.**"
_CAP_OUT_END = "- **Interactive — perform the Cap-pause behavior**"
_STEP_6_LEAD = "6. Run `autopilot defer --prd <filename> --batch <batch_id> --json '<record>'`"
_STEP_6A_LEAD = "6a. **Render this PRD's audit file:**"
_BATCH_END_LEAD = "- **Loop mode (`$_AUTOPILOT_LOOP` set) — non-interactive batch end.**"
_BATCH_END_END = "- **Outside the loop — interactive batch end.**"
_NOTIFY = "Batch done: {n} done, {m} stalled, {k} deferred, {s} stubs."

# A paraphrase that keeps the verb but tells the operator not to run it.
_MINT_NEGATIONS = (
    "Do NOT run `autopilot mint-stubs`",
    "do not run `autopilot mint-stubs`",
    "never run `autopilot mint-stubs`",
    "mint-stubs is retired",
    "skip the mint",
)


def _cap_out() -> str:
    return _section(_REVIEW_TEXT, _PHASE_REVIEW, _CAP_OUT_LEAD, _CAP_OUT_END)


def _step_6() -> str:
    return _section(_DONE_TEXT, _PHASE_DONE, _STEP_6_LEAD, _STEP_6A_LEAD)


def _batch_end() -> str:
    return _section(_DONE_TEXT, _PHASE_DONE, _BATCH_END_LEAD, _BATCH_END_END)


def test_cap_out_mints_after_a_successful_stall_and_never_after_a_failed_one() -> None:
    cap_out = _cap_out()
    where = "the loop-mode cap-out bullet"
    _assert_in_order(
        cap_out,
        _PHASE_REVIEW,
        where,
        ("stall the PRD", 'site: "cap_critical"', "exits 0", f"`{_MINT} <state.batch.id>`"),
    )
    _assert_present(
        cap_out,
        _PHASE_REVIEW,
        where,
        (
            "custody write and its deferral migration both succeeded",
            "exited non-zero mints nothing",
            "state.batch.minted_stubs",
            "idempotent",
            "PRD 00195",
        ),
    )
    _assert_absent(cap_out, _PHASE_REVIEW, where, _MINT_NEGATIONS)
    assert cap_out.count(_MINT) == 1, (
        f"{_PHASE_REVIEW}: expected exactly one mint call in {where} - found "
        f"{cap_out.count(_MINT)}."
    )


def test_cap_out_mint_leaves_the_stall_order_and_the_review_roster_unchanged() -> None:
    cap_out = _cap_out()
    _assert_present(
        cap_out,
        _PHASE_REVIEW,
        "the loop-mode cap-out bullet",
        ("changes nothing about the stall's own retry/reset order or the review roster",),
    )
    # The stall procedure itself is untouched: the mint sits after its exit
    # table in the caller, never inside it.
    assert "mint-stubs" not in _RECOVERY_TEXT, (
        f"{_RECOVERY}: the stall procedure must not carry the mint call - it "
        "runs in the caller after the stall's exit 0 row."
    )
    assert _REVIEW_TEXT.count(_ROSTER_SENTENCE) == 1, (
        f"{_PHASE_REVIEW}: the review-lens roster sentence is no longer "
        "byte-identical; the mint changes no lens."
    )


def test_phase_9_step_6_mints_after_the_migration_and_never_after_a_failed_defer() -> None:
    step = _step_6()
    where = "Phase 9 step 6"
    _assert_in_order(
        step,
        _PHASE_DONE,
        where,
        (
            "migration path for cap-out records",
            "Mint hold stubs (PRD 00195)",
            "exited 0",
            f"`{_MINT} <batch_id>`",
        ),
    )
    _assert_present(
        step,
        _PHASE_DONE,
        where,
        (
            "state.batch.minted_stubs",
            "exited 9 mints nothing",
            "idempotent",
            "hold/<NNNNN>-triage-<slug>-v1.md",
            "autopilot never drains `hold/`",
            "neither triages them nor changes the review roster",
        ),
    )
    _assert_absent(step, _PHASE_DONE, where, _MINT_NEGATIONS)
    assert _MINT not in _DONE_TEXT[: _DONE_TEXT.index(_STEP_6_LEAD)], (
        f"{_PHASE_DONE}: a mint call appears before step 6 - it must follow the migration."
    )


def test_loop_batch_end_mints_before_drained_and_reports_the_batch_wide_count() -> None:
    end = _batch_end()
    where = "the loop-mode batch-end bullet"
    _assert_in_order(
        end,
        _PHASE_DONE,
        where,
        (
            "already written",
            f"`{_MINT} <batch_id>`",
            "autopilot phase-done --outcome drained",
            "notify.py",
            _NOTIFY,
            "len(state.batch.minted_stubs)",
            "across every mint call",
            "0 when the field is absent",
        ),
    )
    _assert_present(end, _PHASE_DONE, where, ("when m, k and s are all zero",))
    _assert_absent(end, _PHASE_DONE, where, _MINT_NEGATIONS)
    assert "{k} deferred. Run" not in _DONE_TEXT, (
        f"{_PHASE_DONE}: the old notification without `{{s}} stubs` is still present."
    )


def test_notification_count_is_the_accumulated_field_not_the_final_calls_result() -> None:
    end = _batch_end()
    # "usually-zero" names the final call; "12" is the fixture's earlier count
    # that must still be reported. Both must sit in the {s} definition.
    pattern = r"`\{s\}` is `len\(state\.batch\.minted_stubs\)`[^\n]{0,200}usually-zero"
    assert re.search(pattern, end), (
        f"{_PHASE_DONE}: expected `{{s}}` defined as len(state.batch.minted_stubs) "
        "with the final call's usually-zero result named beside it - not found."
    )
    definition = end.split("`{s}` is")[1].split(";")[0]
    assert "12" in definition, (
        f"{_PHASE_DONE}: expected the `{{s}}` definition to name an earlier count "
        "(12) the final zero-result call must not erase."
    )


def test_state_schema_documents_batch_minted_stubs_and_its_three_sites() -> None:
    lead = "| `batch.minted_stubs` |"
    rows = [line for line in _SCHEMA_TEXT.splitlines() if line.startswith(lead)]
    assert len(rows) == 1, (
        f"{_STATE_SCHEMA}: expected exactly one `batch.minted_stubs` field row - found {len(rows)}."
    )
    row = rows[0]
    where = "the `batch.minted_stubs` field row"
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert cells[1] == "string[]?", (
        f"{_STATE_SCHEMA}: expected {where} typed `string[]?` - got {cells[1]!r}."
    )
    _assert_in_order(
        row,
        _STATE_SCHEMA,
        where,
        (
            "_run_mint_stubs",
            "three sites",
            "cap_critical",
            "Phase 9 step 6",
            "loop-mode batch end",
            "len(batch.minted_stubs)",
        ),
    )
    _assert_present(
        row,
        _STATE_SCHEMA,
        where,
        ("deduplicated", "per-PRD reset preserves it", "absence as `[]`", "never re-mint"),
    )
    _assert_absent(row, _STATE_SCHEMA, where, ("nothing writes it", "never written", "not read"))
    idx = _SCHEMA_TEXT.index(lead)
    assert _SCHEMA_TEXT.rfind("| `batch.critical_on_master` |", 0, idx) != -1, (
        f"{_STATE_SCHEMA}: expected {where} after the `batch.critical_on_master` row."
    )


def test_release_checks_l4_block_runs_both_triage_test_files() -> None:
    text = _RELEASE_CHECKS.read_text()
    assert text.count('echo "[checks] l4"') == 1, (
        f"{_RELEASE_CHECKS}: expected exactly one `[checks] l4` block."
    )
    block = text[text.index('echo "[checks] l4"') :]
    block = block.split("\necho ", 1)[0]
    _assert_present(
        block,
        _RELEASE_CHECKS,
        "the `[checks] l4` block",
        (
            "uv run --no-project --with pytest python -m pytest -q",
            "skills/run-autopilot/cli/test_triage.py",
            "skills/run-autopilot/cli/test_triage_prose.py",
        ),
    )


def test_changelog_unreleased_added_carries_the_stub_minting_entry() -> None:
    text = _CHANGELOG.read_text()
    unreleased = _section(text, _CHANGELOG, "## [Unreleased]", "\n## [")
    added = _section(unreleased, _CHANGELOG, "### Added", "### Changed")
    _assert_present(
        added,
        _CHANGELOG,
        "the [Unreleased] Added section",
        (
            "- **run-autopilot**: `autopilot mint-stubs --batch <id>` mints one "
            "`dev/local/prds/hold/<NNNNN>-triage-<slug>-v1.md` triage stub",
            "`{s} stubs`",
            "never drains or promotes",
        ),
    )
    # Preserves its neighbours: the earlier Added entries are still there.
    _assert_present(
        added,
        _CHANGELOG,
        "the [Unreleased] Added section",
        ("- **design-solution**: `--rework <review-file>`", "- **hooks**: deny a Bash `git push`"),
    )
