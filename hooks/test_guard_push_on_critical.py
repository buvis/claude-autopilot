"""Behavior tests for hooks/guard_push_on_critical.py, the PreToolUse Bash
push guard.

The guard denies (exit 2) a Bash `git push` whose target repository carries
pending cap_critical custody and allows (exit 0) everything else. The tables
below drive the exported parsing helpers; the `decide` / `run` tests work
against throwaway `git init` repositories (one seeded with a custody marker,
journal row and locator, one clean) through payload dicts. No test executes a
real push: the guard only inspects command text and custody state on disk.

Stdlib-only unittest, collected by pytest.
"""

from __future__ import annotations

import importlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
guard = importlib.import_module("guard_push_on_critical")

_HOOKS_JSON = _HOOKS_DIR / "hooks.json"
_GUARD_COMMAND = "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_push_on_critical.py"
_GUARD_SUFFIX = "hooks/guard_push_on_critical.py"
_ENFORCE_SUFFIX = "hooks/enforce_prd_location.py"

_COMMIT_RANGE = "1" * 40 + ".." + "2" * 40
_ENTRY = {
    "prd": "00168-x-v1.md",
    "batch": "202607161128",
    "op_id": "a1b2c3d4e5f6",
    "commit_range": _COMMIT_RANGE,
    "commits": 25,
    "detail": "cap-out with unresolved CRITICAL",
    "repo_root": None,  # filled per fixture with the repo's realpath
    "git_dir": None,
    "branch": "master",
}

_COMMIT_RANGE_2 = "3" * 40 + ".." + "4" * 40
_ENTRY_2 = {
    **_ENTRY,
    "prd": "00169-y-v1.md",
    "op_id": "f6e5d4c3b2a1",
    "commit_range": _COMMIT_RANGE_2,
    "commits": 7,
    "detail": "second cap-out with unresolved CRITICAL",
}

_COMMIT_RANGE_3 = "5" * 40 + ".." + "6" * 40
_ENTRY_3 = {  # _ENTRY's PRD under its own op_id: pending ops dedupe by op_id
    **_ENTRY, "op_id": "0f1e2d3c4b5a", "commit_range": _COMMIT_RANGE_3, "commits": 3
}

_BLOCK_HEADER = (
    "BLOCKED: git push targets a repository with pending cap_critical custody."
)
_ENTRY_LINE = (
    f"  00168-x-v1.md commits {_COMMIT_RANGE} (25) on master"
    " - cap-out with unresolved CRITICAL"
)
_ENTRY_LINE_2 = (
    f"  00169-y-v1.md commits {_COMMIT_RANGE_2} (7) on master"
    " - second cap-out with unresolved CRITICAL"
)
_ENTRY_LINE_3 = (
    f"  00168-x-v1.md commits {_COMMIT_RANGE_3} (3) on master"
    " - cap-out with unresolved CRITICAL"
)
_RESOLVE_LINE = (
    "Resolve first: autopilot custody resolve --prd 00168-x-v1"
    " --choice revert|branch-and-revert|accept"
)
_DEGRADED_PREFIX = "policy hook degraded: guard_push_on_critical: unreadable "
_UNRESOLVED_TEXT = "Target repository could not be resolved"

# A per-run token no implementation can have memorised: rows built from it
# force the parsers to parse rather than look the input up.
_NONCE = uuid.uuid4().hex


# --- fixtures -----------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    argv = ["git", "-C", str(repo), *args]
    subprocess.run(argv, check=True, capture_output=True, text=True, timeout=30)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    return path


def _seed_custody(repo: Path) -> tuple[Path, Path]:
    """Marker + matching journal row + locator. Returns (marker, journal)."""
    entry = {**_ENTRY, "repo_root": str(repo)}
    autopilot = repo / "dev" / "local" / "autopilot"
    (autopilot / "ledger").mkdir(parents=True)
    marker = autopilot / "critical-on-master"
    marker.write_text(json.dumps({"entries": [entry]}) + "\n", encoding="utf-8")
    journal = autopilot / "ledger" / "custody.jsonl"
    journal.write_text(
        json.dumps({"event": "recorded", **entry}) + "\n",
        encoding="utf-8",
    )
    _git(repo, "config", "--local", "autopilot.custodyMarker", str(marker))
    return marker, journal


