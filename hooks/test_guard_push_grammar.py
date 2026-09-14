"""Grammar tests for hooks/guard_push_on_critical.py, the PreToolUse Bash
push guard.

The tables below drive the exported parsing helpers (`split_simple_commands`,
`parse_git_call`, `is_push_like`) on command text alone; no repository state
is involved. The `decide` / `run` and registration tests live in
test_guard_push_on_critical.py.

Stdlib-only unittest, collected by pytest.
"""

from __future__ import annotations

import importlib
import shlex
import sys
import unittest
import uuid
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
guard = importlib.import_module("guard_push_on_critical")

# A per-run token no implementation can have memorised: rows built from it
# force the parsers to parse rather than look the input up.
_NONCE = uuid.uuid4().hex


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
            # A wrapper whose value-taking flag hides the executable: the
            # parser cannot see past `-u NAME` / `-n 10`, so it is uncertain.
            "sudo -u bob git push",
            "nice -n 10 git push",
            "env -u VAR git push",
            # Unmemorisable operands: the rule must parse, not look tails up.
            f"sudo -u {_NONCE} git push",
            f"nice -n {int(_NONCE[:4], 16)} git push",
            f"env -u {_NONCE} git push",
            # Any value-taking option hides the executable, not just -u / -n.
            "sudo -g git git push",
            f"sudo --user {_NONCE} git push",
            "nice --adjustment 10 git push",
            # The operand spelt `git` must not read as the executable, and the
            # real executable after it need not be the bare word.
            "env -u git git push",
            "sudo -u git git push",
            "sudo -u git /usr/bin/git push",
            "env -u git exec git push",
            # Quote-split `push` inside a push-capable executable's argument.
            "eval \"git pu''sh\"",
            "sh -c 'git pu\"\"sh'",
        ):
            with self.subTest(segment=segment):
                self.assertTrue(guard.is_push_like(shlex.split(segment), segment))

    def test_ignores_plain_git_calls_and_words_that_merely_mention_push(self) -> None:
        for segment in (
            "git push",
            "echo 'git' 'push'",
            # A flag-free wrapper is looked through: `echo` / `mytool` is the
            # executable, and neither is git nor a shell.
            "command echo 'git' 'push'",
            "nohup mytool git push",
            "echo push",
            "git log push",
            "git -c push=1 status",
            "sh -c 'git status'",
            "git status",
            f"echo push {_NONCE}",
        ):
            with self.subTest(segment=segment):
                self.assertFalse(guard.is_push_like(shlex.split(segment), segment))


if __name__ == "__main__":
    unittest.main()
