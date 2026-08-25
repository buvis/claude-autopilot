# autopilot

A PRD-driven build and review pipeline for Claude Code. Hand it a spec; it plans
the tasks, implements them one at a time, and then refuses to call the work done
until three independent review lenses agree.

The point is the review, not the build. Anything can write code that looks right.
This pack is built around the assumption that the code is subtly wrong until a
reviewer who cannot see your reasoning says otherwise.

## What's inside

Ten skills:

| Skill | Does |
|---|---|
| `run-autopilot` | Drives the whole lifecycle: catchup, design, plan, work, review-rework loop |
| `design-solution` | Turns a PRD into a reviewed design doc before planning |
| `plan-tasks` | Breaks a PRD into sequenced, session-sized tasks |
| `work` | Executes one task at a time, dispatching an implementor and committing after each |
| `review-work-completion` | Consensus review of finished work against the PRD |
| `review-blindly` | Spec-only lens: never sees the diff, finds the code itself |
| `review-plan` | Critiques a plan before implementation |
| `use-codex`, `use-gemini`, `use-sonnet` | Non-interactive dispatch to external model CLIs |

Fourteen agents. One implementor (`ivan`), and thirteen reviewers across four
lenses: consensus (`alice`, `bob`, `carl`), blind (`blake`), doubt (`eve`), and
dimensions (`rita` requirements, `cora` correctness, `grace` quality, `toby`
tests, `mallory` security, `trent` rubric, `victor` adversarial verification,
`pat` per-task patches).

One hook: `enforce_prd_location.py`, which keeps working documents in their
declared homes instead of scattered through the repo. It runs on `PreToolUse`
for `Edit`, `Write`, `MultiEdit` and `Bash`: file mode blocks a PRD written
outside a `dev/local/prds/` lifecycle directory, and Bash mode blocks a command
that references a repo-root `backlog/`, `wip/`, `hold/` or `done/`.

**If you already run this hook from your own config, disable one of them** —
otherwise both fire and you get the same block twice.

## Recursion guard

Two reviewers dispatch out to external CLIs: `bob` through `codex-run.sh` and
`carl` through `gemini-run.sh`. Since this pack is reachable from those same
CLIs, a lane could spawn codex inside codex.

Both runners now refuse. They exit 3 when `AUTOPILOT_DISPATCH_DEPTH` is already
set, and again when a host marker (`CODEX_SESSION_ID`, `COPILOT_CLI`) says the
process is already inside a CLI agent. `review-work-completion` treats a non-zero
runner exit as a failed reviewer and continues with the rest, so the refusal
degrades instead of halting a cycle. Markers are documented in
`skills/use-codex/references/host-markers.md`.

**Known ceiling:** the native Gemini CLI could not be probed (it refuses to
authenticate with `IneligibleTierError` as of 2026-08-25), so no marker is known
for it. `gemini-run.sh` defaults to the Copilot backend, which is covered. If you
force `GEMINI_BACKEND=gemini`, recursion through that path is bounded only by the
depth counter, which permits exactly one nested call before refusing.

## Paths

Skill bodies use `${CLAUDE_PLUGIN_ROOT}`, which Claude Code substitutes when the
skill loads. Files under `references/` are read at runtime and are **not**
substituted — the four skills that have such references carry a note saying so
and naming the resolved root. Scripts locate their own siblings from `$0` or
`__file__` and never read an install path.

## Install

```
/plugin marketplace add buvis/claude-plugins
/plugin install autopilot@buvis-plugins
```

## Update

```
/plugin update autopilot@buvis-plugins
```

## Alternative: install directly from this repo

```
/plugin marketplace add buvis/claude-autopilot
```

## What intentionally stays out

- **The `autoclaude` wrapper.** The shell front-end that relaunches headless
  sessions across a batch lives in the author's dotfiles. A plugin cannot install
  shell functions. Drive `/run-autopilot` from your own automation instead.
- **Run state.** Everything under `dev/local/**` — `state.json`, reports,
  transcripts — belongs to the repo being worked on, not to this pack.
- **`notify.py`.** Desktop notification glue, host-specific, stays personal.
- **`save-session` / `resume-session` / `restore-tasks`.** Codex storage
  workflows with no meaningful Claude projection.
- **The qwen lane.** `work` can route a task to a local Qwen model through
  `use-qwen`, which is not part of this pack. Without it that route is simply
  unavailable; nothing else changes.
- **`review-fanout.workflow.js`.** The fan-out consensus engine is a host-local
  workflow file, conventionally `~/.claude/workflows/review-fanout.workflow.js`.
  It is needed only by the opt-in `workflow` and `shadow` values of a PRD's
  `consensus_engine`. Absent, both fall back to `legacy`, which is the default
  and needs no such file.
- **`rules-library/rationalizations.md`.** `design-solution` reads it for the
  synonym sets that drive its reuse sweep. Absent, the sweep runs on the model's
  own synonyms and says so in its summary line.

## Development

```
bash dev/bin/release-checks     # the gate: registry + runner guards
dev/bin/release minor           # bump, tag, stamp the central marketplace
```

## License

MIT. See [LICENSE](LICENSE).
