"""Tests for the sonnet-pinned test_port and packaging arms of classify_tier.py.

Split out of test_classify_tier.py (which grew past the repo's 800-line file
cap) into this and its sibling test_classify_tier_*.py modules; see
_classify_tier_test_support.py for the shared classify_tier/work_routing
bootstrap and the _classify helper every one of them calls. Fixtures that
have to be "every path is a test path" or "no path is a test path" are
checked against the real ``is_test_path`` from work_routing.py instead of
against our idea of it: the classifier imports that predicate, so a fixture
that merely looks like test code would quietly stop exercising the test_port
arm.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SUPPORT_PATH = Path(__file__).with_name("_classify_tier_test_support.py")
_SUPPORT_SPEC = importlib.util.spec_from_file_location(
    "classify_tier_test_support", _SUPPORT_PATH
)
assert _SUPPORT_SPEC is not None and _SUPPORT_SPEC.loader is not None
_support = importlib.util.module_from_spec(_SUPPORT_SPEC)
_SUPPORT_SPEC.loader.exec_module(_support)

classify_tier = _support.classify_tier
work_routing = _support.work_routing
_classify = _support._classify


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
    "files",
    [
        ["plugin.json", ".claude-plugin/marketplace.json"],
        ["pyproject.toml"],
        ["crates/core/Cargo.toml"],
        ["go.mod", "go.sum"],
    ],
)
def test_packaging_manifests_outrank_algorithmic_risk(files: list[str]) -> None:
    # Mirror of test_packaging_manifests_outrank_a_contract_edit: the packaging
    # arm has to beat the other risk flag too. If algorithmic_risk were checked
    # first, every row returns opus/algorithmic_risk instead.
    assert not any(work_routing.is_test_path(path) for path in files)

    result = _classify(files, "bump the pinned manifests", 12, algorithmic_risk=True)

    assert result == {"model": "sonnet", "tier_reason": "packaging"}


def test_a_slice_mixing_a_real_test_path_with_a_real_packaging_manifest_is_packaging() -> (
    None
):
    # Rule 2 is "every path is a test path OR a packaging path". Every existing
    # packaging fixture is packaging-only, so the OR across differing path
    # types is unpinned until a slice actually holds one of each kind, checked
    # against the real predicates rather than assumed.
    files = ["tests/test_x.py", "pyproject.toml"]
    assert work_routing.is_test_path(files[0]) is True
    assert not work_routing.is_test_path(files[1])
    assert classify_tier.is_packaging_path(files[1]) is True
    assert not classify_tier.is_packaging_path(files[0])

    result = _classify(files, "bump the pinned manifests", 12)

    assert result == {"model": "sonnet", "tier_reason": "packaging"}


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
