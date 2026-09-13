"""PreToolUse hook: deny a Bash `git push` into a repository with pending
cap_critical custody.

When an autopilot batch caps out with an unresolved CRITICAL, custody.py
records the affected commit range in `<repo>/dev/local/autopilot/
critical-on-master` (the marker), appends a `recorded` row to
`<repo>/dev/local/autopilot/ledger/custody.jsonl` (the journal) and sets
`git config --local autopilot.custodyMarker` (the locator). Until
`autopilot custody resolve` lands, nothing may push that range. This hook
inspects the Bash command text, resolves which repository each `git push`
would target (payload cwd, `cd`/`pushd`, `-C`, `--git-dir`, `--work-tree`,
`GIT_DIR`, `GIT_WORK_TREE`) and blocks with exit 2 when any target has
pending custody. A command whose target cannot be told (a shell wrapper, a
command substitution, an expansion in a path) is denied when the payload cwd
or any repository the command names has pending custody. The custody read is
re-implemented here in a few lines: hooks/ never imports from skills/.

Grammar limits (accepted): no variable expansion, here-docs, function
definitions or `case` patterns; `$( )` and backtick bodies are not evaluated,
their presence makes the command uncertain; a `cd` inside `{ }` leaks to
later segments (as in bash); a `cd` whose success is unknown keeps both
directories as candidates; wrapper options that take a value (`nice -n 10`,
`sudo -u NAME`) are not modelled. Every limit errs toward a false deny, never
a false allow. "Cannot tell" is never "nothing pending": custody state that
exists but cannot be read denies with a `policy hook degraded` line, while a
bug in the guard itself fails open (loud) like enforce_prd_location.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from collections import namedtuple
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import allow, block, read_input, resolve_toplevel

GitCall = namedtuple("GitCall", "subcommand c_dirs git_dir work_tree unresolved")

_HEADER = "BLOCKED: git push targets a repository with pending cap_critical custody."
_DEGRADED = "policy hook degraded: guard_push_on_critical"
_AUTOPILOT_DIR = os.path.join("dev", "local", "autopilot")
_MARKER_NAME = "critical-on-master"
_JOURNAL_NAME = os.path.join("ledger", "custody.jsonl")
_MAX_CANDIDATES = 8
_QUOTE_CHARS = str.maketrans("", "", "'\"\\")

_TWO_CHAR_SEPARATORS = {"&&": "&&", "||": "||", "|&": "|"}
_ONE_CHAR_SEPARATORS = {"\n": ";", ";": ";", "|": "|", "(": "(", ")": ")", "&": ";"}
_REDIRECT_OPERATOR = re.compile(r"[0-9]*[<>]{1,2}(&([0-9-]*))?")
_ATTACHED_REDIRECT = re.compile(r"[0-9]*[<>]{1,2}\S+|&>\S*")
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
_RESERVED = {
    "{", "}", "!", "if", "then", "else", "elif", "while", "until", "do", "fi",
    "done", "esac", "in",
}
_WRAPPERS = {"command", "env", "exec", "nohup", "sudo", "nice", "time"}
_GIT_VALUE_OPTIONS = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
    "--super-prefix", "--config-env", "--attr-source",
}
_PUSH_CAPABLE = {
    "sh", "bash", "zsh", "dash", "ksh", "eval", "xargs", "timeout", "ssh",
    "script", "watch", "find", "parallel", "make",
}


class CustodyStateError(Exception):
    """Custody state exists but cannot be read; str(exc) names the path."""


# --- command grammar ----------------------------------------------------------


def _quote_end(command: str, start: int) -> int | None:
    """Index of the quote closing the one at `start`, or None if unterminated."""
    if command[start] == "'":
        end = command.find("'", start + 1)
        return None if end < 0 else end
    i = start + 1
    while i < len(command):
        if command[i] == "\\":
            i += 2
        elif command[i] == '"':
            return i
        else:
            i += 1
    return None


def _separator_at(command: str, i: int) -> tuple[str, str] | None:
    """(token, reported separator) when an unquoted separator starts at i."""
    two = command[i : i + 2]
    if two in _TWO_CHAR_SEPARATORS:
        return two, _TWO_CHAR_SEPARATORS[two]
    ch = command[i]
    if ch not in _ONE_CHAR_SEPARATORS:
        return None
    if ch == "&":
        prev, nxt = command[i - 1 : i], command[i + 1 : i + 2]
        if prev in {"<", ">"} or nxt == ">":
            return None  # part of a redirect: >& <& &>
    return ch, _ONE_CHAR_SEPARATORS[ch]


def split_simple_commands(command: str) -> list[tuple[str, str]] | None:
    """Split `command` into (segment, separator_after) pairs.

    Quote-aware ('...', "...", backslash). An unquoted `#` at a word start
    opens a comment that runs to end of line. Splits at unquoted newline,
    `;`, `|`, `||`, `|&`, `&&`, `(`, `)` and a lone `&` (not `>&`, `<&`,
    `&>`); the reported separator is one of "", ";", "&&", "||", "|", "(",
    ")" (newline and `&` report ";", `|&` reports "|"). Backslash-newline is
    a line continuation. None on an unterminated quote or a trailing lone
    backslash (malformed).
    """
    pieces: list[tuple[str, str]] = []
    buf: list[str] = []
    boundary = True  # at a word start: an unquoted `#` here opens a comment
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if ch == "\\":
            if i + 1 >= n:
                return None
            continued = command[i + 1] == "\n"
            buf.append(" " if continued else command[i : i + 2])
            boundary, i = continued, i + 2
            continue
        if ch in "'\"":
            end = _quote_end(command, i)
            if end is None:
                return None
            buf.append(command[i : end + 1])
            boundary, i = False, end + 1
            continue
        if ch == "#" and boundary:
            newline = command.find("\n", i)
            i = n if newline < 0 else newline
            continue
        separator = _separator_at(command, i)
        if separator is not None:
            token, kind = separator
            pieces.append(("".join(buf), kind))
            buf, boundary, i = [], True, i + len(token)
            continue
        buf.append(ch)
        boundary, i = ch in " \t", i + 1
    pieces.append(("".join(buf), ""))
    return pieces


def _strip_redirects(words: list[str]) -> list[str]:
    """Drop redirection operators and their operands from a word list."""
    kept: list[str] = []
    skip = False
    for word in words:
        if skip:
            skip = False
            continue
        operator = _REDIRECT_OPERATOR.fullmatch(word)
        if operator:
            skip = not operator.group(2)  # `2>&1` names its operand, `>` does not
            continue
        if _ATTACHED_REDIRECT.fullmatch(word):
            continue
        kept.append(word)
    return kept


def _unwrap(words: list[str]) -> tuple[list[str], dict[str, str]]:
    """Drop redirections, then leading reserved words, NAME=value assignments
    and wrappers with their -flags. Returns (remaining words, assignments)."""
    rest = _strip_redirects(words)
    env: dict[str, str] = {}
    while rest:
        word = rest[0]
        if word in _RESERVED:
            rest = rest[1:]
        elif _ASSIGNMENT.match(word):
            name, _, value = word.partition("=")
            env[name] = value
            rest = rest[1:]
        elif word in _WRAPPERS:
            rest = rest[1:]
            while rest and rest[0].startswith("-"):
                rest = rest[1:]
        else:
            break
    return rest, env


def _needs_expansion(value: str) -> bool:
    return "$" in value or "`" in value


def parse_git_call(words: list[str]) -> GitCall | None:
    """Resolve a shlex-split segment to the git call it runs, or None.

    The executable is git iff its basename is `git` after unwrapping. Global
    options before the subcommand fill `c_dirs`, `git_dir` and `work_tree`
    (flags win over GIT_DIR / GIT_WORK_TREE assignments); `unresolved` marks
    a location or subcommand that needs expansion (`$`, backtick) to know.
    """
    rest, env = _unwrap(words)
    if not rest or os.path.basename(rest[0]) != "git":
        return None
    c_dirs: list[str] = []
    located = {"--git-dir": env.get("GIT_DIR"), "--work-tree": env.get("GIT_WORK_TREE")}
    i = 1
    while i < len(rest) and rest[i].startswith("-"):
        option, attached, value = rest[i].partition("=")
        if option in _GIT_VALUE_OPTIONS and not attached:
            i += 1
            value = rest[i] if i < len(rest) else ""
        if option == "-C":
            c_dirs.append(value)
        elif option in located:
            located[option] = value
        i += 1
    subcommand = rest[i] if i < len(rest) else None
    git_dir, work_tree = located["--git-dir"], located["--work-tree"]
    locations = (*c_dirs, git_dir, work_tree, subcommand)
    unresolved = any(_needs_expansion(value) for value in locations if value)
    return GitCall(subcommand, c_dirs, git_dir, work_tree, unresolved)


def is_push_like(words: list[str], segment: str) -> bool:
    """True when the segment mentions push and could run one the parser
    cannot see: an expanded or push-capable executable (`sh -c`, `xargs`,
    `make`, ...), a command substitution, or a git call needing expansion."""
    if "push" not in segment:
        return False
    if any("$(" in word or "`" in word for word in words):
        return True
    rest, _ = _unwrap(words)
    if not rest:
        return False
    if _needs_expansion(rest[0]) or os.path.basename(rest[0]) in _PUSH_CAPABLE:
        return True
    call = parse_git_call(words)
    return call is not None and call.unresolved


# --- repository resolution ----------------------------------------------------


def target_toplevel(cwd: str, call: GitCall) -> str | None:
    """Toplevel the call operates on: the -C chain first, then --work-tree,
    then --git-dir (its parent when named `.git`), else git discovery."""
    if call.unresolved:
        return None
    base = os.path.realpath(os.path.join(cwd, *call.c_dirs))
    if call.work_tree:
        return os.path.realpath(os.path.join(base, call.work_tree))
    if call.git_dir:
        git_dir = os.path.realpath(os.path.join(base, call.git_dir))
        return os.path.dirname(git_dir) if os.path.basename(git_dir) == ".git" else git_dir
    return resolve_toplevel(base)


def marker_from_locator(cwd: str, call: GitCall) -> str | None:
    """The marker path from `git config autopilot.custodyMarker` as the call
    would see it, or None."""
    argv = ["git", "-C", os.path.join(cwd, *call.c_dirs)]
    if call.git_dir:
        argv += ["--git-dir", call.git_dir]
    if call.work_tree:
        argv += ["--work-tree", call.work_tree]
    argv += ["config", "--get", "autopilot.custodyMarker"]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


# --- custody state ------------------------------------------------------------


def _read_text(path: str) -> str | None:
    """File text, None when absent; any other failure is unreadable state."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise CustodyStateError(path) from exc


