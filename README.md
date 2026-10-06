# autopilot

A PRD-driven build and review pipeline for Claude Code. Hand it a spec; it plans
the tasks, implements them one at a time, and then refuses to call the work done
until three independent review lenses agree.

The point is the review, not the build. Anything can write code that looks right.
This pack is built around the assumption that the code is subtly wrong until a
reviewer who cannot see your reasoning says otherwise.

## What's inside

Eleven skills:

| Skill | Does |
|---|---|
| `run-autopilot` | Drives the whole lifecycle: catchup, design, plan, work, review-rework loop |
| `design-solution` | Turns a PRD into a reviewed design doc before planning |
| `plan-tasks` | Breaks a PRD into sequenced, session-sized tasks |
| `work` | Executes one task at a time, dispatching an implementor and committing after each |
| `review-work-completion` | Consensus review of finished work against the PRD |
| `review-blindly` | Spec-only lens: never sees the diff, finds the code itself |
| `review-plan` | Critiques a plan before implementation |
| `fast-track` | Runs one spec card through the full review roster, skipping the loop phases |
| `use-codex`, `use-gemini`, `use-sonnet` | Non-interactive dispatch to external model CLIs |

Eighteen agents. One implementor (`ivan`), four worker tiers (`worker-haiku`,
`worker-sonnet`, `worker-opus`, `worker-fable`) that run an assembled persona
at a set model and effort, and thirteen reviewers across four lenses: consensus (`alice`, `bob`, `carl`), blind (`blake`), doubt (`eve`), and
dimensions (`rita` requirements, `cora` correctness, `grace` quality, `toby`
tests, `mallory` security, `trent` rubric, `victor` adversarial verification,
`pat` per-task patches).

Nine hooks. Seven keep a loop session on its contract:
`guard_phase_delegation.py` (no phase skill handed to a subagent),
`guard_skill_after_leave.py` (no autopilot skill after a hand-off),
`note_session_leave.py` (records which session wrote its `leave` row),
`guard_stop_on_live_lanes.py` (no stop while a codex or gemini lane runs),
`autopilot_context_cap_hook.py` (hands off before the context cap),
`review_coverage_hook.py` (no exit with an incomplete review file) and
`validate_state_json_hook.py` (catches an unparseable `state.json` write). The
other two are below.

`enforce_prd_location.py` keeps working documents in their
declared homes instead of scattered through the repo. It runs on `PreToolUse`
for `Edit`, `Write`, `MultiEdit` and `Bash`: file mode blocks a PRD written
outside a `docs/dev/project-management/prds/` lifecycle directory, and Bash mode blocks a command
that references a repo-root `backlog/`, `wip/`, `hold/` or `done/`.
`guard_push_on_critical.py` runs on `PreToolUse` for `Bash` and denies a
`git push` into a repository with pending cap_critical custody (a capped-out
batch left an unresolved CRITICAL on master); run `autopilot custody resolve`
first.

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
  shell functions. Drive `/autopilot:run-autopilot` from your own automation instead.
- **Run state.** Everything under `docs/dev/project-management/**` — `state.json`, reports,
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

### Autoclaude role effort

Coordinator effort defaults to `low` for build, review, and finalization.
`_AUTOPILOT_COORDINATOR_EFFORT` overrides that default; existing phase effort
settings override it for their phase. Invalid nonempty effort values fail before
launch; empty values use the default. Model promotions and Fable authorization
are unchanged. Unknown recovery phases retain Opus/xhigh.

Native worker agent definitions explicitly set Haiku/low, Sonnet/medium,
Opus/high, and authorized Fable/xhigh. Alice and Blake use high effort. Worker
and reviewer settings do not inherit coordinator effort. External Claude reviews
pass `--effort high` to `sonnet-run.sh`; implementations use their tier default.
These defaults require the updated plugin, not merely a lower launcher setting.