def _append_journal(journal: Path, *rows: dict) -> None:
    with journal.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _bash(command: str, cwd: Path) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}


def _q(path: Path) -> str:
    return shlex.quote(str(path))


# --- split_simple_commands ----------------------------------------------------


def _split(command: str) -> list[tuple[str, str]] | None:
    result = guard.split_simple_commands(command)
    if result is None:
        return None
    return [(segment.strip(), separator) for segment, separator in result]


def _shape(command: str) -> tuple[list[str], list[str]]:
    """Non-empty segments and non-empty separators, independent of how the
    scanner represents the empty segment beside a bare `(`."""
    result = guard.split_simple_commands(command)
    segments = [segment.strip() for segment, _ in result if segment.strip()]
    separators = [separator for _, separator in result if separator]
    return segments, separators


_SPLIT_CASES = [
    ("single command", "git push", [("git push", "")]),
    ("and list", "git push && git status", [("git push", "&&"), ("git status", "")]),
    ("or list", "git push || true", [("git push", "||"), ("true", "")]),
    ("semicolon", "cd /x; git push", [("cd /x", ";"), ("git push", "")]),
    ("push then a non-git command", "git push; ls", [("git push", ";"), ("ls", "")]),
    (
        "unmemorisable path",
        f"cd /{_NONCE} && git push",
        [(f"cd /{_NONCE}", "&&"), ("git push", "")],
    ),
    ("pipe", "git log | grep push", [("git log", "|"), ("grep push", "")]),
    (
        "newline is a separator",
        "git status\ngit push",
        [("git status", ";"), ("git push", "")],
    ),
    ("brace group", "{ git push; }", [("{ git push", ";"), ("}", "")]),
    (
        "if statement",
        "if git push; then :; fi",
        [("if git push", ";"), ("then :", ";"), ("fi", "")],
    ),
    (
        "double-quoted separators stay in the segment",
        'echo "a && b"; git push',
        [('echo "a && b"', ";"), ("git push", "")],
    ),
    (
        "single-quoted separators stay in the segment",
        "echo 'a; b' && git push",
        [("echo 'a; b'", "&&"), ("git push", "")],
    ),
    (
        "backslash-escaped separators stay in the segment",
        "echo a \\&\\& git push",
        [("echo a \\&\\& git push", "")],
    ),
    (
        "comment runs to end of line even over separators",
        "git status # && git push",
        [("git status", "")],
    ),
    (
        "quoted hash is not a comment",
        'echo "# x" && git push',
        [('echo "# x"', "&&"), ("git push", "")],
    ),
    ("hash inside a word is not a comment", "git push#x", [("git push#x", "")]),
    (
        "2>&1 is a redirect, not a background &",
        "git push 2>&1",
        [("git push 2>&1", "")],
    ),
    (
        "&> is a redirect, not a background &",
        "git push &> /dev/null",
        [("git push &> /dev/null", "")],
    ),
    (">&2 is a redirect, not a background &", "git push >&2", [("git push >&2", "")]),
]


class SplitSimpleCommandsTests(unittest.TestCase):
    def test_splits_at_unquoted_separators_and_keeps_quoted_ones(self) -> None:
        for label, command, expected in _SPLIT_CASES:
            with self.subTest(label, command=command):
                self.assertEqual(_split(command), expected)

    def test_parentheses_are_separators_in_their_own_right(self) -> None:
        self.assertEqual(
            _shape("(cd /clean); git push"),
            (["cd /clean", "git push"], ["(", ")", ";"]),
        )
        self.assertEqual(
            _shape("( cd /x && git push )"),
            (["cd /x", "git push"], ["(", "&&", ")"]),
        )

    def test_lone_ampersand_and_pipe_ampersand_split_segments(self) -> None:
        self.assertEqual(_shape("git push & echo done")[0], ["git push", "echo done"])
        self.assertEqual(_shape("git push |& tee log")[0], ["git push", "tee log"])

    def test_unterminated_quote_is_malformed(self) -> None:
        for command in ('git push "oops', "git push 'oops"):
            with self.subTest(command=command):
                self.assertIsNone(guard.split_simple_commands(command))


