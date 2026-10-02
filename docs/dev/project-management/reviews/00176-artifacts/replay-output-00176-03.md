## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `31fe06b59973`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

[MECH] 🟡 2 touched test(s) pass against the pre-change code: test_failed_repair_cleans_tmp_and_repairs_next_target | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py | Task: general

Replay: 7 touched test(s) ran, 5 failed against base, 2 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: uv run --no-project --with pytest python -m pytest
