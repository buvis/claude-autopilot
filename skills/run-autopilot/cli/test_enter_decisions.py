#!/usr/bin/env python3
"""Tests for cli/enter.py - the step 10/11 decisions: the frontmatter write and
the warnings it hands back, the default handoff row and the directory it runs
in, the lane override, and catchup freshness against a moving clock, plus the
`--prd` argument checks that reject any value which is not a bare basename.
Split from test_enter.py for size; shares its Env harness.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import enter, frontmatter, notify_out
from cli.enter_harness import (
    KEYS,
    OTHER,
    PRD,
    Env,
    _arrange,
    _cache,
    _open_state,
    _prd_text,
    enter_twin,
    run_cli,
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


# -- step 10: frontmatter write, handoff row, lane -----------------------------


def test_default_resume_row_runs_the_record_dispatch_handoff(env: Env, monkeypatch) -> None:
    env.write_state(_open_state())
    env.put("wip")
    real_run = subprocess.run
    calls: list[tuple[list, dict]] = []

    def fake_run(args, *a, **k):
        if isinstance(args, list) and str(enter._RECORD_DISPATCH) in args:
            calls.append((args, k))
            return subprocess.CompletedProcess(args, 0, "", "")
        return real_run(args, *a, **k)

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = env.run(default_recorder=True)

    assert out["stop"] is None
    assert [args for args, _ in calls] == [[
        "python3", str(enter._RECORD_DISPATCH), "handoff", "--site", "build",
        "--edge", "resume", "--phase", "build", "--prd", PRD,
    ]]
    assert calls[0][1]["timeout"] == 10


def test_default_resume_row_runs_the_handoff_in_the_autopilot_dir(env: Env, monkeypatch) -> None:
    # record_dispatch.py resolves the ledger from its own cwd, and the parent's
    # cwd is the test runner's, not this tree: only an explicit `cwd` kwarg
    # naming the resolved autopilot dir puts the row in the right project.
    env.write_state(_open_state())
    env.put("wip")
    real_run = subprocess.run
    calls: list[dict] = []

    def fake_run(args, *a, **k):
        if isinstance(args, list) and str(enter._RECORD_DISPATCH) in args:
            calls.append(k)
            return subprocess.CompletedProcess(args, 0, "", "")
        return real_run(args, *a, **k)

    monkeypatch.setattr(subprocess, "run", fake_run)

    out = env.run(default_recorder=True)

    assert out["stop"] is None
    assert len(calls) == 1
    assert Path(calls[0]["cwd"]).resolve() == env.autopilot_dir.resolve()


def test_the_injected_resume_recorder_is_handed_the_autopilot_dir(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    calls: list[tuple[str, str, Path]] = []

    def recorder(prd: str, site: str, autopilot_dir: Path) -> None:
        calls.append((prd, site, autopilot_dir))

    out = env.run(record_resume_row=recorder)

    assert out["stop"] is None
    assert calls == [(PRD, "build", env.autopilot_dir)]


def test_lanes_off_forces_a_solo_prd_to_the_full_lane(env: Env, monkeypatch) -> None:
    monkeypatch.setenv("_AUTOPILOT_LANES", "off")
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(lane="solo"))

    out = env.run()

    assert (out["stop"], out["lane_effective"]) == (None, "full")
    assert env.read_state()["lane_effective"] == "full"


def test_frontmatter_fields_land_in_state_as_declared_or_default(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(doubt_reviewer="fable", rework_cap="5", session_model="opus"))

    out = env.run()

    assert out["stop"] is None
    data = env.read_state()
    keys = ("catchup_mode", "design_mode", "rework_cap", "doubt_reviewer",
            "consensus_engine", "session_model")
    assert {k: data.get(k) for k in keys} == {
        "catchup_mode": "run", "design_mode": "skip", "rework_cap": 5,
        "doubt_reviewer": "fable", "consensus_engine": "legacy", "session_model": "opus",
    }


def test_invalid_frontmatter_value_takes_the_default(env: Env) -> None:
    # enter() is a pure function that returns a dict (see its docstring); it
    # has no stdout/stderr contract of its own. It hands the frontmatter
    # warnings back in its `warnings` key, and the CLI wrapper (`_run_enter`)
    # is what prints them to stderr. Both halves are pinned here: the invalid
    # value resolves to its default, and its warning reaches the caller.
    text = _prd_text(consensus_engine="bogus")
    env.write_state(_open_state())
    env.put("wip", PRD, text)
    _fields, warnings = frontmatter.parse(text)
    assert len(warnings) == 1

    out = env.run()

    assert out["stop"] is None
    assert env.read_state()["consensus_engine"] == "legacy"
    assert out["warnings"] == warnings


# -- step 10: the frontmatter warnings reach the caller ------------------------

# Composed here, not read back from `frontmatter.parse`: a canned result that
# echoes the parse of some other PRD, or a summarised line, cannot match it.
_ENGINE_WARNING = (
    "autopilot: PRD frontmatter consensus_engine='bogus' is not one of "
    "legacy/shadow/workflow; defaulting to legacy"
)


def test_enter_returns_the_frontmatter_warning_line_verbatim(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(consensus_engine="bogus"))

    out = env.run()

    assert (out["stop"], out["warnings"]) == (None, [_ENGINE_WARNING])


def test_two_invalid_values_keep_both_warnings_in_the_parse_order(env: Env) -> None:
    text = _prd_text(consensus_engine="bogus", doubt_reviewer="nope")
    env.write_state(_open_state())
    env.put("wip", PRD, text)
    _fields, expected = frontmatter.parse(text)
    # parse emits doubt_reviewer first - the reverse of the document order - so
    # a re-sorted, document-ordered or deduplicated list cannot match.
    assert len(expected) == 2 and expected[1] == _ENGINE_WARNING

    out = env.run()

    assert out["warnings"] == expected


def test_a_prd_without_a_frontmatter_block_warns_exactly_once(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, "# No frontmatter here\n\nJust prose.\n")

    out = env.run()

    assert (out["stop"], out["warnings"]) == (None, [frontmatter.MALFORMED_WARNING])


def test_a_valid_frontmatter_block_produces_no_warnings(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(doubt_reviewer="fable", rework_cap="5"))

    out = env.run()

    assert (out["stop"], out["warnings"]) == (None, [])


@pytest.mark.parametrize("stop", ["fs_error", "custody", "drained"])
def test_a_halt_before_the_frontmatter_write_still_carries_an_empty_warnings_list(
    env: Env, monkeypatch: pytest.MonkeyPatch, stop: str,
) -> None:
    # `warnings` belongs to the return shape, not to the write step: a caller
    # that reads out["warnings"] on an early halt must not hit a KeyError.
    _arrange(env, monkeypatch, stop)

    out = env.run()

    assert out["stop"] == stop
    assert out["warnings"] == []


# -- the `enter` verb: eleven keys on stdout, the warnings on stderr -----------


def test_the_enter_verb_prints_eleven_keys_on_stdout_when_the_prd_warns(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(consensus_engine="bogus"))

    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 1, proc.stdout
    printed = json.loads(lines[0])
    assert set(printed) == KEYS
    assert (printed["stop"], printed["prd"]) == (None, PRD)
    # not under any key, not appended after the object
    assert "bogus" not in proc.stdout


def test_the_enter_verb_prints_every_warning_on_its_own_stderr_line(env: Env) -> None:
    text = _prd_text(consensus_engine="bogus", doubt_reviewer="nope")
    env.write_state(_open_state())
    env.put("wip", PRD, text)
    _fields, expected = frontmatter.parse(text)
    assert len(expected) == 2 and _ENGINE_WARNING in expected

    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 0, proc.stderr
    # filtered, not sliced: a best-effort handoff-row failure may add a line of
    # its own, but both warnings must appear whole, in order, one per line.
    assert [ln for ln in proc.stderr.splitlines() if ln in expected] == expected


def test_the_enter_verb_still_prints_only_the_detail_line_on_an_early_halt(
    env: Env, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _arrange(env, monkeypatch, "drained")
    expected = enter_twin(env)
    assert expected["stop"] == "drained" and expected["detail"]

    proc = run_cli(env, "enter", "--state", str(env.state_path))

    assert proc.returncode == 0, proc.stderr
    assert proc.stderr.splitlines() == [f"autopilot: {expected['detail']}"]
    assert set(json.loads(proc.stdout.strip())) == KEYS


# -- step 11: catchup freshness against the injected clock ---------------------


@pytest.mark.parametrize(
    ("now", "completed_at", "expected"),
    [
        ("2026-09-29T14:30:00Z", "2026-09-29T11:00:00Z", "delta"),
        ("2026-09-30T12:00:00Z", "2026-09-29T11:00:00Z", "full"),
        ("2026-09-29T12:00:00Z", "2026-09-29T08:01:00Z", "delta"),
        ("2026-09-29T12:00:00Z", "2026-09-29T07:59:00Z", "full"),
        ("2026-09-30T02:00:00Z", "2026-09-29T22:01:00Z", "delta"),
        ("2026-09-30T02:00:00Z", "2026-09-29T21:59:00Z", "full"),
    ],
    ids=["3h30m", "same-cache-a-day-later", "3h59m", "4h01m",
         "3h59m-across-midnight", "4h01m-across-midnight"],
)
def test_catchup_freshness_is_four_hours_before_now(
    env: Env, now: str, completed_at: str, expected: str,
) -> None:
    env.write_state(_open_state(batch=_cache(catchup_completed_at=completed_at)))
    env.put("wip")

    out = env.run(now=lambda: now)

    assert (out["stop"], out["catchup"]) == (None, expected)


# -- the --prd argument must be a bare basename -------------------------------


def _assert_rejected(out: dict, prd_arg: str) -> None:
    """The rejection contract: the `prd_not_found` stop, nothing selected, and a
    detail naming both the offending argument and the rule it broke."""
    assert (out["stop"], out["prd"], out["source"]) == ("prd_not_found", None, None)
    assert out["detail"] and prd_arg in out["detail"]
    assert "bare basename" in out["detail"].lower()


@pytest.mark.parametrize(
    "prd_arg",
    [f"../hold/{OTHER}", f"./{PRD}", f"prds/wip/{PRD}", f"wip/{PRD}", "sub/x.md",
     f"{PRD}/", f"a/../{PRD}", ".", "..", "/etc/passwd", ""],
    ids=["parent-traversal-reaching-hold", "dot-slash-reaching-wip", "nested-relative",
         "nested-into-wip", "nested-unrelated", "trailing-separator", "dot-dot-inside",
         "the-wip-folder-itself", "the-parent-folder-itself",
         "absolute-outside-the-tree", "the-empty-string"],
)
def test_a_prd_arg_that_is_not_a_bare_basename_is_rejected(env: Env, prd_arg: str) -> None:
    # Both arranged files are reachable by joining the argument onto a PRD
    # folder, so a run that consults the filesystem would select one of them;
    # the rejection has to fire before that lookup happens. The shapes that reach
    # nothing (`sub/x.md`, `/etc/passwd`) need no arrangement at all - the rule
    # fires before any disk access, so absence is not what stops them.
    env.write_state(_open_state())
    env.put("wip", PRD)
    env.put("hold", OTHER)

    out = env.run(prd_arg=prd_arg)

    _assert_rejected(out, prd_arg)
    assert env.has("hold", OTHER) and env.has("wip", PRD)
    assert not env.has("wip", OTHER)


def test_a_nested_prd_arg_is_rejected_even_when_it_resolves_inside_wip(env: Env) -> None:
    # Joined onto the wip folder this argument reaches a real file, so a run that
    # consults the filesystem ACCEPTS it. Only a rule applied before the lookup
    # rejects it - a missing target cannot be what does the work here.
    nested = f"prds/wip/{PRD}"
    env.write_state(_open_state())
    env.put("wip", PRD)
    env.put("wip", nested)

    out = env.run(prd_arg=nested)

    _assert_rejected(out, nested)
    assert env.has("wip", nested) and env.has("wip", PRD)


def test_an_absolute_prd_arg_is_rejected_even_though_that_file_exists(env: Env) -> None:
    env.write_state(_open_state())
    target = env.put("hold", OTHER)

    out = env.run(prd_arg=str(target))

    _assert_rejected(out, str(target))
    assert env.has("hold", OTHER)
    assert not env.has("wip", OTHER)


@pytest.mark.parametrize(
    "name", [PRD, OTHER, "notes.md", "x.md", "00010-Sample-PRD.md"],
    ids=["sample-prd", "other-prd", "no-number-prefix", "one-char-stem", "mixed-case-slug"],
)
def test_a_bare_basename_in_wip_is_still_selected_from_the_argument(env: Env, name: str) -> None:
    env.write_state(_open_state())
    env.put("wip", name)

    out = env.run(prd_arg=name)

    assert (out["stop"], out["prd"], out["source"]) == (None, name, "arg")
    assert env.has("wip", name)


@pytest.mark.parametrize(
    "name", [PRD, OTHER, "notes.md", "x.md", "00010-Sample-PRD.md"],
    ids=["sample-prd", "other-prd", "no-number-prefix", "one-char-stem", "mixed-case-slug"],
)
def test_a_bare_basename_in_backlog_is_still_moved_into_wip(env: Env, name: str) -> None:
    env.write_state(_open_state())
    env.put("backlog", name)

    out = env.run(prd_arg=name)

    assert (out["stop"], out["prd"], out["source"]) == (None, name, "arg")
    assert env.has("wip", name) and not env.has("backlog", name)