# --- parse_git_call -----------------------------------------------------------


_GIT_DEFAULTS = {
    "subcommand": "push",
    "c_dirs": [],
    "git_dir": None,
    "work_tree": None,
    "unresolved": False,
}


def _fields(call: guard.GitCall) -> dict:
    return {
        "subcommand": call.subcommand,
        "c_dirs": list(call.c_dirs),
        "git_dir": call.git_dir,
        "work_tree": call.work_tree,
        "unresolved": bool(call.unresolved),
    }


# (label, segment, fields that differ from a plain `git push`)
_PARSE_CASES = [
    ("plain", "git push", {}),
    ("push with remote and refspec", "git push origin master", {}),
    ("push with --force-with-lease", "git push --force-with-lease", {}),
    (
        "-C with an unmemorisable path",
        f"git -C /{_NONCE} push",
        {"c_dirs": [f"/{_NONCE}"]},
    ),
    (
        "--git-dir= with an unmemorisable path",
        f"git --git-dir=/{_NONCE}/.git push",
        {"git_dir": f"/{_NONCE}/.git"},
    ),
    ("command prefix", "command git push", {}),
    ("absolute path", "/usr/bin/git push", {}),
    ("leading assignment", "FOO=1 git push", {}),
    (
        "GIT_WORK_TREE assignment fills work_tree",
        "GIT_WORK_TREE=x git push",
        {"work_tree": "x"},
    ),
    (
        "GIT_DIR assignment fills git_dir",
        "GIT_DIR=/g/.git git push",
        {"git_dir": "/g/.git"},
    ),
    (
        "flag wins over GIT_DIR assignment",
        "GIT_DIR=/a git --git-dir=/b push",
        {"git_dir": "/b"},
    ),
    ("brace group opener", "{ git push", {}),
    ("then keyword", "then git push", {}),
    ("if keyword", "if git push", {}),
    ("do keyword", "do git push", {}),
    ("negation", "! git push", {}),
    ("env wrapper then assignment", "env FOO=1 git push", {}),
    ("sudo wrapper with flag", "sudo -E git push", {}),
    ("nohup wrapper", "nohup git push", {}),
    ("exec wrapper", "exec git push", {}),
    ("nice wrapper", "nice git push", {}),
    ("time wrapper", "time git push", {}),
    ("command wrapper with flag", "command -p git push", {}),
    ("-C chain", "git -C a -C ../b push", {"c_dirs": ["a", "../b"]}),
    ("-c config", "git -c k=v push", {}),
    ("--git-dir=", "git --git-dir=.git push", {"git_dir": ".git"}),
    ("--git-dir value", "git --git-dir .git push", {"git_dir": ".git"}),
    ("--work-tree value", "git --work-tree . push", {"work_tree": "."}),
    ("--work-tree=", "git --work-tree=. push", {"work_tree": "."}),
    (
        "-C then --work-tree",
        "git -C /x --work-tree . push",
        {"c_dirs": ["/x"], "work_tree": "."},
    ),
    ("--namespace value", "git --namespace ns push", {}),
    ("other flag skipped", "git --no-pager push", {}),
    ("redirect operator and operand before the subcommand", "git > /dev/null push", {}),
    ("attached redirect before the subcommand", "git >/dev/null push", {}),
    ("2>&1 already names its operand", "git 2>&1 push", {}),
    ("&> attached redirect", "git &>/dev/null push", {}),
    ("trailing redirect", "git push > /dev/null", {}),
    ("split quotes normalise", "git pu''sh", {}),
    ("read-only subcommand", "git log push", {"subcommand": "log"}),
    ("-c value containing push", "git -c push=1 status", {"subcommand": "status"}),
    ("status with redirect", "git status 2>&1", {"subcommand": "status"}),
]


