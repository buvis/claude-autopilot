#!/usr/bin/env python3
"""Tests for cli/triage.py and the `autopilot mint-stubs` verb (PRD 00195).

The pure helpers (qualification, ownership, folding, template, allocation)
run in-process against a synthetic `<root>/dev/local/{autopilot,prds,
discovery}` tree; the frozen ddb slice in `golden/triage-ddb-202607161128.json`
pins the 12-then-zero contract; the CLI section runs `cli/__main__.py` as a
subprocess and binds stdout, exit 2 / 9, path resolution and the
`batch.minted_stubs` bookkeeping.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import triage

CLI_DIR = Path(__file__).resolve().parent
CLI_MAIN = CLI_DIR / "__main__.py"
GOLDEN = CLI_DIR / "golden" / "triage-ddb-202607161128.json"
BATCH = "202607161128"
LIFECYCLE = ("backlog", "wip", "hold", "done")


def _tree(root: Path) -> tuple[Path, Path]:
    autopilot = root / "dev" / "local" / "autopilot"
    (autopilot / "deferred").mkdir(parents=True)
    prds = root / "dev" / "local" / "prds"
    for lifecycle in LIFECYCLE:
        (prds / lifecycle).mkdir(parents=True)
    return autopilot, prds


def _ledger(autopilot: Path, items: list, batch: str = BATCH) -> Path:
    path = autopilot / "deferred" / f"{batch}-deferred.json"
    path.write_text(json.dumps({"batch_id": batch, "items": items}), encoding="utf-8")
    return path


def _row(**overrides) -> dict:
    base = {
        "prd": "00167-example-v1.md",
        "cycle": 2,
        "type": "cap-overflow",
        "topic": "example-topic",
        "severity": "high",
        "consensus": "1/5",
        "issue": "Something severe is wrong.",
        "detail": "Raised by Bob; verified by the orchestrator.",
    }
    base.update(overrides)
    return base


def _stall_row() -> dict:
    return {
        "type": "stall",
        "site": "cap_critical",
        "detail": "Cycle 2 hit rework_cap 2 with an unresolved CRITICAL.",
        "op_id": "c389f89aed18",
        "prd": "00168-example-v1.md",
    }


def _hold_files(prds: Path) -> list[Path]:
    return sorted((prds / "hold").glob("*.md"))


@pytest.fixture
def tree(tmp_path: Path) -> tuple[Path, Path]:
    return _tree(tmp_path)


# --- qualification ---------------------------------------------------------


def test_mints_unowned_critical_high_and_cap_critical_stall(tree) -> None:
    autopilot, prds = tree
    _ledger(
        autopilot,
        [
            _row(severity="critical", issue="A critical one."),
            _row(severity="high", issue="A high one."),
            _stall_row(),
        ],
    )
    result = triage.mint_stubs(autopilot, prds, BATCH)
    assert len(result["minted"]) == 3 and result["skipped"] == 0
    assert [p.name for p in _hold_files(prds)] == result["minted"]


def test_severity_is_matched_case_insensitively(tree) -> None:
    autopilot, prds = tree
    _ledger(autopilot, [_row(severity="HIGH", issue="a"), _row(severity="Critical", issue="b")])
    assert len(triage.mint_stubs(autopilot, prds, BATCH)["minted"]) == 2


@pytest.mark.parametrize(
    "row",
    [
        _row(severity="medium"),
        _row(severity="low"),
        _row(severity="high", resolved={"at": "2026-09-01"}),
        _row(severity="high", status="resolved"),
        _row(severity=None),
        {k: v for k, v in _row().items() if k != "severity"},
        _row(severity="high", issue="", detail="   "),
        _row(severity="high", issue=None, detail=None),
        {"type": "stall", "site": "wrapper_died", "detail": "died", "prd": "x.md"},
    ],
    ids=[
        "medium",
        "low",
        "resolved-block",
        "resolved-status",
        "severity-null",
        "severity-absent",
        "blank-text",
        "no-text",
        "other-stall-site",
    ],
)
def test_non_qualifying_rows_create_no_file_and_count_as_skipped(tree, row) -> None:
    autopilot, prds = tree
    _ledger(autopilot, [row])
    assert triage.mint_stubs(autopilot, prds, BATCH) == {"minted": [], "skipped": 1}
    assert _hold_files(prds) == []


def test_non_dict_items_are_skipped_not_crashed(tree) -> None:
    autopilot, prds = tree
    _ledger(autopilot, ["not a row", 7, _row()])
    assert triage.mint_stubs(autopilot, prds, BATCH)["skipped"] == 2


# --- ownership -------------------------------------------------------------


@pytest.mark.parametrize("lifecycle", LIFECYCLE)
def test_key_in_first_20_lines_of_any_lifecycle_dir_claims_ownership(tree, lifecycle) -> None:
    autopilot, prds = tree
    row = _row()
    key = triage.ledger_key(row["issue"])
    owner = prds / lifecycle / "00042-hand-written-v1.md"
    owner.write_text(f"# Hand-written PRD\n\nOwns ledger_key {key} deliberately.\n")
    _ledger(autopilot, [row])
    assert triage.mint_stubs(autopilot, prds, BATCH) == {"minted": [], "skipped": 1}
    assert [p for p in _hold_files(prds) if p != owner] == []


def test_key_past_line_20_does_not_claim(tree) -> None:
    autopilot, prds = tree
    row = _row()
    key = triage.ledger_key(row["issue"])
    (prds / "backlog" / "00042-deep-v1.md").write_text("\n" * 25 + f"ledger_key: {key}\n")
    _ledger(autopilot, [row])
    assert len(triage.mint_stubs(autopilot, prds, BATCH)["minted"]) == 1


def test_key_is_computed_from_issue_else_detail_over_normalized_text() -> None:
    assert triage.ledger_key("  Hello   WORLD ") == triage.ledger_key("hello world")
    assert re.fullmatch(r"[0-9a-f]{12}", triage.ledger_key("x"))
    assert triage.finding_text({"issue": "", "detail": "d"}) == "d"
    assert triage.finding_text({"issue": "i", "detail": "d"}) == "i"


def test_identical_normalized_text_folds_within_one_run_and_across_reruns(tree) -> None:
    autopilot, prds = tree
    text = "The malformed-node fallback creates a second rendering"
    _ledger(
        autopilot,
        [
            _row(type="cap-overflow", issue=text),
            _row(type="deferred_decision", topic=None, issue=f"  {text.upper()}  "),
        ],
    )
    first = triage.mint_stubs(autopilot, prds, BATCH)
    assert len(first["minted"]) == 1 and first["skipped"] == 1
    assert triage.mint_stubs(autopilot, prds, BATCH) == {"minted": [], "skipped": 2}
    assert len(_hold_files(prds)) == 1


def test_discovery_reserves_numbers_but_owns_no_keys(tree) -> None:
    autopilot, prds = tree
    row = _row()
    discovery = prds.parent / "discovery"
    discovery.mkdir()
    (discovery / "00050-discovery.md").write_text(f"ledger_key: {triage.ledger_key(row['issue'])}\n")
    _ledger(autopilot, [row])
    minted = triage.mint_stubs(autopilot, prds, BATCH)["minted"]
    assert minted == ["00051-triage-example-topic-v1.md"]


# --- template --------------------------------------------------------------


def _stub_text(tree, row: dict) -> str:
    autopilot, prds = tree
    _ledger(autopilot, [row])
    minted = triage.mint_stubs(autopilot, prds, BATCH)["minted"]
    return (prds / "hold" / minted[0]).read_text(encoding="utf-8")


def test_stub_freezes_the_minimal_heading_order(tree) -> None:
    text = _stub_text(tree, _row())
    headings = re.findall(r"(?m)^#{1,3} .*$", text)
    assert headings == [
        "# Triage: example-topic",
        "## Problem",
        "## Solution",
        "## Requirements",
        "### Must have",
        "### Nice to have",
        "## Implementation",
        "### Module: triage",
        "### Dependencies",
        "## Tasks",
        "### Phase 0: Foundation",
        "### Phase 1: Core",
        "## Success Criteria",
    ]


def test_stub_frontmatter_carries_the_ledger_provenance(tree) -> None:
    row = _row()
    text = _stub_text(tree, row)
    head = text.split("---")[1]
    assert "catchup: skip" in head and "design: skip" in head
    assert f"ledger: deferred/{BATCH}-deferred.json" in head
    assert f"ledger_key: {triage.ledger_key(row['issue'])}" in head
    assert f"source_prd: {row['prd']}" in head
    assert "severity: high" in head
    assert text.index("ledger_key:") < len("\n".join(text.splitlines()[:20]))


def test_stub_preserves_issue_and_detail_verbatim_in_problem(tree) -> None:
    row = _row(issue='Unrecoverable deadlock: `foo` -> Parse("no frontmatter ---")   with   spaces')
    text = _stub_text(tree, row)
    problem = text.split("## Problem")[1].split("## Solution")[0]
    assert f"Issue: {row['issue']}" in problem
    assert f"Detail: {row['detail']}" in problem
    assert row["prd"] in problem and BATCH in problem and "cap-overflow" in problem


def test_stub_has_exactly_one_checkbox_and_no_phase_1_task(tree) -> None:
    text = _stub_text(tree, _row())
    assert re.findall(r"(?m)^- \[ \] .*$", text) == [triage.TRIAGE_TASK]
    phase_1 = text.split("### Phase 1: Core")[1].split("## Success Criteria")[0]
    assert "- [" not in phase_1 and "No implementation tasks until attended triage" in phase_1


def test_stall_stub_is_critical_and_titled_from_its_detail(tree) -> None:
    text = _stub_text(tree, _stall_row())
    assert "severity: critical" in text
    assert "# Triage: Cycle 2 hit rework_cap 2 with an unresolved CRITICAL." in text
    assert "site `cap_critical`" in text and "op_id `c389f89aed18`" in text


def test_minting_never_promotes_into_backlog_or_wip(tree) -> None:
    autopilot, prds = tree
    _ledger(autopilot, [_row(), _stall_row()])
    triage.mint_stubs(autopilot, prds, BATCH)
    assert list((prds / "backlog").iterdir()) == [] and list((prds / "wip").iterdir()) == []
    assert len(_hold_files(prds)) == 2


# --- allocation ------------------------------------------------------------


def test_next_sequence_is_the_tail_across_all_five_dirs(tree) -> None:
    _autopilot, prds = tree
    (prds / "done" / "00007-a-v1.md").touch()
    (prds / "wip" / "00009-b-v1.md").touch()
    (prds / "hold" / "not-numbered.md").touch()
    assert triage.next_sequence(prds) == 10
    (prds.parent / "discovery").mkdir()
    (prds.parent / "discovery" / "00030-idea.md").touch()
    assert triage.next_sequence(prds) == 31


def test_concurrent_claim_after_write_renumbers_only_this_attempts_file(tree, monkeypatch) -> None:
    autopilot, prds = tree
    (prds / "done" / "00040-old-v1.md").touch()
    rival = prds / "backlog" / "00041-rival-v1.md"
    real_write = triage._write_candidate

    def write_then_rival(path: Path, content: str) -> None:
        real_write(path, content)
        rival.write_text("# rival, claimed 00041 between the write and the rescan\n")

    monkeypatch.setattr(triage, "_write_candidate", write_then_rival)
    _ledger(autopilot, [_row()])
    minted = triage.mint_stubs(autopilot, prds, BATCH)["minted"]
    assert minted == ["00042-triage-example-topic-v1.md"]
    assert rival.exists() and rival.read_text().startswith("# rival")
    assert [p.name for p in _hold_files(prds)] == minted


def test_a_revision_of_the_same_work_unit_is_not_a_collision(tree, monkeypatch) -> None:
    autopilot, prds = tree
    (prds / "hold" / "00042-foo-v1.md").touch()
    (prds / "hold" / "00042-foo-v2.md").touch()
    real_write = triage._write_candidate

    def write_then_own_revision(path: Path, content: str) -> None:
        real_write(path, content)
        path.with_name(path.name.replace("-v1.md", "-v2.md")).write_text("revision\n")

    monkeypatch.setattr(triage, "_write_candidate", write_then_own_revision)
    _ledger(autopilot, [_row()])
    assert triage.mint_stubs(autopilot, prds, BATCH)["minted"] == [
        "00043-triage-example-topic-v1.md"
    ]


def test_a_rival_at_the_identical_path_is_never_overwritten(tree, monkeypatch) -> None:
    """00195 review 1, HIGH: a rival that picked the same number AND slug lands
    on our exact path; publication must refuse it and renumber, not truncate."""
    autopilot, prds = tree
    rival = prds / "hold" / "00001-triage-example-topic-v1.md"
    real_next = triage.next_sequence
    planted = {"done": False}

    def plant_rival_then_answer(prds_dir: Path) -> int:
        number = real_next(prds_dir)
        if not planted["done"]:
            planted["done"] = True
            rival.write_text("# rival stub, same number and slug\n")
        return number

    monkeypatch.setattr(triage, "next_sequence", plant_rival_then_answer)
    _ledger(autopilot, [_row()])
    minted = triage.mint_stubs(autopilot, prds, BATCH)["minted"]
    assert rival.read_text() == "# rival stub, same number and slug\n"
    assert minted == ["00002-triage-example-topic-v1.md"]
    assert sorted(p.name for p in _hold_files(prds)) == [rival.name, *minted]


def test_each_publication_uses_its_own_sidecar(tree, monkeypatch) -> None:
    """00195 review 2, HIGH: a sidecar named after the target alone is shared
    by two writers racing for the same name; one truncates the other's
    published inode. Every call must stage through a sidecar of its own."""
    _autopilot, prds = tree
    target = prds / "hold" / "00001-triage-example-topic-v1.md"
    real_stage = triage._stage
    sidecars: list[str] = []

    def record(path: Path, content: str) -> Path:
        sidecar = real_stage(path, content)
        sidecars.append(sidecar.name)
        return sidecar

    monkeypatch.setattr(triage, "_stage", record)
    triage._write_candidate(target, "first writer\n")
    with pytest.raises(FileExistsError):
        triage._write_candidate(target, "second writer\n")
    assert len(sidecars) == 2 and sidecars[0] != sidecars[1], sidecars
    assert target.read_text() == "first writer\n"
    assert [p.name for p in (prds / "hold").iterdir()] == [target.name], "sidecar litter"


def test_a_write_cut_short_after_the_key_claims_nothing_on_retry(tree, monkeypatch) -> None:
    """00195 review 1, HIGH: ledger_key sits on line 5, so a stub truncated
    mid-write must not survive as a published owner."""
    autopilot, prds = tree
    _ledger(autopilot, [_row()])
    real_stage = triage._stage

    def truncate(path: Path, content: str) -> Path:
        real_stage(path, content[: content.index("severity:")])
        raise OSError("disk full")

    monkeypatch.setattr(triage, "_stage", truncate)
    with pytest.raises(OSError):
        triage.mint_stubs(autopilot, prds, BATCH)
    monkeypatch.setattr(triage, "_stage", real_stage)
    assert _hold_files(prds) == [], "a truncated stub was published"
    retry = triage.mint_stubs(autopilot, prds, BATCH)
    assert len(retry["minted"]) == 1
    assert "## Success Criteria" in _hold_files(prds)[0].read_text()


def test_partial_write_failure_leaves_a_retry_that_mints_only_the_rest(tree, monkeypatch) -> None:
    autopilot, prds = tree
    rows = [_row(issue="first"), _row(issue="second"), _row(issue="third")]
    _ledger(autopilot, rows)
    real_write = triage._write_candidate
    calls = {"n": 0}

    def fail_second(path: Path, content: str) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        real_write(path, content)

    monkeypatch.setattr(triage, "_write_candidate", fail_second)
    with pytest.raises(OSError):
        triage.mint_stubs(autopilot, prds, BATCH)
    assert len(_hold_files(prds)) == 1
    monkeypatch.setattr(triage, "_write_candidate", real_write)
    retry = triage.mint_stubs(autopilot, prds, BATCH)
    assert len(retry["minted"]) == 2 and retry["skipped"] == 1
    keys = {re.search(r"ledger_key: (\w+)", p.read_text()).group(1) for p in _hold_files(prds)}
    assert keys == {triage.ledger_key(r["issue"]) for r in rows}


# --- frozen fixture --------------------------------------------------------


def _source_prds(prds: Path) -> list[str]:
    return [
        re.search(r"(?m)^source_prd: (\S+)$", p.read_text()).group(1)[:5]
        for p in _hold_files(prds)
    ]


def test_frozen_ddb_slice_mints_twelve_then_zero(tree) -> None:
    autopilot, prds = tree
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert "00167, 00168, 00169 and 00170" in golden["provenance"]
    assert {i["prd"][:5] for i in golden["items"]} == {"00167", "00168", "00169", "00170"}
    (autopilot / "deferred" / f"{BATCH}-deferred.json").write_text(GOLDEN.read_text())
    first = triage.mint_stubs(autopilot, prds, BATCH)
    assert len(first["minted"]) == 12 and first["skipped"] == len(golden["items"]) - 12
    counts = {p: _source_prds(prds).count(p) for p in ("00167", "00168", "00169", "00170")}
    assert counts == {"00167": 3, "00168": 3, "00169": 4, "00170": 2}
    stall_stubs = [p for p in _hold_files(prds) if "site `cap_critical`" in p.read_text()]
    assert len(stall_stubs) == 1 and "source_prd: 00168-" in stall_stubs[0].read_text()
    assert triage.mint_stubs(autopilot, prds, BATCH) == {
        "minted": [],
        "skipped": len(golden["items"]),
    }
    assert len(_hold_files(prds)) == 12


# --- CLI -------------------------------------------------------------------


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def _state(autopilot: Path, **extra) -> Path:
    path = autopilot / "state.json"
    data = {
        "prd": "00167-example-v1.md",
        "phase": "done",
        "next_phase": "done",
        "batch": {"id": BATCH, "completed_prds": [], **extra},
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_cli_prints_the_minted_list_and_resolves_paths_by_walk_up(tmp_path) -> None:
    autopilot, prds = _tree(tmp_path)
    _ledger(autopilot, [_row(), _stall_row()])
    proc = _run(["mint-stubs", "--batch", BATCH], cwd=prds / "wip")
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert len(out["minted"]) == 2 and out["skipped"] == 0
    assert [p.name for p in _hold_files(prds)] == out["minted"]
    again = _run(["mint-stubs", "--batch", BATCH, "--state", str(autopilot / "state.json")], cwd=tmp_path)
    assert json.loads(again.stdout) == {"minted": [], "skipped": 2}


def test_cli_explicit_prds_flag_wins_over_the_state_default(tmp_path) -> None:
    autopilot, _prds = _tree(tmp_path)
    elsewhere = tmp_path / "elsewhere" / "prds"
    (elsewhere / "hold").mkdir(parents=True)
    _ledger(autopilot, [_row()])
    proc = _run(
        ["mint-stubs", "--batch", BATCH, "--state", str(autopilot / "state.json"), "--prds", str(elsewhere)],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert len(list((elsewhere / "hold").glob("*.md"))) == 1


def test_cli_exits_2_on_unreadable_or_invalid_ledger(tmp_path) -> None:
    autopilot, _prds = _tree(tmp_path)
    (autopilot / "deferred" / f"{BATCH}-deferred.json").mkdir()
    unreadable = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert unreadable.returncode == 2 and "cannot read ledger" in unreadable.stderr
    (autopilot / "deferred" / f"{BATCH}-deferred.json").rmdir()
    (autopilot / "deferred" / f"{BATCH}-deferred.json").write_bytes(b'{"items": [\xff]}')
    bad_bytes = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert bad_bytes.returncode == 2 and "not valid JSON" in bad_bytes.stderr
    (autopilot / "deferred" / f"{BATCH}-deferred.json").write_text("{not json")
    invalid = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert invalid.returncode == 2 and "not valid JSON" in invalid.stderr
    (autopilot / "deferred" / f"{BATCH}-deferred.json").write_text('{"items": "nope"}')
    shape = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert shape.returncode == 2 and '"items"' in shape.stderr


def test_cli_treats_an_absent_ledger_as_nothing_to_mint(tmp_path) -> None:
    """00195 review 1: a batch that deferred nothing has no ledger file, and
    the step-6 and batch-end sites still call the verb."""
    autopilot, prds = _tree(tmp_path)
    proc = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"minted": [], "skipped": 0}
    assert "ledger absent, nothing to mint" in proc.stderr
    assert _hold_files(prds) == []


def test_cli_exits_9_on_write_failure_and_the_retry_is_idempotent(tmp_path) -> None:
    autopilot, prds = _tree(tmp_path)
    _ledger(autopilot, [_row()])
    (prds / "hold").rmdir()
    (prds / "hold").write_text("a file where the hold dir should be")
    proc = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert proc.returncode == 9 and "write failed" in proc.stderr
    (prds / "hold").unlink()
    (prds / "hold").mkdir()
    retry = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert retry.returncode == 0 and len(json.loads(retry.stdout)["minted"]) == 1


def test_cli_accumulates_batch_minted_stubs_across_calls(tmp_path) -> None:
    autopilot, prds = _tree(tmp_path)
    state_path = _state(autopilot)
    _ledger(autopilot, [_row(issue="one")])
    first = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    _ledger(autopilot, [_row(issue="one"), _row(issue="two")])
    second = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert json.loads(second.stdout)["minted"] == ["00002-triage-example-topic-v1.md"]
    third = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert json.loads(third.stdout)["minted"] == []
    stubs = json.loads(state_path.read_text())["batch"]["minted_stubs"]
    assert stubs == [p.name for p in _hold_files(prds)] and len(stubs) == 2


def test_cli_keeps_an_earlier_count_of_12_when_the_final_call_mints_zero(tmp_path) -> None:
    autopilot, prds = _tree(tmp_path)
    earlier = [f"{n:05d}-triage-earlier-v1.md" for n in range(1, 13)]
    state_path = _state(autopilot, minted_stubs=earlier)
    (autopilot / "deferred" / f"{BATCH}-deferred.json").write_text(GOLDEN.read_text())
    for name in earlier:
        (prds / "hold" / name).write_text("ledger_key: placeholder\n")
    triage.mint_stubs(autopilot, prds, BATCH)  # the 12 real stubs, minted earlier
    final = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert json.loads(final.stdout)["minted"] == []
    assert len(json.loads(state_path.read_text())["batch"]["minted_stubs"]) == 12


def test_cli_without_a_state_file_still_mints_and_records_nothing(tmp_path) -> None:
    autopilot, prds = _tree(tmp_path)
    _ledger(autopilot, [_row()])
    proc = _run(["mint-stubs", "--batch", BATCH], cwd=tmp_path)
    assert proc.returncode == 0 and len(_hold_files(prds)) == 1
    assert not (autopilot / "state.json").exists()
