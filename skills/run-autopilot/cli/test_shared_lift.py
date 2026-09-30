#!/usr/bin/env python3
"""Tests for the `select` and `frontmatter` verbs over the shared helpers.

These two verbs each carried an inline copy of logic that also lives in
`selection.select_eligible` / `frontmatter.apply`. This file is the regression
net that makes deleting the copies safe: it pins what the verbs OBSERVABLY do
(the JSON line, the skip record's shape, the exit-code precedence, the stderr
ordering) so a refactor cannot change any of it quietly, plus the two bindings
that only hold once the lift is finished - the verb's skip record is the
helper's entry plus its own `at` stamp, and `enter()` carries the reset lines.

It also pins the lift itself, which no amount of output-comparing can: each
verb's whole answer comes from ONE call to the shared helper, and the private
helpers the inline copies needed are gone from `__main__.py`.

It lives beside `test_lifecycle_cli.py` (630 lines) and `test_cli.py` (758)
rather than inside them: both are near the 800-line ceiling.

The CLI invocation and the project tree come from `cli/enter_harness.py`, the
pattern the enter tests already use, so there is one way to drive the verbs
here and not two.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cli import __main__ as cli_main
from cli import frontmatter, notify_out, selection
from cli.enter_harness import OTHER, PRD, Env, _open_state, _prd_text, run_cli

CLI_DIR = Path(__file__).resolve().parent

_ROOT_IGNORES_MODES = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores directory modes, so the write cannot be made to fail",
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


def _select(env: Env, prds_dir: Path | None = None) -> dict:
    proc = run_cli(env, "select", "--prds", str(prds_dir or env.prds_dir))
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _frontmatter(env: Env, prd: Path) -> subprocess.CompletedProcess:
    return run_cli(
        env, "frontmatter", "--state", str(env.state_path), "--prd", str(prd),
    )


# -- the verbs delegate, rather than keeping a second copy ---------------------
#
# Driven in-process (`main(argv)`) rather than as a subprocess: a spy on the
# shared helper is what proves the verb CALLS it, and no amount of comparing
# one tree's output can tell one call from two agreeing copies.


def test_the_select_verb_gets_its_whole_answer_from_the_shared_helper(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    # The tree holds a PRD whose check fails, so a verb still running its own
    # eligibility loop would print a skip entry the helper never returned.
    env.put("backlog", PRD, _prd_text(eligibility='"exit 3"'))
    calls: list[tuple] = []

    def spy(*args: object, **kwargs: object) -> tuple:
        calls.append((args, kwargs))
        return None, "drained", []

    monkeypatch.setattr(selection, "select_eligible", spy)

    code = cli_main.main(["select", "--prds", str(env.prds_dir)])

    assert code == 0
    assert calls == [((env.prds_dir,), {})], calls
    assert json.loads(capsys.readouterr().out) == {
        "prd": None,
        "source": "drained",
        "skipped": [],
    }


def test_the_frontmatter_verb_gets_its_whole_answer_from_the_shared_helper(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    # `lane: garbage` would earn a warning from any inline copy of the parse,
    # and the PRD's rework_cap is not the one the helper returns: an empty
    # stderr and the helper's own fields are what a thin caller produces.
    env.write_state(_open_state())
    prd = env.put("wip", PRD, _prd_text(rework_cap="4", lane="garbage"))
    applied = {"lane": "solo", "rework_cap": 9}
    calls: list[tuple] = []

    def spy(*args: object, **kwargs: object) -> tuple:
        calls.append(args)
        return dict(applied), [], []

    monkeypatch.setattr(frontmatter, "apply", spy)

    code = cli_main.main(
        ["frontmatter", "--state", str(env.state_path), "--prd", str(prd)],
    )

    assert code == 0
    assert calls == [(prd, env.state_path)], calls
    captured = capsys.readouterr()
    assert json.loads(captured.out) == applied
    assert captured.err == "", captured.err


@pytest.mark.parametrize(
    "orphan",
    ["_listdir", "_prd_text", "_project_root", "_lane_fields", "eligibility.evaluate"],
)
def test_no_inline_copy_of_the_lifted_logic_survives_in_the_cli(orphan: str) -> None:
    # These four helpers exist only to serve the two inline copies; once the
    # verbs call the shared helpers they are orphans, and an orphan left in
    # place is the next caller's invitation to diverge again. The direct
    # `eligibility.evaluate` call is the copy itself.
    source = (CLI_DIR / "__main__.py").read_text(encoding="utf-8")

    assert orphan not in source, f"{orphan} still lives in cli/__main__.py"


# -- `autopilot select`: the skip record --------------------------------------


def test_a_skip_entry_carries_exactly_the_five_documented_keys(env: Env) -> None:
    env.put("backlog", PRD, _prd_text(eligibility='"exit 4"'))

    out = _select(env)

    assert [set(entry) for entry in out["skipped"]] == [
        {"prd", "command", "exit_code", "note", "at"},
    ]
    entry = out["skipped"][0]
    assert (entry["prd"], entry["command"], entry["exit_code"], entry["note"]) == (
        PRD,
        "exit 4",
        4,
        "",
    )


def test_select_stamps_each_skip_with_an_iso_utc_at(env: Env) -> None:
    env.put("backlog", PRD, _prd_text(eligibility='"false"'))

    at = _select(env)["skipped"][0]["at"]

    assert at.endswith("Z"), at
    stamped = datetime.fromisoformat(at.replace("Z", "+00:00"))
    assert stamped.utcoffset() == timedelta(0)
    # A constant would satisfy the format; the stamp is read off a real clock.
    assert abs(datetime.now(timezone.utc) - stamped) < timedelta(minutes=5)


def test_skips_are_appended_under_batch_and_never_at_the_top_level(env: Env) -> None:
    env.write_state(_open_state())
    env.put("backlog", PRD, _prd_text(eligibility='"false"'))

    _select(env)

    state = env.read_state()
    assert [entry["prd"] for entry in state["batch"]["skips"]] == [PRD]
    assert "skips" not in state, "a top-level skips[] is invisible to the batch report"


def test_the_printed_skip_is_the_helpers_entry_plus_the_verbs_at_stamp(
    env: Env,
) -> None:
    # The verb decides nothing of its own here: the pick, the source and every
    # skip field but `at` must be exactly what the shared helper returned for
    # the same tree. Two copies of the loop cannot keep agreeing; one call can.
    env.put("backlog", PRD, _prd_text(eligibility='"exit 3"'))
    env.put("backlog", OTHER, _prd_text(eligibility='"true"'))

    out = _select(env)
    prd, source, skips = selection.select_eligible(env.prds_dir)

    assert (out["prd"], out["source"]) == (prd, source)
    assert [
        {key: value for key, value in entry.items() if key != "at"}
        for entry in out["skipped"]
    ] == skips
    assert [set(entry) - set(plain) for entry, plain in zip(out["skipped"], skips)] == [
        {"at"},
    ]


@pytest.mark.parametrize(
    ("marker_at_the_derived_root", "expected"),
    [(True, (PRD, "backlog", 0)), (False, (None, "drained", 1))],
    ids=["marker-at-the-derived-root", "marker-in-the-prds-dir"],
)
def test_the_eligibility_check_runs_where_the_prds_path_derivation_points(
    env: Env,
    tmp_path: Path,
    marker_at_the_derived_root: bool,
    expected: tuple[str | None, str, int],
) -> None:
    # `--prds` alone names the working directory of the check: resolve it, then
    # take parents[3] (for `<root>/docs/dev/project-management/prds` that is
    # `<root>`). The check below succeeds only in that one directory, so this
    # measures where it RAN, not merely that it ran.
    prds_dir = tmp_path / "a" / "b" / "c" / "d" / "prds"
    (prds_dir / "backlog").mkdir(parents=True)
    (prds_dir / "backlog" / PRD).write_text(
        _prd_text(eligibility='"test -f marker.txt"'), encoding="utf-8",
    )
    derived_root = prds_dir.resolve().parents[3]
    marker_dir = derived_root if marker_at_the_derived_root else prds_dir
    (marker_dir / "marker.txt").write_text("x", encoding="utf-8")

    out = _select(env, prds_dir)

    assert (out["prd"], out["source"], len(out["skipped"])) == expected


# -- `autopilot frontmatter`: the exit-code precedence ------------------------


def test_an_unreadable_prd_is_reported_before_the_state_file_is_read(env: Env) -> None:
    # Precedence, not just the code: the state carries a future schema, which
    # earns exit 6 on its own. The PRD read comes first, so this is exit 1.
    env.write_state(_open_state(schema_version=999))
    before = env.state_path.read_bytes()
    missing = env.prds_dir / "wip" / PRD

    proc = _frontmatter(env, missing)

    assert proc.returncode == 1, proc.stderr
    assert f"autopilot: cannot read PRD {missing}: " in proc.stderr
    assert env.state_path.read_bytes() == before


def test_a_successful_run_prints_one_json_line_sorted_by_key(env: Env) -> None:
    env.write_state(_open_state())
    prd = env.put("wip", PRD, _prd_text(rework_cap="4"))

    proc = _frontmatter(env, prd)

    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, proc.stdout
    fields = json.loads(lines[0])
    assert lines[0] == json.dumps(fields, sort_keys=True)
    assert fields["rework_cap"] == 4
    assert env.read_state()["rework_cap"] == 4


def _write_into_a_sealed_dir(env: Env, text: str) -> subprocess.CompletedProcess:
    """Run the verb with `state.json`'s directory read-only, so the write fails
    after the parse and the lane classification have already happened."""
    env.write_state(_open_state(rework_cap=5))
    prd = env.put("wip", PRD, text)
    env.autopilot_dir.chmod(0o555)
    try:
        return _frontmatter(env, prd)
    finally:
        env.autopilot_dir.chmod(0o755)


@_ROOT_IGNORES_MODES
def test_a_failed_state_write_exits_two_and_names_the_failure(env: Env) -> None:
    proc = _write_into_a_sealed_dir(env, _prd_text(rework_cap="2"))

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "autopilot: frontmatter write failed: " in proc.stderr
    assert env.read_state()["rework_cap"] == 5, "the refused write changed nothing"


@_ROOT_IGNORES_MODES
def test_parse_and_lane_warnings_reach_stderr_even_when_the_write_fails(
    env: Env,
) -> None:
    # The regression this exists to catch: collecting the warnings and printing
    # them only on the success path would lose them exactly when they matter.
    proc = _write_into_a_sealed_dir(
        env, _prd_text(catchup="sometimes", lane="garbage", rework_cap="2"),
    )

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "autopilot: PRD frontmatter catchup='sometimes'" in proc.stderr
    assert "autopilot: PRD frontmatter lane='garbage'" in proc.stderr


@_ROOT_IGNORES_MODES
def test_no_reset_line_is_printed_when_the_write_failed(env: Env) -> None:
    # state holds rework_cap 5 and the PRD says 2, so a run that reached the
    # write would reset it - but nothing was reset, so nothing is claimed.
    proc = _write_into_a_sealed_dir(env, _prd_text(rework_cap="2"))

    # Matched per line, not as a substring of the whole stream: the failure
    # message quotes the tmp path, and this test's own name is in it.
    assert [
        line
        for line in proc.stderr.splitlines()
        if line.startswith("autopilot: PRD frontmatter reset")
    ] == [], proc.stderr


def test_one_reset_line_is_printed_per_field_whose_value_changed(env: Env) -> None:
    env.write_state(_open_state(rework_cap=5, catchup_mode="skip"))
    prd = env.put("wip", PRD, _prd_text(rework_cap="2", catchup="force"))

    proc = _frontmatter(env, prd)

    assert proc.returncode == 0, proc.stderr
    assert sorted(proc.stderr.splitlines()) == sorted(
        [
            "autopilot: PRD frontmatter reset rework_cap 5 -> 2",
            "autopilot: PRD frontmatter reset catchup_mode skip -> force",
        ],
    )
    assert env.read_state()["catchup_mode"] == "force"


@pytest.mark.parametrize(
    ("lane_value", "expected_stderr"),
    [
        (
            "garbage",
            [
                "autopilot: PRD frontmatter lane='garbage' is not one of "
                "solo/fast-track/full; defaulting to full",
            ],
        ),
        (None, []),
    ],
    ids=["invalid-value", "absent-key"],
)
def test_the_lane_warning_fires_for_an_invalid_value_and_never_for_an_absent_one(
    env: Env, lane_value: str | None, expected_stderr: list[str],
) -> None:
    env.write_state(_open_state())
    keys = {"lane": lane_value} if lane_value is not None else {}
    prd = env.put("wip", PRD, _prd_text(**keys))

    proc = _frontmatter(env, prd)

    assert proc.returncode == 0, proc.stderr
    assert proc.stderr.splitlines() == expected_stderr


# -- `enter` carries the reset lines too --------------------------------------


def test_enter_returns_the_frontmatter_reset_lines_among_its_warnings(env: Env) -> None:
    # Without this, a session that enters through `enter` never learns that the
    # PRD's frontmatter overwrote a state field; only the `frontmatter` verb
    # said so.
    env.write_state(_open_state(rework_cap=5))
    env.put("wip", PRD, _prd_text(rework_cap="2"))

    out = env.run()

    assert out["stop"] is None, out["detail"]
    assert "autopilot: PRD frontmatter reset rework_cap 5 -> 2" in out["warnings"]


# -- the by-path load hazard ---------------------------------------------------


@pytest.mark.parametrize(
    ("module", "names"),
    [
        ("frontmatter.py", ("parse", "declared")),
        ("selection.py", ("select", "select_eligible")),
        ("lane.py", ("classify", "effective")),
    ],
    ids=["frontmatter", "selection", "lane"],
)
def test_a_shared_module_still_loads_by_path_with_no_parent_package(
    module: str, names: tuple[str, ...], monkeypatch: pytest.MonkeyPatch,
) -> None:
    # fast-track/scripts/cards_from_prd.py loads these by path, with no parent
    # package, so a MODULE-LEVEL `from . import x` cannot resolve and the
    # script dies on import. cff112f shipped exactly that; 20b4b02 fixed it by
    # deferring the import inside the function that needs it. Importing the
    # package normally would not notice.
    name = f"by_path_{Path(module).stem}"
    spec = importlib.util.spec_from_file_location(name, CLI_DIR / module)
    loaded = importlib.util.module_from_spec(spec)
    # Registered the way cards_from_prd.py registers it, so a module-level
    # dataclass can find its own module; monkeypatch drops the entry after.
    monkeypatch.setitem(sys.modules, name, loaded)
    spec.loader.exec_module(loaded)

    for name in names:
        assert callable(getattr(loaded, name)), f"{module}:{name}"
