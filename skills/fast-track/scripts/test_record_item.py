"""Tests for record_item.py, the fast-track per-item metrics recorder.

One fast-track item produces one row, appended to the loop-metrics ledger and
its GC-exempt mirror, so an attended lane shows up in the same renderer the
autopilot loop feeds. The rows are telemetry and nothing waits on them: a write
that fails says so once and the item still lands.

The script borrows its append helper from record_dispatch.py, which writes to
that module's own FILENAME global. Two rules here guard the borrow - the row
lands under loop-metrics.jsonl, and the shared module is left pointing at
dispatch-metrics.jsonl afterwards.

record_item.py is not an installed package, so it is loaded by path, the same
idiom test_card.py uses. The cost column's producer-to-renderer tests live in
test_record_item_render.py. Every CLI run is driven with `cwd=` inside a
tmp_path tree carrying its own dev/local/autopilot directory, so the walk-up
lands there and no test appends to this repo's own ledger.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import subprocess
import sys
import time
import types
import uuid
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("record_item.py")
_RECORD_DISPATCH_PATH = (
    Path(__file__).resolve().parents[2] / "work" / "scripts" / "record_dispatch.py"
)

_SPEC = importlib.util.spec_from_file_location("fast_track_record_item", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_record_item = importlib.util.module_from_spec(_SPEC)
# Registered before exec_module on purpose, the same reason test_card.py does
# it: a module that resolves its own annotations at import time looks itself up
# in sys.modules, and an unregistered module makes that lookup fail.
sys.modules[_SPEC.name] = _record_item
_SPEC.loader.exec_module(_record_item)

append_item_row = _record_item.append_item_row

_LEDGER_FILENAME = "loop-metrics.jsonl"
_DISPATCH_FILENAME = "dispatch-metrics.jsonl"
# This repo's own ledger: the file no test may ever append to. A run driven
# from a tmp tree that holds no autopilot directory is the one place a walk-up
# starting from the script's own location instead of the cwd would land here.
_REPO_LEDGER = (
    Path(__file__).resolve().parents[3]
    / "dev"
    / "local"
    / "autopilot"
    / _LEDGER_FILENAME
)
_ROW_KEYS = {
    "ts_start",
    "ts_end",
    "wall_secs",
    "prd",
    "batch",
    "phase_launched",
    "phase_end",
    "signal",
    "model",
    "cost_usd",
    "findings",
    "confirmed",
    "rework",
    "outcome",
}
_REQUIRED_FLAGS = (
    "--item",
    "--card",
    "--model",
    "--started",
    "--outcome",
    "--rework",
    "--findings",
    "--confirmed",
)


def _autopilot_tree(root: Path) -> Path:
    """A tmp tree the walk-up can land in, returning its autopilot dir."""
    autopilot_dir = root / "dev" / "local" / "autopilot"
    autopilot_dir.mkdir(parents=True)
    return autopilot_dir


def _card(root: Path, name: str = "widget-slice.md") -> Path:
    """A card file nested deep enough that its basename is not its path."""
    card = root / "cards" / "backlog" / name
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text("item: widget-slice\n", encoding="utf-8")
    return card


def _cli_args(
    card: Path,
    *,
    started: int,
    item: str = "widget-slice",
    model: str = "sonnet",
    outcome: str = "committed",
    rework: int = 0,
    findings: str = "[]",
    confirmed: int = 0,
    cost: str | None = None,
) -> list[str]:
    args = [
        "--item",
        item,
        "--card",
        str(card),
        "--model",
        model,
        "--started",
        str(started),
        "--outcome",
        outcome,
        "--rework",
        str(rework),
        "--findings",
        findings,
        "--confirmed",
        str(confirmed),
    ]
    if cost is not None:
        args += ["--cost", cost]
    return args


def _without(args: list[str], flag: str) -> list[str]:
    index = args.index(flag)
    return args[:index] + args[index + 2 :]


def _run_cli(cwd: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(cwd),
    )


def _ledger_lines(autopilot_dir: Path) -> tuple[list[str], list[str]]:
    """The working ledger's lines and the mirror's, both required to exist."""
    working = autopilot_dir / _LEDGER_FILENAME
    mirror = autopilot_dir / "ledger" / _LEDGER_FILENAME
    assert working.is_file(), f"no working ledger at {working}"
    assert mirror.is_file(), f"no ledger mirror at {mirror}"
    return (
        working.read_text(encoding="utf-8").splitlines(),
        mirror.read_text(encoding="utf-8").splitlines(),
    )


def _record_dispatch_namespace() -> dict:
    """The live namespace of the record_dispatch module record_item imported.

    Found by file rather than by attribute name, so the implementor keeps the
    choice of what to call it: first a module object bound on record_item, then
    the globals of a function re-exported from that file. Nothing found means
    the reuse the contract asks for is not there.
    """
    for value in vars(_record_item).values():
        if isinstance(value, types.ModuleType):
            module_file = getattr(value, "__file__", None)
            if module_file and Path(module_file).resolve() == _RECORD_DISPATCH_PATH:
                return vars(value)
    for value in vars(_record_item).values():
        namespace = getattr(value, "__globals__", None)
        if isinstance(namespace, dict):
            module_file = namespace.get("__file__")
            if module_file and Path(str(module_file)).resolve() == (
                _RECORD_DISPATCH_PATH
            ):
                return namespace
    pytest.fail(
        "record_item holds no reference to record_dispatch.py, so its append "
        "helper is not the shared one the contract names",
    )


def _spy_on_the_borrowed_append_row(
    monkeypatch: pytest.MonkeyPatch,
    namespace: dict,
    *,
    raises: bool,
) -> list[str]:
    """Stand a spy in for the borrowed writer and record what FILENAME said.

    Both ways of reaching it are covered - a call through the shared module's
    attribute, and a name bound onto record_item at import time - so any
    implementation that actually borrows the helper is intercepted, and one
    that re-implements the append inline is not. Returns the list the spy
    appends the live FILENAME to, one entry per call.
    """
    observed: list[str] = []
    original = namespace["append_row"]

    def spy(*_args: object, **_kwargs: object) -> None:
        observed.append(namespace["FILENAME"])
        if raises:
            raise OSError("ledger unwritable")

    monkeypatch.setitem(namespace, "append_row", spy)
    for name, value in list(vars(_record_item).items()):
        if value is original:
            monkeypatch.setattr(_record_item, name, spy)
    return observed


# The renderer reads loop-metrics.jsonl and the ledger mirror is what survives a
# GC sweep, so one item has to reach both, identically, once. The whole row is
# spelled out rather than one key: the fast-track lane is the only producer of
# these rows, so a key that arrives misspelled, as a string instead of an int, or
# carrying the card's full path instead of its basename lands in the ledger
# unnoticed and skews every later reading. The key set is compared exactly, which
# is what refuses the `event` and `effort` keys the dispatch rows carry and this
# one must not.
def test_item_row_lands_in_both_ledgers_with_phase_fast_track(tmp_path: Path) -> None:
    autopilot_dir = _autopilot_tree(tmp_path)
    card = _card(tmp_path)
    started = int(time.time()) - 90

    before = int(time.time())
    result = _run_cli(
        tmp_path,
        _cli_args(
            card,
            started=started,
            model="opus",
            outcome="committed",
            rework=0,
            findings='{"HIGH": 1, "LOW": 2}',
            confirmed=3,
        ),
    )
    after = int(time.time())

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert len(working_lines) == 1
    assert working_lines == mirror_lines

    row = json.loads(working_lines[0])
    assert set(row) == _ROW_KEYS
    assert row["ts_start"] == started
    assert before <= row["ts_end"] <= after
    assert row["wall_secs"] == row["ts_end"] - started
    assert row["prd"] == "widget-slice.md"
    assert row["batch"] == "fast-track"
    assert row["phase_launched"] == "fast-track"
    assert row["phase_end"] == "fast-track"
    assert row["signal"] == "committed"
    assert row["outcome"] == "committed"
    assert row["model"] == "opus"
    assert row["cost_usd"] is None
    assert row["findings"] == {"HIGH": 1, "LOW": 2}
    assert row["confirmed"] == 3
    assert row["rework"] == 0

    # The borrowed helper writes to whatever its own module global names, so a
    # borrow that forgot to redirect leaves the row under the dispatch name.
    assert not (autopilot_dir / _DISPATCH_FILENAME).exists()
    assert not (autopilot_dir / "ledger" / _DISPATCH_FILENAME).exists()


def test_failed_write_exits_zero_and_says_so(tmp_path: Path) -> None:
    # A ledger that cannot be written must not fail the item, and an item that
    # quietly loses its row must not look like a clean run. Both halves are
    # asserted: exit 0 alone passes an implementation that swallows the error
    # in silence, and the operator then reads a gap in the ledger as an item
    # that never ran. Exactly one line, so a stack trace or a per-file message
    # pair fails too. The ledger path is made unwritable by standing a
    # directory where the file belongs, which no permission bit can undo.
    autopilot_dir = _autopilot_tree(tmp_path)
    (autopilot_dir / _LEDGER_FILENAME).mkdir()
    card = _card(tmp_path)

    result = _run_cli(tmp_path, _cli_args(card, started=int(time.time()) - 12))

    assert result.returncode == 0
    complaints = [line for line in result.stderr.splitlines() if line.strip()]
    assert len(complaints) == 1, result.stderr
    assert "Traceback" not in result.stderr
    # The one line has to name the ledger it lost, or the operator reading it
    # learns only that something somewhere failed to write.
    assert _LEDGER_FILENAME in complaints[0]


def test_append_item_row_writes_the_loop_metrics_name_and_no_other(
    tmp_path: Path,
) -> None:
    # Called directly, with no walk-up in the way: the row goes to
    # loop-metrics.jsonl and its ledger/ mirror, the mirror directory is
    # created when absent, and the borrowed helper's own dispatch-metrics name
    # appears nowhere. The directory listing is compared whole, so a redirect
    # that writes the row twice under two names is caught rather than passing
    # on the strength of the file it did get right.
    row = {"batch": "fast-track", "signal": "committed", "confirmed": 2}

    append_item_row(tmp_path, row)

    working_lines, mirror_lines = _ledger_lines(tmp_path)
    assert len(working_lines) == 1
    assert working_lines == mirror_lines
    assert json.loads(working_lines[0]) == row
    # Compact separators: these rows are appended for the life of a repo, and
    # json.dumps' default spacing is the difference.
    assert ", " not in working_lines[0]
    assert '": ' not in working_lines[0]
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "ledger",
        _LEDGER_FILENAME,
    ]
    assert sorted(path.name for path in (tmp_path / "ledger").iterdir()) == [
        _LEDGER_FILENAME,
    ]


@pytest.mark.parametrize("ledger_state", ["writable", "unwritable"])
def test_append_item_row_leaves_the_shared_filename_global_restored(
    tmp_path: Path,
    ledger_state: str,
) -> None:
    # record_dispatch.FILENAME is shared state: /work appends its dispatch rows
    # through the same module inside the same process. A recorder that
    # redirects the write by setting that global and walks away leaves every
    # later dispatch row landing in the fast-track ledger, which no test of
    # this script's own output can see. The failing arm is the one that
    # matters - restoring only on the happy path is the easy version of this
    # bug.
    namespace = _record_dispatch_namespace()
    assert namespace["FILENAME"] == _DISPATCH_FILENAME, "leaked before the call"
    target = tmp_path / "autopilot"
    target.mkdir()
    if ledger_state == "unwritable":
        (target / _LEDGER_FILENAME).mkdir()

    append_item_row(target, {"batch": "fast-track", "signal": "stopped"})

    assert namespace["FILENAME"] == _DISPATCH_FILENAME


@pytest.mark.parametrize("write", ["succeeds", "raises"])
def test_append_item_row_runs_the_shared_writer_under_the_loop_metrics_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write: str,
) -> None:
    # The borrow is the whole design: this script carries no writer of its own,
    # it points the shared one at another file for the length of one call. A
    # reference to record_dispatch on the module proves none of that - an
    # implementation can import it, never call it, append inline, and every
    # file-landing test above still passes while the shared global is never
    # touched. So the shared writer is replaced by a spy: it has to have run,
    # it has to have seen loop-metrics.jsonl while it ran, and the global has
    # to be back to the dispatch name once the call returns - including on the
    # arm where the write blew up, which is the one a redirect without a
    # try/finally gets wrong. No file lands here on purpose; where the row goes
    # is pinned by the tests above.
    namespace = _record_dispatch_namespace()
    assert namespace["FILENAME"] == _DISPATCH_FILENAME, "leaked before the call"
    observed = _spy_on_the_borrowed_append_row(
        monkeypatch,
        namespace,
        raises=write == "raises",
    )

    # The spy's OSError stands in for a ledger that cannot be written. Whether
    # append_item_row swallows it or lets it out is not this test's business -
    # the restore is, and it is asserted on either path.
    with contextlib.suppress(OSError):
        append_item_row(tmp_path, {"batch": "fast-track", "signal": "committed"})

    assert observed, "append_item_row never called the borrowed append_row"
    assert observed == [_LEDGER_FILENAME] * len(observed)
    assert namespace["FILENAME"] == _DISPATCH_FILENAME


def test_a_second_item_appends_a_line_instead_of_replacing_the_first(
    tmp_path: Path,
) -> None:
    # A fast-track batch runs items one process at a time, so the ledger is
    # built by appending: a recorder that opens its files for writing keeps
    # only the last item of the batch, and both files still exist and still
    # parse, so nothing else in these tests notices.
    autopilot_dir = _autopilot_tree(tmp_path)
    card = _card(tmp_path)
    started = int(time.time()) - 60

    first = _run_cli(
        tmp_path,
        _cli_args(card, started=started, model="sonnet", confirmed=1),
    )
    second = _run_cli(
        tmp_path,
        _cli_args(
            card,
            started=started,
            model="opus",
            outcome="branched",
            confirmed=4,
        ),
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert len(working_lines) == 2
    assert working_lines == mirror_lines
    assert json.loads(working_lines[0])["model"] == "sonnet"
    assert json.loads(working_lines[0])["confirmed"] == 1
    assert json.loads(working_lines[1])["model"] == "opus"
    assert json.loads(working_lines[1])["confirmed"] == 4
    assert json.loads(working_lines[1])["outcome"] == "branched"


@pytest.mark.parametrize(
    ("findings_json", "expected_findings", "rework"),
    [
        ("[]", [], 0),
        ('{"HIGH": 1, "LOW": 2}', {"HIGH": 1, "LOW": 2}, 1),
        ('["naming", "docs"]', ["naming", "docs"], 1),
    ],
)
def test_findings_and_rework_are_carried_through_unreshaped(
    tmp_path: Path,
    findings_json: str,
    expected_findings: object,
    rework: int,
) -> None:
    # The findings value comes from the review roster in whatever shape that
    # roster produced - an empty list when nothing was raised, a severity count
    # object, a list of strings - and this script is a recorder, not a
    # summariser. A recorder that counted, sorted or coerced it would pass an
    # object-only test and lose the two list arms. rework rides along because
    # it is an int in the row and a string on the command line, and the 1 arm
    # is the one a recorder defaulting to 0 gets wrong.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(
            _card(tmp_path),
            started=int(time.time()) - 5,
            findings=findings_json,
            rework=rework,
            outcome="stopped",
        ),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert working_lines == mirror_lines
    row = json.loads(working_lines[0])
    assert row["findings"] == expected_findings
    assert row["rework"] == rework
    assert row["signal"] == "stopped"
    assert row["outcome"] == "stopped"


@pytest.mark.parametrize("outcome", ["merged", "shipped", "", "COMMITTED"])
def test_an_outcome_outside_the_three_words_is_refused(
    tmp_path: Path,
    outcome: str,
) -> None:
    # signal is the key the loop-metrics renderer buckets on, so a fourth word
    # invented at the call site becomes a silent bucket nobody reads. Refusing
    # it at the boundary is cheaper than finding it in a rendered report, and
    # the refusal has to leave the ledger untouched rather than record the bad
    # word and complain afterwards. The arms are the shapes a caller actually
    # produces: a near-synonym, a plausible alternative word, an empty string
    # from an unset shell variable, and the right word in the wrong case -
    # these are enum values, not a case-insensitive vocabulary.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(_card(tmp_path), started=int(time.time()), outcome=outcome),
    )

    assert result.returncode != 0
    assert result.stderr.strip() != ""
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()


@pytest.mark.parametrize("outcome", ["committed", "branched", "stopped"])
def test_every_accepted_outcome_word_lands_in_signal_and_outcome(
    tmp_path: Path,
    outcome: str,
) -> None:
    # The refusal above is only half the enum: a recorder that rejected
    # everything but its own favourite word would pass it, and a fast-track
    # item that stopped or branched would never make it into the ledger at all.
    # All three words are driven, and each one has to reach both keys - signal
    # for the renderer's buckets, outcome for the item-level word.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(_card(tmp_path), started=int(time.time()) - 8, outcome=outcome),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert working_lines == mirror_lines
    row = json.loads(working_lines[0])
    assert row["signal"] == outcome
    assert row["outcome"] == outcome


# A refused rework value no list can anticipate: taken from the clock at
# import, never 0 or 1, so a parser that blocklists the wrong values it has
# seen written down still lets this one through.
_UNLISTED_REWORK = int(time.time()) % 1000 + 2


@pytest.mark.parametrize("rework", [-1, 2, -7, 3, 100, _UNLISTED_REWORK])
def test_a_rework_count_outside_zero_or_one_is_refused(
    tmp_path: Path,
    rework: int,
) -> None:
    # rework is a one-bit fact - the item either took its single rework pass
    # or it did not - documented 0|1 and read that way by anyone summing the
    # column. A parser typed int and nothing more takes -1 and 2 just as
    # happily, and the ledger then carries a count no reader can interpret.
    # Refused the way a bad --outcome is: exit 2, argparse's own bad-choice
    # usage error naming the flag, the offending value and the legal ones,
    # and neither ledger touched. The arms are the nearest wrong value on
    # each side of the range, a far one on each side, and one no blocklist
    # written against this file can contain.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(_card(tmp_path), started=int(time.time()), rework=rework),
    )

    assert result.returncode == 2, result.stderr
    assert "--rework" in result.stderr
    assert "invalid choice" in result.stderr
    assert "choose from" in result.stderr
    assert str(rework) in result.stderr
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()
    assert not (autopilot_dir / "ledger" / _LEDGER_FILENAME).exists()


@pytest.mark.parametrize("rework", [0, 1])
def test_both_rework_values_are_accepted_and_land_as_integers(
    tmp_path: Path,
    rework: int,
) -> None:
    # The other half of the boundary: a guard tight enough to refuse 2 has to
    # take both legal values, and 0 is the one a truthiness check drops. The
    # bool check is there because True == 1 and a JSON `true` in the column
    # would pass the equality on its own.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(_card(tmp_path), started=int(time.time()) - 7, rework=rework),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert working_lines == mirror_lines
    row = json.loads(working_lines[0])
    assert row["rework"] == rework
    assert isinstance(row["rework"], int)
    assert not isinstance(row["rework"], bool)


@pytest.mark.parametrize("card_name", ["widget-slice.md", "other-thing.md"])
def test_prd_carries_whichever_card_basename_was_passed(
    tmp_path: Path,
    card_name: str,
) -> None:
    # prd is what every later reading of the ledger groups by, so it has to
    # come from --card rather than from anywhere else. Two differently named
    # cards, because one name cannot tell a basename apart from a constant, and
    # the card's full path is asserted absent from the whole row: it is a
    # tmp_path that means nothing to a reader a week later, and stored in any
    # column it turns the ledger into a machine-specific artefact.
    autopilot_dir = _autopilot_tree(tmp_path)
    card = _card(tmp_path, name=card_name)

    result = _run_cli(tmp_path, _cli_args(card, started=int(time.time()) - 3))

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert working_lines == mirror_lines
    row = json.loads(working_lines[0])
    assert row["prd"] == card_name
    assert str(card) not in working_lines[0]


@pytest.mark.parametrize(
    ("flag_value", "expected"),
    [("2.5", 2.5), ("0", 0.0), ("13.75", 13.75)],
)
def test_the_cost_flag_lands_as_the_number_it_was_given(
    tmp_path: Path,
    flag_value: str,
    expected: float,
) -> None:
    # The column is summed across a batch, so the row has to carry the number
    # that was measured and not a stand-in for "a cost was passed". The 0 arm
    # is the one that matters twice over: a free item and an unmeasured item
    # are different facts, and 0.0 is the value most likely to be flattened
    # back into null by an implementation testing the flag for truthiness.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(_card(tmp_path), started=int(time.time()) - 4, cost=flag_value),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert working_lines == mirror_lines
    row = json.loads(working_lines[0])
    assert row["cost_usd"] == expected
    assert isinstance(row["cost_usd"], float)


def test_a_findings_payload_never_seen_before_is_stored_verbatim(
    tmp_path: Path,
) -> None:
    # The recorder does not reshape findings, and the shapes above are the ones
    # a reviewer roster happens to produce today. This payload is built fresh
    # per run around a uuid, so it cannot be recognised, mapped or defaulted -
    # only parsed and stored. Nested, because a copy that survives one level
    # deep can still lose the level below it.
    autopilot_dir = _autopilot_tree(tmp_path)
    payload = {
        "HIGH": 1,
        "marker": str(uuid.uuid4()),
        "raised_by": {"reviewer": "eve", "at": int(time.time())},
    }

    result = _run_cli(
        tmp_path,
        _cli_args(
            _card(tmp_path),
            started=int(time.time()) - 6,
            findings=json.dumps(payload),
        ),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert working_lines == mirror_lines
    assert json.loads(working_lines[0])["findings"] == payload


def test_a_run_from_a_nested_directory_lands_in_the_tree_root_ledger(
    tmp_path: Path,
) -> None:
    # The item's commands run wherever the operator happened to be standing,
    # which is rarely the repo root. A recorder that resolved its ledger
    # relative to the cwd would scatter one batch's rows across every directory
    # it was invoked from, each file plausible on its own, and the renderer
    # would read whichever one it found. So the row has to walk up to the tree
    # root, and nothing may be left behind where it was invoked.
    autopilot_dir = _autopilot_tree(tmp_path)
    nested = tmp_path / "src" / "widget" / "internals"
    nested.mkdir(parents=True)
    card = _card(tmp_path)

    result = _run_cli(
        nested,
        _cli_args(card, started=int(time.time()) - 11, model="haiku"),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert len(working_lines) == 1
    assert working_lines == mirror_lines
    assert json.loads(working_lines[0])["model"] == "haiku"
    assert list(nested.rglob("*")) == []


def test_no_autopilot_directory_anywhere_above_still_exits_zero(
    tmp_path: Path,
) -> None:
    # Telemetry never fails the item, and a tree with nowhere to write is the
    # cheapest way to be sure: an item run outside a repo, or before the
    # directory exists, still finishes. The marker rides in findings so this
    # test can also prove the negative that matters most - a recorder that
    # walked up from the script's own location instead of the cwd would find
    # this repo's real ledger and quietly append a test row to it.
    marker = str(uuid.uuid4())

    result = _run_cli(
        tmp_path,
        _cli_args(
            _card(tmp_path),
            started=int(time.time()) - 2,
            findings=json.dumps({"marker": marker}),
        ),
    )

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert list(tmp_path.rglob(_LEDGER_FILENAME)) == []
    landed = _REPO_LEDGER.read_text(encoding="utf-8") if _REPO_LEDGER.is_file() else ""
    assert marker not in landed, f"this test's row landed in {_REPO_LEDGER}"


def test_the_item_name_reaches_no_column_of_the_row(tmp_path: Path) -> None:
    # --item names the item for the caller's own bookkeeping and the row
    # deliberately carries no item key: the ledger is keyed by prd. Two runs
    # differing in nothing else produce rows that match key for key once the
    # clock is set aside, so an implementation cannot quietly smuggle the value
    # into prd, model or findings and still look like it dropped it.
    autopilot_dir = _autopilot_tree(tmp_path)
    card = _card(tmp_path)
    started = int(time.time()) - 45

    first = _run_cli(tmp_path, _cli_args(card, started=started, item="widget-slice"))
    second = _run_cli(tmp_path, _cli_args(card, started=started, item="other-item"))

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    working_lines, mirror_lines = _ledger_lines(autopilot_dir)
    assert len(working_lines) == 2
    assert working_lines == mirror_lines
    rows = [json.loads(line) for line in working_lines]
    for row in rows:
        del row["ts_end"], row["wall_secs"]
    assert rows[0] == rows[1]


@pytest.mark.parametrize("flag", _REQUIRED_FLAGS)
def test_a_missing_required_flag_is_refused_and_writes_nothing(
    tmp_path: Path,
    flag: str,
) -> None:
    # Every flag but --cost is required, and each one is a column of the row.
    # A recorder that defaulted any of them writes a plausible row carrying a
    # made-up model, a zero start time or an empty findings value, and the
    # ledger cannot tell that apart from a measurement. Each arm drops exactly
    # one flag, so a parser that guards some of them fails the rest.
    autopilot_dir = _autopilot_tree(tmp_path)
    args = _cli_args(_card(tmp_path), started=int(time.time()))

    result = _run_cli(tmp_path, _without(args, flag))

    assert result.returncode != 0
    assert result.stderr.strip() != ""
    assert not (autopilot_dir / _LEDGER_FILENAME).exists()