def _marker_entries(path: str) -> list[dict]:
    text = _read_text(path)
    if text is None:
        return []
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise CustodyStateError(path) from exc
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise CustodyStateError(path)
    return entries


def _journal_pending(path: str) -> dict:
    """op_id -> recorded row for rows no later `resolved` row released."""
    pending: dict = {}
    for line in (_read_text(path) or "").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise CustodyStateError(path) from exc
        if not isinstance(row, dict):
            raise CustodyStateError(path)
        if row.get("event") == "recorded":
            pending[row.get("op_id")] = row
        elif row.get("event") == "resolved":
            pending.pop(row.get("op_id"), None)
    return pending


def _read_pending(autopilot_dir: str) -> list[dict]:
    """Marker entries plus unresolved journal rows, by op_id; marker wins."""
    marker = _marker_entries(os.path.join(autopilot_dir, _MARKER_NAME))
    pending = {entry.get("op_id"): entry for entry in marker}
    for op_id, row in _journal_pending(os.path.join(autopilot_dir, _JOURNAL_NAME)).items():
        pending.setdefault(op_id, row)
    return list(pending.values())


def _nearest_autopilot_dir(start: str) -> str | None:
    path = os.path.abspath(start)
    while True:
        candidate = os.path.join(path, _AUTOPILOT_DIR)
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def _merge(pending: dict, entries: list[dict]) -> bool:
    for entry in entries:
        pending.setdefault(entry.get("op_id"), entry)
    return bool(entries)


