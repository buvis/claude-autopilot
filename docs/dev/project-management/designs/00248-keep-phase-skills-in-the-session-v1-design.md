## Architecture fit

Two independent, small surfaces, both already-established patterns in this
repo:

- A new PreToolUse hook on the `Agent` tool, in `hooks/`, alongside the
  existing `guard_skill_after_leave.py` (PreToolUse/Skill) and
  `guard_push_on_critical.py` (PreToolUse/Bash). Same module shape: a single
  pure predicate, a `main()` that reads stdin via `_common.read_input`, and
  `allow()`/`block()` from `hooks/_common.py`. Registered in `hooks/hooks.json`
  under a new `"Agent"` matcher (none exists today).
- A one-sentence addition to `cli/runner.py`'s `CLI_SUFFIX` string, which
  already rides every autopilot launch prompt (`prompt_for`).

Both are read-only with respect to `state.json` and do not touch the
build/review/done state machine; they are enforcement and prose, not new
phases.

## Module placement

- **New file** `hooks/guard_phase_delegation.py` — the predicate
  `is_phase_delegation` and the PreToolUse `main()`.
- **New file** `hooks/test_guard_phase_delegation.py` — subprocess-driven
  tests, same harness shape as `hooks/test_guard_skill_after_leave.py`.
- **New directory** `hooks/fixtures/phase_delegation/` — the four observed
  delegation prompts (`denied/*.txt`, recovered from the retained
  2026-10-03 session transcript where possible, else reconstructed and
  labeled as such — see the note under Interfaces & contracts) and a
  committed sample of 20 allowed prompts (`allowed/*.txt`), copied verbatim
  from `docs/dev/tmp/dispatch-*.txt`.
- **Edit** `hooks/hooks.json` — add a `"Agent"` matcher entry to `PreToolUse`.
- **Edit** `skills/run-autopilot/cli/runner.py` — append one sentence to
  `CLI_SUFFIX`.
- **Edit** `skills/run-autopilot/cli/test_runner.py` — one new test asserting
  the rendered prompt contains the new sentence.
- **Edit** `skills/run-autopilot/references/phase-build.md` — one sentence
  each in Phase 2 and Phase 3.
- **Edit** `skills/work/SKILL.md` — one sentence appended to the existing STOP
  paragraph (line 51 area).
- **Edit** `dev/bin/release-checks` — add the new test file to its `[checks]`
  block set.
- **Edit** `CHANGELOG.md` — one `[Unreleased]` / `### Added` / `**hooks**`
  line.

## Interfaces & contracts

### `hooks/guard_phase_delegation.py`

```python
def is_phase_delegation(tool_input: dict) -> bool:
    """True iff this Agent dispatch instructs the subagent to run a phase
    skill (/autopilot:work, /autopilot:plan-tasks, /autopilot:design-solution,
    or the Skill tool generally) rather than a single per-task job.

    Looks at tool_input["prompt"] and tool_input["description"] (both
    optional, default ""). Case-insensitive substring/regex match on:
      - an imperative instruction to run/execute/invoke a phase skill or its
        SKILL.md, OR
      - the phrase "work phase" / "plan phase" / "design phase" together
        with an imperative verb (run/execute/continue/resume) OR
      - an instruction to "read work/SKILL.md" / "read plan-tasks/SKILL.md"
        / "read design-solution/SKILL.md" "and run/follow every task"

    A payload where tool_input is not a dict, or has neither key present as
    a non-empty string, returns False (fail open).
    """
```

Exact predicate (regex, compiled once at module scope):