class ParseGitCallTests(unittest.TestCase):
    def test_resolves_the_git_call_and_its_global_options(self) -> None:
        for label, segment, overrides in _PARSE_CASES:
            with self.subTest(label, segment=segment):
                call = guard.parse_git_call(shlex.split(segment))
                self.assertIsNotNone(call, segment)
                self.assertEqual(_fields(call), {**_GIT_DEFAULTS, **overrides})

    def test_dollar_or_backtick_in_a_location_or_subcommand_marks_the_call_unresolved(
        self,
    ) -> None:
        cases = [
            ('git "${ACTION:-push}"', "${ACTION:-push}"),
            ('git -C "$DIR" push', "push"),
            ("git --git-dir=`pwd`/.git push", "push"),
            ('git --work-tree "$WT" push', "push"),
        ]
        for segment, subcommand in cases:
            with self.subTest(segment=segment):
                call = guard.parse_git_call(shlex.split(segment))
                self.assertIsNotNone(call, segment)
                self.assertEqual(call.subcommand, subcommand)
                self.assertTrue(call.unresolved)

    def test_returns_none_when_the_executable_is_not_git(self) -> None:
        for segment in (
            "echo 'git' 'push'",
            "echo push",
            "sh -c 'git push'",
            "gitk push",
            "FOO=1 echo git push",
        ):
            with self.subTest(segment=segment):
                self.assertIsNone(guard.parse_git_call(shlex.split(segment)))


# --- is_push_like -------------------------------------------------------------


class IsPushLikeTests(unittest.TestCase):
    def test_flags_commands_that_could_run_a_push_the_parser_cannot_see(self) -> None:
        for segment in (
            "sh -c 'git push'",
            'sh -c "git push -f"',
            f"bash -c 'git push origin {_NONCE}'",
            'bash -c "git push"',
            "zsh -c 'git push'",
            "dash -c 'git push'",
            "ksh -c 'git push'",
            'eval "git push"',
            "xargs git push",
            "ssh host git push",
            "timeout 10 git push",
            "make push",
            "find . -exec git push \\;",
            "parallel git push ::: a",
            "watch git push",
            "FOO=1 sh -c 'git push'",
            "command bash -c 'git push'",
            "$GIT push",
            'echo "$(git push)"',
            "echo `git push`",
            'git "${ACTION:-push}"',
        ):
            with self.subTest(segment=segment):
                self.assertTrue(guard.is_push_like(shlex.split(segment), segment))

    def test_ignores_plain_git_calls_and_words_that_merely_mention_push(self) -> None:
        for segment in (
            "git push",
            "echo 'git' 'push'",
            "echo push",
            "git log push",
            "git -c push=1 status",
            "sh -c 'git status'",
            "git status",
            f"echo push {_NONCE}",
        ):
            with self.subTest(segment=segment):
                self.assertFalse(guard.is_push_like(shlex.split(segment), segment))


# --- decide / run against real repositories -----------------------------------


