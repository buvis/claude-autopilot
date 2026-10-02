## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `4f9ca6405081`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

[MECH] 🟡 1 touched test(s) pass against the pre-change code: test_target_deleted_after_stat_is_verdicted | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py | Task: general

Replay: 2 touched test(s) ran, 1 failed against base, 1 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: uv run --no-project --with pytest python -m pytest
