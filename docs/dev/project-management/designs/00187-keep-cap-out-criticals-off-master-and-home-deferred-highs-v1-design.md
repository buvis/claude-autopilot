# Design: 00187 Keep cap-out CRITICALs under custody

PRD: `dev/local/prds/wip/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1.md`

## Architecture fit

- `skills/run-autopilot/cli/` is the sole `state.json` mutator surface (capsule § Component Boundaries). Custody is a stall-time side effect, so it lands as a site-keyed step inside `cli/records.do_stall` plus one new module `cli/custody.py`; no skill hand-edits state.
- The batch deferred JSON (`dev/local/autopilot/deferred/<batch>-deferred.json`, `records.record_defer`, op_id-deduped) is the durable ledger every batch-end surface already reads; custody records land there, not in a new file.
- Marker files in `dev/local/autopilot/` are the established session-boundary hand-off (`state-schema.md` § Marker files). `critical-on-master` joins that table as the guard's source of truth; `state.batch.critical_on_master` is a display mirror only.
- Hooks live in `hooks/`, Python, stdlib-only, allow/block via `hooks/_common.py`, registered in `hooks/hooks.json`. The push guard is a second `PreToolUse` `Bash` handler beside `enforce_prd_location.py`.
- Batch runs here execute the installed cache, so nothing in this PRD is live until release (memory `project-batch-runs-installed-cache`).

## Module placement

New files:

- `skills/run-autopilot/cli/custody.py` - capture, marker, hold refresh, migration, resolve.
- `skills/run-autopilot/cli/test_custody.py` - do_stall(cap_critical) fixture/retry tests + resolve subprocess tests.
- `skills/run-autopilot/cli/test_custody_prose.py` - prose contract pins.
- `skills/run-autopilot/cli/test_render_custody.py` - stalled renderer with/without range, through the CLI.
- `hooks/guard_push_on_critical.py` - PreToolUse Bash guard.
- `hooks/test_guard_push_on_critical.py` - parser/decision/repo fixtures.

Edits:

- `cli/records.py` - `_stall_preflight` captures the range for `site == "cap_critical"`; `_stamp_stall_intent` persists it; new step 4b (custody write) between append and commit; `_commit_stall` composes the batch mirror mutator; `PER_PRD_RESET_FIELDS` gains `git_dir`.
- `cli/schema.py` - `_STR_FIELDS` gains `git_dir`.
- `cli/__main__.py` - `custody` subcommand (`list`, `resolve`); `render report --stalled` passes the stall record's range to `stalled_section`; docstring exit-code table.
- `cli/frontmatter.py` - `_HEAD_LINES` 20 -> 22 (docstring line updated; `test_frontmatter` unchanged).
- `cli/render_report.py` - `stalled_section` gains the custody line.
- `hooks/hooks.json` - second entry in the existing `Bash` matcher's `hooks` array.
- `skills/run-autopilot/references/phase-review.md`, `phase-build.md`, `recovery.md`, `state-schema.md`, `SKILL.md` - prose (§ Data flow lists each sentence).
- `README.md` - "One hook" paragraph becomes two hooks (one sentence).
- `dev/bin/release-checks` - `[checks] custody push guard` block.
- `CHANGELOG.md` - two `[Unreleased]` / `### Added` entries.

## Interfaces & contracts

### `cli/custody.py`

