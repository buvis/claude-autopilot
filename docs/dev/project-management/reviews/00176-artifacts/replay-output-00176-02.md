## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `ece9ac34053a`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

Replay: 3 touched test(s) ran, 3 failed against base, 0 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: uv run --no-project --with pytest python -m pytest