class DecideTests(unittest.TestCase):
    def setUp(self) -> None:
        # macOS tmp paths resolve through /private/var; realpath once so the
        # marker's repo_root and every payload cwd already match git's output.
        self.base = Path(tempfile.mkdtemp(prefix="guard-push-")).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.guarded = _init_repo(self.base / "guarded")
        (self.guarded / "sub").mkdir()
        self.marker, self.journal = _seed_custody(self.guarded)
        self.clean = _init_repo(self.base / "clean")
        self.unrelated = self.base / "unrelated"
        self.unrelated.mkdir()

    def assertDenied(self, payload: dict, *, resolved: bool = False) -> str:
        reason = guard.decide(payload)
        self.assertIsNotNone(reason, payload["tool_input"])
        self.assertIn(_BLOCK_HEADER, reason)
        if resolved:
            # The target was found by parsing; the uncertain-path note that
            # names an unresolvable segment must not appear.
            self.assertNotIn(_UNRESOLVED_TEXT, reason)
        return reason

    def _seed_marker(self, *entries: dict) -> list[dict]:
        """Rewrite the guarded marker with these entries (repo_root filled in)."""
        rows = [{**entry, "repo_root": str(self.guarded)} for entry in entries]
        self.marker.write_text(json.dumps({"entries": rows}), encoding="utf-8")
        return rows

    def test_allows_tools_other_than_bash(self) -> None:
        edit = {"file_path": "x", "old_string": "git push", "new_string": ""}
        payload = {"tool_name": "Edit", "tool_input": edit, "cwd": str(self.guarded)}
        self.assertIsNone(guard.decide(payload))

    def test_allows_commands_without_push_from_a_guarded_cwd(self) -> None:
        for command in ("git status 2>&1", "git log --oneline", "echo hello", "ls"):
            with self.subTest(command=command):
                self.assertIsNone(guard.decide(_bash(command, self.guarded)))

    def test_allows_read_only_git_and_echo_that_mention_push(self) -> None:
        for command in (
            "git log push",
            "git -c push=1 status",
            "echo 'git' 'push'",
            "echo push",
            "git log | grep push",
        ):
            with self.subTest(command=command):
                self.assertIsNone(guard.decide(_bash(command, self.guarded)))

    def test_allows_commands_where_push_is_only_text_from_a_guarded_cwd(self) -> None:
        for command in (
            "git status # git push",
            'echo "git push"',
            "git log --grep=push",
            "git -c push=2 status",
            "cat push.txt",
        ):
            with self.subTest(command=command):
                self.assertIsNone(guard.decide(_bash(command, self.guarded)))

    def test_denies_direct_push_naming_prd_range_and_resolve_command(self) -> None:
        reason = guard.decide(_bash("git push", self.guarded))
        self.assertIsNotNone(reason)
        self.assertTrue(reason.startswith(_BLOCK_HEADER), reason)
        self.assertIn(_ENTRY_LINE, reason)
        self.assertIn(_RESOLVE_LINE, reason)
        self.assertNotIn(_UNRESOLVED_TEXT, reason)
        self.assertLess(reason.index(_ENTRY_LINE), reason.index(_RESOLVE_LINE))
        self.assertEqual(
            reason.count("00168-x-v1.md commits"),
            1,
            "marker and journal copies of one op_id must dedupe to one line",
        )

    def test_allows_push_from_a_clean_repo_or_a_non_repo_directory(self) -> None:
        for cwd in (self.clean, self.unrelated):
            for command in ("git push", "exec git push", "nice git push"):
                with self.subTest(cwd=str(cwd), command=command):
                    self.assertIsNone(guard.decide(_bash(command, cwd)))

    def test_denies_every_spelling_that_resolves_to_git_push_in_the_guarded_cwd(
        self,
    ) -> None:
        for command in (
            "command git push",
            "/usr/bin/git push",
            "FOO=1 git push",
            "exec git push",
            "nice git push",
            "{ git push; }",
            "(git push)",
            "( git push ) && echo ok",
            "if git push; then :; fi",
            "git > /dev/null push",
            "git pu''sh",
            "git pu\\sh",
            "git -c k=v push",
            "git --git-dir=.git push",
            "git --work-tree . push",
            "git push origin master",
            "git push --force-with-lease",
            "git push # deploy",
            "git status && git push",
            "git fetch; git push",
        ):
            with self.subTest(command=command):
                self.assertDenied(_bash(command, self.guarded), resolved=True)

    def test_denies_push_from_a_subdirectory_of_the_guarded_repo(self) -> None:
        self.assertDenied(_bash("git push", self.guarded / "sub"), resolved=True)

    def test_cd_into_the_guarded_repo_makes_it_the_target(self) -> None:
        for command in (
            f"cd {_q(self.guarded)} && git push",
            f"pushd {_q(self.guarded)} && git push",
            f"cd {_q(self.guarded)}; git push",
            f"(cd {_q(self.guarded)} && git push)",
        ):
            with self.subTest(command=command):
                self.assertDenied(_bash(command, self.clean))

    def test_cd_inside_a_subshell_does_not_leak_to_later_segments(self) -> None:
        self.assertIsNone(
            guard.decide(_bash(f"(cd {_q(self.guarded)}); git push", self.clean)),
        )
        self.assertDenied(_bash(f"(cd {_q(self.clean)}); git push", self.guarded))

    def test_cd_inside_a_brace_group_leaks_like_bash(self) -> None:
        self.assertDenied(_bash(f"{{ cd {_q(self.guarded)}; git push; }}", self.clean))

    def test_cd_of_uncertain_success_keeps_the_original_cwd_as_a_target(self) -> None:
        command = f"true || cd {_q(self.clean)} && git push"
        self.assertDenied(_bash(command, self.guarded))

    def test_explicit_c_target_overrides_the_cwd(self) -> None:
        clean, guarded = _q(self.clean), _q(self.guarded)
        self.assertIsNone(guard.decide(_bash(f"git -C {clean} push", self.guarded)))
        payload = _bash(f"git -C {guarded} push", self.unrelated)
        self.assertDenied(payload, resolved=True)
        # Relative -C values chain from the payload cwd: clean/../guarded.
        self.assertDenied(_bash("git -C .. -C guarded push", self.clean), resolved=True)

    def test_explicit_repo_pointers_reach_the_guarded_repo_from_an_unrelated_cwd(
        self,
    ) -> None:
        git_dir = self.guarded / ".git"
        for command in (
            f"git --git-dir={_q(git_dir)} push",
            f"git --git-dir {_q(git_dir)} --work-tree {_q(self.guarded)} push",
            f"git -C {_q(self.guarded)} --work-tree . push",
            f"GIT_DIR={_q(git_dir)} git push",
            f"GIT_WORK_TREE={_q(self.guarded)} git push",
        ):
            with self.subTest(command=command):
                self.assertDenied(_bash(command, self.unrelated), resolved=True)

    def test_locator_alone_discovers_custody_for_a_work_tree_elsewhere(self) -> None:
        # The work tree points at a directory with no custody state, so only
        # the locator in the guarded repo's config can reveal the marker.
        command = (
            f"git --git-dir={_q(self.guarded / '.git')}"
            f" --work-tree={_q(self.unrelated)} push"
        )
        self.assertDenied(_bash(command, self.unrelated), resolved=True)
        _git(self.guarded, "config", "--local", "--unset", "autopilot.custodyMarker")
        self.assertIsNone(guard.decide(_bash(command, self.unrelated)))

    def test_journal_row_alone_keeps_custody_pending_until_resolved(self) -> None:
        self.marker.unlink()
        reason = self.assertDenied(_bash("git push", self.guarded), resolved=True)
        self.assertIn(_ENTRY_LINE, reason)
        with self.journal.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"event": "resolved", "op_id": _ENTRY["op_id"]}) + "\n")
        self.assertIsNone(guard.decide(_bash("git push", self.guarded)))

    def test_resolved_journal_row_releases_only_its_own_op_id(self) -> None:
        self.marker.unlink()
        _append_journal(
            self.journal,
            {"event": "recorded", **_ENTRY_2, "repo_root": str(self.guarded)},
            {"event": "resolved", "op_id": _ENTRY["op_id"]},
        )
        reason = self.assertDenied(_bash("git push", self.guarded), resolved=True)
        self.assertIn(_ENTRY_LINE_2, reason)
        self.assertNotIn("00168-x-v1", reason)

    def test_journal_row_is_pending_while_the_marker_file_still_exists(self) -> None:
        # Marker keeps entry 1; entry 2 is recorded in the journal only.
        row = {"event": "recorded", **_ENTRY_2, "repo_root": str(self.guarded)}
        _append_journal(self.journal, row)
        reason = self.assertDenied(_bash("git push", self.guarded), resolved=True)
        self.assertIn(_ENTRY_LINE, reason)
        self.assertIn(_ENTRY_LINE_2, reason)

    def test_a_second_pending_op_for_the_same_prd_gets_its_own_line(self) -> None:
        self._seed_marker(_ENTRY, _ENTRY_3)
        reason = self.assertDenied(_bash("git push", self.guarded), resolved=True)
        self.assertIn(_ENTRY_LINE, reason)
        self.assertIn(_ENTRY_LINE_3, reason)
        self.assertIn(_RESOLVE_LINE, reason)
        self.assertEqual(reason.count("00168-x-v1.md commits"), 2, reason)

    def test_resolved_journal_row_does_not_release_an_entry_still_in_the_marker(
        self,
    ) -> None:
        # Pending = marker entries plus unresolved journal rows; a journal
        # `resolved` row never removes an entry the marker still lists.
        _append_journal(self.journal, {"event": "resolved", "op_id": _ENTRY["op_id"]})
        reason = self.assertDenied(_bash("git push", self.guarded), resolved=True)
        self.assertIn(_ENTRY_LINE, reason)

    def test_denial_lists_every_pending_entry_and_names_every_prd_to_resolve(
        self,
    ) -> None:
        _, second = self._seed_marker(_ENTRY, _ENTRY_2)
        _append_journal(self.journal, {"event": "recorded", **second})
        reason = self.assertDenied(_bash("git push", self.guarded), resolved=True)
        self.assertIn(_ENTRY_LINE, reason)
        self.assertIn(_ENTRY_LINE_2, reason)
        resolve_text = "\n".join(
            line for line in reason.splitlines() if line.startswith("Resolve first:")
        )
        self.assertIn("--prd 00168-x-v1 ", resolve_text)
        self.assertIn("--prd 00169-y-v1 ", resolve_text)

    def test_empty_marker_allows(self) -> None:
        autopilot = self.clean / "dev" / "local" / "autopilot"
        autopilot.mkdir(parents=True)
        marker = autopilot / "critical-on-master"
        marker.write_text(json.dumps({"entries": []}), encoding="utf-8")
        self.assertIsNone(guard.decide(_bash("git push", self.clean)))

    def test_corrupt_marker_denies_with_the_degraded_line(self) -> None:
        self.marker.write_text("{not json", encoding="utf-8")
        code, _, err = guard.run(_bash("git push", self.guarded))
        self.assertEqual(code, 2, err)
        self.assertIn(_DEGRADED_PREFIX, err)
        self.assertIn("critical-on-master", err)

    def test_corrupt_journal_line_denies_with_the_degraded_line(self) -> None:
        with self.journal.open("a", encoding="utf-8") as fh:
            fh.write("not json\n")
        code, _, err = guard.run(_bash("git push", self.guarded))
        self.assertEqual(code, 2, err)
        self.assertIn(_DEGRADED_PREFIX, err)
        self.assertIn("custody.jsonl", err)

    def test_custody_state_is_not_read_for_calls_that_cannot_push(self) -> None:
        # An unreadable marker only matters once a push is on the table; the
        # tool and command classification must come first.
        self.marker.write_text("{not json", encoding="utf-8")
        code, _, err = guard.run(_bash("ls", self.guarded))
        self.assertEqual((code, err), (0, ""))
        self.assertIsNone(guard.decide(_bash("git status", self.guarded)))
        edit = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "x", "old_string": "git push"},
            "cwd": str(self.guarded),
        }
        self.assertIsNone(guard.decide(edit))

    def test_pending_entries_reads_the_toplevel_and_walks_up_from_a_subdirectory(
        self,
    ) -> None:
        def op_ids(toplevel: str | None, start_cwd: str, locator: str | None) -> list:
            entries = guard.pending_entries(toplevel, start_cwd, locator)
            return [entry["op_id"] for entry in entries]

        seeded = [_ENTRY["op_id"]]
        self.assertEqual(op_ids(str(self.guarded), str(self.guarded), None), seeded)
        self.assertEqual(op_ids(None, str(self.guarded / "sub"), None), seeded)
        self.assertEqual(op_ids(str(self.clean), str(self.clean), None), [])

    def test_marker_from_locator_reads_the_configured_marker_via_git_dir(self) -> None:
        call = guard.GitCall("push", [], str(self.guarded / ".git"), None, False)
        found = guard.marker_from_locator(str(self.unrelated), call)
        self.assertIsNotNone(found)
        self.assertEqual(os.path.realpath(found), str(self.marker))
        _git(self.guarded, "config", "--local", "--unset", "autopilot.custodyMarker")
        self.assertIsNone(guard.marker_from_locator(str(self.unrelated), call))

    def test_target_toplevel_follows_cwd_c_chain_and_git_dir(self) -> None:
        sub = str(self.guarded / "sub")
        git_dir = str(self.guarded / ".git")
        for cwd, call in (
            (sub, guard.GitCall("push", [], None, None, False)),
            (sub, guard.GitCall("push", [".."], None, None, False)),
            (str(self.unrelated), guard.GitCall("push", [], git_dir, None, False)),
        ):
            with self.subTest(cwd=cwd, call=call):
                top = guard.target_toplevel(cwd, call)
                self.assertIsNotNone(top)
                self.assertEqual(os.path.realpath(top), str(self.guarded))
        unresolved = guard.GitCall("push", [], None, None, True)
        self.assertIsNone(guard.target_toplevel(sub, unresolved))

    def test_unresolved_target_denies_only_when_the_payload_cwd_has_custody(
        self,
    ) -> None:
        for command in (
            'git -C "$DIR" push',
            'cd "$DIR" && git push',
            "cd - && git push",
        ):
            with self.subTest(command=command):
                self.assertDenied(_bash(command, self.guarded))
                self.assertIsNone(guard.decide(_bash(command, self.clean)))

    def test_hidden_push_denies_only_when_the_payload_cwd_has_custody(self) -> None:
        for command in (
            'echo "$(git push)"',
            "sh -c 'git push'",
            "zsh -c 'git push'",
            'git "${ACTION:-push}"',
        ):
            with self.subTest(command=command):
                reason = self.assertDenied(_bash(command, self.guarded))
                self.assertIn(_UNRESOLVED_TEXT, reason)
                self.assertIsNone(guard.decide(_bash(command, self.clean)))

    def test_hidden_push_also_checks_repos_named_elsewhere_in_the_command(self) -> None:
        command = f"git -C {_q(self.guarded)} status && sh -c 'git push'"
        self.assertDenied(_bash(command, self.unrelated))

    def test_malformed_command_follows_the_uncertain_fallback(self) -> None:
        # An unterminated quote cannot be parsed; "cannot tell" must never read
        # as "nothing pending", so it denies exactly when the cwd has custody.
        command = 'git push "oops'
        self.assertDenied(_bash(command, self.guarded))
        self.assertIsNone(guard.decide(_bash(command, self.clean)))

    def test_run_exits_2_with_the_reason_on_stderr(self) -> None:
        code, _, err = guard.run(_bash("git push", self.guarded))
        self.assertEqual(code, 2)
        self.assertIn(_BLOCK_HEADER, err)
        self.assertIn(_ENTRY_LINE, err)
        self.assertIn(_RESOLVE_LINE, err)

    def test_run_exits_0_without_stderr_for_an_allowed_command(self) -> None:
        code, _, err = guard.run(_bash("git push", self.clean))
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")


# --- registration -------------------------------------------------------------


class RegistrationTests(unittest.TestCase):
    def test_bash_matcher_registers_the_guard_once_beside_enforce_prd_location(
        self,
    ) -> None:
        data = json.loads(_HOOKS_JSON.read_text(encoding="utf-8"))
        bash_blocks = [
            block
            for block in data["hooks"]["PreToolUse"]
            if block.get("matcher") == "Bash"
        ]
        self.assertEqual(
            len(bash_blocks), 1, "exactly one PreToolUse block matches Bash"
        )
        hooks = bash_blocks[0]["hooks"]
        guard_hooks = [h for h in hooks if h.get("command", "").endswith(_GUARD_SUFFIX)]
        enforce_hooks = [
            h for h in hooks if h.get("command", "").endswith(_ENFORCE_SUFFIX)
        ]
        self.assertEqual(len(guard_hooks), 1, hooks)
        self.assertEqual(len(enforce_hooks), 1, hooks)
        self.assertEqual(
            guard_hooks[0],
            {"type": "command", "command": _GUARD_COMMAND, "timeout": 10},
        )


if __name__ == "__main__":
    unittest.main()