```python
CUSTODY_SITE = "cap_critical"
MARKER_NAME = "critical-on-master"          # <autopilot_dir>/critical-on-master
JOURNAL_REL = "ledger/custody.jsonl"        # <autopilot_dir>/ledger/custody.jsonl (GC-exempt)
CONFIG_KEY = "autopilot.custodyMarker"      # git local config locator -> marker path
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
GIT_TIMEOUT_SECS = 30

class CustodyError(Exception): ...          # message is the loud reason

def marker_lock(path: Path):
    """Context manager: fcntl.flock(LOCK_EX) on f"{path}.lock" (same sidecar
    pattern as record_defer). Every marker read-modify-write in this module
    (record_critical, resolve) runs inside it, re-reading under the lock, so a
    stall racing an attended resolve cannot drop the other's entry."""

def append_journal(autopilot_dir: Path, row: dict) -> None:
    """Append one JSON line to <autopilot_dir>/ledger/custody.jsonl (mkdir -p
    ledger). Rows: {"event": "recorded", **entry} at step 4b;
    {"event": "resolving", "op_id", "choice", "head_before"} before resolve
    runs git; {"event": "resolved", "op_id", "prd", "choice", "at"} after.
    The journal lives in ledger/ so purge-devlocal's 14-day `stale-autopilot`
    rule never trashes it; it is the restore source when the marker is gone."""

def compact_journal(autopilot_dir: Path) -> None:
    """Growth bound, run at the end of every successful resolve under
    marker_lock: rewrite the journal atomically (tmp + os.replace) keeping only
    the rows of op_ids with no `resolved` row, one `recorded` row per op_id
    (last wins) plus its `resolving` row if any. Resolved history is dropped -
    the batch ledger's `<op_id>-resolve` record is the receipt. So the file
    holds O(pending custodies) rows, never a history."""

def read_journal(autopilot_dir: Path) -> list[dict]:
    """All rows. Raises CustodyError on an unparseable line or an unreadable
    file (never skips silently - a corrupt journal after the marker was
    trashed would otherwise read as 'nothing pending'). Absent file -> []."""

def unresolved_from_journal(autopilot_dir: Path) -> list[dict]:
    """Entries of `recorded` rows whose op_id has no `resolved` row (last
    row wins per op_id)."""

def pending(autopilot_dir: Path) -> list[dict]:
    """Marker entries ∪ unresolved journal entries, deduped by op_id (marker
    copy wins). This is what the guard, resolve, `custody list` and Phase 0
    consult; a trashed marker still leaves the journal's entries pending
    (tested). Raises CustodyError when either source is present but
    unreadable."""

def git_argv(repo_root: str, git_dir: str | None) -> list[str]:
    """["git", "--git-dir", git_dir, "--work-tree", repo_root] when git_dir is
    set (bare-repo-backed project, e.g. ~/.claude under ~/.buvis), else
    ["git", "-C", repo_root]. Every git call in this module and in resolve
    starts from this."""

def capture_range(repo_root: str, git_dir: str | None, base: str) -> tuple[str, int, str]:
    """Return ("<base>..<end>", <int count>, <branch>). Runs git_argv(...) +
    rev-parse --verify --quiet HEAD^{commit} -> `end` (captured ONCE; every
    later call names `end`, never HEAD, so the pair cannot straddle a commit);
    when base != EMPTY_TREE also rev-parse --verify --quiet <base>^{commit};
    rev-list --count <base>..<end> (works for the EMPTY_TREE base too -
    measured); rev-parse --abbrev-ref HEAD (the protected branch, "HEAD" when
    detached). Raises CustodyError on:
    base not a 40-hex sha, repo_root not a dir, any git exit != 0, timeout
    (GIT_TIMEOUT_SECS), or git missing."""

def project_root(autopilot_dir: Path) -> Path:
    """autopilot_dir.parents[2] when autopilot_dir ends with dev/local/autopilot
    (parents[0] is dev/local, parents[1] is dev - same index __main__.py:732
    uses), else autopilot_dir.parent - the PRD's 'project root when repo_root
    absent'."""

def load_marker(path: Path) -> list[dict]:
    """[] when absent. Raises CustodyError when the file is not
    {"entries": [dict, ...]}."""

def write_marker(path: Path, entries: list[dict]) -> None:
    """state.atomic_write(path, {"entries": entries}); deletes the file when
    entries is empty."""

def upsert_entry(entries: list[dict], entry: dict) -> tuple[list[dict], bool]:
    """New list with `entry` replacing the one sharing its op_id, else
    appended. Second value: True when appended (created)."""

def refresh_hold_prd(text: str, entry: dict) -> str:
    """PURE. See § Hold PRD refresh."""

def migration_records(state: dict, op_id: str, prd: str) -> list[dict]:
    """PURE. One record per pending state.deferred_decisions[i]
    (render_report._is_pending): {**decision, "type": decision.get("type",
    "deferred_decision"), "cycle": decision.get("cycle", state.get("cycle")),
    "op_id": f"{op_id}-dd{i}"} - a decision raised in an earlier cycle keeps
    its own cycle. `prd` is stamped by record_defer."""

def record_critical(*, autopilot_dir: Path, prds_dir: Path, current: dict,
                    prd: str, op_id: str, detail: str, capture: dict) -> int | None:
    """do_stall step 4b, under marker_lock. In order: record_defer each
    migration record; upsert the marker entry and write it;
    append_journal("recorded"); git_argv(...) + ["config", "--local",
    CONFIG_KEY, str(marker_path)]; read <prds_dir>/hold/<prd>, `created` =
    its text has no notice line for this batch yet, rewrite it via
    refresh_hold_prd (the LAST durable write); then, only when `created` and
    every write above succeeded, notify_out.notify("autopilot 🔒 custody",
    f"{prd}: commits {commit_range} ({commits}) live on {branch}; run
    autopilot custody resolve"). A first attempt that fails before the hold
    rewrite therefore still notifies on its retry; the one unclosed window is
    a crash between the rewrite and the notify call (best-effort delivery,
    documented). Returns None on success, 9 on any OSError / ValueError /
    CustodyError / git config failure (PRD is already in hold/, intent
    retained; the retry re-runs every write idempotently)."""

def mirror_mutator(entry: dict):
    """Returns fn(state)->state that upserts `entry` into
    state["batch"]["critical_on_master"] (list, created when absent)."""

def resolve(*, autopilot_dir: Path, state_path: Path, prd: str, choice: str) -> int:
    """See § Attended resolution. Exit 0 ok | 1 no pending entry for prd, or a
    different choice already recorded | 5 git refused or failed (custody
    retained) | 9 ledger/marker/journal write failed."""
```

