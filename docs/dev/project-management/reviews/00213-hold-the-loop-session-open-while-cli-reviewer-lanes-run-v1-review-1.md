---
prd: dev/local/prds/wip/00213-hold-the-loop-session-open-while-cli-reviewer-lanes-run-v1.md
review: 1
date: 2026-09-26
head_sha: 270ba72c44aa1423d2446c54323201a75a3b4b24
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00213-hold-the-loop-session-open-while-cli-reviewer-lanes-run-v1

Diff range: `88853005812436975cd9b8453ddc955f1100473c..270ba72c44aa1423d2446c54323201a75a3b4b24`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Every prompt carried the `(no pack available this cycle)` sentinel instead. Blake never receives a pack by design.

bob: codex lane failed twice (exit 1, `turn.failed` after repeated `error` events, no `-o` file, no salvageable sidecar). The one-retry budget was spent on an unchanged re-dispatch, per `references/retry-policy.md`. The doubt lens did not drop: a Claude Task subagent ran Bob's exact assembled prompt (context, diff, checklist, R-rubric and the doubt lens inlined) and its output is Bob's section below.

## Reviewers

- **Alice** (consensus, Claude subagent) — ran; 5 findings; R2 fail, all other R rules pass.
- **Blake** (blind, PRD-only Claude subagent) — ran; 2 findings; B1-B19 all pass.
- **Bob** (doubt + de-slop + consensus) — codex unavailable after one retry; **Claude fallback** ran the same prompt; 9 findings, FIX/VERIFY/KNOWN buckets, R2 fail, D1-D5 all pass.
- **Carl** (Gemini, backend `copilot`, model `gemini-3.8-flash`) — ran; 3 findings; R2 fail, all other R rules pass.

## Consolidated Findings