def _rooted_at(entry: dict, toplevel: str) -> bool:
    repo_root = entry.get("repo_root")
    return bool(repo_root) and os.path.realpath(str(repo_root)) == os.path.realpath(toplevel)


def pending_entries(
    toplevel: str | None, start_cwd: str, locator: str | None,
) -> list[dict]:
    """Pending custody from `<toplevel>/dev/local/autopilot`, the nearest
    such dir above `start_cwd` (all of it when `toplevel` is None, else only
    entries rooted at `toplevel`) and the locator's dir. Raises
    CustodyStateError when present state cannot be read."""
    pending: dict = {}
    if toplevel:
        _merge(pending, _read_pending(os.path.join(toplevel, _AUTOPILOT_DIR)))
    nearest = _nearest_autopilot_dir(start_cwd)
    if nearest:
        entries = _read_pending(nearest)
        if toplevel:
            entries = [entry for entry in entries if _rooted_at(entry, toplevel)]
        _merge(pending, entries)
    if locator:
        _merge(pending, _read_pending(os.path.dirname(locator)))
    return list(pending.values())


# --- decision -----------------------------------------------------------------


def _after_cd(candidates: set[str] | None, args: list[str]) -> set[str] | None:
    """Candidate cwds after `cd`/`pushd`: the old ones plus the target from
    each (whether the cd ran depends on the list before it)."""
    if candidates is None:
        return None
    target = os.path.expanduser(args[0] if args else "~")
    if target == "-" or _needs_expansion(target):
        return None
    grown = candidates | {os.path.realpath(os.path.join(c, target)) for c in candidates}
    return grown if len(grown) <= _MAX_CANDIDATES else None


