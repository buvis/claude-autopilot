"""Tests for classify_tier.py - the /plan-tasks model-tier classifier.

The classifier is a pure function over a task's shape (its files, its prose,
its size) plus two risk flags, so every test calls it directly and asserts on
the returned dict. Fixtures that have to be "every path is a test path" or
"no path is a test path" are checked against the real ``is_test_path`` from
work_routing.py instead of against our idea of it: the classifier imports that
predicate, so a fixture that merely looks like test code would quietly stop
exercising the test_port arm.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("classify_tier.py")
_SPEC = importlib.util.spec_from_file_location("classify_tier", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
classify_tier = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(classify_tier)

_ROUTING_PATH = Path(__file__).parents[2] / "work" / "scripts" / "work_routing.py"
_ROUTING_SPEC = importlib.util.spec_from_file_location("work_routing", _ROUTING_PATH)
assert _ROUTING_SPEC is not None and _ROUTING_SPEC.loader is not None
work_routing = importlib.util.module_from_spec(_ROUTING_SPEC)
_ROUTING_SPEC.loader.exec_module(work_routing)

# The closed list of phrases that may buy a task the cheap tier. A tenth phrase
# would be a routing decision nobody made; a missing one silently overprices
# every task that says it.
_MECHANICAL_PHRASES = (
    "add log",
    "rename",
    "add test for",
    "port",
    "mirror",
    "inline",
    "extract constant",
    "update import",
    "bump version",
)


def _classify(
    files: list[str],
    text: str = "",
    lines_changed: int = 0,
    *,
    contract_edit: bool = False,
    algorithmic_risk: bool = False,
    default_model: str | None = None,
) -> dict:
    return classify_tier.classify(
        files=files,
        text=text,
        lines_changed=lines_changed,
        contract_edit=contract_edit,
        algorithmic_risk=algorithmic_risk,
        default_model=default_model,
    )


def _run_cli(
    tmp_path: Path,
    files: list[str],
    text: str,
    lines: int,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    files_file = tmp_path / "files.txt"
    files_file.write_text("\n".join(files) + "\n", encoding="utf-8")
    text_file = tmp_path / "text.txt"
    text_file.write_text(text + "\n", encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--files-file",
            str(files_file),
            "--text-file",
            str(text_file),
            "--lines",
            str(lines),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_slice_of_only_test_paths_is_a_sonnet_test_port() -> None:
    # One file, 10 lines, and the word "port" in the text: every mechanical
    # precondition is met, so this passes only if test_port is checked ahead of
    # the mechanical rule. Porting tests is cheap to type and expensive to get
    # wrong, which is why it is priced at sonnet rather than haiku.
    files = ["tests/test_x.py"]
    assert all(work_routing.is_test_path(path) for path in files)

    assert _classify(files, "port the concurrency tests", 10) == {
        "model": "sonnet",
        "tier_reason": "test_port",
    }


@pytest.mark.parametrize(
    "path",
    [
        "src/conftest.py",
        "pkg/foo_test.go",
        "web/a.spec.ts",
        "app/__tests__/util.js",
        # Two more that appear nowhere else in this file, so a classifier that
        # memorised the fixtures above (rather than calling the predicate)
        # cannot have them in its set.
        "lib/helpers_test.go",
        "tests/test_something_else.py",
    ],
)
def test_every_shape_the_shared_test_path_predicate_accepts_is_a_test_port(
    path: str,
) -> None:
    # Shapes the classifier's own fixtures never use: a pytest conftest, a Go
    # sibling test, a TypeScript spec, a JS file under a test directory. The
    # spec says the arm keys off work_routing.is_test_path, so anything that
    # predicate accepts routes here; a private check tuned to "tests/test_*.py"
    # returns sonnet/default for most of them.
    assert work_routing.is_test_path(path) is True

    assert _classify([path], "cover the new branch", 10) == {
        "model": "sonnet",
        "tier_reason": "test_port",
    }


def test_a_slice_mixing_test_paths_with_production_code_is_not_a_test_port() -> None:
    # The arm needs EVERY path in the slice to be a test path. One production
    # file means the task edits shipped code, and the slice is not
    # all-packaging-or-test either, so it falls through to the default tier.
    # An "any path is a test path" reading returns sonnet/test_port here.
    files = ["tests/test_x.py", "src/app.py"]
    assert work_routing.is_test_path(files[0]) is True
    assert work_routing.is_test_path(files[1]) is False

    assert _classify(files, "make the parser handle nested quotes", 10) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


@pytest.mark.parametrize(
    "files",
    [
        ["plugin.json", ".claude-plugin/marketplace.json"],
        ["pyproject.toml"],
        ["crates/core/Cargo.toml"],
        ["go.mod", "go.sum"],
    ],
)
def test_packaging_manifests_outrank_a_contract_edit(files: list[str]) -> None:
    # Manifests are declarative even when the planner flags them as a contract
    # edit, so the packaging arm has to win. If contract were checked first,
    # every row returns opus/contract. Four ecosystems, so an arm gated on one
    # literal filename passes at most the first row.
    assert not any(work_routing.is_test_path(path) for path in files)

    assert _classify(files, "bump the pinned manifests", 12, contract_edit=True) == {
        "model": "sonnet",
        "tier_reason": "packaging",
    }


@pytest.mark.parametrize(
    "path",
    [
        "plugin.json",
        "marketplace.json",
        "package.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "setup.py",
        "setup.cfg",
        "MANIFEST.in",
        "Pipfile",
        "Pipfile.lock",
        "Cargo.toml",
        "Cargo.lock",
        "go.mod",
        "go.sum",
        "mise.toml",
        ".mise.toml",
        ".tool-versions",
        "requirements.txt",
        "requirements-dev.txt",
        "nested/dir/pyproject.toml",
        ".claude-plugin/anything.md",
        "plugins/warden/.claude-plugin/notes.txt",
        # The same manifests again at depths nobody listed. Both rules are
        # positional, not literal: the basename rule ignores every directory
        # above it, and the `.claude-plugin` rule fires on any segment. A
        # predicate that memorised the paths above fails every row below.
        "frontend/package.json",
        "crates/core/Cargo.toml",
        "services/api/go.mod",
        "a/b/c/.mise.toml",
        "tools/py/requirements-test.txt",
        "vendor/pack/.claude-plugin/marketplace.json",
    ],
)
def test_is_packaging_path_accepts_every_named_manifest(path: str) -> None:
    # The list is closed and load-bearing: each entry is a file whose edit must
    # never buy an opus task on the strength of the prose around it.
    assert classify_tier.is_packaging_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "cli/schema.py",
        "src/plugin.py",
        "docs/requirements.md",
        "config/settings.json",
        "claude-plugin/notes.md",
        "src/cargo.rs",
        # A manifest name embedded in a longer basename. The rule is about the
        # basename and about whole path segments, so a bare substring scan
        # ("go.mod" appears somewhere in the string) accepts all three and
        # prices a backup, a doc, and a template as packaging work.
        "src/plugin.json.bak",
        "docs/notes-about-go.mod.md",
        "tests/fixtures/package.json.tmpl",
    ],
)
def test_is_packaging_path_rejects_ordinary_source_paths(path: str) -> None:
    # Near misses, on purpose: a `.md` next to a manifest name, a segment that
    # drops the leading dot, a basename that only shares a stem. Matching any
    # of these would let real logic changes slip into the packaging lane.
    assert classify_tier.is_packaging_path(path) is False


def test_a_contract_edit_routes_to_opus() -> None:
    result = _classify(
        ["cli/schema.py"],
        "widen the result schema",
        30,
        contract_edit=True,
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


def test_algorithmic_risk_routes_to_opus() -> None:
    result = _classify(
        ["cli/loop.py"],
        "fix the retry backoff",
        30,
        algorithmic_risk=True,
    )

    assert result == {"model": "opus", "tier_reason": "algorithmic_risk"}


def test_a_contract_edit_outranks_algorithmic_risk_when_both_are_flagged() -> None:
    # Both flags buy opus, so the tier hides the ordering and only the recorded
    # reason exposes it. The spec checks contract first, and the record is what
    # a later reader uses to know which risk paid for the tier.
    result = _classify(
        ["cli/x.py"],
        "",
        30,
        contract_edit=True,
        algorithmic_risk=True,
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


def test_a_small_mechanical_edit_is_haiku() -> None:
    assert _classify(["src/app.py"], "rename foo to bar", 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize("phrase", _MECHANICAL_PHRASES)
def test_every_mechanical_phrase_routes_to_haiku(phrase: str) -> None:
    # Parametrized over the whole list because a classifier that recognises
    # five of the nine still passes any single-phrase test.
    assert _classify(["src/app.py"], f"{phrase} in the parser module", 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize("phrase", _MECHANICAL_PHRASES)
@pytest.mark.parametrize(
    "carrier",
    [
        "before the release we {phrase}",
        "cleanup task: {phrase} across the two helpers, nothing else",
    ],
)
def test_a_mechanical_phrase_is_matched_anywhere_in_the_text(
    carrier: str,
    phrase: str,
) -> None:
    # The gate is a substring search over the whole lowercased text, not a
    # match against the sentence one earlier test happened to use. Here each
    # phrase ends the sentence once and sits mid-sentence once, so recognising
    # a fixed carrier string buys nothing.
    assert _classify(["src/app.py"], carrier.format(phrase=phrase), 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize(
    "text",
    [
        "Rename Foo To Bar",
        "BUMP VERSION TO 2.0",
        "Add Log lines around the retry",
        "InLiNe the tiny helper",
    ],
)
def test_a_mechanical_phrase_is_matched_case_insensitively(text: str) -> None:
    # Task titles arrive capitalised, shouted, and everything between; the
    # match runs on lowercased text, so four phrases in four casings all land.
    assert _classify(["src/app.py"], text, 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize(
    "text",
    [
        "make the parser handle nested quotes",
        # Near misses: each carries one bare word out of a two-word phrase
        # without the phrase itself. A gate loosened to "version", "log",
        # "constant", or "test" alone prices all four at haiku, and these are
        # exactly the tasks (a decision, a design, a refactor, a test suite)
        # that the cheap tier must not get.
        "the API version is stale, decide what to do",
        "improve the logging strategy for the scheduler",
        "extract the constant folding pass",
        "add tests for the new parser",
    ],
)
def test_text_without_a_mechanical_phrase_is_not_haiku(text: str) -> None:
    # Small and cheap-sounding is not enough: the phrase list is the whole gate.
    assert _classify(["src/app.py"], text, 10) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


@pytest.mark.parametrize(
    ("files", "lines_changed", "expected"),
    [
        (["a.py", "b.py"], 50, {"model": "haiku", "tier_reason": "mechanical"}),
        (["a.py", "b.py", "c.py"], 50, {"model": "sonnet", "tier_reason": "default"}),
        (["a.py", "b.py"], 51, {"model": "sonnet", "tier_reason": "default"}),
    ],
)
def test_the_mechanical_bounds_are_inclusive_at_two_files_and_fifty_lines(
    files: list[str],
    lines_changed: int,
    expected: dict,
) -> None:
    # Both bounds are "at or below". One off-by-one here either prices a real
    # refactor at haiku or denies the cheap tier to the edits it exists for.
    assert _classify(files, "rename foo to bar", lines_changed) == expected


@pytest.mark.parametrize("lines_changed", [0, 49, 50, 51, 200])
@pytest.mark.parametrize("file_count", [1, 2, 3, 4])
def test_the_cheap_tier_tracks_both_bounds_across_the_whole_range(
    file_count: int,
    lines_changed: int,
) -> None:
    # A sweep, not three named rows: every cell is derived from the rule
    # itself (at most two files AND at most fifty lines), so the two inputs
    # have to be counted and compared rather than recognised.
    files = [f"src/mod_{i}.py" for i in range(file_count)]
    cheap = file_count <= 2 and lines_changed <= 50
    expected = (
        {"model": "haiku", "tier_reason": "mechanical"}
        if cheap
        else {"model": "sonnet", "tier_reason": "default"}
    )

    assert _classify(files, "rename foo to bar", lines_changed) == expected


@pytest.mark.parametrize(
    ("files", "text", "lines_changed", "expected"),
    [
        (
            ["lib/util.rb"],
            "mirror the retry helper into the worker",
            8,
            {"model": "haiku", "tier_reason": "mechanical"},
        ),
        (
            ["docs/guide.md", "docs/index.md"],
            "update import paths in the guide",
            40,
            {"model": "haiku", "tier_reason": "mechanical"},
        ),
        (
            ["api/handler.go", "api/router.go", "api/middleware.go"],
            "extract constant for the timeout",
            12,
            {"model": "sonnet", "tier_reason": "default"},
        ),
        (
            ["web/render.ts"],
            "rewrite the layout engine",
            22,
            {"model": "sonnet", "tier_reason": "default"},
        ),
    ],
)
def test_fresh_task_shapes_classify_from_the_stated_rules(
    files: list[str],
    text: str,
    lines_changed: int,
    expected: dict,
) -> None:
    # Inputs that appear nowhere else in this file, in languages the other
    # fixtures never use. They are ordinary cases, not edges: the point is
    # that the rules answer them, so a lookup of the fixtures above cannot.
    assert _classify(files, text, lines_changed) == expected


def test_a_multi_file_design_task_is_the_sonnet_default() -> None:
    files = ["cache/store.py", "cache/keys.py", "cli/main.py"]

    assert _classify(files, "design and migrate the cache layer", 120) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


def test_a_nine_file_slice_is_never_mechanical() -> None:
    # Mechanical text, tiny diff, nine files. Breadth alone disqualifies it.
    files = [f"src/mod_{i}.py" for i in range(9)]

    assert _classify(files, "rename foo to bar", 10) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


def test_an_empty_slice_is_the_sonnet_default() -> None:
    # No files means no test_port and no packaging: an empty list must not be
    # read as "every path qualifies".
    assert _classify([], "", 0) == {"model": "sonnet", "tier_reason": "default"}


def test_a_higher_default_model_raises_the_tier_and_renames_the_reason() -> None:
    # The batch floor overrides the classification, and the record has to say
    # so: keeping "test_port" here would hide why the task ran on opus.
    result = _classify(
        ["tests/test_x.py"],
        "port the concurrency tests",
        10,
        default_model="opus",
    )

    assert result == {"model": "opus", "tier_reason": "floor"}


@pytest.mark.parametrize("default_model", ["haiku", "sonnet"])
def test_a_default_model_at_or_below_the_tier_changes_nothing(
    default_model: str,
) -> None:
    # A floor only lifts. Equal is not a raise, so the reason stays "default".
    result = _classify(
        ["cache/store.py", "cache/keys.py", "cli/main.py"],
        "design and migrate the cache layer",
        120,
        default_model=default_model,
    )

    assert result == {"model": "sonnet", "tier_reason": "default"}


def test_a_default_model_floor_lifts_haiku_to_sonnet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _classify(
        ["src/app.py"],
        "rename foo to bar",
        10,
        default_model="sonnet",
    )

    assert result == {"model": "sonnet", "tier_reason": "floor"}
    # A valid floor is routine, so it says nothing. Without this the stderr
    # assertion in the "fable" test passes on a classifier that warns on every
    # single call.
    assert capsys.readouterr().err == ""


def test_a_default_model_of_opus_leaves_an_opus_classification_alone() -> None:
    # The top of the ordering floored at the top of the ordering. Nothing was
    # raised, so nothing is renamed: recording "floor" here would erase the
    # real reason the task went to opus and make the floor look responsible.
    result = _classify(
        ["cli/schema.py"],
        "widen the result schema",
        30,
        contract_edit=True,
        default_model="opus",
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


def test_an_unknown_default_model_is_ignored_and_warned_about(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # "fable" is a real tier elsewhere but not in this ordering. Coercing it
    # silently would misprice every task in the batch, so the value is dropped
    # and the drop is announced on stderr.
    result = _classify(
        ["cache/store.py", "cache/keys.py", "cli/main.py"],
        "design and migrate the cache layer",
        120,
        default_model="fable",
    )

    captured = capsys.readouterr()
    assert result == {"model": "sonnet", "tier_reason": "default"}
    # The wording is free, but the dropped value has to be in it: a warning
    # that never names what it rejected leaves the operator hunting the batch
    # for a typo the classifier already found.
    assert "fable" in captured.err


@pytest.mark.parametrize(
    ("files", "text", "lines", "extra", "expected"),
    [
        (
            ["tests/test_x.py"],
            "port the concurrency tests",
            10,
            (),
            {"model": "sonnet", "tier_reason": "test_port"},
        ),
        (
            ["cli/schema.py"],
            "widen the result schema",
            30,
            ("--contract-edit",),
            {"model": "opus", "tier_reason": "contract"},
        ),
        (
            ["cli/loop.py"],
            "fix the retry backoff",
            30,
            ("--algorithmic-risk",),
            {"model": "opus", "tier_reason": "algorithmic_risk"},
        ),
        (
            ["src/app.py"],
            "rename foo to bar",
            10,
            ("--default-model", "opus"),
            {"model": "opus", "tier_reason": "floor"},
        ),
        (
            ["src/app.py"],
            "rename foo to bar",
            10,
            (),
            {"model": "haiku", "tier_reason": "mechanical"},
        ),
        (
            ["src/app.py"],
            "rename foo to bar",
            500,
            (),
            {"model": "sonnet", "tier_reason": "default"},
        ),
    ],
)
def test_the_cli_prints_the_classification_as_json_and_exits_zero(
    tmp_path: Path,
    files: list[str],
    text: str,
    lines: int,
    extra: tuple[str, ...],
    expected: dict,
) -> None:
    # The planner shells out to this and parses stdout, so the JSON shape is
    # the contract. The last two rows are the plumbing check: same production
    # file, no flags, so only --text-file can produce "mechanical" and only
    # --lines can take it away again. A CLI that passed an empty text through
    # fails the fifth row; one that hardcoded the line count fails the sixth.
    result = _run_cli(tmp_path, files, text, lines, *extra)

    assert result.returncode == 0
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("missing", ["--files-file", "--text-file"])
def test_the_cli_exits_one_when_an_input_file_cannot_be_read(
    tmp_path: Path,
    missing: str,
) -> None:
    # A planner that read "no files" from an unreadable list would classify
    # every task as sonnet/default and never say why, so this arm fails loud
    # with exit 1 and a plain message.
    present = "--text-file" if missing == "--files-file" else "--files-file"
    real = tmp_path / "real.txt"
    real.write_text("src/app.py\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            present,
            str(real),
            missing,
            str(tmp_path / "gone.txt"),
            "--lines",
            "10",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert "Traceback" not in result.stderr


def test_the_cli_exits_one_when_the_files_file_argument_is_absent(
    tmp_path: Path,
) -> None:
    # Omitting the flag entirely is the same failure as pointing it at nothing.
    text_file = tmp_path / "text.txt"
    text_file.write_text("rename foo to bar\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--text-file",
            str(text_file),
            "--lines",
            "10",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert "Traceback" not in result.stderr
