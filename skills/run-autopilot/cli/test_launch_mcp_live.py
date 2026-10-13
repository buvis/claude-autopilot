"""Live test for the loop's MCP launch restriction (task
00284-loop-launch-context-v1-c1, PRD 00281 F7/F9).

Exercises `build_argv`'s `mcp_config` kwarg together with `mcp_config_for`
against the real `claude` binary: a loop launch should load only Context7 by
default, and an `_AUTOPILOT_MCP_CONFIG` override should scope it further. The
assertion reads the `mcp_servers` entries' `name` values off the `system`/
`init` stream event only -- never `status` -- so an unreachable Context7
endpoint cannot red this test; the session still starts without it, exactly
as the connector being down today behaves.

Skipped unless AUTOPILOT_LIVE=1, so the default suite never spends money or
needs the network.

The child env strips `_AUTOPILOT_LOOP` and sets `CLAUDE_NESTED=1` and
`_CLAUDE_NOTIFY_QUIET=1`, exactly as skills/use-sonnet/scripts/sonnet-run.sh
lines 16-33 do, so this nested session can never write the loop's signal
file.
"""

from __future__ import annotations

import json
import os
import subprocess

import pytest

from cli.runner import build_argv, mcp_config_for

LIVE = os.environ.get("AUTOPILOT_LIVE") == "1"
SKIP_REASON = "live claude CLI call: set AUTOPILOT_LIVE=1 to run"


def _nested_env() -> dict:
    env = dict(os.environ)
    env.pop("_AUTOPILOT_LOOP", None)
    env["CLAUDE_NESTED"] = "1"
    env["_CLAUDE_NOTIFY_QUIET"] = "1"
    return env


def _mcp_server_names(env: dict) -> list[str]:
    argv = build_argv(
        "haiku", "low", None, mcp_config=mcp_config_for(env), prompt="reply ok"
    )
    argv = argv + ["--max-turns", "1"]
    proc = subprocess.run(
        argv,
        env=_nested_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            return [server["name"] for server in event.get("mcp_servers", [])]
    raise AssertionError(
        f"no system/init event in stdout (exit {proc.returncode}): {proc.stdout!r}"
    )


@pytest.mark.skipif(not LIVE, reason=SKIP_REASON)
def test_default_launch_loads_only_context7():
    assert _mcp_server_names({}) == ["context7"]


@pytest.mark.skipif(not LIVE, reason=SKIP_REASON)
def test_override_launch_loads_no_servers():
    assert _mcp_server_names({"_AUTOPILOT_MCP_CONFIG": '{"mcpServers":{}}'}) == []