def _walk(
    pieces: list[tuple[str, str]], cwd: str,
) -> Iterator[tuple[str, list[str], set[str] | None]]:
    """Yield (segment, words, candidate cwds) per non-empty segment. `(`
    saves the candidate set and `)` restores it; `{ }` groups do not. None
    means the cwd cannot be told."""
    candidates: set[str] | None = {cwd}
    stack: list[set[str] | None] = []
    for segment, separator in pieces:
        words = shlex.split(segment)
        rest, _ = _unwrap(words)
        if rest and rest[0] in {"cd", "pushd"}:
            candidates = _after_cd(candidates, rest[1:])
        elif words:
            yield segment.strip(), words, candidates
        if separator == "(":
            stack.append(candidates)
        elif separator == ")" and stack:
            candidates = stack.pop()


def _check_uncertain(pending: dict, cwd: str, calls: list) -> str | None:
    """Uncertain path: the payload cwd plus every repository a git call in
    the command resolves to. Returns the first source with pending custody."""
    blame = cwd if _merge(pending, pending_entries(None, cwd, None)) else None
    for candidates, call in calls:
        if candidates is None:
            continue
        for base in candidates:
            toplevel = target_toplevel(base, call)
            if toplevel is None:
                continue
            found = pending_entries(toplevel, cwd, marker_from_locator(base, call))
            if _merge(pending, found) and blame is None:
                blame = toplevel
    return blame


def _format_block(entries: list[dict], note: str | None) -> str:
    lines = [_HEADER]
    lines += [
        f"  {e.get('prd')} commits {e.get('commit_range')} ({e.get('commits')})"
        f" on {e.get('branch')} - {e.get('detail')}"
        for e in entries
    ]
    for stem in dict.fromkeys(Path(str(e.get("prd"))).stem for e in entries):
        lines.append(
            f"Resolve first: autopilot custody resolve --prd {stem}"
            " --choice revert|branch-and-revert|accept",
        )
    if note:
        lines.append(note)
    return "\n".join(lines)


def _decide_command(command: str, cwd: str) -> str | None:
    pieces = split_simple_commands(command)
    pushes: list[tuple[set[str], GitCall]] = []
    calls: list[tuple[set[str] | None, GitCall]] = []
    uncertain: list[str] = [] if pieces is not None else [command]
    for segment, words, candidates in _walk(pieces or [], cwd):
        call = parse_git_call(words)
        if call is not None:
            calls.append((candidates, call))
        pushing = call is not None and call.subcommand == "push"
        if pushing and candidates is not None and not call.unresolved:
            pushes.append((candidates, call))
        elif pushing or is_push_like(words, segment):
            uncertain.append(segment)
    pending: dict = {}
    for candidates, call in pushes:
        for base in candidates:
            toplevel = target_toplevel(base, call)
            _merge(pending, pending_entries(toplevel, base, marker_from_locator(base, call)))
    blame = _check_uncertain(pending, cwd, calls) if uncertain else None
    if not pending:
        return None
    note = None
    if blame:
        note = (
            f"Target repository could not be resolved ({'; '.join(uncertain)});"
            f" denied because {blame} has pending custody."
        )
    return _format_block(list(pending.values()), note)


def decide(payload: dict) -> str | None:
    """Block reason for the payload, None to allow. Custody state is read
    only once a push is on the table."""
    if payload.get("tool_name") != "Bash":
        return None
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if "push" not in command.translate(_QUOTE_CHARS):
        return None
    cwd = str(payload.get("cwd") or os.getcwd())
    try:
        return _decide_command(command, cwd)
    except CustodyStateError as exc:
        return f"{_DEGRADED}: unreadable {exc}"


def main() -> None:
    try:
        reason = decide(read_input())
    except Exception as exc:
        # A guard bug must not lock every push on the host: fail open but
        # LOUD, as enforce_prd_location does. Unreadable custody state is
        # not a bug and never reaches here; decide already denied it.
        print(f"{_DEGRADED}: {exc}", file=sys.stderr)
        reason = None
    if reason:
        block(reason)
    allow()


def run(payload):
    """Dispatcher entry point (hooks/dispatch.py). `capture_main` feeds
    `payload` as stdin, captures stdout/stderr and maps main()'s exit, so
    run() RETURNS the (exit_code, stdout, stderr) triple."""
    from _common import capture_main

    return capture_main(main, payload)


if __name__ == "__main__":
    main()
