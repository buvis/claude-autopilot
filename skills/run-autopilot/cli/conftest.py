"""Keep the operator's AUTOPILOT_WORKTREE_ROOT out of the suite: wave tests
assert the default beside-the-repo worktree layout unless they set it."""

import pytest


@pytest.fixture(autouse=True)
def _no_operator_worktree_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTOPILOT_WORKTREE_ROOT", raising=False)