```python
_IMPERATIVE = r"(run|execute|invoke|follow|continue|resume)"
_PHASE_JARGON = r"(work phase|plan(?:ning)? phase|design phase)"
# (?P=bt) requires the SAME backtick-or-nothing to close immediately after
# the skill name - "`/autopilot:plan-tasks`" (tight close) matches; "invoke
# `/autopilot:design-solution dev/local/prds/wip/..." (an opening backtick
# whose matching close is many words later, around an args list) does not,
# because nothing closes immediately. No trailing \b: a literal backtick is
# a non-word char, and \b between two non-word chars (backtick, space)
# never matches - see Review log dispatch 3 for the bug this caused.
_BARE_SKILL = r"(?P<bt>`?)(?:/)?(autopilot:work|autopilot:plan-tasks|autopilot:design-solution|plan-tasks|design-solution)(?P=bt)"
_SKILL_READ = (
    r"read\s+(?:skills/)?(work|plan-tasks|design-solution)/SKILL\.md"
    r".{0,60}\b(run|follow|execute|continue)\b.{0,20}\b(every|all)\s+tasks?\b"
)
_NEGATION = r"\b(not|never|n't|does\s+not|doesn't|don't|won't)\b"
_NEGATION_RE = re.compile(_NEGATION, re.IGNORECASE)

_DELEGATION_PATTERNS = (
    # jargon form, either order, loose gap: nobody says "the work phase"
    # except to mean the whole phase, so a wider gap is safe here.
    re.compile(rf"\b{_IMPERATIVE}\b.{{0,40}}\b{_PHASE_JARGON}\b", re.IGNORECASE),
    re.compile(rf"\b{_PHASE_JARGON}\b.{{0,40}}\b{_IMPERATIVE}\b", re.IGNORECASE),
    # bare skill-name form: the imperative must sit immediately before the
    # skill name (verb-object order only, tight gap) - this is what tells
    # "run plan-tasks" apart from "plan-tasks tests and run [pytest]" or
    # "tests for design-solution", where the real object of the verb is
    # something else entirely.
    re.compile(rf"\b{_IMPERATIVE}\s+(?:the\s+)?{_BARE_SKILL}", re.IGNORECASE),
    re.compile(_SKILL_READ, re.IGNORECASE | re.DOTALL),
)


def _negated_before(text: str, start: int, window: int = 20) -> bool:
    """True iff a negation word sits in the `window` chars immediately
    before `start` - the match is `run plan-tasks` inside `does not run
    plan-tasks`, and that is a prohibition, not a delegation."""
    return bool(_NEGATION_RE.search(text[max(0, start - window):start]))
```

`is_phase_delegation` joins `prompt` and `description` with a newline, runs
`finditer` (not `search`) for every pattern so every candidate match is
checked, and returns `True` iff at least one candidate match is NOT
`_negated_before` it. `re.DOTALL` on the `_SKILL_READ` pattern lets its
`.{0,N}` gaps cross a newline (a prompt's imperative and its object
routinely sit on different lines); the other three patterns keep the
default non-`DOTALL` `.` because their looser gaps are exactly where a
false positive would hide inside a long multi-paragraph prompt — a
`run`/`plan phase` pair 40 chars apart but on different lines is not the
same instruction.

**Direction and tightness, and why they differ between the jargon and
bare-skill forms** (dispatch 2, a codex adversarial pass, broke the first
version of this regex with three real counter-examples — see Review log):

- `_PHASE_JARGON` ("work phase" / "plan phase" / "design phase") stays
  bidirectional with a loose `{0,40}` gap, because this exact phrase is
  close to unambiguous jargon for "the whole phase" — no real per-task
  prompt in the corpus says "the work phase" to mean anything else, so the
  loose gap buys robustness against phrasing variance with no observed
  cost.
- `_BARE_SKILL` ("plan-tasks" / "design-solution" / "autopilot:work" / …)
  is the opposite: these are also ordinary nouns a per-task prompt uses
  when it edits or tests the thing (`"Fix plan-tasks tests and run
  pytest."`, `"Run tests for design-solution."`) — codex's repro showed
  both false-denied under the old bidirectional loose-gap pattern. The verb
  must now sit **immediately before** the skill name (`run plan-tasks`,
  `execute design-solution`, optionally with one `the`), never after and
  never with other words between: that is the one word order real
  delegation prompts use ("told to run plan-tasks") and the one word order
  "fix X tests and run Y" cannot produce, because there the verb's real
  object (`pytest`, `Y`) sits between the skill name and `run`.
