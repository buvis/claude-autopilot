# Style-Limit Gate (step 5.65)

Moved out of SKILL.md step 7.0, which measured a whole phase at once (PRD
00163). The gate now runs on one task's own diff, so an oversize file is split
while the context that produced it is still in session, and step 5.7's reviewer
reads an already-conforming diff.

Base = `<task_base_sha>`, the HEAD SKILL.md step 2 captures right after
`task-start`. Every git invocation below runs with the repo's own
`--git-dir`/`--work-tree` flags in a bare-repo home, and every interpolated path is
`shlex.quote()`-d before it lands in a command - `git ls-files` reports whatever
names exist on disk, spaces and `$(...)` included. Commands are written on one
line each; do not re-wrap them.

## Diff construction

Write the committed range with `git diff <base>..HEAD --output=${TMPDIR:-/tmp}/task-diff-<task-id>.txt`, then cover the Python files no commit holds yet: for every path `git ls-files --others --exclude-standard -- '*.py'` prints, append its whole-file add block with `git diff --no-index -- /dev/null <path> >> ${TMPDIR:-/tmp}/task-diff-<task-id>.txt` (`--no-index` exits 1 whenever it finds differences, which is the normal case here — only exit ≥2 is a real failure), and `mv ${TMPDIR:-/tmp}/task-diff-<task-id>.txt dev/local/tmp/task-diff-<task-id>.txt` once the appends are done: stage it outside `dev/local/` because a shell append into that tree is blocked, and with no untracked `.py` file the moved diff is byte-identical to the committed range.

## Invocation

The candidate list is the changed Python files from `git diff --name-only --diff-filter=d <base>..HEAD -- '*.py'` (deleted files excluded: the script reads every path it is given) plus those untracked paths. The combined list is empty — a docs-only or config-only task, or any task that touched no `.py`: skip the script and record `style_gate: clean`. Otherwise:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/check_style_limits.py --diff dev/local/tmp/task-diff-<task-id>.txt <every candidate as an absolute path>
```

Function spans come from `review-work-completion/scripts/compute_mech_facts.py`,
reused by import (see SKILL.md `## Dependencies`).

## Outcome ladder

Carried over from step 7.0 unchanged except for what follows a failure: the task
proceeds to step 5.7, where the phase used to proceed to its suite.

- **Exit 0**: record `style_gate: clean`.
- **Exit 1**: write the violation lines to the `FAILING_TESTS` scratch file
  (`dev/local/tmp/ivan-style-violations-<task-id>.md`) and run the fix dispatch
  below once, commit per step 5, then re-run from § Diff construction - the fix
  commit moved HEAD, so rebuild both the diff and the candidate list or a sibling
  module the fixer just created is never measured. Clean ->
  `style_gate: fixed:<sha of the fix commit>`; still exit 1 ->
  `style_gate: failed:<the violation lines, joined by "; ">` and proceed to step
  5.7 anyway (fail loud, never silent).
- **Exit 2** (or any other non-0/1 exit): the gate could not run at all, so
  there are no violation lines to hand a fix agent — record
  `style_gate: failed:<the script's stderr message>`, do NOT dispatch Ivan, and
  proceed to step 5.7 anyway (fail loud, never silent, same as the
  still-failing exit-1 case).

A `failed:` value never blocks the task and never changes its `outcome`: it is a
fail-loud marker, so a skipped check never reads as a passed one.

## Fix dispatch

Exit 1 only, and the one Ivan dispatch that carries a widened allowlist —
splitting an 800-line file needs sibling modules that are by construction absent
from the task's Contract paths, and `agents/ivan.md` tells a fixer to report a
blocker rather than touch a file nobody listed.

Write `dev/local/tmp/ivan-<task-id>-style-files.txt`: one absolute path per
violating file (every violation line names one), then one absolute directory
path per distinct parent directory of those files, each directory line suffixed
` (new modules may be created here)`. Parent directories of violating files
only — never the repo root, never a directory walked further upward. Every other
Ivan dispatch keeps passing `dev/local/tmp/ivan-<task-id>-files.txt` unchanged.

Render and dispatch with `references/gate-failure.md` § Style-fix render, whose
`RETRY_INSTRUCTION` is verbatim:

```
Fix only the listed style-limit violations. You may create new modules in the directories marked above and update imports in the listed files to use them. Do not change behavior, do not touch other code, and do not modify tests except to split a test file a violation line names.
```

`agents/ivan.md` stays untouched: `{RETRY_INSTRUCTION}` is already free text, and
a persona edit would reach every dispatch instead of this one.

## Split hygiene

Runs immediately after the style-limit ladder above, on the same candidate list
narrowed to test paths — `is_test_path` from
`${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/work_routing.py` decides, so the
subset is the one steps 5.6 and 5.7 already agree on. Empty subset: record
`split_hygiene: skipped:no-tests` and run nothing.

This is the mechanical half of a question the self-deslop pass is forbidden to
answer (PRD 00166). It reports bindings only — a module-level name nothing in
the file reads, a local reassigned before its previous value is read — never an
assertion, test function, fixture or parametrization, so the fix that follows is
deletion-only.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/check_split_hygiene.py <every test candidate as an absolute path>
```

No `--diff` here, unlike the style gate: a binding a split left dead is dead
whether or not a hunk touched its line, and the checker has no diff to consult.

## Split-hygiene outcome ladder

- **Exit 0**: record `split_hygiene: clean`.
- **Exit 1**: write the reported lines to the `FAILING_TESTS` scratch file
  `dev/local/tmp/ivan-split-hygiene-<task-id>.md` and run the fix dispatch below
  once, commit per step 5, then re-run from § Split hygiene — the fix commit
  moved HEAD, so rebuild the candidate list. Clean →
  `split_hygiene: fixed:<sha of the fix commit>`; still exit 1 →
  `split_hygiene: failed:<the reported lines, joined by "; ">` and proceed to
  step 5.7 anyway (fail loud, never silent).
- **Exit 2** (or any other non-0/1 exit): the check could not run, so there are
  no lines to hand a fix agent — record
  `split_hygiene: failed:<the script's stderr message>`, do NOT dispatch Ivan,
  and proceed to step 5.7 anyway.

A `failed:` value never blocks the task and never changes its `outcome`, exactly
as `style_gate` does not.

## Split-hygiene fix dispatch

Exit 1 only. Render and dispatch with `references/gate-failure.md` § **Retry**
render — not § Style-fix render, which widens the allowlist. Two lines differ
from that shape: `FAILING_TESTS` is the split-hygiene scratch file, and
`RETRY_INSTRUCTION` is the deletion-only string below. `FILE_PATHS` stays the
task's own `dev/local/tmp/ivan-<task-id>-files.txt`, unchanged:
**no widened allowlist here**. A test file this check can flag is one the task already
touched, so it is inside the task's Contract paths, and a deletion creates no
new module.

`RETRY_INSTRUCTION` is verbatim:

```
Delete only the listed unused or shadowed bindings. Do not change any assertion, test function, fixture or parametrization. Do not add code.
```
