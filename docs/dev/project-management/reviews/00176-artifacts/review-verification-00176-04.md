# Review verification: PRD 00176 cycle 4

Reviewed HEAD: `fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63`.
Incremental base: `4f9ca6405081eea7b869883c6b53d301e53f6080`.

The immutable matching record is `review-verification-record-00176-04.json`.
The parent supplied the exact-HEAD foreground full-suite and release results;
the coordinator ran no duplicate suite, release checks, doctor-version suites,
or worktree replay. The suite passed 2616 tests, 459 additional subtests, with
0 failures, 1 existing skip and 4 existing warnings. Release checks passed 224.
The doctor suite passed 91 on Python 3.10, 3.13 and 3.14. The raw mechanical
replay is `replay-output-00176-04.md`: two touched tests, one expected failure
against the base, one passing pre-existing disappearance test.

## Reviewer dispatch

Alice and Blake were dispatched with `fork_turns=none`; Bob followed with
`fork_turns=none` when a slot was released. Native Codex agents are the available
host adapter for native Task reviewers; there is no model diversity.

Real Bob and Carl wrapper calls each returned exit 3 on the initial attempt:
`refusing nested dispatch (already inside a CLI agent)`.

`[RETRY] Bob attempt 1/1` and `[RETRY] Carl attempt 1/1` repeated the real
wrapper calls with the same prompt/output paths and intact guard environment.
Both again returned exit 3 with the same message. No live model backend started,
no thread ID was produced, and no stale output was used. Bob's native fallback
carries the full current R and D rubrics plus the doubt/de-slop appendix.
Carl is unavailable this cycle, not permanently unavailable.

Engram was attempted twice and returned exit 1 both times:
`not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv`.
No external registration/configuration was changed; the prompts use the
required `(no pack available this cycle)` sentinel.

## Real parent-directory permission reproduction

The coordinator ran only this bounded supplementary check, using temporary
fixtures and restoring the directory mode in `finally`:

```text
/Users/bob/.local/share/mise/installs/python/3.14.6/bin/python -B dev/local/tmp/reproduce-parent-permission-00176-04.py
```

The script asserts HEAD before and after and checks actual mode-000 parent
permissions for a registered readable hook followed by a readable second hook.
It returned exit 0 with this output (temporary prefix shortened here):

```text
Python: 3.14.6
HEAD: fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63
target.exists(): False
target.stat(): PermissionError 13
exit: 1
syntax_error  <fixture>/hooks/denied/protect_config.py  [Errno 13] Permission denied: '<fixture>/hooks/denied/protect_config.py'
ok  <fixture>/hooks/validate_commit_msg.py
summary  1 ok, 0 stale, 1 broken
stderr: empty
PASS: real parent permissions retain error detail and later rows; modes restored and fixture removed.
```

The root decision gate accepted the portable regression as the persistent
replacement for the prior follow-up's real-parent-fixture wording: it models
Python 3.14 existence-error suppression and fails on the prior module across
Python versions, while a real parent fixture alone passes against that prior
module on Python 3.13. Existing PRD-mandated real directory and read-only repair
tests remain. This real Python 3.14 reproduction confirms the host behavior.

`git diff --check 4f9ca6405081eea7b869883c6b53d301e53f6080 HEAD` passed.

## Blind verification limit

Blake independently attempted the PRD doctor suite and hit sandbox cache
denial opening `/Users/bob/.cache/uv/sdists-v9/.git`. He did not request
nested escalation. His final output preserves the blocked command and the
unrun release check; no implementation-aware verification/context was fed to
him. The coordinator resolves that observation from the matching recorded
full-suite/release evidence after retaining his raw output and B15 failure.

## Explicit current replay decision

The parent dismisses the passing `test_target_deleted_after_stat_is_verdicted`
observation: the pre-existing disappearance test moved its fault injection from
exists/stat to stat/read because exists was removed. It still checks the same
required disappearance behavior and error detail. Passing the incremental base
is expected for preserved behavior; the newly added permission-suppression
regression fails there. The raw `[MECH]` finding remains visible in the report.