- `_SKILL_READ` keeps its `skills/`-optional prefix (every real instance in
  this repo is `skills/work/SKILL.md`, never bare `work/SKILL.md`) but now
  **requires an explicit "run/follow/execute/continue every/all task(s)"
  clause after the read instruction**, not just the read instruction alone
  — codex's repro showed `"Read skills/work/SKILL.md and fix its Phase 3
  wording."` false-denied under the old unconditional pattern; reading a
  skill file to edit it is exactly what 16 of the real corpus prompts do.

**Unverified pending real fixture capture:** the "four observed denials" are
known today only from a truncated summary line in
`docs/dev/project-management/notes/batch-0.7.0-reflection-2026-10-03.md`
("`Agent · Execute work phase …`") — no verbatim transcript for any of the
four cases is currently recoverable (`rg` over
`docs/dev/project-management/autopilot/dispatch-metrics.jsonl` finds
nothing). Task 1 (Phase 0, below) must first attempt to recover the real
prompt text from the retained session transcript/log for the 2026-10-03
00242 build session; if unrecoverable, it builds the fixtures from the
PRD's own quoted paraphrases and the realistic phrasing above, and must
spell out in the fixture file's own leading comment that it is a
reconstruction, not a captured verbatim prompt. Either way, the regex above
is re-validated against whatever fixture text is actually committed (not
against this doc's prose) during Task 1's own test-writing, which is also
where the `{0,40}` gap bound gets its real evidence.

**Why not a `subagent_type == "general-purpose"` signal (PRD's second
candidate):** 16 of the ~180 allowed corpus prompts mention `autopilot:work`
or `skills/work/SKILL.md` *and* most per-task dispatches already use a named
agent (Ivan, Tess, Devon) — but Phase 3 also legitimately dispatches
`general-purpose` for one-off repo investigation tasks unrelated to running a
phase skill, so gating on `subagent_type` alone would either miss the real
denial cases (named agents can still be told to run a whole phase) or
over-deny legitimate `general-purpose` research dispatches. The imperative +
phase-noun pattern is the correct signal: it tests *what the prompt asks the
subagent to do*, not which agent type carries it, and is the only candidate
that cleanly separates the two Risk-section example sets (the 16 mentions,
all of which *reference* the skill while editing it, never *instruct running
it end-to-end*).

**`main()`:**

```python
def main() -> None:
    if not os.environ.get("_AUTOPILOT_LOOP"):
        allow()
    payload = read_input()
    if not payload:
        print("guard_phase_delegation: empty/unparseable payload, allowing", file=sys.stderr)
        allow()
    if payload.get("tool_name") != "Agent":
        allow()
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        print("guard_phase_delegation: unparseable tool_input, allowing", file=sys.stderr)
        allow()
    try:
        delegates = is_phase_delegation(tool_input)
    except Exception:
        print("guard_phase_delegation: predicate raised, allowing", file=sys.stderr)
        allow()  # fail open, defensive — predicate is pure regex, should not raise
    if not delegates:
        allow()
    block(
        "autopilot: run the phase skill (plan-tasks / design-solution / work) "
        "with the Skill tool in THIS session; dispatch Agent calls only for "
        "per-task subagents (Ivan, Tess, Devon, reviewers). "
        "hooks/guard_phase_delegation.py denied this Agent call."
    )
```

One stderr line on each fail-open path, per the PRD's "fail open … with one
stderr line" — this is the single canonical `main()`; there is no second,
silent variant of the dict check. The `if not payload` check comes BEFORE
the `tool_name` check: `read_input()` returns `{}` (falsy) for empty stdin
or unparseable JSON per `hooks/_common.py`, and that is the "payload the
hook cannot parse" case the PRD's stderr-line requirement names — it is not
the same thing as a normal, well-formed payload for an unrelated tool
(`tool_name == "Bash"`, say), which must stay silent and just `allow()`
without printing anything. Testing `not payload` first, instead of folding
it into the `tool_name` check, is what keeps those two cases distinct:
dispatch 2's adversarial pass caught that an earlier draft folded the empty
check into the tool_name branch, so an empty-stdin call exited silently
(the test's required diagnostic never fired, since `{}.get("tool_name")`
also returns `None != "Agent"` and `allow()` runs first either way).

### `hooks/hooks.json`

Add to `PreToolUse` (new array entry, matcher `"Agent"`):

```json
{
  "matcher": "Agent",
  "hooks": [
    {
      "type": "command",
      "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/guard_phase_delegation.py",
      "timeout": 5
    }
  ]
}
```

### `skills/run-autopilot/cli/runner.py`

`CLI_SUFFIX` (line 80-83) gains a trailing sentence:

```python
CLI_SUFFIX = (
    f" The `autopilot` CLI in this shell is `python3 {CLI_MAIN}`;"
    " no `autopilot` binary or shell function is on PATH."
    " Never call `cat`, `head`, `tail`, `grep` or `find` (a hook blocks them):"
    " use Read, `rg`, and `jq <file>`."
)
```

### `skills/work/SKILL.md`

Append to the existing STOP paragraph (the line ending "...collapses per-task
attempt logging."):

> In loop mode a hook denies dispatching a whole phase skill to an Agent
> (`hooks/guard_phase_delegation.py`) — it does not enforce the one-task-
> per-dispatch rule in general (e.g. `"Implement tasks 1 and 2"` is outside
> its scope; the STOP rule above still governs that case by prose alone).

### `skills/run-autopilot/references/phase-build.md`

Phase 2 (just before "Invoke `/autopilot:plan-tasks` with the selected PRD."):

> Invoke `/autopilot:plan-tasks` with the Skill tool in this session; never
> delegate planning to an Agent.

Phase 3 (just before "Invoke `/autopilot:work` skill."):

> Invoke `/autopilot:work` with the Skill tool in this session; never
> delegate work execution to an Agent.

## Data flow

Unchanged request/response shape of every other PreToolUse hook: the harness
sends one JSON payload on stdin (`session_id`, `cwd`, `tool_name`,
`tool_input`) before dispatching an `Agent` tool call; the hook exits 0
(allow, call proceeds) or 2 with a stderr reason (block, call is refused and
the reason is fed back to the model so it can redispatch correctly — same
mechanics as `guard_skill_after_leave.py`). No state is read or written by
this hook; `_AUTOPILOT_LOOP` (env, already set by the wrapper) is the only
external input besides the payload.

The `CLI_SUFFIX` sentence rides the existing one-way flow:
`prompt_for()` → `build_argv()` → the launched `claude -p` child's first
turn. No new data path.

## Reuse inventory

- `hooks/_common.py`: `read_input()`, `allow()`, `block()` — reused verbatim,
  no new helper needed (checked `rg -i "def (allow|block|read_input)"
  hooks/_common.py`).
- `hooks/guard_skill_after_leave.py`: the structural template for a
  loop-mode-only PreToolUse guard (env check → payload shape check → tool
  check → predicate → block). Nothing importable (its predicate is
  marker-file based, unrelated), but the shape is copied.
- `hooks/test_guard_skill_after_leave.py`: the subprocess-harness template
  for the new test file (`_run`, env construction, payload builders).
- `docs/dev/tmp/dispatch-*.txt`: the ~180-prompt allow corpus already exists
  on disk; nothing to build, just select and copy 20 into
  `hooks/fixtures/phase_delegation/allowed/`.
- Searched for an existing "phase delegation" or "agent dispatch guard"
  concept: `rg -i "phase.delegat|dispatch.*guard|guard.*dispatch"
  hooks/ skills/` — nothing found, this is new.
- Searched for an existing prompt-classification regex utility: `rg -i "re\.compile.*prompt|classify.*prompt" hooks/ skills/` —
  nothing found; the regex is small enough that a shared module would be a
  speculative abstraction for one caller.

## Alternatives considered

1. **Chosen: imperative + phase-noun regex, Agent-tool PreToolUse hook.**
   Smallest correct signal — tests what the prompt instructs rather than
   which agent carries it, matches the PRD's example sets, needs no new
   abstraction.
2. **Smallest-diff alternative: substring match on bare phase-skill names**
   (`"work phase"`, `"plan-tasks"`, `"design-solution"` anywhere in the
   prompt). Rejected per the PRD's own finding: 16 of ~180 real dispatch
   prompts mention these names while editing the very hooks/skills this PRD
   touches, so a bare substring match would deny legitimate work. The chosen
   design is only marginally larger (one regex with an imperative-proximity
   bound instead of a flat substring list) and is what buys correctness on
   that 16-prompt set.
3. **`subagent_type == "general-purpose"` as the primary signal.** Rejected
   (see Interfaces & contracts) — doesn't separate the two example sets
   cleanly; `general-purpose` is also used for legitimate one-off
   investigation, and a named agent can still be mis-instructed to run a
   whole phase.

## Risks & edge cases

- **False positive mid-batch**: bounded by the 3-way test — four observed
  denials, ~180-prompt allow corpus (16 adversarial), fail-open on any
  unparseable payload. A block costs one retry turn (the model rereads the
  reason and redispatches correctly or runs the skill itself), never data —
  this is the PRD's own stated risk tolerance.
- **New delegation phrasing the regex misses**: the predicate is a closed
  pattern set over four observed shapes; a differently-worded delegation
  ("have an agent handle all the tasks for PRD X") would pass. The PRD's own
  mitigation is the post-release signal (an `Agent ·` line in a loop log
  whose prompt runs a phase skill) — no code change needed now, this is the
  explicitly accepted gap.
- **Quoting the denial phrase, as opposed to issuing it**: dispatch 3 found
  `'Add a regression test asserting that "run plan-tasks" is denied.'` still
  matches (the negation filter catches "not run X" but not a quotation of
  X). This has zero occurrences in the real corpus today, but Task 1 of
  THIS PRD writes the denied-fixture test content and may, under loop mode,
  dispatch a per-task Agent prompt that quotes "run plan-tasks" or "run
  design-solution" verbatim while describing what the fixture asserts —
  which this very hook would then deny. Mitigation if it comes up: phrase
  that one dispatch prompt to avoid the exact substring (e.g. build the
  literal string via concatenation in the fixture file itself, not in the
  dispatch prompt that describes it) rather than extending the regex
  further — same accepted-gap reasoning as above, and the cost is one retry
  turn.
- **Next likely changes**: (a) the same predicate style could later guard
  `Task`-tool-equivalent dispatch surfaces if the harness adds one — the
  predicate is kept pure and importable (`is_phase_delegation(tool_input)`)
  so a future hook can reuse it without duplicating the regex; (b) the
  fixtures directory (`hooks/fixtures/phase_delegation/`) is a natural home
  for future observed-delegation-shape additions — keep the denied/allowed
  split so a new shape is a fixture add, not a code change, when the regex
  already covers it; (c) if `docs/dev/tmp/dispatch-*.txt` is purged before
  release (it's scratch, globally gitignored), the test's "parametrized when
  present" branch must still pass on the committed 20-sample fixture alone —
  verified in Test strategy outline below.
- **This design boxes in**: nothing structural — the hook is a pure
  predicate behind a thin main(), easy to extend or replace independently of
  the CLI_SUFFIX change, which is unrelated and independently revertible.

## Test strategy outline

`hooks/test_guard_phase_delegation.py`, subprocess-driven (same harness as
`test_guard_skill_after_leave.py`):

- `test_the_four_observed_delegations_are_denied` — parametrized over the
  four fixtures in `hooks/fixtures/phase_delegation/denied/*.txt` (verbatim
  observed prompts), `_AUTOPILOT_LOOP` set, `tool_name="Agent"` → exit 2,
  stderr names the rule.
- `test_every_real_dispatch_prompt_is_allowed` — parametrized over
  `docs/dev/tmp/dispatch-*.txt` when that directory exists and is non-empty,
  else over the committed `hooks/fixtures/phase_delegation/allowed/*.txt`
  (20 files, copied from the 16-mentioning-skill-names set plus 4 plain
  per-task prompts), `_AUTOPILOT_LOOP` set → exit 0 for every file.
- `test_outside_the_loop_everything_passes` — one denied fixture, no
  `_AUTOPILOT_LOOP` → exit 0 (the env-gate short-circuits before any payload
  parsing).
- `test_unparseable_payload_fails_open` — `tool_input` missing / not a dict /
  empty stdin, `_AUTOPILOT_LOOP` set → exit 0, one stderr line.
- `test_hooks_json_registers_the_guard_on_agent` — reads `hooks/hooks.json`,
  asserts a `PreToolUse` entry with `matcher == "Agent"` whose command
  references `guard_phase_delegation.py`.
- `test_gate_prose_names_the_guard` — `rg`-equivalent (plain string `in`
  check) that `phase-build.md` Phase 2 and Phase 3 and `work/SKILL.md` each
  contain their new sentence.

`skills/run-autopilot/cli/test_runner.py`:

- `test_launch_prompt_forbids_blocked_coreutils` — `prompt_for(...)` contains
  the exact substring `` Never call `cat`, `head`, `tail`, `grep` or `find` ``.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 4, non-blocker 1, question 0
- Fixed: `_PHASE_NOUN` had no bare `plan-tasks`/`design-solution` alternative, so the PRD's own "Plan"/"Design" delegation cases never matched any pattern. Added bare alternatives.
- Fixed: `\b` placed immediately before the slash in `/autopilot:work` etc. never matches mid-sentence (`/` is a non-word char), making that branch dead on real prose. Dropped the leading `/` from the literal alternatives.
- Fixed: `_SKILL_READ`'s literal path required bare `work/SKILL.md`, but every real instance in this repo is `skills/work/SKILL.md`. Made the `skills/` prefix optional.
- Fixed: the `main()` sketch showed the dict-type check twice — once silent, once with the stderr line — in a way that reads as two sequential checks where only the first (silent) one would ever run. Collapsed to one canonical block with the stderr print inline, and added the same stderr-and-allow pattern to the predicate's defensive except-clause.
- Non-blocker (not fixed, recorded): the "four observed denials" have no recoverable verbatim source today — only a truncated summary line exists. Added an explicit note in Interfaces & contracts directing Task 1 to attempt recovery from the retained session log first, and to label any reconstructed fixture text as such; the regex gets re-validated against whatever is actually committed, not against this doc's prose.

dispatch 2 (codex): cardinal-sin 0, blocker 3, non-blocker 1, question 0
- Fixed: pattern 3 (`_SKILL_READ`, then unconditional) denied `"Read skills/work/SKILL.md and fix its Phase 3 wording."` — reading a skill file to edit it, one of the 16 real corpus cases. Added a required "run/follow/execute/continue every/all task(s)" clause after the read instruction, so reading-to-edit no longer matches.
- Fixed: the bidirectional loose-gap bare-skill-name patterns denied `"Fix plan-tasks tests and run pytest."` and `"Run tests for design-solution."` — both real-shaped per-task prompts where the verb's true object is something else. Replaced with a single verb-immediately-before-skill-name pattern (tight gap, one direction only: `run plan-tasks`, not `plan-tasks ... run`), which is the one word order the actual denial cases use and the one the false-positive examples cannot produce. Verified: 0 false positives across all 183 real `docs/dev/tmp/dispatch-*.txt` files with the revised pattern set (Python repro), all 4 observed-shape denials and 2 synthetic `_SKILL_READ` denials still match.
- Fixed: `main()`'s fail-open diagnostic for an empty/unparseable payload was unreachable — `payload.get("tool_name") != "Agent"` short-circuited to a silent `allow()` before the dict-shape check ever ran, because `{}.get(...)` also returns a non-`"Agent"` value. Added an explicit `if not payload` check, with its own stderr line, BEFORE the `tool_name` check.
- Non-blocker: the proposed `work/SKILL.md` sentence ("In loop mode a hook enforces this") overclaimed — the hook only denies phase-skill delegation, not the STOP paragraph's broader one-task-per-dispatch rule (e.g. `"Implement tasks 1 and 2"` is untouched by this hook). Reworded to scope the claim to what the hook actually checks.

dispatch 3 (codex, verification pass — required because dispatch 2 found blockers): cardinal-sin 0, blocker 1, non-blocker 3, question 0
- Fixed: `"Invoke \`/autopilot:plan-tasks\` for PRD 00242."` (markdown-backtick-wrapped slash invocation) false-ALLOWED — the tightened bare-skill pattern had no backtick form at all. First attempt (an unconditionally-optional `` `? `` on both sides) reintroduced 2 real corpus false DENIALS: `"invoke \`/autopilot:design-solution dev/local/prds/wip/<state.prd> --rework ...\`"` (args inside the backticks, closing backtick far away) and, on closer inspection, a THIRD real corpus false denial this fix-attempt surfaced on its own re-verification — `"enter() does not invoke \`/autopilot:design-solution\` and does not write state.design_doc"` (negated prose describing the system's own internals) — neither of which dispatch 3 itself had flagged, but both are real text in this repo and both would have broken under a naive fix. Final fix, verified by Python repro against the full 183-file corpus with zero false positives: (a) a named-group backreference `(?P<bt>` \`?)...(?P=bt)` requires the SAME backtick-or-nothing to close immediately after the skill name, so a backtick that reopens around an unrelated args list no longer pairs; (b) a `_negated_before()` post-match filter rejects any candidate match preceded within 20 chars by `not`/`never`/`doesn't`/`don't`/`won't`/`n't`, so "does not invoke X" is read as a prohibition, not a delegation. `is_phase_delegation` switched from `pattern.search()` to `pattern.finditer()` so every candidate match is checked against the negation filter, not just the first.
- Non-blocker (not fixed, accepted): `"Read skills/work/SKILL.md and run all task-boundary tests."` matches `_SKILL_READ` (`\btasks?\b` is satisfied by the "task" in "task-boundary", a word-boundary-correct but semantically wrong match) — a synthetic example with zero occurrences in the real 183-file corpus (`rg -il "run (all|every) task" docs/dev/tmp/dispatch-*.txt` finds nothing). Left as an accepted limitation per the same risk-tolerance the design already states for "new delegation phrasing the regex misses": a false deny costs one retry turn, never data, and this exact phrasing does not occur today.
- Non-blocker (not fixed, accepted): `'Add a regression test asserting that "run plan-tasks" is denied.'` (a quoted example, as opposed to a negated instruction) still matches pattern 3 — the negation filter catches "not run X" but not a quotation of the denied phrase. Zero occurrences in the real corpus today; flagged in Risks & edge cases as a concrete near-term watch-item for Task 1's own test-writing (quoting the denial strings verbatim in a per-task dispatch prompt, under loop mode, could in principle trip this very hook — mitigated by phrasing those dispatch prompts to avoid the exact "run plan-tasks"/"run design-solution" substring, e.g. via string concatenation in the test fixture itself).
- Non-blocker: confirmed (not a defect) — re-verified against the actual `hooks/_common.py` that the dispatch-2 fail-open fix holds: `read_input()` returns `{}` for empty/malformed/non-object stdin, the revised `main()`'s `if not payload` branch catches it and prints the diagnostic before `allow()`, and a normal `{"tool_name": "Bash", ...}` payload reaches the `tool_name` check and exits silently (no spurious stderr for an unrelated tool).
result: ok
