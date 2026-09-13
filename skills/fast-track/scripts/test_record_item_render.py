"""Producer-to-renderer tests for the fast-track cost column.

record_item.py writes `"cost_usd": null` when no --cost arrives, and the
render_metrics.py renderers are the only readers of that key. These tests
drive the real CLI, the real loader and both public renderers, so the
producer's spelling and the consumer's reading are checked against each other
rather than each against a fixture written by hand. The rest of the recorder's
contract lives in test_record_item.py.

Neither script is an installed package: render_metrics.py is loaded by path,
the same idiom test_card.py uses, and record_item.py runs as a subprocess.
Every CLI run is driven with `cwd=` inside a tmp_path tree carrying its own
dev/local/autopilot directory, so the walk-up lands there and no test appends
to this repo's own ledger.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name("record_item.py")
_RENDER_METRICS_PATH = (
    Path(__file__).resolve().parents[2] / "run-autopilot" / "cli" / "render_metrics.py"
)

# The consumer of these rows, loaded by path: the renderers are what the
# ledger exists for, and only a real row through the real loader can show
# whether the producer's spelling and the consumer's reading agree.
_RENDER_SPEC = importlib.util.spec_from_file_location(
    "autopilot_render_metrics",
    _RENDER_METRICS_PATH,
)
assert _RENDER_SPEC is not None and _RENDER_SPEC.loader is not None
_render_metrics = importlib.util.module_from_spec(_RENDER_SPEC)
sys.modules[_RENDER_SPEC.name] = _render_metrics
_RENDER_SPEC.loader.exec_module(_render_metrics)

_LEDGER_FILENAME = "loop-metrics.jsonl"


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


def _table_row(table: str, prefix: str) -> str:
    """The one line of a rendered markdown table that starts with prefix."""
    lines = [line for line in table.splitlines() if line.startswith(prefix)]
    assert len(lines) == 1, f"expected one {prefix!r} row in:\n{table}"
    return lines[0]


def test_cost_is_null_unless_passed(tmp_path: Path) -> None:
    # An attended fast-track session has no session log to read a cost out of,
    # so the recorder never guesses one - but the key still has to be there,
    # because a row missing it and a row costing nothing are different facts to
    # anyone summing the column. Asserting presence separately from the value
    # is what fails an implementation that simply omits the key when no --cost
    # arrives.
    without_root = tmp_path / "without-cost"
    without_root.mkdir()
    without_dir = _autopilot_tree(without_root)
    started = int(time.time()) - 30

    result = _run_cli(without_root, _cli_args(_card(without_root), started=started))

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(without_dir)
    assert working_lines == mirror_lines
    row = json.loads(working_lines[0])
    assert "cost_usd" in row
    assert row["cost_usd"] is None

    with_root = tmp_path / "with-cost"
    with_root.mkdir()
    with_dir = _autopilot_tree(with_root)

    result = _run_cli(
        with_root,
        _cli_args(_card(with_root), started=started, cost="1.25"),
    )

    assert result.returncode == 0, result.stderr
    working_lines, mirror_lines = _ledger_lines(with_dir)
    assert working_lines == mirror_lines
    priced = json.loads(working_lines[0])
    # 1.25, not "1.25": the column is summed, and a string sums to nothing.
    assert priced["cost_usd"] == 1.25
    assert isinstance(priced["cost_usd"], float)


def test_a_row_written_without_cost_renders_through_both_metrics_tables(
    tmp_path: Path,
) -> None:
    # The test above pins the producer to `"cost_usd": null` - key present,
    # value unknown - and the renderers are the only readers of that key. A
    # reader that filters costs by key presence lets the null into its sum and
    # both tables die with a TypeError the first time a fast-track row lands
    # in a real ledger, which no test of the producer alone can see. The
    # contract is decided on the consumer side: a null cost renders exactly
    # like an absent one, a blank cell between the pipes, never 0.00 (an
    # unmeasured item is not a free one) and never the word None. Driven end
    # to end - real CLI, real loader, both public renderers - so the two
    # scripts are checked against each other rather than each against a
    # fixture written by hand. The model cell is left unpinned: only the cost
    # cell is this test's business.
    autopilot_dir = _autopilot_tree(tmp_path)

    result = _run_cli(
        tmp_path,
        _cli_args(_card(tmp_path), started=int(time.time()) - 30),
    )

    assert result.returncode == 0, result.stderr
    rows = _render_metrics.load_rows(autopilot_dir / _LEDGER_FILENAME)
    assert len(rows) == 1
    assert rows[0]["cost_usd"] is None
    wall = rows[0]["wall_secs"]

    table = _render_metrics.phase_table(rows)
    summary = _render_metrics.render_metrics(rows)

    phase_row = _table_row(table, "| fast-track |")
    assert phase_row.startswith(f"| fast-track | 1 | {wall} |")
    assert phase_row.endswith("|  |")
    assert "0.00" not in table
    assert "None" not in table
    assert f"| widget-slice.md | 1 | {wall} |  |" in summary
    assert "0.00" not in summary
    assert "None" not in summary


def test_priced_and_unpriced_rows_render_the_priced_sum_alone(
    tmp_path: Path,
) -> None:
    # One batch mixes measured items and unmeasured ones, and they share a
    # phase and a prd, so they share a cost cell. That cell has to be the sum
    # of the priced rows, 3.75 - a null that crashes the sum loses the whole
    # table, and a null dropped from the group is what leaves the sum honest.
    # Two distinct prices, so the cell has to come from a real sum and not
    # from whichever priced row the renderer kept. A null coerced to zero
    # would sum to 3.75 here too, which is why the single unpriced row above
    # is pinned to a blank cell rather than to 0.00: the two tests hold the
    # contract between them.
    autopilot_dir = _autopilot_tree(tmp_path)
    card = _card(tmp_path)
    started = int(time.time()) - 20

    first = _run_cli(tmp_path, _cli_args(card, started=started, cost="1.25"))
    second = _run_cli(tmp_path, _cli_args(card, started=started, cost="2.50"))
    unpriced = _run_cli(tmp_path, _cli_args(card, started=started))

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert unpriced.returncode == 0, unpriced.stderr
    rows = _render_metrics.load_rows(autopilot_dir / _LEDGER_FILENAME)
    assert [row["cost_usd"] for row in rows] == [1.25, 2.50, None]
    wall = sum(row["wall_secs"] for row in rows)

    table = _render_metrics.phase_table(rows)
    summary = _render_metrics.render_metrics(rows)

    phase_row = _table_row(table, "| fast-track |")
    assert phase_row.startswith(f"| fast-track | 3 | {wall} |")
    assert phase_row.endswith("| 3.75 |")
    assert "1.25" not in table
    assert "2.50" not in table
    assert "0.00" not in table
    assert f"| widget-slice.md | 3 | {wall} | 3.75 |" in summary
    assert "1.25" not in summary
    assert "2.50" not in summary
    assert "0.00" not in summary


def test_a_free_item_renders_zero_not_blank_even_beside_an_unpriced_one(
    tmp_path: Path,
) -> None:
    # --cost 0 is a measurement (the item cost nothing) and no --cost is the
    # absence of one; the producer keeps them apart as 0.0 and null, and the
    # two tests above only ever hand the renderers a null or a non-zero price.
    # A renderer that drops costs by truthiness passes both of them and folds
    # every free item back into an unmeasured one. So a free row has to show
    # 0.00 on its own, and again beside an unpriced row in the same group:
    # the null leaves the sum, the zero stays in it.
    autopilot_dir = _autopilot_tree(tmp_path)
    card = _card(tmp_path)
    started = int(time.time()) - 15

    free = _run_cli(tmp_path, _cli_args(card, started=started, cost="0"))

    assert free.returncode == 0, free.stderr
    rows = _render_metrics.load_rows(autopilot_dir / _LEDGER_FILENAME)
    assert [row["cost_usd"] for row in rows] == [0.0]
    wall = rows[0]["wall_secs"]
    phase_row = _table_row(_render_metrics.phase_table(rows), "| fast-track |")
    assert phase_row.startswith(f"| fast-track | 1 | {wall} |")
    assert phase_row.endswith("| 0.00 |")
    summary = _render_metrics.render_metrics(rows)
    assert f"| widget-slice.md | 1 | {wall} | 0.00 |" in summary

    unpriced = _run_cli(tmp_path, _cli_args(card, started=started))

    assert unpriced.returncode == 0, unpriced.stderr
    rows = _render_metrics.load_rows(autopilot_dir / _LEDGER_FILENAME)
    assert [row["cost_usd"] for row in rows] == [0.0, None]
    wall = sum(row["wall_secs"] for row in rows)
    table = _render_metrics.phase_table(rows)
    summary = _render_metrics.render_metrics(rows)
    phase_row = _table_row(table, "| fast-track |")
    assert phase_row.startswith(f"| fast-track | 2 | {wall} |")
    assert phase_row.endswith("| 0.00 |")
    assert "None" not in table
    assert f"| widget-slice.md | 2 | {wall} | 0.00 |" in summary
    assert "None" not in summary