Marker entry (also the `batch.critical_on_master[]` element and the journal `recorded` row's payload) - every key required:

```json
{"prd": "00168-x-v1.md", "batch": "202607161128", "op_id": "a1b2c3d4e5f6",
 "commit_range": "<work_start_sha>..<head>", "commits": 25,
 "detail": "<stall detail>", "repo_root": "/abs/path", "git_dir": null,
 "branch": "master"}
```

Three keys beyond the PRD's listed six. `repo_root`: the guard needs it to match a resolved git toplevel against a marker found by walking up from the payload cwd (a bare-repo-backed project such as `~/.claude` has toplevel `$HOME`, not the project dir); it is `state.repo_root` when set, else `str(project_root(autopilot_dir))`. `git_dir`: `state.git_dir` when set, else `null`; without it neither capture nor resolve can run git for a bare-repo-backed project (`git -C $HOME rev-parse` exits 128 there - measured). `branch`: the checked-out branch at the stall; resolve refuses to revert on any other checkout, so a feature branch that happens to contain the commits cannot release custody while `master` still carries them.

Locator: `git config --local autopilot.custodyMarker <abs marker path>` is set at 4b and unset by resolve when no entries for that repo remain. The guard reads it (`git ... config --get autopilot.custodyMarker`) once it has a target repository, so a push aimed at `$HOME` with explicit `--git-dir/--work-tree` flags still finds `~/.claude`'s marker. Any git repo can name at most one marker (one project per repo; the last stall wins, which is the same project in practice).

`state.git_dir` (new optional `str` field, Phase 3 capture, per-PRD reset): `phase-build.md` Phase 3 "Capture `repo_root`" step also writes `state.git_dir` = the `--git-dir` value it had to pass for the bare-repo case (`~/.buvis` -> `/Users/<you>/.buvis`), and leaves it unset when a plain `git rev-parse --show-toplevel` worked. `records.PER_PRD_RESET_FIELDS` gains `"git_dir"` right after `"repo_root"`; `schema._STR_FIELDS` gains `"git_dir"`.

Deferred-JSON records written by custody (all through `records.record_defer`, deduped by `op_id`):

- stall record (existing shape + the capture keys): `{"type": "stall", "site": "cap_critical", "detail", "op_id", "prd", "commit_range", "commits", "branch", "repo_root", "git_dir"}`.
- migrated pending deferral: `{**decision, "type": <decision type or "deferred_decision">, "cycle", "prd", "op_id": "<op_id>-dd<i>"}`.
- resolution: `{"type": "custody", "choice": "revert"|"branch-and-revert"|"accept", "prd", "commit_range", "op_id": "<op_id>-resolve"}`.

`state.stall_op` for `site == "cap_critical"` carries `commit_range`, `commits`, `branch`, `repo_root`, `git_dir` beside `{op_id, prd, site, detail}`. `_stall_op_malformed` gains a site-keyed clause: when `site == "cap_critical"` the capture must be complete and valid - `commit_range` matching `^[0-9a-f]{40}\.\.[0-9a-f]{40}$`, `commits` a non-negative int, `branch` and `repo_root` non-empty strings, `git_dir` a string or None - else the intent is malformed (exit 2, `autopilot: malformed stall_op in state; refusing`, state untouched). An existing intent is therefore never recaptured and never accepted half-written.

### `cli/records.py` changes

- `_stall_preflight(current, prd, site, autopilot_dir) -> tuple[str, dict, int | None]` returns `(op_id, capture, rc)`; `capture` is `{}` for other sites, `{"commit_range", "commits", "branch", "repo_root", "git_dir"}` for `cap_critical`. Retry (stall_op present - already shape-checked by `_stall_op_malformed`'s cap_critical clause) reuses the persisted values and never runs git. Fresh: `base = current.get("work_start_sha")`, `repo_root = current.get("repo_root") or str(custody.project_root(autopilot_dir))`, `git_dir = current.get("git_dir")`; `CustodyError` prints `autopilot: cap_critical custody capture failed: <reason>` on stderr and returns rc 2 BEFORE mkdir/intent/move. That stderr prefix is the discriminator the prose uses (§ Prose contract, recovery.md exit table): a capture-failed exit 2 leaves state and the PRD untouched, so it is NOT the corrupted-state row, and the PRD is never stalled under another site (that would ship the CRITICAL uncustodied - the exact loss this PRD closes).
- `_stamp_stall_intent(..., capture)` merges `capture` into the stall_op dict.
- `_append_stall_deferred(..., capture)` merges `capture` into the stall record.
- New step between append and commit, only for `cap_critical`: `_trip("after-append-before-custody")` then `custody.record_critical(...)`; rc 9 propagates. Failpoint name `after-append-before-custody` joins the documented set.
- `_commit_stall(state_path, site, extra_mutator, entry)`: when `entry` is not None, run `custody.mirror_mutator(entry)` before the caller's `extra_mutator`, inside the one commit. `_reconcile_stall_op` needs no change: the mirror is site-keyed inside do_stall, so a park-time retry still writes it.
- Docstring exit codes for do_stall gain: `2 ... or cap_critical range capture failed`; `9 ... or custody write failed`.

### `cli/__main__.py`

```
custody list [--state]
custody resolve --prd <stem-or-filename-or-path> --choice {revert,branch-and-revert,accept} [--state]
```

`list` prints `custody.pending(autopilot_dir)` as one JSON object per line (exit 0; exit 9 when a source is present but unreadable) - the read-only surface Phase 0 enumerates from, so attended prompts and the loop-mode count never miss a journal-only entry. `resolve --prd` matches `entry["prd"].removesuffix(".md") == Path(arg).name.removesuffix(".md")`. Both resolve `--state` by the existing walk-up; `autopilot_dir = state_path.parent`. Exit codes: 0 | 1 no pending entry / a different choice already recorded | 5 git refused or failed (custody retained) | 9 ledger/marker/journal write or read failed. The docstring's exit-code table gains `5 ... / git refused or failed (custody resolve)`.

`render report --stalled --site S --detail D`: after the existing arg check, look up `deferred_items` (already loaded) for the LAST item with `type == "stall"`, `prd == state.prd`, `site == S` and a `commit_range` key; pass `commit_range=item["commit_range"], commits=item.get("commits")` to `stalled_section`. No new flags.

### `cli/render_report.py`

```python
def stalled_section(prd, site, detail, stamp, commit_range=None, commits=None) -> str
```
When `commit_range` is truthy, insert `- Commits: {commit_range} ({commits}) live on master, custody pending\n` between the `- Detail:` and `- Resume:` lines. Range-less output is byte-identical to today.

### Hold PRD refresh (`refresh_hold_prd`)

1. Frontmatter: `frontmatter._HEAD_LINES` moves from 20 to **22** (docstring: "20, plus the two custody keys the hold refresh may add"; `test_frontmatter.test_block_closing_past_the_head_bound_is_malformed` closes on line 27 and stays red-for-malformed). If line 0 is `---` and a closing `---` exists within the first 20 lines, replace an existing `critical_on_master:` / `ledger:` line in the block in place, else append the missing key lines just before the closing `---` - always both keys; a block that closed within 20 lines closes within 22 afterwards, so every existing key (`design_gate: user`, `pause_on_ambiguity: true`, ...) keeps parsing. A block that does not close within 20 lines is what the parser already calls malformed: treat it as no block. No block: prepend `---\ncritical_on_master: <range>\nledger: deferred/<batch>-deferred.json#<op_id>\n---\n`. Values: `critical_on_master: <commit_range>`, `ledger: deferred/<batch>-deferred.json#<op_id>`.
2. Notice line: `> **Custody (cap_critical, batch <batch>):** <detail> Commits <commit_range> (<commits>) are live on <branch>. Resolve with autopilot custody resolve.` If a line starting with `> **Custody (cap_critical, batch <batch>):**` exists, replace that line in place (same operation = same batch; no padding change). Otherwise insert after the first line matching `^#{1,6} Problem Statement\s*$`, else after the first `^# ` line, else at end of text, with one blank line each side. `refresh(refresh(t, e), e) == refresh(t, e)` holds.
3. Everything else in `text` is preserved byte-for-byte.

### `hooks/guard_push_on_critical.py`

Payload: `{"tool_name": "Bash", "tool_input": {"command": str}, "cwd": str}`. Not Bash, or `"push"` not in the command after stripping every `'`, `"` and `\` character (`git pu''sh` and `git pu\sh` normalise to `git push`; shlex joins the same way) -> allow with no parsing.

```python
def split_simple_commands(command: str) -> list[tuple[str, str]] | None
    # quote-aware scan ('...', "...", backslash): drops unquoted `#` comments
    # (at start or after whitespace/separator) to end of line; splits at
    # unquoted \n ; | || |& && ( ) and a lone & (not part of >& <& &>);
    # returns (segment, separator_after) pairs where separator_after is one
    # of "", ";", "&&", "||", "|", "(", ")" (newline -> ";"); None on an
    # unterminated quote (malformed).
GitCall = namedtuple("GitCall", "subcommand c_dirs git_dir work_tree unresolved")
def parse_git_call(words: list[str]) -> GitCall | None
    # words = shlex.split(segment). First drop redirections anywhere in the
    # word list: a word matching ^[0-9]*[<>]{1,2}&?[0-9-]*$ is an operator
    # and takes the NEXT word as its operand unless it already names one
    # (2>&1, >&2); a word matching ^[0-9]*[<>]{1,2}\S+$ or ^&>\S*$ is an
    # attached redirect (>/dev/null) and is dropped alone. So
    # `git > /dev/null push` yields [git, push]. Then strip, repeating until
    # none applies: leading shell reserved words / group openers {"{", "}",
    # "!", "if", "then", "else", "elif", "while", "until", "do", "fi",
    # "done", "esac", "in"}; leading NAME=value words; a leading wrapper in
    # {"command", "env", "exec", "nohup", "sudo", "nice", "time"} plus its
    # following -flags. Executable = next word; git iff
    # os.path.basename(exe) == "git". (`{ git push; }`, `then git push`,
    # `if git push; then`, `do git push` all resolve to git - measured
    # bypasses otherwise.)
    # Global options before the subcommand: -C <p>; -c <k=v>; --git-dir=<p> |
    # --git-dir <p>; --work-tree=<p> | --work-tree <p>; value-taking
    # --namespace/--exec-path/--super-prefix/--config-env/--attr-source in
    # both forms; any other -x/--x word skipped. First remaining word =
    # subcommand.
    # A leading GIT_DIR=<p> / GIT_WORK_TREE=<p> assignment fills git_dir /
    # work_tree when the flag form is absent (flags win).
    # unresolved=True when any -C/--git-dir/--work-tree value, OR the
    # subcommand word itself (`git "${ACTION:-push}"`), contains $ or `.
def is_push_like(words: list[str], segment: str) -> bool
    # True when "push" is in the segment AND any of: exe (after the same
    # unwrap) contains $ or `; basename(exe) in {"sh","bash","zsh","dash",
    # "ksh","eval","xargs","timeout","ssh","script","watch","find","parallel",
    # "make"}; any word contains "$(" or "`" (command substitution such as
    # `echo "$(git push)"`); a git call whose subcommand is unresolved.
    # `echo 'git' 'push'` has none of these -> False.
def target_toplevel(cwd: str, call: GitCall) -> str | None
    # base = realpath(join(cwd, *c_dirs)) - the -C chain applies FIRST, so
    # `git -C /guarded --work-tree . push` resolves against /guarded.
    # work_tree -> realpath(join(base, work_tree)); else git_dir ->
    # realpath(join(base, git_dir)) then its parent when basename == ".git";
    # else hooks/_common.resolve_toplevel(base). None when unresolved.
def marker_from_locator(cwd: str, call: GitCall) -> str | None
    # `git [-C base | --git-dir/--work-tree] config --get autopilot.custodyMarker`
    # (timeout 5) -> the marker path, or None.
def pending_entries(toplevel: str | None, start_cwd: str, locator: str | None) -> list[dict]
    # Sources: M1 = <toplevel>/dev/local/autopilot/ (toplevel given);
    # M2 = nearest <ancestor of start_cwd>/dev/local/autopilot/;
    # M3 = dirname(locator) (locator given). For each source dir read
    # custody.pending(dir): marker ∪ unresolved journal rows (the hook
    # re-implements that 15-line read - hooks/ imports nothing from skills/).
    # Entries: all of M1 and M3, plus M2 entries whose repo_root realpath ==
    # toplevel, or ALL M2 entries when toplevel is None. Custody state that
    # is PRESENT but cannot be read (unparseable marker, a bad journal line,
    # an I/O error on either, a locator pointing at an unreadable dir) is
    # not "nothing pending": raise CustodyStateError, which decide turns
    # into a deny with stderr `policy hook degraded: guard_push_on_critical:
    # unreadable <path>`. Absent files are simply [].
def decide(payload: dict) -> str | None   # block reason, None = allow
```

`decide` walks the segments with a **set of candidate cwds** (starts as `{payload cwd}`) and a scope stack: `(` pushes a copy of the set, `)` pops it back (a `cd` inside a subshell never leaks out - `(cd /clean); git push` still targets the payload cwd); `{ }` groups do not push (a cd there leaks, as in bash). `cd <p>` / `pushd <p>` with a literal `p` **adds** `{join(c, p) for c in candidates}` to the set and never removes anything: whether the `cd` ran at all depends on the whole `&&`/`||` list before it (`true || cd /clean && git push` skips the cd and pushes from the original cwd), so the pre-cd directories stay candidates; `~` expanded; `cd` alone -> `$HOME`; `cd -`, `p` containing `$`/`` ` ``, or more than 8 candidates -> the set becomes `None` (unresolved). For each segment: a git call with `subcommand == "push"` -> `target_toplevel` for every candidate cwd (None set or `call.unresolved` -> `[None]`) -> `pending_entries` per toplevel (with `marker_from_locator`); else `is_push_like` -> the uncertain path: `pending_entries(None, payload cwd, None)` ∪ `pending_entries(t, payload cwd, locator)` for every toplevel `t` resolved from any git call anywhere in the command (the "resolvable target repos"). Any pending entry from any source -> block. Block text:

```
BLOCKED: git push targets a repository with pending cap_critical custody.
  <prd> commits <commit_range> (<commits>) on <branch> - <detail>
Resolve first: autopilot custody resolve --prd <stem> --choice revert|branch-and-revert|accept
```
plus, on the uncertain path, `Target repository could not be resolved (<segment>); denied because <cwd or repo> has pending custody.` Exception policy, two tiers: `CustodyStateError` (custody state present but unreadable) -> deny with the degraded line, because "cannot tell" must not read as "nothing pending"; any other unexpected exception (a parser bug) -> `policy hook degraded: guard_push_on_critical: <exc>` on stderr and allow, mirroring `enforce_prd_location.main`, so a guard bug cannot lock every push on the host. `main()`/`run(payload)` follow `enforce_prd_location.py` otherwise.

Documented grammar limits (module docstring): no variable expansion, no here-docs, no evaluation of `$( )` bodies (their presence makes the command uncertain), no function definitions, no `case` patterns; a `cd` inside `{ }` leaks to later segments (as in bash); a `cd` whose success is unknown keeps both directories as candidates (false deny possible, never a false allow).

`hooks/hooks.json`: the existing `"matcher": "Bash"` object's `hooks` array gains `{"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_push_on_critical.py", "timeout": 10}` as its second element; the `enforce_prd_location.py` element is unchanged.

### Attended resolution (`custody.resolve`)

All steps run under `marker_lock`; `prd` is compared as `Path(arg).name.removesuffix(".md")` so a pasted path works.

1. `entries = pending(autopilot_dir)` (marker ∪ journal; `CustodyError` -> 9); find by prd stem; none -> print `autopilot: no pending custody for <prd> (pass the PRD stem, filename or path)` and return 1.
2. **Durable choice first.** If the batch ledger already holds `<op_id>-resolve` (a crashed earlier run), its `choice` wins: a different `--choice` prints `already resolved as <recorded>; finishing cleanup` and returns 1 after running step 5; the same choice skips step 3 (git already applied or never needed) and goes to step 5. Otherwise continue.
3. Git (`revert` / `branch-and-revert` only; `accept` touches nothing). `argv = git_argv(entry["repo_root"], entry.get("git_dir"))`; `base, end = entry["commit_range"].split("..")`; `targets` = `rev-list <base>..<end>` (newest first, revert's expected order; for `base == EMPTY_TREE`, `rev-list <end>` - `git revert <tree>..HEAD` exits 128 "can't cherry-pick a tree", measured) - the explicit commit list is what is reverted and what is reconciled against.
   - Refuse before mutating (exit 5, message names the fix): `rev-parse --abbrev-ref HEAD != entry["branch"]` (`checkout <branch> first`); an unfinished operation (`<git-dir>/REVERT_HEAD`, `MERGE_HEAD`, `CHERRY_PICK_HEAD` or `sequencer/` present - `finish or abort it first`).
   - Intent, then reconcile. If the journal has no `resolving` row for this op_id: `append_journal({"event": "resolving", "op_id", "choice", "head_before": <rev-parse HEAD>})` first. If it has one (a rerun): every target `t` counts as reverted iff some commit in `head_before..HEAD` has the exact line `This reverts commit <t>.` in its body (`rev-list --format=%B head_before..HEAD`; the line `git revert --no-edit` writes); all targets reverted -> skip git; none -> run git; a partial set -> refuse (exit 5, `partial revert; finish by hand, then --choice accept`). A revert of an unrelated commit matches no target, so it can never release custody.
   - `branch-and-revert`: `rev-parse --verify --quiet refs/heads/custody/<stem>`; when it exists and points at `end`, skip; when it exists elsewhere -> 5; else `argv + ["branch", f"custody/{stem}", end]`.
   - Revert: `argv + ["revert", "--no-edit", *targets]`.
   Any git exit != 0 (or timeout) -> print its stderr, return 5, custody retained, git left as it is for the operator.
4. `record_defer(autopilot_dir, entry["prd"], entry["batch"], {"type": "custody", "choice", "commit_range", "op_id": f"{op_id}-resolve"})`; OSError/ValueError -> 9. This is the durable boundary: from here every later step is idempotent and a rerun resumes at step 2.
5. Cleanup, each idempotent: `append_journal("resolved")`; `write_marker(path, entries minus this op_id)` (absent marker: nothing); when no entry for this `repo_root` remains, `argv + ["config", "--local", "--unset", CONFIG_KEY]` (exit 5 from git = key absent, ignored); when `state_path` exists, `state.transaction` removing the op_id from `batch.critical_on_master` (owned-fields validator: `batch` dict; `state.StateError`/`schema.SchemaError`/`OSError` -> print `mirror stale, custody closed` and return 9 - marker and journal are the sources of truth); a missing state file (archived after drain) is skipped silently; finally `compact_journal`.
6. Print `custody: <prd> resolved (<choice>)`, return 0.

Crash windows: before step 4 -> rerun redoes git safely (branch check, exact reconciliation against the recorded `head_before`, idempotent branch creation); after step 4 -> rerun hits step 2 and only cleans up. A crash between the revert commits landing and step 4 is closed by the reconciliation; an interrupted multi-commit revert leaves `sequencer/`, which the refusal catches.

### Prose contract (pinned by `test_custody_prose.py`, substring asserts)

- `phase-review.md` cap-out bullet: after `site: "cap_critical"`, add ` — the stall itself captures the PRD's live commit range (`work_start_sha..HEAD`) into custody; there is no range flag to pass`.
- `phase-build.md` Phase 0, new subsection `### Handle pending custody` placed before `### Normal PRD selection`: run `autopilot custody list` (one Bash call; marker ∪ journal, so a journal-only entry after a trashed marker is still listed); no lines -> nothing; interactive -> for each entry ask via `AskUserQuestion` with the three choices `revert`, `branch-and-revert`, `accept`, then run `autopilot custody resolve --prd <stem> --choice <choice>`; exit 5 -> report git's message and STOP the turn (do not select a PRD while a revert is unfinished; the operator finishes or aborts it, then closes custody with `--choice accept` or re-runs the same choice); loop mode -> print `custody: <n> entries await an attended resume` (n = the line count) and continue; exit 9 from `list` -> PAUSE (`site: "sub_skill_fail"`, the stderr as detail) in every mode, because unreadable custody state must not be walked past.
- `recovery.md` § Stall site slugs: `cap_critical` bullet naming the marker, the journal, the locator config key, the batch mirror, the migrated deferrals and `autopilot custody resolve`; the exit table's `2` row becomes `2 | state unreadable, OR (stderr starts with `autopilot: cap_critical custody capture failed:`) the range capture failed with state and the PRD untouched | corrupted-state row for the former; for the latter retry the same stall ONCE, then PAUSE in every mode: `phase`/`next_phase: "paused"`, `pause_reason = {"site": "sub_skill_fail", "detail": "<the capture stderr line>"}`, PRD left in `wip/`, state otherwise untouched. This is sanctioned batch-halt row 1 (a CRITICAL is about to ship with no custody) - never delete `state.json`, never stall the PRD under another site` and `9` extends with `or custody write failed (PRD already in hold/, intent retained; re-run the same stall)`. `SKILL.md` § Error Handling row 1 gains the parenthetical `(including a cap_critical custody capture that fails twice)`.
- `phase-build.md` Phase 3 "Capture `repo_root`" step: add the `state.git_dir` sentence from § Interfaces (bare-repo case only).
- `state-schema.md`: Marker files row `critical-on-master` (writer `do_stall` step 4b, consumer `hooks/guard_push_on_critical.py` and Phase 0; content `{"entries":[...]}`; note that purge-devlocal's 14-day rule may trash it and the journal below is the restore source); new `## Custody journal` section for `ledger/custody.jsonl` (rows, GC-exempt, the locator config key); `batch.critical_on_master` and `git_dir` field rows; `stall_op` sentence extended with the custody keys; Batch Deferred Log gains the `custody` type and the stall record's `commit_range`/`commits`/`branch`. `SKILL.md` § Retention durable list gains `dev/local/autopilot/ledger/custody.jsonl`.
- `SKILL.md` Error Handling "Git push fails" row: add `A push denied by hooks/guard_push_on_critical.py names a pending cap_critical custody: resolve it with autopilot custody resolve, never bypass the hook.`
- Byte-identical: `phase-review.md` line `Invoke `/autopilot:review-work-completion` skill. Every cycle runs ALL lenses (its roster, PRD 00015): ...` (the whole sentence through `activates her.`).
- Absent: no `--commit-range` / `--range` flag anywhere in `skills/run-autopilot`; no `mint-stubs` / `custody stub` / `design-rework` mention.

### `dev/bin/release-checks`

```
echo "[checks] custody push guard"
uv run --no-project --with pytest python -m pytest -q hooks/test_guard_push_on_critical.py
```

### `CHANGELOG.md` `[Unreleased]` / `### Added`

- `**run-autopilot**: a cap-out with an unresolved CRITICAL now records the PRD's live commit range as custody (marker, batch mirror, migrated deferrals, refreshed hold PRD) and offers revert / branch-and-revert / accept through `autopilot custody resolve``
- `**hooks**: deny a Bash `git push` that targets a repository with pending cap_critical custody, naming the PRD, range and resolve command`

## Data flow

1. Review gate cap-out (loop mode, unresolved CRITICAL) runs `autopilot stall --prd F --site cap_critical --detail D`.
2. `do_stall`: preflight reads `state.work_start_sha` + `state.repo_root` + `state.git_dir`, `capture_range` -> `(range, n, branch)` (exit 2 on failure, nothing moved; the prose PAUSEs after one retry) -> mkdir hold -> stamp `stall_op{op_id, prd, site, detail, commit_range, commits, branch, repo_root, git_dir}` -> move wip->hold -> append stall record (+range) -> **4b** under the marker lock: migration records, marker upsert, journal `recorded` row, `git config --local autopilot.custodyMarker`, hold refresh, notify-on-create -> commit: per-PRD reset + `batch.critical_on_master` upsert + stall_op delete.
3. Kill after any boundary: rerun/`autopilot park` reconciles with the same op_id; capture is reused from `stall_op`, `record_defer` dedupes each op_id, the marker upsert replaces, the journal row repeats harmlessly (last row per op_id wins), the config set is idempotent, the notice replaces, notify fires only on create.
4. Every later Bash `git push` aimed at that repo (any mode, any cwd) hits the guard: parse -> candidate cwds -> toplevel -> marker/journal/locator lookup -> exit 2 with PRD/range/branch/resolve.
5. Next attended Phase 0: pending custody -> three choices -> `custody resolve` -> branch check, git -> `custody` ledger record (durable boundary) -> journal `resolved`, marker + locator + mirror entry removed -> guard passes. Loop-mode Phase 0 logs the count and continues.
6. `render report --stalled` after the stall reads the range off the stall record and adds the `- Commits:` line.

## Reuse inventory

- `cli/records.record_defer` (op_id-deduped ledger append) - used for stall, migration and custody records; no new ledger writer.
- `cli/state.atomic_write` / `state.transaction` - marker file write and the batch mirror commit.
- `cli/render_report._is_pending` - the pending-deferral predicate for migration (same rule Phase 9 and `complete-prd` use).
- `cli/notify_out.notify` - best-effort custody notification (30s timeout, never raises).
- `records._trip` failpoint + `_AUTOPILOT_CLI_FAILPOINT` - crash-window tests for step 4b.
- `hooks/_common.py` `read_input/allow/block`, `resolve_toplevel` (memoized `git rev-parse --show-toplevel`, reused for the `-C` chain branch of `target_toplevel`) and `enforce_prd_location.main`'s degrade-loud pattern - the guard's skeleton.
- `records.record_defer`'s `.lock` sidecar + `fcntl.flock` pattern - `marker_lock`.
- `cli/statectl.append_attempt_rows`' JSONL convention (`open(..., "a")`, one `json.dumps` per line, `ledger/` mkdir) - the journal append follows it; `hooks/_common.append_jsonl_row` is the same idea but `cli/` does not import from `hooks/`, so the three lines are written in `custody.py`.
- `cli/frontmatter._HEAD_LINES` - the block boundary the refresh must respect (raised 20 -> 22 for the two custody keys); `frontmatter.parse` ignores unknown keys, so `critical_on_master:`/`ledger:` need no key-level parser change (its docstring: unknown keys fall through).
- `test_lifecycle_cli._run` / `test_render_cli` fixtures - subprocess pattern for `test_custody.py` resolve tests and `test_render_custody.py`.
- `render_report.stalled_section` - extended, not duplicated.
- Not found (greps tried: `rev-list`, `rev-parse` outside tracon/qwen snapshot, `punctuation_chars`, `def .*marker`, `def .*frontmatter` for a writer): no shared git-range helper, no shell-command splitter beyond `shlex.split` token-presence checks (`enforce_prd_location._validate_bash_mode`, `check_build_overhead`), no frontmatter writer. Each is written once in the layer its consumer lives in.

## Alternatives considered

1. **Smallest diff**: stall record gains `commit_range`/`commits`, guard reads the deferred JSON, no marker, no hold refresh, no resolve verb (operator resolves by hand). Rejected: the PRD fixes the marker, the mirror, the notice and the three choices as contracts; without the marker the guard would have to parse every batch's deferred JSON to find unresolved stalls.
2. **Chosen**: marker file (PRD contract) plus a GC-exempt journal in `ledger/` as the durable twin, batch mirror for display, custody folded into `do_stall` as one site-keyed step so retry/idempotency rides the existing `stall_op`/op_id machinery. Extra size over (1) buys: retry-stable capture, one-notice hold PRD, attended resolve that records before clearing, and a guard that stays armed after the 14-day GC (the journal is retention insurance, not a second report surface - nothing renders it).
3. **Separate `autopilot custody record` verb called by prose after the stall**: rejected - the PRD requires the capture before the move and one operation id; a second verb re-introduces the crash window between stall and custody that `stall_op` exists to close, and a caller could pass a range.

Guard parser: (a) `shlex.shlex(punctuation_chars=True)` - loses comment/newline correctness (`# ...` swallows the next line; `echo '#'; git push` hides the push); (b) full shell grammar - out of scope. Chosen: a ~30-line quote-aware splitter + `shlex.split` per segment, with the conservative fallback for anything dynamic.

## Risks & edge cases

- Zero-commit custody (`commits == 0`, e.g. cap-out on a PRD whose only commits were reverted): recorded as-is; `revert` of an empty range exits 5, `accept` clears it. Documented, not special-cased.
- `work_start_sha` absent at cap-out (PRD never reached Phase 3 - not a real path, since a review needs work), git missing or timing out -> exit 2 with the capture-failed stderr, state and PRD untouched; the recovery.md row retries once then PAUSES the batch (row 1: a CRITICAL cannot ship uncustodied). Never the corrupted-state row, never a stall under another site.
- Retention: purge-devlocal (`stale-autopilot`, 14 days, trash-first, manual) can trash `critical-on-master` and the batch deferred JSON; the journal in `ledger/` is exempt and the guard/resolve read it, so the guard stays armed. Trashed files are recoverable from `.trash/`; the deferred JSON's 14-day exposure is the pre-existing one SKILL.md § Retention already documents.
- Concurrency: a stall and an attended resolve on the same repo serialize on the marker lock; two loops per repo are already refused by the loop registry.
- Wrong checkout at resolve: refused (exit 5) until `entry.branch` is checked out; a feature branch that contains the commits can never release custody.
- Custody in a repo shared by two projects (two `dev/local` roots under one git toplevel): the locator holds the last stall's marker; the M2 walk-up still finds the current project's own marker. Not a real layout today.
- Empty-tree sentinel base: `rev-list --count` accepts it; `git revert` does not (tree, not commit), so resolve expands the range to explicit commits for that base only.
- Later commits on master after the stall make `revert` conflict -> exit 5, Git left mid-revert for the operator, custody retained (PRD Risks).
- The guard runs on every Bash call: the `"push" not in command` short-circuit keeps the common path to one `in` check; a real push costs one `git rev-parse` (5s timeout).
- False denies are possible (a `cd` whose success is unknown keeps the old cwd as a candidate; a `cd` inside `{ }` leaks). Documented as grammar limits.
- Hold refresh always adds both keys; `frontmatter._HEAD_LINES` 20 -> 22 absorbs them, so a block that parsed before the refresh parses after it with every existing key intact; tested for blocks closing on lines 18, 19 and 20 (both keys present, `design_gate: user` and `pause_on_ambiguity: true` still applied by `frontmatter.parse`).
- Journal growth: bounded by `compact_journal` at every successful resolve (O(pending) rows); between resolves it grows by one row per stall retry, which is a handful per batch at most.
- Bare-repo-backed projects (`~/.claude`): `git -C` cannot open them, so capture and resolve need `state.git_dir` (captured at Phase 3) - covered by a `git init --bare` + `--work-tree` fixture in `test_custody.py`. On the guard side the `repo_root` entry key + walk-up marker lookup covers a push issued from inside the project; a push issued from `$HOME` itself finds no marker (no `$HOME/dev/local`) - documented limitation.
- Next changes boxed in: 00194 (design-critical rework) and 00195 (stub minting for deferred findings) consume the marker entries and the `custody` ledger records; both keys are stable strings, nothing here calls either.
- 00188/00189 leave `do_stall` alone; the site-keyed step keeps other sites byte-identical in behavior (`test_records_stall.py` unchanged).

## Test strategy outline

- `cli/test_custody.py` (unittest, tmp git repos via `git init` + 3 commits, plus one `git init --bare` + `--work-tree` fixture driven through `git_dir`): capture range/count; invalid/missing base -> 2 with the `autopilot: cap_critical custody capture failed:` stderr prefix and PRD still in wip, state byte-unchanged; EMPTY_TREE base resolves by `revert` in a first-commit repo; retry after HEAD advances keeps the stored range (`stall_op` seeded); pending `deferred_decisions` migrate before reset, `-dd<i>` op_ids dedupe on retry; frontmatterless hold refresh; refresh idempotency and the 18/19/20-line overflow cases; second run of the same op yields one marker entry, one journal `recorded` row is enough (last wins), one notice; non-cap_critical stall writes no marker; failpoint `after-append-before-custody` and an unwritable marker path -> 9 with hold/intent/unreset state, then a clean retry -> 0; notify called once (mock `notify_out.notify`), including a first attempt that failed after the marker upsert; `git config --get autopilot.custodyMarker` set after the stall; `pending()` still lists the entry after the marker file is deleted (journal restore); resolve via subprocess (`__main__.py custody resolve`): revert / branch-and-revert (branch at range end, second run idempotent) / accept (git untouched, `git log` unchanged), refused on a different checkout (5) and mid-revert (5), rerun after the revert landed reconciles by `This reverts commit <sha>.` and does not double-revert, an unrelated revert commit does NOT count (custody retained), partial multi-commit revert -> 5, a recorded different choice -> 1 with cleanup done, ledger record written before removal, marker, journal `resolved`, locator and `batch.critical_on_master` cleared only on success, journal compacted to pending rows, conflict -> 5 with custody retained; `custody list` prints the journal-only entry after the marker is deleted and exits 9 on a corrupt journal line; a half-written cap_critical `stall_op` (no `commits`) -> exit 2, state untouched, no recapture.
- `hooks/test_guard_push_on_critical.py`: pure `split_simple_commands`/`parse_git_call`/`is_push_like` tables (direct, absolute git, `command git`, `FOO=1 git`, `GIT_WORK_TREE=x git push`, `{ git push; }`, `then git push`, `-C a -C ../b`, `-c k=v`, `--git-dir`/`--work-tree` both forms, `-C /x --work-tree . push`, compound `;`/`&&`/`||`/`|`/newline/`( )`, `echo 'git' 'push'`, `git log push`, `git -c push=1 status`, `2>&1`, `git > /dev/null push`, `git pu''sh`, `if git push; then :; fi`, `git "${ACTION:-push}"`, `echo "$(git push)"`); `decide` against tmp repos with and without markers (payload cwd, `cd` chain, `true || cd /clean && git push` from a guarded cwd denies, `(cd /clean); git push` from a guarded cwd denies, `-C` target, locator-only discovery from an unrelated cwd with explicit `--git-dir/--work-tree`, journal-only discovery after the marker is deleted, unresolved `$DIR` fallback both ways, absent/empty marker allows, corrupt marker and corrupt journal line deny with the degraded line, malformed quote fallback); the block text names PRD, range, branch and the resolve command; `hooks.json` lists the guard once under the Bash matcher and keeps `enforce_prd_location.py`.
- `cli/test_render_custody.py`: `render report --stalled --stdout` with a seeded stall record carrying a range -> `- Commits:` line; without -> unchanged; `test_golden_contracts.py` stays green (`report-section.md` byte-identical).
- `cli/test_custody_prose.py`: the § Prose contract pins.
- `bash dev/bin/release-checks` green.

## Review log

Dispatch 1 fixed (blockers): exit-2 capture failure now discriminated from the corrupted-state row by its stderr prefix with a retry-then-`sub_skill_fail` action; `state.git_dir` captured at Phase 3 and carried into stall_op/marker so capture and resolve work for bare-repo-backed projects; the guard strips shell reserved words / group openers before the executable; resolve expands an EMPTY_TREE range to explicit commits. Also corrected `project_root` to `parents[2]` (factual off-by-one).

- non-blocker: purge-devlocal's `stale-autopilot` rule (14d, `autopilot/**` except `ledger/**`) trashes `critical-on-master` and the deferred JSON of an unresolved custody older than 14 days, silently disarming the guard. Follow-up in the agent-skills repo (exempt the marker) or re-touch the marker at Phase 0; note the rule in the state-schema marker row.
- non-blocker: `resolve` step 1 must catch `CustodyError` from `load_marker` (-> 9), and step 4 must catch `state.StateError`/`schema.SchemaError` as well as `OSError` (-> 9, printing that the mirror is stale while custody is closed - marker is the source of truth).
- non-blocker: hold-PRD notice must be replaced in place when present (only insert with blank-line padding when absent) so retries do not grow the gap; pin `refresh(refresh(t)) == refresh(t)`.
- non-blocker: `branch-and-revert` retry after a conflict fails on `git branch` (exists); make branch creation idempotent (skip when `refs/heads/custody/<stem>` already points at `<end>`) and document that a hand-finished revert closes custody with `--choice accept`.
- non-blocker: reuse `hooks/_common.resolve_toplevel` (memoized `git rev-parse --show-toplevel`) for the `-C` chain branch; name the guard's wrapper `target_toplevel` to avoid the import collision.
- non-blocker: a present-but-unparseable marker should print `policy hook degraded: guard_push_on_critical: unreadable <path>` and deny (evidence of pending custody), not silently allow.
- non-blocker: treat leading `GIT_DIR=` / `GIT_WORK_TREE=` assignments as the equivalent flags (flags win when both present).
- non-blocker: decide `created` from the marker at 4b entry, notify only after every 4b write succeeded (a rewrite failure after the upsert must not lose the one notification).
- question: should a migrated deferral keep its own `cycle` (`decision.get("cycle", state["cycle"])`) rather than be re-stamped with the stall cycle? Planner: keep the decision's own cycle when present.
- question: `custody resolve --prd` should accept a pasted path (`Path(arg).name.removesuffix(".md")`) and name the accepted forms in the exit-1 message.

dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 8, question 2

Dispatch 2 fixed (cardinal sin + blockers): GC-exempt custody journal `ledger/custody.jsonl` as the restore source behind the marker (guard and resolve read marker ∪ journal); `marker_lock` around every marker read-modify-write; frontmatter overflow strategy that never pushes the closing `---` past line 20; subshell scope stack and candidate-cwd set in the guard (`(cd /clean); git push` denies); `-C` chain applied before `--work-tree`/`--git-dir`; `git config --local autopilot.custodyMarker` locator so a push at the bare-backed repo from any cwd finds the project marker; unresolved subcommand and `$( )` words count as uncertain, and the uncertain path checks every resolvable target repo; entry `branch` + checkout/mid-operation refusal at resolve; durable resolve boundary (ledger record wins on rerun, already-reverted detection, idempotent branch creation and cleanup); capture failure now PAUSES (row 1) instead of stalling under `sub_skill_fail`. Adopted dispatch-1 non-blockers while there: `resolve_toplevel` reuse, corrupt-marker deny, `GIT_DIR=`/`GIT_WORK_TREE=` assignments, notify-after-all-writes, in-place notice replace, path-tolerant `--prd`.

- non-blocker (fixed in prose): attended Phase 0 STOPs on a resolve exit 5 instead of selecting a PRD over an unfinished revert.

dispatch 2 (codex): cardinal-sin 1, blocker 9, non-blocker 1, question 0

Dispatch 3 fixed (cardinal sin + blockers): `compact_journal` bounds the journal to O(pending) rows at every resolve; resolve reconciles exactly (a `resolving` row with `head_before`, then `This reverts commit <sha>.` bodies per target - an unrelated revert never releases custody, a partial one refuses); the guard normalises quotes/backslashes before its `push` shortcut, consumes redirection operands, strips `if`/`while`/`until`, never drops pre-`cd` candidate cwds (`true || cd /clean && git push` denies), and treats present-but-unreadable custody state as a deny (`CustodyStateError`) instead of an allow; `_stall_op_malformed` validates the complete cap_critical capture on every existing intent (no recapture, no half-written intent accepted); `frontmatter._HEAD_LINES` 20 -> 22 so the hold refresh always inserts both keys without breaking existing keys. Non-blockers adopted in the contract: range/count from one captured `end`; `created` derived from the hold-PRD notice so a failed first attempt still notifies on retry; migration keeps a decision's own `cycle`; Phase 0 enumerates through `autopilot custody list` (marker ∪ journal).

dispatch 3 (codex): cardinal-sin 1, blocker 6, non-blocker 4, question 0
