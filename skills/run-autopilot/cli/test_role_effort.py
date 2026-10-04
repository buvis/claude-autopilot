from pathlib import Path

import pytest

from cli.routing import route


@pytest.mark.parametrize("phase", ["", "build", "review", "done"])
def test_coordinator_defaults_to_low(phase: str, tmp_path: Path) -> None:
    assert route(phase, tmp_path, env={}).effort == "low"


def test_coordinator_override_is_not_a_worker_default(tmp_path: Path) -> None:
    assert (
        route("build", tmp_path, env={"_AUTOPILOT_COORDINATOR_EFFORT": "medium"}).effort
        == "medium"
    )
    agents = Path(__file__).resolve().parents[3] / "agents"
    assert "\neffort: high\n" in (agents / "worker-opus.md").read_text()
    assert "\neffort: high\n" in (agents / "alice.md").read_text()


def test_invalid_coordinator_effort_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="effort"):
        route("build", tmp_path, env={"_AUTOPILOT_COORDINATOR_EFFORT": "typo"})
