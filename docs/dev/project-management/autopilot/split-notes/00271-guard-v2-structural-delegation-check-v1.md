# Split note: 00271-guard-v2-structural-delegation-check-v1.md
planned=10 prd_tasks=10 expansion=1.00 reasons=module_drift

## . (UNLISTED)

- 10 CHANGELOG: replace the 00267 guard line with v2's real behavior: CHANGELOG.md

## dev/bin (UNLISTED)

- 2 Replay fixture: commit the 17-record real-dispatch fixture: dev/bin/release-checks
- 9 Full local replay: standalone CLI replaying every real dispatch: dev/bin/replay_delegation_guard.py, dev/bin/test_replay_delegation_guard.py, dev/bin/release-checks

## hooks (UNLISTED)

- 1 Normalization: add _normalize and call it on each field: hooks/guard_phase_delegation.py, hooks/test_guard_phase_delegation_structure.py
- 2 Replay fixture: commit the 17-record real-dispatch fixture: hooks/test_guard_phase_delegation_replay.py
- 3 Lone surrogate: normalize file_path before resolve(): hooks/enforce_prd_location.py, hooks/test_enforce_prd_location.py
- 4 Session id with U+FFFD: leave-marker hooks allow() on a replaced byte: hooks/note_session_leave.py, hooks/guard_skill_after_leave.py, hooks/test_guard_skill_after_leave.py
- 5 Structural predicate: object-position, bare-prompt, SKILL.md, scoping, bound negation: hooks/guard_phase_delegation.py, hooks/test_guard_phase_delegation_structure.py, hooks/test_guard_phase_delegation_narrowing.py, hooks/test_guard_phase_delegation.py
- 6 Dispatch policy: agoge exemption and per-type deny message with the matched span: hooks/guard_phase_delegation.py, hooks/test_guard_phase_delegation_dispatch.py
- 7 Cost bound: pin guard time-per-MB under the baseline: hooks/test_guard_phase_delegation_dispatch.py
- 8 Six-hook stdin matrix: pin every stdin-reading hook against bad input: hooks/test_read_input.py

## hooks/fixtures/phase_delegation (UNLISTED)

- 2 Replay fixture: commit the 17-record real-dispatch fixture: hooks/fixtures/phase_delegation/replay.jsonl