16 rows, sorted by consensus then severity. **No CRITICAL, no HIGH.** Both
`[MECH]` lines from the context file's computed blocks are absorbed: the
tautological-shape line onto the `test_hooks_json_is_valid` row, and the
fail-first replay line onto the `test_every_plugin_owned_handler_is_a_python3_command`
row (each gains `mech-check` as a finder).

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 | New test `test_every_plugin_owned_handler_is_a_python3_command` passes against the pre-change code (confirmed by the pack's fail-first replay: 1 of 19 touched tests passes at base) — it's a generic "every hooks.json entry has this shape" invariant that happened to already hold before this PRD's registration existed, so it doesn't itself pin the new Stop entry (the specific pin is `test_guard_stop_on_live_lanes_runs_on_stop` in hooks/test_hook_registration.py, which does fail-first correctly). Not a blocker, but per rubric R2's literal definition it counts as tautological. | skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:86 | 3 | ALICE, BOB, CARL, mech-check |
| [2/4] | 🟡 | [MECH] test_hooks_json_is_valid has no assertion: it only proves the code does not raise | skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:60 | general | BOB, CARL, mech-check |
| [1/4] | 🟡 | A failed `.lane-guard-blocks` write silently disables the guard: `counter.write_text()` is unguarded, so an OSError there reaches `main()`'s blanket handler and the hook exits 0 instead of blocking — the opposite of `review_coverage_hook.py:201-205`, the valve the PRD names as the model, which wraps the same write in `try/except OSError: pass` and still returns 2 | hooks/guard_stop_on_live_lanes.py:111 | 2 | BOB |
| [1/4] | 🟡 | `except Exception: sys.exit(0)` swallows every internal failure with no stderr line, so a bug in the guard makes the keep-alive permanently inert and invisible — exactly the silent-skip class this PRD exists to end; the repo's own fail-open precedent (cli/gate.py, quoted in review_coverage_hook.py:106-108) is loud | hooks/guard_stop_on_live_lanes.py:117 | 2 | BOB |
| [1/4] | 🟡 | When every live lane has an empty `-o` line, `outputs` is empty and the blocking reason tells the model to run `await_reviewer_outputs.py --budget 100` with no files; that script declares `files` as `nargs="+"` (await_reviewer_outputs.py:44), so argparse exits 2 and the session is handed an unrunnable instruction on every one of up to 40 blocked stops. Untested: `test_lane_without_an_output_file_is_named_but_not_awaited` always keeps one lane with an output | hooks/guard_stop_on_live_lanes.py:78 | 2 | BOB |
| [1/4] | 🟡 | test_both_registrations_point_at_pack_relative_files_that_exist still names "both" after adding a third hook; rename to test_all_guard_registrations_point_at_pack_relative_files_that_exist | hooks/test_hook_registration.py:63 | 3 | CARL |
| [1/4] | ⚪ | Pre-existing `test_hooks_json_is_valid` has no assertion body (only proves the JSON load doesn't raise) — not touched by this diff, flagged here only because the pack's mechanical check surfaces it in the same file. | skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:60 | general | ALICE |
| [1/4] | ⚪ | `_guard()`'s cwd resolution (`Path(payload.get("cwd") or os.getcwd())`) skips the `str(...)` cast its sibling hook uses (`guard_skill_after_leave.py:70`); harmless since `main()`'s outer `except Exception` would catch a malformed-payload TypeError anyway, but worth aligning for consistency next time this file is touched. | hooks/guard_stop_on_live_lanes.py:127 | 2 | ALICE |
| [1/4] | ⚪ | The lane-snapshot one-liner (`ls "$STUB_LANES_DIR" > ...; cp ...; for _p in ...; do ps -o command= ...`) is duplicated verbatim across three stub heredocs (codex stub, copilot stub, gemini stub); each is a standalone subshell script so extraction isn't trivial without a larger stub-generation refactor, flagging only as a minor redundancy note. | skills/use-codex/scripts/codex_run_test_lib.sh:70 | 1 | ALICE |
| [1/4] | ⚪ | `reason()`'s `outputs` string is empty when every live lane's `-o` is blank, which would render the awaiter instruction with a trailing double space and zero positional files (`await_reviewer_outputs.py` requires `nargs="+"`); untested edge case, low likelihood since the review workflow always passes `-o` to Bob and Carl. | hooks/guard_stop_on_live_lanes.py:113 | 2 | ALICE |
| [1/4] | ⚪ | gemini-run.sh writes the lane marker (skills/use-gemini/scripts/gemini-run.sh:186) before the per-mode empty-prompt validation that lives inside run_copilot/run_gemini (skills/use-gemini/scripts/gemini-run.sh:254, :270, :306, :310), unlike codex-run.sh which validates the prompt (skills/use-codex/scripts/codex-run.sh:154) before writing its marker (skills/use-codex/scripts/codex-run.sh:173). The PRD states the marker is "written after argument parsing and prompt validation, before any backend runs" (00213 PRD line 64). Functionally harmless — the merged EXIT trap (skills/use-gemini/scripts/gemini-run.sh:183) removes the marker on the validation-triggered exit — and no acceptance test exercises this ordering, so it does not fail any Phase 0 acceptance criterion. | skills/use-gemini/scripts/gemini-run.sh | Phase 0 (Mark the lanes) | BLAKE |
| [1/4] | ⚪ | skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:86 adds a new test method (`test_every_plugin_owned_handler_is_a_python3_command`) beyond what Phase 1 task 2 asked for ("add the `guard_stop_on_live_lanes.py: Stop` row to `_EXPECTED_REGISTRATIONS`"). It is defensive test hardening, not product functionality, and does not change behavior, but it is scope beyond the PRD's stated task text. | skills/run-autopilot/scripts/test_review_coverage_hook_registration.py | Phase 1 task 2 | BLAKE |
| [1/4] | ⚪ | The lane-snapshot stub line drops the `${VAR:?}` guard its immediate neighbours use (`${COPILOT_STDIN_FILE:?}`, `${GEMINI_ARGV_FILE:?}`) — with `STUB_LANES_DIR` set and `STUB_LANES_SNAPSHOT_DIR` unset it writes `/.list` and `cp`s markers into `/` — and packs four commands into one ~280-char line in a file that is otherwise multi-line bash | skills/use-codex/scripts/codex_run_test_lib.sh:73 | 1 | BOB |
| [1/4] | ⚪ | The backstop sentence is spliced before the sentence that introduces the Watcher, so "When the Watcher is skipped" has no antecedent in the bullet and the escape hatch is read before the instruction the PRD wants kept as the normal path; review-work-completion/SKILL.md:274 appends the same sentence after the Watcher prose, which reads correctly | skills/fast-track/SKILL.md:30 | 4 | BOB |
| [1/4] | ⚪ | The marker removal is on `EXIT` only, not `INT`/`TERM`, so the PRD's own scenario (headless claude killing the wrapper seconds after a turn ends) can leave the marker behind; harmless because the hook reaps dead-pid markers, but it means the lanes dir is not self-cleaning without a later loop session in that checkout | skills/use-codex/scripts/codex-run.sh:186 | 1 | BOB |
| [1/4] | ⚪ | No test or recorded run exercises the real chain end to end (loop session -> backgrounded wrapper writes a marker -> Stop hook blocks): the hook tests fabricate markers and `_AUTOPILOT_LOOP`, and the bash tests never run the hook | N/A | general | BOB |

## Alice

Read the context, the full diff, re-derived the bash-wrapper marker logic and
the Stop hook's control flow line by line, and independently ran the three
touched suites: 26 passed (`hooks/test_guard_stop_on_live_lanes.py`,
`hooks/test_hook_registration.py`,
`skills/run-autopilot/scripts/test_review_coverage_hook_registration.py`),
`test_codex_run.sh` 25 passed / 0 failed, `test_gemini_run.sh` 38 passed / 0
failed.

Traced and confirmed: `allow()`/`block()` in `hooks/_common.py` are `NoReturn`,
so `_guard()`'s early-return calls genuinely stop execution; `AWAITER` resolves
from `__file__` to the real `await_reviewer_outputs.py`; the new `hooks.json`
Stop entry sits in the matcher-less block after `review_coverage_hook.py` with
timeout 5; both wrappers stay `set -eo pipefail`-safe (every risky command
followed by `||`); `codex-run.sh`'s trap is genuinely new and `gemini-run.sh`'s
merges `RUN_TMP` cleanup with marker removal in one statement; `sonnet-run.sh`
untouched; age-ceiling and block-cap arithmetic (3700 s / 61 min, 39→40 still
denies, 40→41 gives up) match the PRD and the tests exercise both sides of each
boundary.

Findings: 1 Medium, 4 Low (rows above).

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD only, no diff. He located the code himself and verified by
running, not reading: `hooks/test_guard_stop_on_live_lanes.py` +
`hooks/test_hook_registration.py` 20 passed; `test_codex_run.sh` 25 passed;
`test_gemini_run.sh` 38 passed; full `dev/bin/release-checks` exit 0. He
confirms every PRD Success Metric command is genuinely green rather than merely
claimed.

Spec-conformance checks he confirmed correct: the two-line marker contract in
both wrappers, loop-gated with the `_walk_up.py --bash` lookup and
observation-only failure; codex's own new EXIT trap versus gemini's single
merged trap statement; `live_lanes`/`reason`/`main` signatures, dead-pid unlink,
non-integer skip, the age-ceiling stderr line, the BLOCK_CAP=40 valve and the
exact reason string; the matcher-less Stop block with timeout 5; all ten
PRD-named test functions present verbatim plus `test_docs_name_the_guard`; the
three prose locations and the CHANGELOG entry; `sonnet-run.sh` untouched and the
Watcher prose retained; the diff touching exactly the 16 files the PRD's
Repository Structure lists. He also verified the fail-open design (`SystemExit`
is a `BaseException`, so it propagates through `except Exception`) and the
TOCTOU path (a lane vanishing mid-scan is caught by the inner `except OSError`).

Findings: 2 Low (rows above).

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Codex lane failed twice; this section is the **Claude fallback** running Bob's
exact assembled prompt (doubt + de-slop lens and the R-rubric included).

Findings: 5 Medium, 4 Low (rows above).

FIX:
- Counter write failure cancels the block — hooks/guard_stop_on_live_lanes.py:111 — wrap `counter.write_text(f"{count}\n")` in `try/except OSError: pass` and call `block(reason(lanes, AWAITER))` unconditionally, matching review_coverage_hook.py:201-206.
- Blanket exception handler is silent — hooks/guard_stop_on_live_lanes.py:117 — `except Exception as exc:` then one `sys.stderr.write(f"autopilot: lane_guard: internal error, not holding the session: {exc}\n")` before `sys.exit(0)`, plus a test that a malformed autopilot dir still exits 0 and says so.
- Awaiter command has no arguments when no lane carries `-o` — hooks/guard_stop_on_live_lanes.py:78 — when `outputs` is empty, replace the "Run python3 ... --budget 100 ..." sentence with "No lane published an `-o` file; wait for the listed pids to exit before ending the turn.", and add a test with a single `-o`-less lane.
- New registration test passes against the pre-change code — skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:86 — drop `test_every_plugin_owned_handler_is_a_python3_command` (task 3 asked only for the `_EXPECTED_REGISTRATIONS` row, and two existing tests already pin the new command exactly), or keep it and accept it as a pack-wide invariant that pins nothing in this diff.
- Stub snapshot line is unguarded and unreadable — skills/use-codex/scripts/codex_run_test_lib.sh:73 (same line duplicated at skills/use-gemini/scripts/test_gemini_run.sh:60 and :72) — use `"${STUB_LANES_SNAPSHOT_DIR:?}"` like the neighbouring stub lines and break the `{ ...; ...; for ...; }` chain across lines.
- Fast-track sentence lands before the instruction it backstops — skills/fast-track/SKILL.md:30 — move the dispatch sentence first and reword the backstop to "If that dispatch is skipped, the Stop hook `hooks/guard_stop_on_live_lanes.py` (PRD 00213) holds the session open ..."; it stays inside the `- **Loop session.**` bullet, so `test_docs_name_the_guard` and the `refus*` ban both still hold.

VERIFY:
- The chain from a real loop session to a blocked stop is never exercised together — from the repo root run `_AUTOPILOT_LOOP=1 bash skills/use-codex/scripts/codex-run.sh -f dev/local/tmp/p.txt -o /tmp/lane.md &`, then `ls dev/local/autopilot/lanes/` while it runs (expect one file named by the wrapper's pid), then `echo '{"cwd":"'$PWD'","hook_event_name":"Stop"}' | _AUTOPILOT_LOOP=1 python3 hooks/guard_stop_on_live_lanes.py; echo $?` (expect 2 with `/tmp/lane.md` in the reason).
  - **not queued: command shape** — three chained commands with backgrounding and command substitution, which the verification-check queue forbids (one runnable command line, no `&&`/`;`/`|`, no substitution). It stays an ordinary finding and is swept as "add the end-to-end test" instead.

KNOWN:
- `test_hooks_json_is_valid` has no assertion (skills/run-autopilot/scripts/test_review_coverage_hook_registration.py:60) — pre-existing test untouched by this diff; fixing it is unrelated cleanup under the surgical-changes rule, so it is reported, not changed.
- Marker survives a signal kill because the trap is `EXIT`-only (skills/use-codex/scripts/codex-run.sh:186, skills/use-gemini/scripts/gemini-run.sh:183) — adding `INT TERM` would also change the pre-existing `RUN_TMP` cleanup path in gemini-run.sh, outside this PRD's scope, and the hook already unlinks dead-pid markers so the leak is self-healing on the next loop stop.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini lane, backend `copilot`, model `gemini-3.8-flash`. Read the context and
the full diff, inspected `948175b` directly, checked when
`test_hooks_json_is_valid` was introduced with `git log -S`, and ran
`test_codex_run.sh`, `test_gemini_run.sh` and the full `release-checks`.

Findings: 3 Medium (rows above).

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Decision gate

No CRITICAL, no HIGH → the cycle converges. `cycle 1` of `rework_cap 2`; the cap
is irrelevant on a converged cycle.

**Settled deferrals** (ledgered in
`00213-hold-the-loop-session-open-while-cli-reviewer-lanes-run-v1-ledger.json`,
5 rows): the two `test_hooks_json_is_valid` rows (pre-existing test, surgical
changes), the three-stub one-liner duplication (needs a stub-generation
refactor), the gemini marker-versus-validation ordering (observable contract
holds via the merged trap), and the EXIT-only trap (self-healing via dead-pid
reaping). The last two are Bob's own KNOWN bucket with his written
justification.

**Swept** (tail sweep, one `[D1]` task): 9 findings — the three real hook
defects (counter-write cancelling the block, silent blanket handler, unrunnable
awaiter command when no lane carries `-o`), the tautological registration test,
the misnamed `test_both_registrations_...`, the `${VAR:?}`-less stub line, the
`str(...)` cwd cast, the fast-track sentence ordering, and the missing
end-to-end chain test.

## Tail sweep outcome

Three `[D1]` tasks (ids 5, 6, 7), all opus per the PRD's `default_model` floor,
covering the 11 swept findings. All three completed on their first attempt; Pat
returned `NO FINDINGS` on each, with every swept finding carrying a `resolved`
closure verdict except one.

- **Task 5** — `hooks/guard_stop_on_live_lanes.py`: the counter write is wrapped
  so a failure cannot cancel the block, the fail-open handler reports the
  exception it actually caught, and a lane set with no `-o` file gets `ps -p
  <pids>` guidance instead of an awaiter command with zero arguments. The
  registration test was renamed for three hooks. Devon broke Tess's first tests
  and broke the strengthened ones too (his one round is spent): the tests still
  admit a wrong implementation that pre-checks the exact fixtures. Flagged, not
  blocking — the implementation is the honest one, and Pat judged it directly.
  One extra assertion was added beyond Tess's round (the sibling exception name
  must be absent) to close Devon's strongest exploit.
- **Task 6** — the tautological registration test was deleted (micro lane, a
  17-line deletion).
- **Task 7** — the three stub snapshot lines gained their `${VAR:?}` guards and
  multi-line shape, the fast-track bullet now reads dispatch-then-backstop, and
  `test_codex_run.sh` gained a case that runs the real chain: wrapper writes a
  marker, the repo's own Stop hook blocks with exit 2 naming the `-o` path, and
  allows with exit 0 once the marker is gone. The self-deslop pass returned
  `no slop found`.

**One finding closed as `unresolved` by design**: the `str(...)` cwd cast (LOW,
Alice). Applying it conflicts with the same cycle's MEDIUM loud-internal-failure
finding — with the cast a non-string `cwd` resolves quietly and the hook allows
the stop in silence; without it the TypeError is reported. The louder behaviour
wins. Ledgered as a settled deferral so it is not re-raised.

No queued verification checks existed this cycle (the one VERIFY item was not
queueable: three chained commands with backgrounding and substitution), so there
are no verify escapes. Pat raised no CRITICAL or HIGH on any sweep task, so there
are no sweep escapes.

Verdict: 16 findings
Tests: 1182 passed, 0 failed, 0 skipped (suite run this cycle: `bash dev/bin/release-checks` exit 0 at 14da0ce87c9a5a8d4c1fcca4b35691c250b92e67, after the tail sweep)
