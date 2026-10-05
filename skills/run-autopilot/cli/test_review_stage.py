#!/usr/bin/env python3
"""Tests for cli/review_stage.stage() (PRD 00249 task 2).

gather-context.sh, compute_mech_facts.py, detect_tautological_tests.py and
record_dispatch.py run for real against a tiny git repo in tmp_path: the
point is to bind the real CLI shapes stage() consumes. Two collaborators are
swapped for fakes through module constants, because the real ones are slow
or external: replay_tests_against_base.py (a recorder script that captures
its argv) and `engram` (a fake executable, or a name that resolves nowhere).
Tests that only need stage()'s wiring replace render_roster with a writer
that records which personas stage() handed it.

The render_roster tests (PRD 00249 task 3) run the real render_prompt.py and
compare every prompt byte for byte against fixtures/*-prompt-00244c1.md. The
alice/bob/blake/carl goldens are the real hand-assembled 00244c1 prompts with
three recorded deltas: the hand-added "The project root is ..." line is gone
(no persona or table declares it), the repo root reads @ROOT@, and Bob's doubt
appendix gains eve.md's FIX/VERIFY/KNOWN section and the trailing "Do not
modify" paragraph of the "Rubric verdicts" section (PRD 00249 requires the
bucket section). No Eve prompt exists for that cycle: eve-prompt-00244c1.md is
hand-built from agents/eve.md and agent-invocation.md's five run inputs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cli import review_stage

GATE = "echo 'PASS 3 FAIL 0 SKIP 1 EXIT 0'"
REPLAY = "uv run --no-project --with pytest python -m pytest"
CYCLE = "00001-c1"
AUTOPILOT_REL = Path("docs/dev/project-management/autopilot")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str]) -> str:
    for rel, body in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        _git(repo, "add", "--", rel)
    _git(repo, "commit", "--no-verify", "-q", "-m", "change")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    base = _commit(repo, {"README.md": "hi\n", ".gitignore": "docs/dev/tmp/\n"})
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(
        repo,
        {
            "src/calc.py": "def add(a, b):\n    return a + b\n",
            "tests/test_calc.py": "def test_add():\n    assert 1 + 2 == 3\n",
        },
    )
    (repo / AUTOPILOT_REL).mkdir(parents=True)

    prd = tmp_path / "00001-calc-v1.md"
    prd.write_text("# PRD 00001\n\nPRD-BODY-MARKER: add two numbers.\n")
    design = tmp_path / "design.md"
    design.write_text("DESIGN-MARKER: one function.\n")
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            [
                {
                    "cycle": 1,
                    "disposition": "settled-deferral",
                    "severity": "low",
                    "issue": "LEDGER-ISSUE-MARKER",
                    "file": "src/calc.py:1",
                    "reason": "accepted",
                },
            ],
        ),
    )

    # replay_tests_against_base.py stand-in: records its argv, prints a block.
    replay_log = tmp_path / "replay-argv.json"
    fake_replay = tmp_path / "fake_replay.py"
    fake_replay.write_text(
        "import json, sys\n"
        f"open({str(replay_log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        "print('## Replay against base (computed)\\nREPLAY-MARKER')\n",
    )
    monkeypatch.setattr(review_stage, "REPLAY_SCRIPT", fake_replay)

    # engram stand-in that succeeds: writes the pack where the skill expects it.
    fake_engram = tmp_path / "bin" / "engram"
    fake_engram.parent.mkdir()
    fake_engram.write_text(
        "#!/bin/sh\n"
        'pack="$PWD/docs/dev/tmp/engram-pack-$3.md"\n'
        'mkdir -p "$(dirname "$pack")"\n'
        "printf '# Pack\\n\\n## Findings precedent\\n\\nPRECEDENT-MARKER\\n' > \"$pack\"\n"
        'echo "$pack"\n',
    )
    fake_engram.chmod(0o755)
    monkeypatch.setattr(review_stage, "ENGRAM", str(fake_engram))

    return {
        "repo": repo,
        "base": base,
        "prd": prd,
        "design": design,
        "ledger": ledger,
        "replay_log": replay_log,
        "tmp": tmp_path,
    }


TASKS = [
    {
        "id": "1",
        "name": "Add calc",
        "status": "completed",
        "description": "adds add()",
        "commit": "abc1234",
    },
    {
        "id": "2",
        "name": "Test calc",
        "status": "completed",
        "commit": "abc1234",
        "companions": ["1"],
    },
]


def _stage(env: dict, **overrides) -> dict:
    kwargs = {
        "cycle_id": CYCLE,
        "tasks": TASKS,
        "prd_path": env["prd"],
        "design_doc": env["design"],
        "roster": ["alice", "bob", "blake", "carl"],
        "repo_root": env["repo"],
        "gate_command": GATE,
        "replay_cmd": REPLAY,
        "settled_ledger": env["ledger"],
    }
    kwargs.update(overrides)
    return review_stage.stage(**kwargs)


def _prompt_writer(seen: list[list[str]]):
    """A render_roster replacement that writes one prompt file per persona."""

    def fake(
        context_file,
        diff_file,
        prd_file,
        pack_file,
        settled_ledger,
        prior_findings,
        roster,
    ):
        seen.append(list(roster))
        out = {}
        for name in roster:
            path = Path(context_file).parent / f"{name}-prompt-test.md"
            path.write_text(f"prompt for {name}\n")
            out[name] = path
        return out

    return fake


def test_stage_writes_every_input_file(env: dict) -> None:
    summary = _stage(env)

    assert summary["ok"] is True
    json.dumps(summary)  # the summary is the CLI's stdout line: must serialize
    tasks_md = Path(summary["tasks_file"]).read_text()
    rows = [
        line
        for line in tasks_md.splitlines()
        if line.startswith("| 1 ") or line.startswith("| 2 ")
    ]
    assert len(rows) == 2, tasks_md  # one row per task, folded task not merged
    assert "abc1234" in rows[0] and "abc1234" in rows[1]
    assert "1" in rows[1].split("|")[-2]  # companion id named on the folded row

    prd_md = Path(summary["prd_file"]).read_text()
    assert "PRD-BODY-MARKER" in prd_md
    assert prd_md.index("## Design Doc") < prd_md.index("DESIGN-MARKER")

    assert Path(summary["diff_file"]).name == f"review-diff-{CYCLE}.diff"
    assert "src/calc.py" in Path(summary["diff_file"]).read_text()

    context = Path(summary["context_file"]).read_text()
    assert Path(summary["context_file"]).name == f"review-context-{CYCLE}.md"
    ordered = [
        "## Completed Tasks",
        "## Mechanical facts (computed, do not re-count)",
        "## Tautological test shapes (computed, do not re-judge)",
        "REPLAY-MARKER",
        "## Settled decisions — do not re-raise",
        "LEDGER-ISSUE-MARKER",
        "PRECEDENT-MARKER",
        "Tests: 3 passed, 0 failed, 1 skipped (suite run this cycle)",
    ]
    positions = [context.index(marker) for marker in ordered]
    assert positions == sorted(positions), context
    # the mech-facts block measured the changed source file
    assert "src/calc.py" in context.split("## Mechanical facts")[1]

    assert summary["pack"] == "ok"
    assert summary["gate"] == {
        "verdict": "stale",
        "tests_line": "Tests: 3 passed, 0 failed, 1 skipped (suite run this cycle)",
        "timed_out": False,
    }
    assert summary["mode"] == "standalone"
    assert set(summary["prompts"]) == {"alice", "bob", "blake", "carl"}
    assert isinstance(summary["elapsed_s"], float)


@pytest.mark.parametrize(
    "engram_body, reason_fragment",
    [
        (None, "failed ("),
        (
            "#!/bin/sh\n"
            "echo 'engram: not inside a registered repo; register it in repos.csv' >&2\n"
            "exit 1\n",
            "gita add",
        ),
        ("#!/bin/sh\nexit 0\n", "no pack file"),
    ],
    ids=["missing-binary", "unregistered-repo", "no-pack-written"],
)
def test_stage_survives_pack_failure(
    env: dict,
    monkeypatch: pytest.MonkeyPatch,
    engram_body: str | None,
    reason_fragment: str,
) -> None:
    if engram_body is None:
        monkeypatch.setattr(review_stage, "ENGRAM", "engram-absent-from-every-path-xyz")
    else:
        broken = env["tmp"] / "bin" / "engram-broken"
        broken.write_text(engram_body)
        broken.chmod(0o755)
        monkeypatch.setattr(review_stage, "ENGRAM", str(broken))

    summary = _stage(env)

    assert summary["ok"] is True
    assert summary["pack"].startswith("failed (")
    assert reason_fragment in summary["pack"]
    context = Path(summary["context_file"]).read_text()
    assert "(no pack available this cycle)" in context
    # the stage kept going past the pack: the gate still ran
    assert summary["gate"]["tests_line"].startswith("Tests: 3 passed")


def test_stage_stamps_roster_and_opens_cli_rows(
    env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = env["repo"] / AUTOPILOT_REL / "state.json"
    state_path.write_text(
        json.dumps(
            {"phase": "review", "tasks": [], "review_lenses": {"fable": "done"}}
        ),
    )
    seen: list[list[str]] = []
    monkeypatch.setattr(review_stage, "render_roster", _prompt_writer(seen))

    summary = _stage(env, state_path=state_path)

    assert summary["mode"] == "autopilot"
    state = json.loads(state_path.read_text())
    # full replace: the prior cycle's fable key is gone, siblings survive
    assert state["review_lenses"] == {
        "consensus": "running",
        "blind": "running",
        "doubt": "running",
        "ui": "running",
    }
    assert state["phase"] == "review"

    rows = [
        json.loads(line)
        for line in (env["repo"] / AUTOPILOT_REL / "dispatch-metrics.jsonl")
        .read_text()
        .splitlines()
    ]
    starts = {row["kind"]: row for row in rows if "queued_at" in row}
    assert set(starts) == {"bob", "carl"}  # CLI reviewers only
    assert all(row["task"] == f"review-{CYCLE}" for row in starts.values())
    assert summary["dispatch_rows"] == {
        "bob": starts["bob"]["id"],
        "carl": starts["carl"]["id"],
    }
    assert starts["bob"]["prompt_bytes"] == len("prompt for bob\n")


def test_stage_stamps_doubt_and_fable_when_eve_joins(
    env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = env["repo"] / AUTOPILOT_REL / "state.json"
    state_path.write_text(json.dumps({"phase": "review", "tasks": []}))
    monkeypatch.setattr(review_stage, "render_roster", _prompt_writer([]))

    _stage(env, state_path=state_path, roster=["alice", "blake", "eve"])

    lenses = json.loads(state_path.read_text())["review_lenses"]
    assert lenses == {
        "consensus": "running",
        "blind": "running",
        "doubt": "running",
        "fable": "running",
    }


def test_stage_standalone_mode_skips_state_write(
    env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = env["repo"] / AUTOPILOT_REL / "state.json"
    state_path.write_text(json.dumps({"phase": "review", "tasks": []}))
    before = state_path.read_bytes()
    monkeypatch.setattr(review_stage, "render_roster", _prompt_writer([]))

    summary = _stage(env)  # no state_path: standalone

    assert summary["mode"] == "standalone"
    assert state_path.read_bytes() == before
    assert not (env["repo"] / AUTOPILOT_REL / "dispatch-metrics.jsonl").exists()
    assert summary["dispatch_rows"] == {"bob": None, "carl": None}
    # steps 1-8 still ran: prompts came back from render_roster
    assert summary["prompts"]["bob"] is not None


def test_blake_prompt_excludes_the_design_doc_appended_to_the_staged_prd(
    env: dict,
) -> None:
    summary = _stage(env)

    blake_prompt = Path(summary["prompts"]["blake"]).read_text()
    assert "PRD-BODY-MARKER" in blake_prompt
    assert "DESIGN-MARKER" not in blake_prompt


def test_eve_gets_raw_prd_only(env: dict) -> None:
    summary = _stage(env, roster=["alice", "eve"])

    eve_prompt = Path(summary["prompts"]["eve"]).read_text()
    assert "PRD-BODY-MARKER" in eve_prompt
    assert "DESIGN-MARKER" not in eve_prompt


def test_replay_uses_gather_context_base(env: dict) -> None:
    # One resolver (PRD 00256): the replay base is whatever gather-context.sh
    # itself recorded in the context file's `_Diff scope:` line -- not a
    # second, independently-derived merge-base. resolve_base() no longer
    # exists as a symbol in the module.
    assert not hasattr(review_stage, "resolve_base")
    since = env["base"]
    summary = _stage(env, since=since)

    argv = json.loads(env["replay_log"].read_text())
    assert argv[:2] == ["--base", since]
    context_text = Path(summary["context_file"]).read_text()
    assert f"changes since {since}" in context_text


def test_stage_wires_prior_findings_into_render_roster(
    env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    def fake_render_roster(
        context_file,
        diff_file,
        prd_file,
        pack_file,
        settled_ledger,
        prior_findings,
        roster,
    ):
        seen.append(prior_findings)
        out = {}
        for name in roster:
            path = Path(context_file).parent / f"{name}-prompt-test.md"
            path.write_text(f"prompt for {name}\n")
            out[name] = path
        return out

    monkeypatch.setattr(review_stage, "render_roster", fake_render_roster)
    prior = env["tmp"] / "prior-findings.md"
    prior.write_text("PRIOR-FINDING-MARKER\n")

    summary = _stage(env, prior_findings=prior)

    assert seen == [prior]
    assert summary["ok"] is True


def test_persona_preflight_fails_closed_on_malformed_frontmatter(
    env: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agents = env["tmp"] / "agents"
    agents.mkdir()
    (agents / "alice.md").write_text(
        "---\nname: alice\ndescription: consensus\ntools: Read, Bash\n---\nbody\n",
    )
    (agents / "blake.md").write_text("no frontmatter at all\n")
    (agents / "carl.md").write_text("---\nname: carl\ndescription: ui\n---\nbody\n")
    (agents / "eve.md").write_text("---\nname: eve\ndescription: doubt\ntools: Read\n")
    (agents / "dana.md").write_text(
        "---\nname: dana\ndescription:\ntools: Read\n---\nbody\n",
    )
    # bob.md deliberately absent
    monkeypatch.setattr(review_stage, "AGENTS_DIR", agents)
    seen: list[list[str]] = []
    monkeypatch.setattr(review_stage, "render_roster", _prompt_writer(seen))

    summary = _stage(env, roster=["alice", "bob", "blake", "carl", "eve", "dana"])

    assert seen == [["alice"]]  # failed personas never reach render_roster
    prompts = summary["prompts"]
    assert prompts["alice"] is not None
    for failed in ("bob", "blake", "carl", "eve", "dana"):
        assert prompts[failed] is None, failed


# Passes against the pre-change code too: `env["base"]` is a sha that is
# already HEAD's direct ancestor (the fixture never moves the branch tip),
# so merge-base(HEAD, base) == base trivially -- this fixture can't tell the
# merge-base step apart from using the recorded base as-is. The sibling test
# below (a branch NAME whose tip actually moves) is the one that pins it.
def test_replay_cmd_never_receives_gate_command(env: dict) -> None:
    summary = _stage(env)

    argv = json.loads(env["replay_log"].read_text())
    # The base is read from gather-context.sh's own recorded `_Diff scope:`
    # line (the one resolver, PRD 00256) -- for a full review that is the
    # base branch NAME it found ("master"), resolved to its merge-base with HEAD.
    assert argv == ["--base", env["base"], "--cmd", REPLAY]
    assert GATE not in argv
    assert summary["ok"] is True

    # replay_cmd None skips the replay sub-step entirely
    env["replay_log"].unlink()
    skipped = _stage(env, cycle_id="00001-c2", replay_cmd=None)
    assert not env["replay_log"].exists()
    assert "REPLAY-MARKER" not in Path(skipped["context_file"]).read_text()


# Passes against the pre-change code too: the pre-PRD-00256 stage() called
# the old standalone resolve_base(), whose "merge-base of HEAD with origin/
# HEAD, then master" search independently lands on this fixture's same expected
# commit, for an unrelated reason (that resolver is gone; see the sibling test).
def test_replay_base_is_branch_point_when_scope_records_a_branch_name(
    env: dict,
) -> None:
    # Full review records the base branch NAME; the replay must start at the
    # branch point (merge-base), not at the moved tip of that branch.
    repo = env["repo"]
    _git(repo, "checkout", "-q", "master")
    _commit(repo, {"moved.txt": "base moved on\n"})
    _git(repo, "checkout", "-q", "feature")
    expected = _git(repo, "merge-base", "HEAD", "master")
    assert expected != _git(repo, "rev-parse", "master")

    _stage(env)

    argv = json.loads(env["replay_log"].read_text())
    assert argv[:2] == ["--base", expected]


def test_replay_base_follows_since(env: dict) -> None:
    since = _git(env["repo"], "rev-parse", "HEAD~1")
    _stage(env, since=since)

    argv = json.loads(env["replay_log"].read_text())
    assert argv[:2] == ["--base", since]


def test_stage_returns_gather_context_refusal_without_raising(env: dict) -> None:
    _git(env["repo"], "checkout", "-q", "master")  # clean HEAD on base: empty diff

    summary = _stage(env)

    assert summary["ok"] is False
    assert "empty diff" in summary["error"]
    assert not env["replay_log"].exists()


FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_ID = "00244c1"
GOLDEN_ROSTER = ["alice", "bob", "blake", "carl"]  # the 00244c1 roster: no Eve


@pytest.fixture
def golden(tmp_path: Path) -> dict:
    """The staged inputs of cycle 00244c1, laid out the way stage() leaves them."""
    root = tmp_path / "proj"
    tmp = root / "docs" / "dev" / "tmp"
    tmp.mkdir(parents=True)
    staged = {}
    for key, name in (
        ("context", f"review-context-{GOLDEN_ID}.md"),
        ("diff", f"review-diff-{GOLDEN_ID}.diff"),
        ("prd", f"review-prd-{GOLDEN_ID}.md"),
        ("pack", f"engram-pack-{GOLDEN_ID}.md"),
    ):
        staged[key] = tmp / name
        shutil.copyfile(FIXTURES / name, staged[key])
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            [
                {
                    "disposition": "settled-deferral",
                    "severity": "low",
                    "issue": "LEDGER-ISSUE-MARKER",
                    "file": "src/calc.py:1",
                    "reason": "accepted",
                },
            ],
        ),
    )
    prior = tmp_path / "prior-findings.md"
    prior.write_text("| [2/3] | 🟠 High | PRIOR-FINDING-MARKER | src/calc.py |\n")
    return {"root": root, "ledger": ledger, "prior": prior, **staged}


def _render(golden: dict, roster: list[str], **inputs) -> dict:
    return review_stage.render_roster(
        golden["context"],
        golden["diff"],
        golden["prd"],
        inputs.get("pack"),
        inputs.get("ledger"),
        inputs.get("prior"),
        roster,
    )


def _assert_golden(golden: dict, name: str, rendered: dict) -> None:
    out = golden["context"].parent / f"{name}-prompt-{GOLDEN_ID}.md"
    assert rendered[name] == out
    expected = (FIXTURES / f"{name}-prompt-{GOLDEN_ID}.md").read_text()
    assert out.read_text() == expected.replace("@ROOT@", str(golden["root"]))


def test_render_matches_golden_alice(golden: dict) -> None:
    _assert_golden(golden, "alice", _render(golden, GOLDEN_ROSTER))


def test_render_matches_golden_bob(golden: dict) -> None:
    _assert_golden(golden, "bob", _render(golden, GOLDEN_ROSTER))


def test_render_matches_golden_blake(golden: dict) -> None:
    _assert_golden(golden, "blake", _render(golden, GOLDEN_ROSTER))


def test_render_matches_golden_carl(golden: dict) -> None:
    _assert_golden(golden, "carl", _render(golden, GOLDEN_ROSTER))


def test_render_matches_golden_eve(golden: dict) -> None:
    rendered = _render(golden, ["alice", "blake", "eve"], pack=golden["pack"])
    _assert_golden(golden, "eve", rendered)


def test_blake_prompt_carries_no_diff_or_ledger(golden: dict) -> None:
    rendered = _render(
        golden,
        ["alice", "blake"],
        pack=golden["pack"],
        ledger=golden["ledger"],
        prior=golden["prior"],
    )

    alice = rendered["alice"].read_text()
    blake = rendered["blake"].read_text()
    # the same markers do reach an implementation-aware prompt
    assert "LEDGER-ISSUE-MARKER" in alice
    assert "PRIOR-FINDING-MARKER" in alice
    assert str(golden["diff"]) in alice
    for leak in (
        str(golden["diff"]),
        str(golden["context"]),
        str(golden["pack"]),
        "DIFF-BODY-MARKER",
        "skills/run-autopilot/cli/enter_io.py",
        "LEDGER-ISSUE-MARKER",
        review_stage.SETTLED_HEADING,
        "PRIOR-FINDING-MARKER",
        "This is an **incremental review**",
        "Findings precedent",
    ):
        assert leak not in blake, leak
    assert "Tidy the enter verb and the review diff plumbing" in blake


def test_blake_prompt_includes_output_format(golden: dict) -> None:
    blake = _render(golden, ["blake"])["blake"].read_text()

    assert "{OUTPUT_FORMAT}" not in blake
    formats = (
        review_stage._SKILLS
        / "review-work-completion"
        / "references"
        / "output-formats.md"
    ).read_text()
    head = "## Agent Output Format (Single Source of Truth)"
    section = formats[formats.index(head) : formats.index("## Per-Rule Verdict Format")]
    assert section.strip() in blake
    assert "Your agent name is BLAKE." in blake
    # in its slot: after the mandatory-format line, before the verdict rules
    assert (
        blake.index("OUTPUT FORMAT IS MANDATORY")
        < blake.index(head)
        < blake.index("PER-RULE VERDICTS ARE MANDATORY")
    )


def test_bob_doubt_prompt_includes_eve_sections(golden: dict) -> None:
    eve = (review_stage.AGENTS_DIR / "eve.md").read_text()
    precedent = "- 00236 review: `diff_signal` missed the store in a bare-repo layout."
    sections = [
        eve[eve.index("## Two lenses") : eve.index("## Categorize")].strip(),
        eve[eve.index("## Categorize") : eve.index("## Rubric verdicts")].strip(),
        eve[eve.index("## Rubric verdicts") :].strip(),
    ]

    bob = _render(golden, ["alice", "bob"], pack=golden["pack"])["bob"].read_text()

    for section in sections:
        assert section.replace("{PACK_FINDINGS}", precedent) in bob
    assert "FIX:\n" in bob and "D5: pass|fail" in bob
    assert bob.rstrip().endswith('never with a "(lines a-b)" suffix.')


def test_bob_keeps_doubt_appendix_when_eve_rostered(golden: dict) -> None:
    # PRD 00256: Bob's doubt appendix survives Eve -- it is no longer gated
    # off when Eve is also on the roster. Both carry the doubt lens.
    with_eve = _render(golden, ["bob", "eve"], pack=golden["pack"])
    bob_with_eve = with_eve["bob"].read_text()
    assert "## Two lenses" in bob_with_eve
    assert "D1:" in bob_with_eve and "D5: pass|fail" in bob_with_eve
    assert "## Two lenses" in with_eve["eve"].read_text()


def test_incremental_cycle_reaches_every_persona_but_blake(golden: dict) -> None:
    roster = ["alice", "bob", "blake", "carl", "eve"]

    rendered = _render(
        golden,
        roster,
        ledger=golden["ledger"],
        prior=golden["prior"],
    )

    for name in ("alice", "bob", "carl", "eve"):
        text = rendered[name].read_text()
        assert "This is an **incremental review**" in text, name
        assert "PRIOR-FINDING-MARKER" in text, name
        assert review_stage.SETTLED_HEADING in text, name
        assert "LEDGER-ISSUE-MARKER" in text, name
    blake = rendered["blake"].read_text()
    assert "This is an **incremental review**" not in blake
    assert "PRIOR-FINDING-MARKER" not in blake


def test_failed_render_marks_only_that_persona_none(
    golden: dict,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agents = tmp_path / "agents"
    shutil.copytree(review_stage.AGENTS_DIR, agents)
    with open(agents / "carl.md", "a", encoding="utf-8") as fh:
        fh.write("\n{NEVER_SUPPLIED}\n")  # render_prompt.py exits 1 on it
    monkeypatch.setattr(review_stage, "AGENTS_DIR", agents)

    rendered = _render(golden, GOLDEN_ROSTER)

    assert rendered["carl"] is None
    assert not (golden["context"].parent / f"carl-prompt-{GOLDEN_ID}.md").exists()
    for name in ("alice", "bob", "blake"):
        assert rendered[name] is not None and rendered[name].is_file(), name


def test_blake_gets_filesystem_notes_only_when_the_store_is_a_symlink(
    golden: dict,
    tmp_path: Path,
) -> None:
    plain = _render(golden, ["blake"])["blake"].read_text()
    assert "## Filesystem notes" not in plain

    real_store = tmp_path / "real-store"
    real_store.mkdir()
    (golden["root"] / "docs" / "dev" / "project-management").symlink_to(real_store)

    blake = _render(golden, ["blake"])["blake"].read_text()

    notes = blake[blake.index("## Filesystem notes") :]
    assert f"Project root: {golden['root']}" in notes
    assert f"`docs/dev/project-management` realpath: {real_store.resolve()}" in notes
    assert "`rg --files` does not descend into dot-directories" in notes


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
